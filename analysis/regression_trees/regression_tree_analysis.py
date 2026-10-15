"""Conditional regression trees for saved simulations, without rerunning models.

Trees describe the saved parameter domain and, for oscillation diagnostics, only
eligible trajectories. They are predictive summaries, not Sobol indices.
"""
from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import asdict, dataclass, replace
from datetime import datetime
import hashlib
import json
from pathlib import Path
import re

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import sklearn
from sklearn.dummy import DummyRegressor
from sklearn.inspection import permutation_importance
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import GridSearchCV, GroupKFold, GroupShuffleSplit
from sklearn.tree import DecisionTreeRegressor, export_text, plot_tree

from analysis.regression_trees.regression_tree_plots import create_regression_tree_overview
from utils.paths import PLOTS_DIR


SENSITIVITY_TARGETS = ("x_mean", "final_temperature", "cumulative_emissions", "first_time_x95",
                       "bool_x95", "oscillation_occurrence", "oscillations_per_500_years")
CONDITIONAL_TARGETS = ("median_period", "oscillation_amplitude", "damping_index", "damping_rate")
TARGETS = SENSITIVITY_TARGETS + ("final_x", *CONDITIONAL_TARGETS)
BOOLEAN_TARGETS = {"bool_x95", "oscillation_occurrence"}
PERCENT_TARGETS = {"final_x", "x_mean", "oscillation_amplitude", *BOOLEAN_TARGETS}
ANALYSIS_MODES = ("per_norm", "pooled_common", "per_norm_common")
AGENT_SCENARIO = "Observation-based / intention motivation (agents)"
TARGET_LABELS = {
    "x_mean": "Zeitmittel des Mitigationsanteils x (0–1)",
    "final_temperature": "Endtemperatur (°C)",
    "cumulative_emissions": "Kumulierte Emissionen (GtC)",
    "first_time_x95": "Erste Erreichung von x ≥ 95 % (Jahre; 0 = nie)",
    "bool_x95": "x ≥ 95 % jemals erreicht (0/1)",
    "oscillation_occurrence": "Oszillation erkannt (mindestens 2 Zyklen; 0/1)",
    "oscillations_per_500_years": "Oszillationen pro 500 Jahre",
    "final_x": "Finaler Mitigationsanteil x (0–1)",
    "median_period": "Mediane Periodendauer (Jahre)",
    "oscillation_amplitude": "Gespeicherte Oszillationsamplitude (0–1)",
    "damping_index": "Dämpfungsindex (dimensionslos)",
    "damping_rate": "Dämpfungsrate (1/Jahr)",
}


@dataclass(frozen=True)
class TreeConfig:
    seed: int = 42
    test_fraction: float = 0.25
    depths: tuple[int, ...] = (2, 3, 4)
    leaf_fractions: tuple[float, ...] = (0.05, 0.1)
    cv_folds: int = 5
    minimum_rows: int = 20
    stability_repeats: int = 8
    relative_split_tolerance: float = 1e-10

    def __post_init__(self):
        if not 0 < self.test_fraction < 1:
            raise ValueError("test_fraction must be between 0 and 1")
        if not self.depths or any(d < 1 for d in self.depths):
            raise ValueError("Tree depths must be positive")
        if not self.leaf_fractions or any(not 0 < f <= 0.5 for f in self.leaf_fractions):
            raise ValueError("Leaf fractions must be in (0, 0.5]")
        if self.cv_folds < 2 or self.minimum_rows < 2 or self.stability_repeats < 1:
            raise ValueError("Invalid validation settings")
        if not np.isfinite(self.relative_split_tolerance) or self.relative_split_tolerance <= 0:
            raise ValueError("relative_split_tolerance must be finite and positive")


