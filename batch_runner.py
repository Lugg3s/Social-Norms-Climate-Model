from __future__ import annotations

import argparse
import json
import math
import traceback
from dataclasses import dataclass, field
from datetime import datetime
from itertools import product
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from model_equations import SimulationResult, load_scenarios, simulate


TIME_ZERO_YEAR = 1800
DEFAULT_SIMULATION_TIME = 400
DEFAULT_OUTPUT_ROOT = Path("plots")
DEFAULT_TIME_FORMAT = "%Y-%m-%d_%H-%M-%S"


@dataclass(frozen=True)
class ExperimentGroup:
    name: str
    scenarios: list[str]
    sweep_parameters: dict[str, list[Any]]
    fixed_overrides: dict[str, Any] = field(default_factory=dict)
    simulation_time: int = DEFAULT_SIMULATION_TIME
    n_agents: int = 1000
    coupling_interval: float = 1.0
    output_points_per_year: int = 100
    seed: int = 42


GLOBAL_SWEEP_VALUES = [0, 0.25, 0.5, 1, 1.5, 2, 2.5, 3, 5]
X0_SWEEP_VALUES = [0.1, 0.25, 0.4, 0.55, 0.7, 0.85]
MID_SWEEP_VALUES = [0.5, 1, 1.5]
TAU_SWEEP_VALUES = [0.5, 1, 2, 4]
BELIEF_SWEEP_VALUES = [0, 0.05, 0.1, 0.2, 0.5]
APPROVAL_SWEEP_VALUES = [0.25, 0.5, 1, 2, 4]
AGENT_THRESHOLD_VALUES = [0.001, 0.01, 0.05, 0.1]
AGENT_OMEGA_VALUES = [0.005, 0.01, 0.05, 0.1]
AGENT_SUSCEPTIBILITY_VALUES = [0.2, 0.5, 0.8, 1.0]
AGENT_NETWORK_SIZE_VALUES = [20, 50, 100, 200]


DEFAULT_EXPERIMENT_GROUPS: list[ExperimentGroup] = [
    ExperimentGroup(
        name="global_norm_temperature",
        scenarios=[
            "baseline",
            "Dynamic social norm",
            "Dynamic baseline",
            "Observation-based / imitation",
            "Observation-based / intention motivation (agents)",
            "Belief-based / intention motivation",
            "Belief-based / approval",
            "Observation based / approval (punish only one behaviour)",
            "Observation based / approval (relative to mean)",
        ],
        sweep_parameters={
            "social_norm_factor": GLOBAL_SWEEP_VALUES,
            "temperature_factor": GLOBAL_SWEEP_VALUES,
        },
    ),
    ExperimentGroup(
        name="x0_sensitivity",
        scenarios=[
            "baseline",
            "Dynamic social norm",
            "Dynamic baseline",
            "Observation-based / imitation",
            "Belief-based / intention motivation",
            "Belief-based / approval",
            "Observation based / approval (punish only one behaviour)",
        ],
        sweep_parameters={
            "x0": X0_SWEEP_VALUES,
            "social_norm_factor": MID_SWEEP_VALUES,
            "temperature_factor": MID_SWEEP_VALUES,
        },
    ),
    ExperimentGroup(
        name="observation_based_norm",
        scenarios=["Observation-based / imitation"],
        sweep_parameters={
            "beta": [0.5, 1, 1.5, 2],
            "kappa": [0.01, 0.03, 0.05, 0.1, 0.2],
            "delta": [0.5, 1, 1.5, 2],
        },
    ),
    ExperimentGroup(
        name="dynamic_norm_trend",
        scenarios=["Dynamic social norm", "Dynamic baseline"],
        sweep_parameters={
            "tau_ref": TAU_SWEEP_VALUES,
            "tau_STref": TAU_SWEEP_VALUES,
            "tau_xp": TAU_SWEEP_VALUES,
        },
    ),
    ExperimentGroup(
        name="belief_based",
        scenarios=["Belief-based / intention motivation", "Belief-based / approval"],
        sweep_parameters={
            "N": BELIEF_SWEEP_VALUES,
            "sanction_term": [0, 0.005, 0.01, 0.05, 0.1],
        },
    ),
    ExperimentGroup(
        name="approval_sensitivity",
        scenarios=["Observation based / approval (punish only one behaviour)"],
        sweep_parameters={
            "alpha": APPROVAL_SWEEP_VALUES,
        },
    ),
    ExperimentGroup(
        name="agent_based_intention",
        scenarios=["Observation-based / intention motivation (agents)"],
        sweep_parameters={
            "threshold": AGENT_THRESHOLD_VALUES,
            "omega": AGENT_OMEGA_VALUES,
            "agent_susceptibility": AGENT_SUSCEPTIBILITY_VALUES,
            "network_size": AGENT_NETWORK_SIZE_VALUES,
        },
        n_agents=1000,
    ),
]