@dataclass
class SavedScenario:
    directory: Path
    metadata: dict
    parameters: dict
    data: pd.DataFrame
    feature_names: list[str]
    block_size: int
    feature_transforms: dict


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def load_scenario(directory: Path) -> SavedScenario:
    directory = Path(directory)
    metadata = _read_json(directory / "metadata.json")
    problem = metadata["problem"]
    names = problem["names"]
    if len(names) != problem["num_vars"] or len(set(names)) != len(names):
        raise ValueError("Parameter names and num_vars disagree")
    if problem.get("groups") is not None:
        raise ValueError("Grouped Sobol designs need an explicit group-layout definition")
    samples = pd.read_csv(directory / "samples.csv", sep=";")
    outputs = pd.read_csv(directory / "simulation_outputs.csv", sep=";")
    for label, frame in [("samples", samples), ("outputs", outputs)]:
        indices = pd.to_numeric(frame["sample_index"], errors="raise").to_numpy()
        if not np.all(np.isfinite(indices)) or not np.all(indices == np.floor(indices)):
            raise ValueError(f"{label}: sample_index must contain finite integers")
        if frame["sample_index"].duplicated().any():
            raise ValueError(f"{label}: duplicate sample_index")
    missing = set(metadata.get("outputs_for_ranking", [])) - set(outputs.columns)
    if missing:
        raise ValueError(f"Saved metadata/output mismatch (possibly mixed code versions): {sorted(missing)}")
    if set(samples.sample_index) != set(outputs.sample_index):
        raise ValueError("Samples and outputs must have identical sample_index sets")
    base_size = int(metadata["base_sample_size"])
    if base_size < 2:
        raise ValueError("At least two Sobol base samples are required")
    expected_indices = set(range(len(samples)))
    if set(samples.sample_index) != expected_indices:
        raise ValueError("The saved sample design must have consecutive original indices")
    if len(samples) == base_size * (len(names) + 2):
        block_size = len(names) + 2
    elif len(samples) == base_size * (2 * len(names) + 2):
        block_size = 2 * len(names) + 2
    else:
        raise ValueError("Sample count does not match the saved Sobol block layout")
    # Only sampled model parameters enter X; no outcomes or sample indices.
    features = samples[["sample_index", *names]].copy()
    for name in names:
        features[name] = pd.to_numeric(features[name], errors="raise")
    if not np.isfinite(features[names].to_numpy(dtype=float)).all():
        raise ValueError("Non-finite model input parameters")
    transforms = {}
    if "agent_initialization" in metadata and "network_size" in names:
        features["network_size"] = np.rint(features["network_size"])
        transforms["network_size"] = "Nearest integer, matching actual agent peer counts"
    overlap = (set(names) & set(outputs.columns))
    if overlap:
        raise ValueError(f"Model inputs also appear as output columns: {sorted(overlap)}")
    data = features.merge(outputs, on="sample_index", validate="one_to_one").sort_values("sample_index").reset_index(drop=True)
    data["sobol_block"] = data.sample_index.astype(int) // block_size
    parameters_path = directory / "parameters.json"
    parameters = _read_json(parameters_path) if parameters_path.exists() else {}
    return SavedScenario(directory, metadata, parameters, data, list(names), block_size, transforms)


def eligible_target(data: pd.DataFrame, target: str) -> tuple[np.ndarray, dict]:
    if target not in TARGETS:
        raise ValueError(f"Unknown regression target: {target}")
    required = {target, "status"}
    if target in CONDITIONAL_TARGETS:
        required.add("n_oscillations")
    if target in {"damping_index", "damping_rate"}:
        required |= {"amplitude_initial", "amplitude_final"}
    if target == "damping_rate":
        required.add("n_prominent_half_cycles")
    if required - set(data.columns):
        raise ValueError(f"Missing columns for {target}: {sorted(required - set(data.columns))}")
    values = pd.to_numeric(data[target], errors="raise").to_numpy(dtype=float)
    completed = data.status.eq("completed").to_numpy()
    finite = np.isfinite(values)
    criterion = np.ones(len(data), dtype=bool)
    definition = "All successful simulations with a finite saved target value."
    if target == "first_time_x95":
        definition += " The saved zero (= threshold never reached) is included; leaf means include these zeros."
    if target in BOOLEAN_TARGETS:
        definition += " Saved 0/1 values are retained; a leaf mean is the share of positive training runs."
        if np.any(finite & ~np.isin(values, [0.0, 1.0])):
            raise ValueError(f"{target} must contain only 0/1 or missing values")
    if target in CONDITIONAL_TARGETS:
        # Same complete-cycle threshold as oscillillation_occurrence; independent
        # of whether the saved run already contains that boolean column.
        criterion &= data.n_oscillations.to_numpy(dtype=float) >= 2
        definition = "At least two complete prominent cycles over the saved simulation interval."
    if target == "oscillation_amplitude":
        criterion &= values > 0
        definition += " Uses the SAVED median half-cycle amplitude (half peak-to-trough swing); does not redefine it as a full-cycle height."
    if target in {"damping_index", "damping_rate"}:
        for name in ("amplitude_initial", "amplitude_final"):
            amplitudes = data[name].to_numpy(dtype=float)
            criterion &= np.isfinite(amplitudes) & (amplitudes > 1e-12)
        definition += " Initial and final amplitudes must be finite and positive; a genuine zero damping remains valid."
    if target == "damping_rate":
        criterion &= data.n_prominent_half_cycles.to_numpy(dtype=float) >= 3
        definition += " At least three prominent half-cycles for the saved log-amplitude slope."
    mask = completed & finite & criterion
    return mask, {
        "definition": definition, "total_rows": len(data),
        "completed_rows": int(completed.sum()), "eligible_rows": int(mask.sum()),
        "excluded_failed_rows": int((~completed).sum()),
        "excluded_nonfinite_target_rows": int((completed & ~finite).sum()),
        "excluded_by_definition_rows": int((completed & finite & ~criterion).sum()),
        "interpretation": ("Conditional on eligible oscillating trajectories; not the whole parameter domain."
                           if target in CONDITIONAL_TARGETS else "Saved parameter domain and simulation horizon."),
    }


def group_holdout(data: pd.DataFrame, config: TreeConfig) -> tuple[np.ndarray, np.ndarray]:
    if data.sobol_block.nunique() < 4:
        raise ValueError("At least four Sobol blocks are required for a holdout")
    splitter = GroupShuffleSplit(n_splits=1, test_size=config.test_fraction, random_state=config.seed)
    return next(splitter.split(data, groups=data.sobol_block))


def _scores(y: np.ndarray, prediction: np.ndarray) -> dict:
    return {"mae": float(mean_absolute_error(y, prediction)),
            "rmse": float(np.sqrt(mean_squared_error(y, prediction))),
            "r2": float(r2_score(y, prediction)) if len(y) >= 2 and np.ptp(y) > 1e-12 else None}


def fit_target(scenario: SavedScenario, target: str, config: TreeConfig,
               split: tuple[np.ndarray, np.ndarray]) -> tuple[dict, dict | None]:
    data = scenario.data
    report = {"scenario": scenario.metadata["scenario"], "target": target,
              "analysis_mode": scenario.metadata.get("analysis_mode", "per_norm"),
              "feature_names": scenario.feature_names}
    try:
        mask, eligibility = eligible_target(data, target)
    except ValueError as error:
        return {**report, "status": "unavailable", "reason": str(error)}, None
    report.update(eligibility)
    if target == "oscillations_per_500_years":
        definitions = scenario.metadata.get("source_rate_definitions", {
            report["scenario"]: scenario.metadata.get("oscillations_per_500_years_definition")})
        report["saved_target_definitions"] = definitions
        if any(not d or d.get("method") != "zero_below_minimum_otherwise_scaled_complete_cycle_count"
               for d in definitions.values()):
            report["saved_definition_note"] = (
                "Gespeicherte ältere Rate: einzelne Zyklen können mitzählen; Werte unverändert übernommen.")
    train = split[0][mask[split[0]]]
    test = split[1][mask[split[1]]]
    train_groups = data.iloc[train].sobol_block.to_numpy()
    test_groups = data.iloc[test].sobol_block.to_numpy()
    assert not set(train_groups) & set(test_groups)
    report.update(train_rows=len(train), test_rows=len(test),
                  train_blocks=len(np.unique(train_groups)), test_blocks=len(np.unique(test_groups)))
    if "source_scenario" in data:
        report["norm_composition"] = {
            name: {"total_rows": int(data.source_scenario.eq(name).sum()),
                   "eligible_rows": int((data.source_scenario.eq(name).to_numpy() & mask).sum()),
                   "train_rows": int(data.iloc[train].source_scenario.eq(name).sum()),
                   "test_rows": int(data.iloc[test].source_scenario.eq(name).sum())}
            for name in scenario.metadata["source_norms"]
        }
        report["pooling_note"] = (
            "Each eligible simulation has equal weight. Norm contributions depend on their "
            "eligible sample counts; the norm label is not a decision feature. Test scores "
            "describe held-out blocks within these norms, not transfer to unseen norms."
        )
    if mask.sum() < config.minimum_rows or len(train) < 10 or len(test) < 5 or report["train_blocks"] < 3 or report["test_blocks"] < 2:
        return {**report, "status": "insufficient_data", "reason": "Too few eligible rows or blocks for grouped training and testing."}, None
    y = data[target].to_numpy(dtype=float)
    if np.ptp(y[train]) <= 1e-12:
        return {**report, "status": "constant_training_target", "reason": "No variation in the eligible training target; no informative tree."}, None
    X = data[scenario.feature_names].to_numpy(dtype=float)
    cv = GroupKFold(n_splits=min(config.cv_folds, report["train_blocks"]))
    search = GridSearchCV(
        DecisionTreeRegressor(random_state=config.seed,
                              min_impurity_decrease=config.relative_split_tolerance * float(np.var(y[train]))),
        {"max_depth": list(config.depths), "min_samples_leaf": list(config.leaf_fractions)},
        scoring="neg_mean_absolute_error", cv=cv, n_jobs=1, error_score="raise",
    )
    # Hyperparameters use training blocks only; the test partition stays untouched.
    search.fit(X[train], y[train], groups=train_groups)
    model = search.best_estimator_
    prediction = model.predict(X[test])
    baseline = DummyRegressor(strategy="mean").fit(X[train], y[train])
    report.update(status="fitted", best_parameters=search.best_params_,
                  cv_mae=float(-search.best_score_), train_metrics=_scores(y[train], model.predict(X[train])),
                  test_metrics=_scores(y[test], prediction), baseline_test_metrics=_scores(y[test], baseline.predict(X[test])),
                  actual_depth=int(model.get_depth()), leaves=int(model.get_n_leaves()),
                  train_block_ids=sorted(map(int, np.unique(train_groups))),
                  test_block_ids=sorted(map(int, np.unique(test_groups))))
    report["beats_mean_baseline"] = report["test_metrics"]["mae"] < report["baseline_test_metrics"]["mae"]
    warnings = []
    if report["train_blocks"] < 30 or report["test_blocks"] < 10:
        warnings.append("Small block count: functional/exploratory result, not a reliable parameter ranking.")
    if not report["beats_mean_baseline"]:
        warnings.append("Tree does not improve test MAE over the training-mean baseline.")
    if report["test_metrics"]["r2"] is None:
        warnings.append("Test target is constant: R2 is undefined.")
    roots = Counter()
    stability = GroupShuffleSplit(n_splits=config.stability_repeats, test_size=0.2, random_state=config.seed + 1)
    for subset, _ in stability.split(X[train], groups=train_groups):
        trial = DecisionTreeRegressor(**model.get_params()).fit(X[train][subset], y[train][subset])
        feature = trial.tree_.feature[0]
        roots[scenario.feature_names[feature] if feature >= 0 else "no_split"] += 1
    report["root_stability"] = dict(roots)
    report["stability_note"] = "Training-block subset refits; root counts are a diagnostic, not confidence intervals."
    importance = permutation_importance(model, X[test], y[test], scoring="neg_mean_absolute_error", n_repeats=10, random_state=config.seed)
    importances = pd.DataFrame({"parameter": scenario.feature_names,
                               "test_mae_increase_mean": importance.importances_mean,
                               "test_mae_increase_std": importance.importances_std})
    report["importance_note"] = "Permutation increases in held-out MAE, not Sobol indices or causal effects."
    report["warnings"] = warnings
    identity = (["source_scenario"] if "source_scenario" in data else []) + ["sample_index", "sobol_block"]
    predictions = data.iloc[np.r_[train, test]][[*identity, target]].copy()
    predictions = predictions.rename(columns={target: "observed"})
    predictions["partition"] = ["train"] * len(train) + ["test"] * len(test)
    predictions["predicted"] = model.predict(X[np.r_[train, test]])
    payload = {"model": model, "predictions": predictions, "importances": importances,
               "cv_results": pd.DataFrame(search.cv_results_), "test_y": y[test], "test_prediction": prediction}
    return report, payload