KEY_METRICS = [
    "max_temperature",
    "final_temperature",
    "temperature_area",
    "time_to_peak_temperature",
    "final_x",
    "max_x",
    "min_x",
    "x_area",
    "final_social_norm",
    "max_social_norm",
    "min_social_norm",
]


def sanitize_name(value: Any) -> str:
    text = str(value)
    replacements = {
        " ": "_",
        "/": "_",
        "\\": "_",
        ":": "_",
        "=": "_",
        ",": "_",
        "(": "",
        ")": "",
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    while "__" in text:
        text = text.replace("__", "_")
    return text.strip("_") or "value"


def format_value_for_slug(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        if math.isfinite(value):
            if float(value).is_integer():
                return str(int(value))
            return ("{:.4g}".format(value)).replace("-", "m").replace(".", "p")
        return str(value)
    return sanitize_name(value)


def ensure_directory(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def read_json_if_exists(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def save_json(path: Path, payload: dict[str, Any]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, ensure_ascii=True)


def create_run_name(scenario_name: str, sweep_values: dict[str, Any]) -> str:
    parts = [sanitize_name(scenario_name)]
    for parameter_name, parameter_value in sweep_values.items():
        parts.append(f"{sanitize_name(parameter_name)}-{format_value_for_slug(parameter_value)}")
    return "__".join(parts)


def build_sweep_combinations(sweep_parameters: dict[str, list[Any]]) -> list[dict[str, Any]]:
    parameter_names = list(sweep_parameters.keys())
    parameter_values = [list(values) for values in sweep_parameters.values()]
    combinations: list[dict[str, Any]] = []

    for combo in product(*parameter_values):
        combinations.append(dict(zip(parameter_names, combo)))

    return combinations


def make_output_root(base_output_root: Path = DEFAULT_OUTPUT_ROOT) -> Path:
    timestamp = datetime.now().strftime(DEFAULT_TIME_FORMAT)
    return ensure_directory(base_output_root / f"{timestamp}_night_batch")


def simulation_to_dataframe(result: dict[str, Any], params: dict[str, Any]) -> pd.DataFrame:
    simulation = result["simulation"]
    if not isinstance(simulation, SimulationResult):
        raise TypeError("Expected result['simulation'] to be a SimulationResult")

    frame = pd.DataFrame(
        {
            "t": simulation.t,
            "year": simulation.t + TIME_ZERO_YEAR,
            "C_at": simulation.C_at,
            "C_oc": simulation.C_oc,
            "C_v": simulation.C_v,
            "C_so": simulation.C_so,
            "T": simulation.T,
            "x": simulation.x,
            "x_p": simulation.x_p,
            "x_ref": simulation.x_ref,
            "social_norm_term": np.asarray(result.get("social_norm_term", np.full_like(simulation.t, np.nan, dtype=float)), dtype=float),
        }
    )

    for key, value in params.items():
        frame[key] = value

    return frame


def compute_run_metrics(result: dict[str, Any]) -> dict[str, Any]:
    simulation = result["simulation"]
    social_norm = np.asarray(result.get("social_norm_term", []), dtype=float)
    temperature = np.asarray(simulation.T, dtype=float)
    x_values = np.asarray(simulation.x, dtype=float)

    max_temperature_index = int(np.nanargmax(temperature))

    metrics = {
        "max_temperature": float(np.nanmax(temperature)),
        "final_temperature": float(temperature[-1]),
        "temperature_area": float(np.trapz(temperature, simulation.t)),
        "time_to_peak_temperature": float(simulation.t[max_temperature_index]),
        "final_x": float(x_values[-1]),
        "max_x": float(np.nanmax(x_values)),
        "min_x": float(np.nanmin(x_values)),
        "x_area": float(np.trapz(x_values, simulation.t)),
        "final_social_norm": float(social_norm[-1]) if social_norm.size else float("nan"),
        "max_social_norm": float(np.nanmax(social_norm)) if social_norm.size else float("nan"),
        "min_social_norm": float(np.nanmin(social_norm)) if social_norm.size else float("nan"),
    }
    return metrics


def save_temperature_plot(frame: pd.DataFrame, run_dir: Path, run_label: str) -> None:
    fig, (ax, ax_x) = plt.subplots(1, 2, figsize=(14, 6), sharex=True)
    fig.subplots_adjust(left=0.08, right=0.82, bottom=0.12, top=0.95, wspace=0.25)

    ax.set_xlabel("Time (year)", fontsize=16)
    ax.set_ylabel("Temperature Anomaly (celsius)", fontsize=16)
    ax.set_ylim(top=max(5, float(np.nanmax(frame["T"])) + 0.25))
    ax.set_xlim(1900, float(frame["year"].iloc[-1]))

    ax_x.set_xlabel("Time (year)", fontsize=16)
    ax_x.set_ylabel("X", fontsize=16)
    ax_x.set_xlim(1900, float(frame["year"].iloc[-1]))
    ax_x.set_ylim(0, 1)

    ax.plot(frame["year"], frame["T"], label="Temperature")
    ax_x.plot(frame["year"], frame["x"], label="x")

    handles, labels = ax.get_legend_handles_labels()
    if ax_x.get_legend_handles_labels()[0]:
        x_handles, x_labels = ax_x.get_legend_handles_labels()
        handles.extend(x_handles)
        labels.extend(x_labels)

    fig.legend(handles, labels, loc="center left", bbox_to_anchor=(0.84, 0.5), fontsize=9)
    fig.suptitle(run_label, fontsize=12)
    fig.savefig(run_dir / "temperature_and_x.png", dpi=300)
    plt.close(fig)


def save_social_norm_plot(frame: pd.DataFrame, run_dir: Path, run_label: str) -> None:
    fig, ax = plt.subplots(1, 1, figsize=(14, 6), sharex=True)
    ax.set_xlabel("Time (year)", fontsize=16)
    ax.set_ylabel("Social norm value", fontsize=16)
    ax.set_xlim(1900, float(frame["year"].iloc[-1]))

    series = frame["social_norm_term"].to_numpy(dtype=float)
    if np.all(np.isnan(series)):
        series = np.zeros_like(series)
    ax.plot(frame["year"], series, label="social_norm_term")
    ax.axhline(0, color="black", linewidth=0.8, linestyle="--")
    ax.legend(loc="center left", bbox_to_anchor=(1.02, 0.5))
    ax.set_title(run_label, fontsize=12)
    fig.tight_layout()
    fig.savefig(run_dir / "social_norm.png", dpi=300)
    plt.close(fig)


def save_auxiliary_plot(frame: pd.DataFrame, run_dir: Path, run_label: str) -> None:
    fig, ax = plt.subplots(1, 1, figsize=(14, 6), sharex=True)
    ax.set_xlabel("Time (year)", fontsize=16)
    ax.set_ylabel("Auxiliary states", fontsize=16)
    ax.set_xlim(1900, float(frame["year"].iloc[-1]))
    ax.set_ylim(0, 1)

    ax.plot(frame["year"], frame["x"], label="x", linewidth=2)
    ax.plot(frame["year"], frame["x_p"], label="x_p", linestyle="--")
    ax.plot(frame["year"], frame["x_ref"], label="x_ref", linestyle=":")
    ax.legend(loc="center left", bbox_to_anchor=(1.02, 0.5))
    ax.set_title(run_label, fontsize=12)
    fig.tight_layout()
    fig.savefig(run_dir / "auxiliary_states.png", dpi=300)
    plt.close(fig)


def save_run_outputs(
    run_dir: Path,
    run_label: str,
    params: dict[str, Any],
    result: dict[str, Any],
    metrics: dict[str, Any],
) -> None:
    ensure_directory(run_dir)
    frame = simulation_to_dataframe(result, params)
    frame.to_csv(run_dir / "time_series.csv", index=False)

    metadata = {
        "run_label": run_label,
        "parameters": params,
        "metrics": metrics,
    }
    save_json(run_dir / "metadata.json", metadata)

    save_temperature_plot(frame, run_dir, run_label)
    save_social_norm_plot(frame, run_dir, run_label)
    save_auxiliary_plot(frame, run_dir, run_label)


def append_failure_record(run_dir: Path, run_label: str, error: Exception) -> None:
    payload = {
        "run_label": run_label,
        "error_type": type(error).__name__,
        "error_message": str(error),
        "traceback": traceback.format_exc(),
    }
    save_json(run_dir / "failure.json", payload)


def run_single_combination(
    base_params: dict[str, Any],
    sweep_values: dict[str, Any],
    group: ExperimentGroup,
    run_root: Path,
    scenario_name: str,
    overwrite: bool = False,
) -> dict[str, Any]:
    params = {**base_params, **group.fixed_overrides, **sweep_values}
    run_name = create_run_name(scenario_name, sweep_values)
    run_dir = run_root / group.name / sanitize_name(scenario_name) / run_name
    ensure_directory(run_dir.parent)
    ensure_directory(run_dir)

    summary_path = run_dir / "metadata.json"
    if summary_path.exists() and not overwrite:
        existing = read_json_if_exists(summary_path) or {}
        existing_metrics = existing.get("metrics", {})
        if (run_dir / "time_series.csv").exists() and existing_metrics:
            return {
                "status": "skipped",
                "group": group.name,
                "scenario": scenario_name,
                "run_name": run_name,
                "run_dir": str(run_dir),
                **sweep_values,
                **existing_metrics,
            }

    try:
        print(f"Running {group.name} | {scenario_name} | {run_name}")
        result = simulate(
            params,
            simulation_time=group.simulation_time,
            n_agents=group.n_agents,
            coupling_interval=group.coupling_interval,
            output_points_per_year=group.output_points_per_year,
            seed=group.seed,
        )
        metrics = compute_run_metrics(result)
        save_run_outputs(run_dir, f"{group.name} | {scenario_name} | {run_name}", params, result, metrics)
        return {
            "status": "ok",
            "group": group.name,
            "scenario": scenario_name,
            "run_name": run_name,
            "run_dir": str(run_dir),
            **sweep_values,
            **metrics,
        }
    except Exception as error:
        append_failure_record(run_dir, f"{group.name} | {scenario_name} | {run_name}", error)
        return {
            "status": "failed",
            "group": group.name,
            "scenario": scenario_name,
            "run_name": run_name,
            "run_dir": str(run_dir),
            **sweep_values,
            "error_type": type(error).__name__,
            "error_message": str(error),
        }


def save_heatmap_for_two_parameters(
    summary_df: pd.DataFrame,
    group_dir: Path,
    metric_name: str,
    x_param: str,
    y_param: str,
) -> None:
    pivot = summary_df.pivot_table(
        index=y_param,
        columns=x_param,
        values=metric_name,
        aggfunc="mean",
    ).sort_index(axis=0).sort_index(axis=1)

    if pivot.empty:
        return

    fig, ax = plt.subplots(figsize=(10, 7))
    image = ax.imshow(pivot.to_numpy(), origin="lower", aspect="auto")
    ax.set_xticks(range(len(pivot.columns)))
    ax.set_xticklabels([format_value_for_slug(value) for value in pivot.columns], rotation=45, ha="right")
    ax.set_yticks(range(len(pivot.index)))
    ax.set_yticklabels([format_value_for_slug(value) for value in pivot.index])
    ax.set_xlabel(x_param)
    ax.set_ylabel(y_param)
    ax.set_title(f"{metric_name} over {x_param} and {y_param}")
    fig.colorbar(image, ax=ax, label=metric_name)
    fig.tight_layout()
    fig.savefig(group_dir / f"comparison_{metric_name}_heatmap.png", dpi=300)
    plt.close(fig)


def save_metric_vs_parameters(summary_df: pd.DataFrame, group_dir: Path, metric_name: str, sweep_parameters: list[str]) -> None:
    if not sweep_parameters:
        return

    fig, axes = plt.subplots(len(sweep_parameters), 1, figsize=(12, 4 * len(sweep_parameters)), squeeze=False)
    axes = axes.flatten()

    for axis, parameter_name in zip(axes, sweep_parameters):
        numeric_values = pd.to_numeric(summary_df[parameter_name], errors="coerce")
        axis.scatter(numeric_values, summary_df[metric_name], alpha=0.65)
        axis.set_xlabel(parameter_name)
        axis.set_ylabel(metric_name)
        axis.set_title(f"{metric_name} vs {parameter_name}")
        axis.grid(True, alpha=0.2)

    fig.tight_layout()
    fig.savefig(group_dir / f"comparison_{metric_name}_vs_parameters.png", dpi=300)
    plt.close(fig)


def save_correlation_heatmap(summary_df: pd.DataFrame, group_dir: Path) -> None:
    numeric_df = summary_df.select_dtypes(include=[np.number]).copy()
    if numeric_df.shape[1] < 2:
        return

    correlation = numeric_df.corr(numeric_only=True)
    fig, ax = plt.subplots(figsize=(max(8, 0.65 * len(correlation.columns)), max(6, 0.65 * len(correlation.columns))))
    image = ax.imshow(correlation.to_numpy(), vmin=-1, vmax=1, cmap="coolwarm")
    ax.set_xticks(range(len(correlation.columns)))
    ax.set_xticklabels(correlation.columns, rotation=45, ha="right")
    ax.set_yticks(range(len(correlation.index)))
    ax.set_yticklabels(correlation.index)
    ax.set_title("Correlation heatmap")
    fig.colorbar(image, ax=ax, label="Pearson correlation")
    fig.tight_layout()
    fig.savefig(group_dir / "comparison_correlation_heatmap.png", dpi=300)
    plt.close(fig)


def save_group_comparison_plots(summary_df: pd.DataFrame, group_dir: Path, group: ExperimentGroup) -> None:
    summary_df.to_csv(group_dir / "summary_metrics.csv", index=False)
    sweep_parameters = list(group.sweep_parameters.keys())

    save_correlation_heatmap(summary_df, group_dir)
    for metric_name in KEY_METRICS:
        if metric_name not in summary_df.columns:
            continue
        save_metric_vs_parameters(summary_df, group_dir, metric_name, sweep_parameters)

    if len(sweep_parameters) == 2:
        for metric_name in KEY_METRICS:
            if metric_name not in summary_df.columns:
                continue
            save_heatmap_for_two_parameters(
                summary_df,
                group_dir,
                metric_name,
                sweep_parameters[0],
                sweep_parameters[1],
            )


def save_approach_comparison_plot(summary_df: pd.DataFrame, group_dir: Path, scenario_name: str) -> None:
    scenario_summary = summary_df[summary_df["scenario"] == scenario_name].copy()
    if scenario_summary.empty:
        return

    metric_candidates = [
        "max_temperature",
        "final_temperature",
        "final_x",
        "final_social_norm",
        "time_to_peak_temperature",
    ]
    available_metrics = [metric for metric in metric_candidates if metric in scenario_summary.columns]
    if not available_metrics:
        return

    fig, axes = plt.subplots(len(available_metrics), 1, figsize=(12, 3.5 * len(available_metrics)), squeeze=False)
    axes = axes.flatten()

    for axis, metric_name in zip(axes, available_metrics):
        values = pd.to_numeric(scenario_summary[metric_name], errors="coerce").dropna().to_numpy()
        if values.size == 0:
            continue
        axis.boxplot(values, vert=True)
        axis.set_ylabel(metric_name)
        axis.set_xticks([1])
        axis.set_xticklabels([sanitize_name(scenario_name)], rotation=15, ha="right")
        axis.grid(True, axis="y", alpha=0.2)

    fig.suptitle(f"{scenario_name}: summary across all parameter combinations", fontsize=12)
    fig.tight_layout(rect=(0, 0, 1, 0.97))
    output_name = f"approach_summary_{sanitize_name(scenario_name)}.png"
    fig.savefig(group_dir / output_name, dpi=300)
    plt.close(fig)


def save_overall_comparison_plots(all_summaries: pd.DataFrame, run_root: Path) -> None:
    if all_summaries.empty:
        return

    metric_candidates = ["max_temperature", "final_temperature", "final_x", "final_social_norm"]
    available_metrics = [metric for metric in metric_candidates if metric in all_summaries.columns]
    if not available_metrics:
        return

    fig, axes = plt.subplots(len(available_metrics), 1, figsize=(12, 4 * len(available_metrics)), squeeze=False)
    axes = axes.flatten()
    for axis, metric_name in zip(axes, available_metrics):
        grouped = []
        labels = []
        for group_name, subset in all_summaries.groupby("group"):
            values = pd.to_numeric(subset[metric_name], errors="coerce").dropna().to_numpy()
            if values.size == 0:
                continue
            grouped.append(values)
            labels.append(group_name)
        if grouped:
            axis.boxplot(grouped, labels=labels, vert=True)
        axis.set_title(f"{metric_name} by group")
        axis.tick_params(axis="x", rotation=25)
        axis.grid(True, axis="y", alpha=0.2)

    fig.tight_layout()
    fig.savefig(run_root / "overall_metric_comparison.png", dpi=300)
    plt.close(fig)


def load_default_groups() -> list[ExperimentGroup]:
    return DEFAULT_EXPERIMENT_GROUPS


def run_groups(
    selected_group_names: list[str] | None = None,
    output_root: Path = DEFAULT_OUTPUT_ROOT,
    overwrite: bool = False,
) -> Path:
    run_root = make_output_root(output_root)
    available_scenarios = load_scenarios()

    groups = load_default_groups()
    if selected_group_names:
        selected = set(selected_group_names)
        groups = [group for group in groups if group.name in selected]

    manifest = {
        "created_at": datetime.now().isoformat(),
        "selected_groups": [group.name for group in groups],
        "available_scenarios": list(available_scenarios.keys()),
        "groups": [
            {
                "name": group.name,
                "scenarios": group.scenarios,
                "sweep_parameters": group.sweep_parameters,
                "fixed_overrides": group.fixed_overrides,
                "simulation_time": group.simulation_time,
                "n_agents": group.n_agents,
                "coupling_interval": group.coupling_interval,
                "output_points_per_year": group.output_points_per_year,
                "seed": group.seed,
            }
            for group in groups
        ],
    }
    save_json(run_root / "manifest.json", manifest)

    all_records: list[dict[str, Any]] = []
    all_group_summaries: list[pd.DataFrame] = []

    for group in groups:
        group_dir = ensure_directory(run_root / group.name)
        scenarios_to_run = [scenario for scenario in group.scenarios if scenario in available_scenarios]

        missing_scenarios = [scenario for scenario in group.scenarios if scenario not in available_scenarios]
        if missing_scenarios:
            save_json(
                group_dir / "missing_scenarios.json",
                {
                    "missing_scenarios": missing_scenarios,
                    "available_scenarios": list(available_scenarios.keys()),
                },
            )

        if not scenarios_to_run:
            continue

        sweep_combinations = build_sweep_combinations(group.sweep_parameters)
        group_records: list[dict[str, Any]] = []

        for scenario_name in scenarios_to_run:
            base_params = available_scenarios[scenario_name]
            for sweep_values in sweep_combinations:
                record = run_single_combination(
                    base_params=base_params,
                    sweep_values=sweep_values,
                    group=group,
                    run_root=run_root,
                    scenario_name=scenario_name,
                    overwrite=overwrite,
                )
                group_records.append(record)
                all_records.append(record)

        group_summary = pd.DataFrame(group_records)
        save_group_comparison_plots(group_summary, group_dir, group)
        for scenario_name in scenarios_to_run:
            save_approach_comparison_plot(group_summary, group_dir, scenario_name)
        all_group_summaries.append(group_summary)

    combined_summary = pd.concat(all_group_summaries, ignore_index=True) if all_group_summaries else pd.DataFrame()
    if not combined_summary.empty:
        combined_summary.to_csv(run_root / "all_runs_summary.csv", index=False)
        save_overall_comparison_plots(combined_summary, run_root)

    save_json(run_root / "run_index.json", {"records": all_records})
    return run_root


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run parameter sweeps and save CSVs plus plots for each combination.")
    parser.add_argument(
        "--groups",
        nargs="*",
        default=None,
        help="Optional list of experiment group names to run. If omitted, all default groups are selected.",
    )
    parser.add_argument(
        "--output-root",
        type=Path,
        default=DEFAULT_OUTPUT_ROOT,
        help="Base output directory for batch results.",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Re-run combinations even if a completed run directory already exists.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    selected_groups = args.groups if args.groups else None
    run_root = run_groups(
        selected_group_names=selected_groups,
        output_root=args.output_root,
        overwrite=args.overwrite,
    )
    print(f"Batch run completed: {run_root}")


if __name__ == "__main__":
    main()