def _write_json(path: Path, data) -> None:
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False, allow_nan=False), encoding="utf-8")


def _leaf_prediction(target: str, value: float) -> str:
    if target in BOOLEAN_TARGETS:
        return f"{target}: {100 * value:.1f} %\nAnteil der Läufe mit Wert 1".replace(".", ",")
    if target in {"final_x", "x_mean"}:
        return f"{target}: {100 * value:.1f} %".replace(".", ",")
    if target == "oscillation_amplitude":
        return f"oscillation_amplitude\n{100 * value:.1f} Prozentpunkte".replace(".", ",")
    if target in {"median_period", "first_time_x95"}:
        return f"{target}: {value:.1f} Jahre".replace(".", ",")
    units = {"final_temperature": " °C", "cumulative_emissions": " GtC",
             "damping_index": "", "damping_rate": " / Jahr",
             "oscillations_per_500_years": " / 500 Jahre"}
    return f"{target}: {value:.3g}{units[target]}".replace(".", ",")


def _leaf_spread(target: str, standard_deviation: float) -> str:
    if target in PERCENT_TARGETS:
        value = f"{100 * standard_deviation:.1f} Prozentpunkte"
    elif target in {"median_period", "first_time_x95"}:
        value = f"{standard_deviation:.1f} Jahre"
    elif target == "damping_rate":
        value = f"{standard_deviation:.3g} / Jahr"
    elif target == "final_temperature":
        value = f"{standard_deviation:.3g} °C"
    elif target == "cumulative_emissions":
        value = f"{standard_deviation:.3g} GtC"
    elif target == "oscillations_per_500_years":
        value = f"{standard_deviation:.3g} / 500 Jahre"
    else:
        value = f"{standard_deviation:.3g}"
    return "Std.-Abw.: " + value.replace(".", ",")


def _leaf_standard_deviations(scenario: SavedScenario, target: str,
                              report: dict, model: DecisionTreeRegressor) -> dict[int, float]:
    eligible, _ = eligible_target(scenario.data, target)
    training = scenario.data.loc[eligible & scenario.data.sobol_block.isin(report["train_block_ids"])]
    leaf_ids = model.apply(training[scenario.feature_names].to_numpy(dtype=float))
    values = training[target].to_numpy(dtype=float)
    deviations = {}
    for node in np.unique(leaf_ids):
        leaf_values = values[leaf_ids == node]
        # Compute from training values directly to avoid cancellation in tree impurity.
        deviations[int(node)] = (float(np.std(leaf_values, ddof=0))
                                 if np.ptp(leaf_values) > 0 else 0.0)
    return deviations


def render_tree(directory: Path, scenario: SavedScenario, target: str,
                report: dict, model: DecisionTreeRegressor) -> None:
    """Decision questions, leaf means and within-leaf training standard deviations."""
    labels = scenario.feature_names
    tree = model.tree_
    standard_deviations = _leaf_standard_deviations(scenario, target, report, model)
    order = []

    def visit(node):
        order.append(node)
        if tree.children_left[node] >= 0:
            visit(tree.children_left[node])
            visit(tree.children_right[node])

    visit(0)
    width = max(14, 3.6 * model.get_n_leaves())
    height = 2.0 + 1.9 * (model.get_depth() + 1)
    with plt.rc_context({"svg.fonttype": "none", "font.family": "DejaVu Sans"}):
        fig, ax = plt.subplots(figsize=(width, height))
        artists = plot_tree(model, feature_names=labels, filled=False, rounded=True,
                            impurity=False, fontsize=13, ax=ax)
        nodes = [artist for artist in artists if artist.get_bbox_patch() is not None]
        # Remove sklearn's English root-edge labels and label all decisions.
        for artist in artists:
            if artist.get_bbox_patch() is None:
                artist.remove()
        positions = {}
        for node, artist in zip(order, nodes):
            leaf = tree.children_left[node] < 0
            count = int(tree.n_node_samples[node])
            if leaf:
                caption = _leaf_prediction(target, float(tree.value[node, 0, 0]))
                caption += "\n" + _leaf_spread(target, standard_deviations[node])
            else:
                threshold = f"{tree.threshold[node]:.3f}".replace(".", ",")
                caption = f"{labels[tree.feature[node]]} ≤ {threshold}?"
            artist.set_text(caption + f"\n{count} Trainingsläufe")
            artist.set_color("#183344")
            artist.set_fontsize(13)
            bbox = artist.get_bbox_patch()
            bbox.set_facecolor("#e5f2ec" if leaf else "#edf3f9")
            bbox.set_edgecolor("#8ba0ac")
            bbox.set_linewidth(1.1)
            if artist.arrow_patch is not None:
                artist.arrow_patch.set_edgecolor("#657986")
                artist.arrow_patch.set_linewidth(1.4)
            positions[node] = artist.get_position()
        for node in order:
            if tree.children_left[node] < 0:
                continue
            for child, answer in [(tree.children_left[node], "Ja"),
                                  (tree.children_right[node], "Nein")]:
                parent_x, parent_y = positions[node]
                child_x, child_y = positions[child]
                ax.text((parent_x + child_x) / 2, (parent_y + child_y) / 2,
                        answer, transform=ax.transAxes, ha="center", va="center",
                        fontsize=12, color="#183344",
                        bbox={"facecolor": "white", "edgecolor": "none", "pad": 2})
        display_target = f"{target} ({TARGET_LABELS[target].replace(' (0–1)', '')})"
        scope = " · gemeinsame Parameter" if report.get("analysis_mode") == "per_norm_common" else ""
        if report.get("analysis_variant_label"):
            scope += " · " + report["analysis_variant_label"]
        fig.suptitle(f"{report['scenario']}{scope}\n{display_target}",
                     fontsize=17, fontweight="bold", y=0.98, color="#183344")
        fig.text(0.5, 0.90, "Bedingung prüfen → Ja oder Nein folgen → Zielwert am Blatt ablesen",
                 ha="center", fontsize=11, color="#526579")
        note = ("Zielwert = Mittelwert der Trainingsläufe im jeweiligen Blatt.\n"
                "Std.-Abw. = Streuung dieser Zielwerte (kein Konfidenzintervall).")
        if report.get("analysis_mode") == "pooled_common":
            note += "\nJeder gültige Lauf zählt gleich; Normen tragen entsprechend ihrer Fallzahl bei."
        if target == "first_time_x95":
            note += "\nMittelwert einschließlich 0 (= nie erreicht); keine reine Wartezeit erfolgreicher Läufe."
        if report.get("saved_definition_note"):
            note += "\n" + report["saved_definition_note"]
        fig.text(0.04, 0.025, note, fontsize=10, color="#526579", va="bottom")
        fig.subplots_adjust(left=0.025, right=0.975, top=0.87, bottom=0.13)
        for extension in ("svg", "png"):
            fig.savefig(directory / f"tree.{extension}", dpi=160, facecolor="white")
        plt.close(fig)


def _export_tree(directory: Path, scenario: SavedScenario, target: str, report: dict, payload: dict) -> None:
    model = payload["model"]
    payload["predictions"].to_csv(directory / "predictions.csv", sep=";", index=False)
    payload["importances"].to_csv(directory / "permutation_importance.csv", sep=";", index=False)
    payload["cv_results"].to_csv(directory / "training_cv.csv", sep=";", index=False)
    (directory / "rules.txt").write_text(export_text(model, feature_names=scenario.feature_names, decimals=4), encoding="utf-8")
    render_tree(directory, scenario, target, report, model)
    with plt.rc_context({"svg.fonttype": "none"}):
        fig, ax = plt.subplots(figsize=(6.4, 6.4))
        observed, predicted = payload["test_y"], payload["test_prediction"]
        ax.scatter(observed, predicted, alpha=0.65, s=28)
        lo, hi = float(min(observed.min(), predicted.min())), float(max(observed.max(), predicted.max()))
        if hi == lo:
            lo, hi = lo - 0.01, hi + 0.01
        ax.plot([lo, hi], [lo, hi], "--", color="#68727e")
        ax.set(xlabel="Simulierter Zielwert", ylabel="Vorhergesagter Zielwert",
               title=f"Testblöcke: {target}\nMAE = {report['test_metrics']['mae']:.4g}")
        ax.grid(alpha=0.2)
        fig.tight_layout()
        for extension in ("svg", "png"):
            fig.savefig(directory / f"prediction_check.{extension}", dpi=150)
        plt.close(fig)


def scenario_directories(input_root: Path, names: list[str] | None = None) -> list[Path]:
    root = Path(input_root)
    directories = [root] if (root / "metadata.json").exists() else sorted(p.parent for p in root.glob("*/metadata.json"))
    if not directories:
        raise ValueError("No completed scenario metadata found in the input folder")
    if names:
        selected = [p for p in directories if p.name in names or _read_json(p / "metadata.json")["scenario"] in names]
        matched = {label for p in selected for label in (p.name, _read_json(p / "metadata.json")["scenario"])}
        missing = set(names) - matched
        if missing:
            raise ValueError(f"Requested scenarios not found: {sorted(missing)}")
        directories = selected
    return directories


def common_parameter_scenarios(scenarios: list[SavedScenario]) -> tuple[list[str], list[SavedScenario], SavedScenario]:
    """Restrict X to sampled parameters shared by every selected source norm."""
    common = set.intersection(*(set(s.feature_names) for s in scenarios))
    names = [name for name in scenarios[0].feature_names if name in common]
    if not names:
        raise ValueError("The selected norms have no shared sampled input parameters")
    norms = [s.metadata["scenario"] for s in scenarios]
    if len(set(norms)) != len(norms):
        raise ValueError("The common-parameter analysis requires distinct source norms")
    if len({s.metadata["simulation_time"] for s in scenarios}) != 1:
        raise ValueError("Pooled trees require the same simulation horizon across norms")
    restricted = [replace(s, feature_names=list(names),
                          metadata={**s.metadata, "analysis_mode": "per_norm_common"},
                          feature_transforms={name: value for name, value in s.feature_transforms.items()
                                              if name in common}) for s in scenarios]
    frames = []
    all_inputs = set().union(*(set(s.feature_names) for s in scenarios))
    for scenario in restricted:
        # Keep the original block index shared across norms: matching Sobol blocks
        # stay together in holdout and CV, including duplicate common inputs.
        frame = scenario.data.drop(columns=[name for name in scenario.data.columns
                                            if name in all_inputs
                                            and name not in common]).copy()
        frame["source_scenario"] = scenario.metadata["scenario"]
        frames.append(frame)
    pooled = SavedScenario(
        directory=Path("all_norms"),
        metadata={"scenario": "Alle Normen (gemeinsame Parameter)", "analysis_mode": "pooled_common",
                  "source_norms": norms, "simulation_time": scenarios[0].metadata["simulation_time"],
                  "source_rate_definitions": {s.metadata["scenario"]:
                      s.metadata.get("oscillations_per_500_years_definition") for s in scenarios}},
        parameters={}, data=pd.concat(frames, ignore_index=True), feature_names=list(names),
        block_size=0, feature_transforms={},
    )
    return names, restricted, pooled


def _source_record(scenario: SavedScenario) -> dict:
    return {"directory": str(scenario.directory.resolve()), "scenario": scenario.metadata["scenario"],
                  "saved_metadata": scenario.metadata, "saved_parameters": scenario.parameters,
                  "feature_names": scenario.feature_names, "feature_transforms": scenario.feature_transforms,
                  "block_size": scenario.block_size,
                  "version_note": "Saved source scenario; metadata is not a complete archived model-code version. Analysis modes define whether sources are pooled.",
                  "file_sha256": {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in
                                  [scenario.directory / name for name in ("samples.csv", "simulation_outputs.csv", "metadata.json", "parameters.json")]
                                  if p.exists()}}


def _export_group(scenarios: list[SavedScenario], output_dir: Path, targets, config: TreeConfig,
                  manifest: dict) -> list[dict]:
    output_dir.mkdir(parents=True, exist_ok=True)
    reports = []
    for scenario in scenarios:
        try:
            split = group_holdout(scenario.data, config)
        except ValueError as error:
            split = None
            split_error = str(error)
        for target in targets:
            if split is None:
                report, payload = {"scenario": scenario.metadata["scenario"], "target": target,
                                   "status": "insufficient_data", "reason": split_error}, None
            else:
                report, payload = fit_target(scenario, target, config, split)
            if manifest.get("analysis_variant"):
                report["analysis_variant"] = manifest["analysis_variant"]
                report["analysis_variant_label"] = manifest["analysis_variant_label"]
            slug = re.sub(r"[^A-Za-z0-9_.-]+", "_", scenario.directory.name)
            destination = output_dir / slug / target
            destination.mkdir(parents=True)
            _write_json(destination / "report.json", report)
            if payload is not None:
                _export_tree(destination, scenario, target, report, payload)
            reports.append(report)
            print(f"[{manifest['analysis_mode']}] {report['scenario']} / {target}: {report['status']} "
                  f"({report.get('eligible_rows', 0)} eligible rows)", flush=True)
    _write_json(output_dir / "manifest.json", manifest)
    _write_json(output_dir / "reports.json", reports)
    summary = []
    for report in reports:
        summary.append({key: report.get(key) for key in ("scenario", "target", "status", "eligible_rows", "train_rows", "test_rows", "train_blocks", "test_blocks", "cv_mae", "beats_mean_baseline")} | {
            "test_mae": report.get("test_metrics", {}).get("mae"),
            "baseline_test_mae": report.get("baseline_test_metrics", {}).get("mae"),
            "test_r2": report.get("test_metrics", {}).get("r2"),
            "reason": report.get("reason", ""),
        })
    pd.DataFrame(summary).to_csv(output_dir / "summary.csv", sep=";", index=False)
    create_regression_tree_overview(output_dir)
    return reports


def run_analysis(input_root: Path, output_dir: Path, targets=TARGETS,
                 scenario_names=None, config: TreeConfig | None = None,
                 analysis_modes=None) -> list[dict]:
    config = config or TreeConfig()
    targets = tuple(targets)
    if not targets or set(targets) - set(TARGETS):
        raise ValueError("Choose at least one supported regression target")
    scenarios = [load_scenario(path) for path in scenario_directories(input_root, scenario_names)]
    # Keep the single-norm entry point useful; common comparisons need multiple norms.
    modes = tuple(analysis_modes) if analysis_modes is not None else (
        ANALYSIS_MODES if len(scenarios) > 1 else ("per_norm",))
    if not modes or set(modes) - set(ANALYSIS_MODES) or len(set(modes)) != len(modes):
        raise ValueError("Choose distinct supported regression analysis modes")
    common_names, restricted, pooled = (None, None, None)
    common_variants = []
    if set(modes) & {"pooled_common", "per_norm_common"}:
        if len(scenarios) < 2:
            raise ValueError("Common-parameter comparisons require at least two norms")
        common_names, restricted, pooled = common_parameter_scenarios(scenarios)
        has_agents = any(s.metadata["scenario"] == AGENT_SCENARIO for s in scenarios)
        common_variants.append(("with_agents" if has_agents else "selected_norms",
                                "mit Agentennorm" if has_agents else "", scenarios,
                                common_names, restricted, pooled, Path("_common_parametes")))
        without_agents = [s for s in scenarios if s.metadata["scenario"] != AGENT_SCENARIO]
        if has_agents and len(without_agents) >= 2:
            names, restricted_ode, pooled_ode = common_parameter_scenarios(without_agents)
            common_variants.append(("without_agents", "ohne Agentennorm", without_agents,
                                    names, restricted_ode, pooled_ode,
                                    Path("_common_parametes/without_agents")))
    output_dir = Path(output_dir)
    resolved_output = output_dir.resolve()
    if any(resolved_output == s.directory.resolve() or s.directory.resolve().is_relative_to(resolved_output) for s in scenarios):
        raise ValueError("Output must be separate from the saved source scenario folders")
    output_dir.mkdir(parents=True, exist_ok=False)
    manifest = {"config": asdict(config), "targets": list(targets), "scikit_learn_version": sklearn.__version__,
                "analysis_source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                "analysis_modes": list(modes), "common_feature_names": common_names,
                "common_variants": {variant: {"label": label, "directory": str(folder),
                    "common_feature_names": names,
                    "source_norms": [s.metadata["scenario"] for s in sources]}
                    for variant, label, sources, names, _, _, folder in common_variants},
                "split_definition": "Whole Sobol blocks assigned once before target filtering; equal original block indices across norms stay together in pooled holdout and CV.",
                "sources": [_source_record(s) for s in scenarios], "groups": {}}
    reports = []
    for mode in modes:
        if mode == "per_norm":
            manifest["groups"][mode] = "."
            reports.extend(_export_group(scenarios, output_dir, targets, config,
                {**manifest, "analysis_mode": mode,
                 "feature_selection": "All sampled inputs of each norm"}))
            continue
        for variant, label, sources, names, restricted_group, pooled_group, folder in common_variants:
            group_scenarios = [pooled_group] if mode == "pooled_common" else restricted_group
            destination = output_dir / folder / ("pooled" if mode == "pooled_common" else "per_norm")
            group_key = mode + ("_without_agents" if variant == "without_agents" else "")
            manifest["groups"][group_key] = str(destination.relative_to(output_dir))
            group_manifest = {**manifest, "analysis_mode": mode, "analysis_variant": variant,
                "analysis_variant_label": label, "common_feature_names": names,
                "sources": [_source_record(s) for s in sources],
                "feature_selection": "Intersection of sampled inputs across the variant's source norms"}
            reports.extend(_export_group(group_scenarios, destination, targets, config, group_manifest))
    _write_json(output_dir / "manifest.json", manifest)
    return reports


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-root", required=True, type=Path, help="Saved run root or a single scenario folder")
    parser.add_argument("--output-root", type=Path, default=PLOTS_DIR / "regression_tree_results")
    parser.add_argument("--scenarios", nargs="+")
    parser.add_argument("--targets", nargs="+", choices=TARGETS, default=list(TARGETS))
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--test-fraction", type=float, default=0.25)
    parser.add_argument("--max-depths", nargs="+", type=int, default=[2, 3, 4])
    parser.add_argument("--analysis-modes", nargs="+", choices=ANALYSIS_MODES,
                        help="Default: per-norm trees plus both common-parameter analyses for multi-norm runs")
    args = parser.parse_args()
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S_%f")
    config = TreeConfig(seed=args.seed, test_fraction=args.test_fraction, depths=tuple(args.max_depths))
    output_dir = args.output_root / timestamp
    run_analysis(args.input_root, output_dir, args.targets, args.scenarios, config, args.analysis_modes)
    print(f"Saved regression-tree analysis: {output_dir}")


if __name__ == "__main__":
    main()
