from __future__ import annotations

import json
import re
import warnings
import xml.etree.ElementTree as ET
from io import StringIO
from pathlib import Path
from typing import Iterable

import matplotlib.pyplot as plt
from matplotlib.ticker import MaxNLocator
import numpy as np
import pandas as pd


OUTPUT_LABELS = {
    "first_time_x95": "First time x >= 95% (0 = never reached)",
    "bool_x95": "x >= 95% reached at least once (0/1)",
    "final_x": "Final mitigation share (x)",
    "x_mean": "Time-averaged mitigation share (x)",
    "final_temperature": "Final temperature",
    "cumulative_emissions": "Cumulative emissions",
    "time_to_elimination_censored": "First threshold time (replacement for non-reaching runs)",
    "threshold_reached": "Mitigation threshold ever reached (0/1)",
    "oscillation_occurrence": "Oscillation detected: at least two complete cycles (0/1)",
    "oscillation_amplitude": "Oscillation amplitude",
    "oscillations_per_500_years": "Oscillations per 500 years",
    "damping_index": "Damping index",
}


def _safe_filename(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", value).strip("_")


def _simulation_time_label(run_root: Path) -> str:
    simulation_times = set()
    for scenario_dir in run_root.iterdir():
        metadata_path = scenario_dir / "metadata.json"
        if not scenario_dir.is_dir() or not metadata_path.exists():
            continue
        try:
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            simulation_time = metadata.get("simulation_time")
            if simulation_time is not None:
                simulation_times.add(float(simulation_time))
        except (OSError, TypeError, ValueError, json.JSONDecodeError):
            continue

    if not simulation_times:
        return ""
    labels = [
        f"{int(value)}" if value.is_integer() else f"{value:g}"
        for value in sorted(simulation_times)
    ]
    return f"t = {', '.join(labels)} years"


def _output_label(output_name: str, time_label: str) -> str:
    label = OUTPUT_LABELS.get(output_name, output_name)
    if not time_label or output_name not in {"final_x", "final_temperature"}:
        return label
    elapsed_label = time_label.removeprefix("t = ")
    if output_name == "final_x":
        return f"Mitigation share after {elapsed_label}"
    return f"Temperature anomaly after {elapsed_label}"


def _completed_values(run_root: Path, output_name: str) -> list[tuple[str, np.ndarray]]:
    values_by_scenario = []
    for scenario_dir in sorted(run_root.iterdir(), key=lambda path: path.name):
        if not scenario_dir.is_dir():
            continue
        output_path = scenario_dir / "simulation_outputs.csv"
        if not output_path.exists():
            continue
        frame = pd.read_csv(output_path, sep=";")
        if "status" not in frame or output_name not in frame:
            continue
        values = pd.to_numeric(
            frame.loc[frame["status"].eq("completed"), output_name],
            errors="coerce",
        ).dropna().to_numpy(dtype=float)
        if values.size:
            values_by_scenario.append((scenario_dir.name, values))
    return values_by_scenario


def _plot_one_output(
    values_by_scenario: list[tuple[str, np.ndarray]],
    output_name: str,
    output_path: Path,
    time_label: str,
) -> None:
    distributions = [values for _, values in values_by_scenario]
    positions = np.arange(1, len(distributions) + 1, dtype=float)
    figure, axis = plt.subplots(
        figsize=(max(10, 1.2 * len(distributions)), 7),
    )

    violin = axis.violinplot(
        distributions,
        positions=positions,
        widths=0.72,
        showmeans=False,
        showmedians=False,
        showextrema=False,
    )
    for body in violin["bodies"]:
        body.set_facecolor("#5B7DB1")
        body.set_edgecolor("#36506F")
        body.set_alpha(0.55)
        body.set_zorder(1)

    axis.boxplot(
        distributions,
        positions=positions,
        widths=0.18,
        patch_artist=True,
        showfliers=False,
        boxprops={"facecolor": "white", "edgecolor": "#263238", "linewidth": 1.0},
        medianprops={"color": "#C0392B", "linewidth": 1.5},
        whiskerprops={"color": "#263238", "linewidth": 1.0},
        capprops={"color": "#263238", "linewidth": 1.0},
        zorder=3,
    )

    random_state = np.random.default_rng(42)
    for position, values in zip(positions, distributions):
        jitter = random_state.uniform(-0.06, 0.06, size=values.size)
        axis.scatter(
            np.full(values.size, position) + jitter,
            values,
            s=7,
            color="#263238",
            alpha=0.45,
            linewidths=0,
            rasterized=True,
            zorder=5,
        )

    axis.set_xticks(positions)
    axis.set_xticklabels(
        [name.replace("_", " ") for name, _ in values_by_scenario],
        rotation=45,
        ha="right",
    )
    axis.set_xlabel("Social norm")
    label = _output_label(output_name, time_label)
    axis.set_ylabel(label)
    axis.set_title(f"{label} by social norm")
    axis.grid(axis="y", alpha=0.25)
    axis.set_axisbelow(True)
    figure.tight_layout()
    figure.savefig(output_path, dpi=300, bbox_inches="tight")
    plt.close(figure)


def create_goal_variable_violin_boxplots(
    run_root: Path,
    output_names: Iterable[str],
) -> list[Path]:
    """Create one violin plot with an overlaid boxplot per sensitivity output.

    Only rows with ``status == "completed"`` are included. Existing PNGs with
    the same names are overwritten; folders without simulation outputs are
    ignored so the function can be called after incremental runs.
    """
    run_root = Path(run_root)
    time_label = _simulation_time_label(run_root)
    created_paths = []
    for output_name in output_names:
        values_by_scenario = _completed_values(run_root, output_name)
        if not values_by_scenario:
            continue
        output_path = run_root / f"violin_boxplot_{_safe_filename(output_name)}.png"
        _plot_one_output(values_by_scenario, output_name, output_path, time_label)
        created_paths.append(output_path)
    return created_paths


RANKING_LABELS = {
    "first_time_x95": "Erste Erreichung von x ≥ 95 % (0 = nie)",
    "bool_x95": "x ≥ 95 % jemals erreicht (0/1)",
    "final_x": "Endanteil x",
    "x_mean": "Zeitmittel x",
    "final_temperature": "Endtemperatur",
    "cumulative_emissions": "Kumulierte Emissionen",
    "time_to_elimination_censored": "Erste Schwelle (zensiert bei T)",
    "threshold_reached": "Schwelle jemals erreicht",
    "oscillation_occurrence": "Oszillation erkannt (mindestens 2 Zyklen, 0/1)",
    "oscillation_amplitude": "Oszillationsamplitude",
    "oscillations_per_500_years": "Oszillationen pro 500 Jahre",
    "damping_index": "Dämpfungsindex",
    "mitigation": "Mitigation",
    "climate": "Climate",
    "dynamics": "Dynamics",
    "overall_score": "Overall score",
}
RANKING_SCORES = ("mitigation", "climate", "dynamics", "overall_score")
RANKING_PARAMETER_COLORS = dict(zip(
    ["social_norm_factor", "temperature_factor", "N", "alpha", "c_inj",
     "x_target", "c_dyn", "tau_ref", "tau_xp", "tau", "theta"],
    ["#2463A6", "#D46B20", "#B54066", "#877A28", "#36826D",
     "#008A9A", "#A76387", "#687EAA", "#AB763D", "#73635A", "#858C42"],
))
RANKING_PARAMETER_COLORS["rho"] = "#507D42"
RANKING_PLOT_STEMS = ("ranking_balken_gruppen_gesamt", "ranking_balken_zielvariablen")
RANKING_OVERVIEW_FILENAME = "ranking_balken_alle_normen.svg"
RANKING_STYLE = {
    "font.family": "DejaVu Sans", "font.size": 10,
    "axes.spines.top": False, "axes.spines.right": False, "axes.spines.left": False,
    "axes.edgecolor": "#A8B1BC", "axes.labelcolor": "#384A5C",
    "text.color": "#172D44", "xtick.color": "#46596B", "ytick.color": "#172D44",
    "savefig.facecolor": "white", "svg.fonttype": "none",
}


def _ranking_number(value: float) -> str:
    return f"{value:.3f}".replace(".", ",")


def _ranking_limits(values: np.ndarray) -> tuple[float, float]:
    finite = values[np.isfinite(values)]
    low = min(0.0, float(finite.min())) if finite.size else 0.0
    high = max(0.05, float(finite.max())) if finite.size else 0.05
    return low * 1.22, high * 1.22


def _ranking_bars(axis, values, metric, limits, colors, label=None) -> None:
    numbers = values[metric].to_numpy(dtype=float)
    finite = np.isfinite(numbers)
    positions = np.arange(len(values))
    bars = axis.barh(
        positions[finite], numbers[finite], height=0.65,
        color=[colors[parameter] for parameter in values.index[finite]], zorder=3,
    )
    axis.bar_label(bars, labels=[_ranking_number(v) for v in numbers[finite]], padding=4, fontsize=9)
    for position in positions[~finite]:
        axis.annotate("n. v.", (0, position), xytext=(4, 0), textcoords="offset points",
                      va="center", fontsize=9, color="#9B4D36")
    axis.set_yticks(positions, values.index, fontsize=9)
    axis.invert_yaxis()
    axis.set_xlim(*limits)
    axis.set_axisbelow(True)
    axis.grid(axis="x", color="#E4EAF0", linewidth=0.8)
    axis.tick_params(axis="y", length=0, pad=7)
    axis.xaxis.set_major_locator(MaxNLocator(nbins=5))
    axis.set_xlabel("Mittlerer ST" if metric in RANKING_SCORES else "Total-Order-Index ST",
                    fontsize=9, labelpad=7)
    axis.axvline(0, color="#708090", linewidth=0.7)
    axis.set_title(label or RANKING_LABELS[metric], loc="left", fontsize=13, fontweight="bold", pad=13)
    if (numbers[finite] > 1).any():
        axis.axvline(1, color="#9B4D36", linestyle=":", linewidth=1)


def _save_ranking_figure(figure, scenario_dir: Path, stem: str) -> list[Path]:
    paths = []
    try:
        for extension in ("png", "svg"):
            path = scenario_dir / f"{stem}.{extension}"
            figure.savefig(path, dpi=180, facecolor="white")
            paths.append(path)
    finally:
        plt.close(figure)
    return paths


def _scenario_ranking_barplots(scenario_dir, metadata, values, limits, colors) -> list[Path]:
    output_names = metadata["outputs_for_ranking"]
    scenario = metadata.get("scenario", scenario_dir.name)
    title = "Baseline" if scenario == "baseline" else scenario
    if scenario == "Observation based / approval (punish only one behaviour)":
        title = "Observation based / approval\n(punish only one behaviour)"
    horizon = metadata.get("simulation_time")
    details = []
    if metadata.get("base_sample_size") is not None:
        details.append(f"N = {metadata['base_sample_size']}")
    if horizon is not None:
        details.append(f"{horizon:,g} Jahre".replace(",", "."))
    if metadata.get("constant_temperature_costs", False):
        details.append("f_T(T) = 1")
    analysis = metadata.get("analysis", {})
    status = analysis.get("status")
    if "analysis_status" in values and values.analysis_status.eq("provisional").any():
        status = "provisional"
    if status == "provisional":
        retained = analysis.get("retained_base_samples")
        if retained is None and "retained_base_samples" in values:
            retained = values.retained_base_samples.iloc[0]
        details.append(f"VORLÄUFIG: {retained} vollständige Basisblöcke"
                       if retained is not None else "VORLÄUFIG: unvollständiges Design")
    suffix = "   ·   " + "   ·   ".join(details) if details else ""
    quality_note = "Punktschätzer ohne Unsicherheitsgewichtung."
    if status == "provisional":
        quality_note += " Unvollständige Blöcke ausgeschlossen; mögliche Auswahlverzerrung."
    if not np.isfinite(values[[*RANKING_SCORES, *output_names]].to_numpy(dtype=float)).all():
        quality_note += " n. v. = nicht verfügbar; siehe CSV."

    figure, axes = plt.subplots(2, 2, figsize=(15, 10))
    for axis, metric in zip(axes.flat, RANKING_SCORES):
        _ranking_bars(axis, values, metric, limits[metric], colors)
    figure.suptitle(title, fontsize=18, fontweight="bold", y=0.981)
    figure.text(0.5, 0.895, "Gruppen und Gesamtscore" + suffix, ha="center", fontsize=11)
    group_sizes = metadata.get("output_groups", {})
    counts = [len(group_sizes[group]) if group in group_sizes else default
              for group, default in zip(RANKING_SCORES[:3], (2, 2, 3))]
    figure.text(0.035, 0.068,
                f"Mitigation = Mittel aus {counts[0]} ST-Werten; Climate = Mittel aus {counts[1]}; "
                f"Dynamics = Mittel aus {counts[2]}.", fontsize=10)
    mode = metadata.get("score_mode", "simple_mean")
    overall_label = {"simple_mean": f"Overall score = Mittel aller {len(output_names)} ST-Werte.",
                     "grouped_mean": "Overall score = Mittel der 3 Gruppenscores."}.get(
                         mode, f"Overall score gemäß gespeichertem Ranking ({mode}).")
    figure.text(0.035, 0.044, overall_label + " Parameterreihenfolge: ursprüngliches Gesamtranking.", fontsize=10)
    figure.text(0.035, 0.020, quality_note, fontsize=9, color="#526579")
    figure.subplots_adjust(left=0.17, right=0.975, bottom=0.16, top=0.855, wspace=0.64, hspace=0.43)
    paths = _save_ranking_figure(figure, scenario_dir, RANKING_PLOT_STEMS[0])

    rows = (len(output_names) + 1 + 3) // 4
    figure, axes = plt.subplots(rows, 4, figsize=(25, 5.75 * rows), squeeze=False)
    for axis, metric in zip(axes.flat, output_names):
        label = ("Erste Schwelle mit Ersatzwert"
                 if metric == "time_to_elimination_censored" and "elimination_censor_offset" in metadata
                 else RANKING_LABELS[metric])
        if (metric == "time_to_elimination_censored"
                and metadata.get("elimination_time_definition", {}).get("method") == "zero_if_not_reached"):
            label = "Erste Schwelle (0 = nie erreicht)"
        _ranking_bars(axis, values, metric, limits[metric], colors, label=label)
    for axis in list(axes.flat)[len(output_names):]:
        axis.axis("off")
    info = axes.flat[len(output_names)]
    info.text(0, 0.96, "Leseschlüssel", fontsize=13, fontweight="bold", va="top")
    info.text(0, 0.84,
              "Jeder Balken: ST eines Parameters\nfür genau eine Zielvariable.\n\n"
              "Reihenfolge in allen Teilplots:\nGesamtranking der Norm.\n\n"
              "Farben kennzeichnen Parameter\nüber alle Normen hinweg.\n\n"
              "Punktschätzer ohne Fehlerbalken.\nKonfidenzhalbbreiten: ST_conf\nin sobol_indices.csv.\n\n"
              "Werte über 1 werden unverändert\ngezeigt, nicht abgeschnitten.\n"
              "n. v. = nicht verfügbar.", fontsize=11, linespacing=1.6, va="top")
    figure.suptitle(title, fontsize=20, fontweight="bold", y=0.983)
    figure.text(0.5, 0.904, f"{len(output_names)} Zielvariablen   ·   Total-Order-Indizes" + suffix,
                ha="center", fontsize=12)
    footer = "Quelle: parameter_ranking.csv. Gleiche Achsenbereiche je Kennzahl über alle Normen."
    offset = metadata.get("elimination_censor_offset")
    if horizon is not None and offset is not None:
        replacement = f"{horizon + offset:,g}".replace(",", ".")
        footer += f" Schwellenzeit: Ersatzwert {replacement} bei Nichterreichen."
    elif horizon is not None and metadata.get("elimination_time_definition", {}).get("method") == "right_censored_at_horizon":
        footer += f" Schwellenzeit: bei {horizon:g} Jahren zensiert; Erreichung separat ausgewertet."
    elif metadata.get("elimination_time_definition", {}).get("method") == "zero_if_not_reached":
        footer += " Schwellenzeit: 0 = nie erreicht; sonst Zeitpunkt der ersten Erreichung."
    figure.text(0.027, 0.044, footer, fontsize=10, color="#526579")
    figure.text(0.027, 0.022, quality_note, fontsize=10, color="#526579")
    figure.subplots_adjust(left=0.086, right=0.982, bottom=0.105, top=0.85, wspace=0.85, hspace=0.47)
    paths.extend(_save_ranking_figure(figure, scenario_dir, RANKING_PLOT_STEMS[1]))
    return paths


def _ranking_svg_panel(path, prefix: str, attribute="data-ranking-panel"):
    """Embed a vector plot with document-wide unique IDs and local references."""
    panel = ET.parse(path).getroot()
    bounds = [float(value) for value in panel.attrib["viewBox"].split()]
    identifiers = {element.attrib["id"]: prefix + element.attrib["id"]
                   for element in panel.iter() if "id" in element.attrib}

    def rewrite_references(value):
        return re.sub(r"url\(#([^)]*)\)",
                      lambda match: f"url(#{identifiers.get(match[1], match[1])})", value)

    for element in panel.iter():
        for key, value in list(element.attrib.items()):
            if key == "id":
                element.set(key, identifiers[value])
            elif key in ("href", "{http://www.w3.org/1999/xlink}href") and value.startswith("#"):
                element.set(key, "#" + identifiers.get(value[1:], value[1:]))
            else:
                element.set(key, rewrite_references(value))
        if element.tag == "{http://www.w3.org/2000/svg}style" and element.text:
            element.text = rewrite_references(element.text)
    # Use translated groups: some SVG viewers ignore nested SVG viewports.
    content = ET.Element("{http://www.w3.org/2000/svg}g", {
        "transform": f"translate({-bounds[0]:g} {-bounds[1]:g})",
    })
    content.extend(list(panel))
    panel = ET.Element("{http://www.w3.org/2000/svg}g", {attribute: prefix})
    panel.append(content)
    return panel, bounds[2], bounds[3]


def _ranking_social_norm_term(norm, names):
    """Adapt the current symbolic term to the saved model's parameterization."""
    import sympy as sp
    from analysis.symbolic_analysis import DELAY_NORMS, DYNAMIC_ODE_NORMS, symbolic_social_norm_term

    term = symbolic_social_norm_term(norm)
    symbols = {symbol.name: symbol for symbol in term.free_symbols}
    sym = lambda name: symbols.get(name, sp.Symbol(name, real=True))
    descriptive = 2 * sym("x") - 1
    # Historical saved approval runs still describe the two-factor model.
    if norm == "Observation based / approval (punish only one behaviour)" and "alpha" in names:
        term *= sym("alpha")
    if norm == "Static injunctive" and "c_inj" in names:
        term *= sym("c_inj")
    if "delta" in names:
        if norm == "Observation-based / imitation":
            term *= sym("delta")
        elif norm in {"Descriptive, injunctive, dynamic", "Descriptive, injunctive, dynamic2"}:
            term = term - descriptive + sym("delta") * descriptive
    if "tau_STref" in names and norm in DYNAMIC_ODE_NORMS:
        if norm == "dynamic social norm":
            term /= sym("tau_STref")
        else:
            dynamic = sym("c_dyn") * (sym("x_p") - sym("x_ref")) / sym("x_ref")
            term = term - dynamic + dynamic / sym("tau_STref")
    if "theta" in names and "rho" not in names and norm in DELAY_NORMS:
        term = term.subs(sym("tau") * sym("rho"), sym("theta"))
    return term


def _ranking_formula_content(metadata, parameters):
    """Display the equations matching saved parameter names, including old runs."""
    import sympy as sp
    from model.model_equations import load_scenarios
    from analysis.symbolic_analysis import (ABM_NORMS, DELAY_NORMS, DYNAMIC_ODE_NORMS,
                                   SUPPORTED_NORMS)

    scenario = metadata.get("scenario", "")
    norm = parameters.get("social_norm") or metadata.get("social_norm")
    if norm is None:
        norm = load_scenarios().get(scenario, {}).get("social_norm")
    if norm not in SUPPORTED_NORMS:
        return [], ["Für dieses gespeicherte Szenario ist keine Formel hinterlegt."]

    names = set(parameters) | set(metadata.get("problem", {}).get("names", []))
    legacy = bool(names & {"delta", "tau_STref"})
    legacy |= norm == "Observation based / approval (punish only one behaviour)" and "alpha" in names
    legacy |= norm == "Static injunctive" and "c_inj" in names
    independent_theta = "theta" in names and "rho" not in names
    legacy |= norm in DELAY_NORMS and independent_theta
    notes = ["Formel des gespeicherten Modells (historische Parameterdefinition)."
             if legacy else "Formel des aktuellen Modells."]
    temperature = (r"f_T(T)=\frac{f_{\mathrm{max}}}"
                   r"{1+\exp[-\omega(T-T_c)]}")
    codes = ["β = beta", "ω = omega", "f_max und T_c wie im Code"]
    if metadata.get("constant_temperature_costs", False):
        temperature = r"f_T(T)=1"
        codes = ["β = beta"]
        notes.append("Konstanter Temperaturbeitrag: temperature_factor; f_T(T) = 1.")
    if norm in ABM_NORMS:
        rows = [
            r"A_i(t)=-\beta_i+\mathtt{temperature\_factor}\,f_T(T(t))"
            r",\quad \beta_i\sim\mathrm{Uniform}(0,2\beta)\;\mathrm{(einmalig)}",
            r"BI_i(t)=A_i(t)+\eta q_i(t)\,\mathbf{1}_{q_i(t)\geq\phi}",
            r"b_i(t)=\mathbf{1}_{BI_i(t)\geq\psi},\quad "
            r"x(t)=\frac{1}{n}\sum_{i=1}^{n}b_i(t)",
            r"q_i(t)=\frac{1}{k}\sum_{j\in\mathcal{N}_i}b_j(t^-),\quad "
            r"k=\mathtt{network\_size},\quad n=\mathtt{n\_agents}",
            temperature,
        ]
        codes += ["η = eta", "φ = phi", "ψ = psi"]
        notes += ["Jährliche, gleichzeitige Entscheidungen ab t = 217; BI bleibt kontinuierlich. "
                  "Ohne Nachbarn ist der Normbeitrag null."]
    else:
        term = _ranking_social_norm_term(norm, names)
        if "delta" in names:
            if norm in {"Observation-based / imitation",
                        "Descriptive, injunctive, dynamic", "Descriptive, injunctive, dynamic2"}:
                codes.append("δ = delta")
        if "tau_STref" in names and norm in DYNAMIC_ODE_NORMS:
            codes.append("τ_STref = tau_STref")
        latex_names = {
            "x_p": r"x_p", "x_ref": r"x_{\mathrm{ref}}",
            "x_target": r"x_{\mathrm{target}}", "c_dyn": r"c_{\mathrm{dyn}}",
            "c_inj": r"c_{\mathrm{inj}}", "tau_STref": r"\tau_{\mathrm{STref}}",
            "x_tau": r"x(t-\tau)",
            "x_tau_theta": r"x(t-\tau-\theta)" if independent_theta else r"x(t-\tau-\tau\rho)",
        }
        rows = [
            r"\dot{x}=\kappa x(1-x)\left[-\beta+\mathtt{temperature\_factor}\,f_T(T)"
            r"+\mathtt{social\_norm\_factor}\,S\right]",
            "S=" + sp.latex(term, symbol_names={symbol: latex_names[symbol.name]
                                               for symbol in term.free_symbols if symbol.name in latex_names}),
            temperature,
        ]
        codes.insert(0, "κ = kappa")
        if norm == "Observation based / approval (punish only one behaviour)" and "alpha" in names:
            codes.append("α = alpha")
        if norm in DYNAMIC_ODE_NORMS:
            rows.insert(2, r"\dot{x}_p=\frac{x-x_p}{\tau_{xp}},\quad "
                        r"\dot{x}_{\mathrm{ref}}=\frac{x_p-x_{\mathrm{ref}}}{\tau_{\mathrm{ref}}}")
            codes += ["τ_xp = tau_xp", "τ_ref = tau_ref"]
            notes.append("Bei |x_ref| < 10⁻¹² wird der dynamische Beitrag null gesetzt.")
        if norm in DELAY_NORMS:
            if independent_theta:
                rows.insert(2, r"\theta\;\mathrm{ist\ ein\ freier\ Parameter}")
                codes += ["τ = tau", "θ = theta"]
            else:
                rows.insert(2, r"\theta=\tau\rho,\quad \tau>0,\quad \rho>1")
                codes += ["τ = tau", "ρ = rho"]
        if norm in {"dynamic social norm2", "Descriptive, injunctive, dynamic",
                    "Descriptive, injunctive, dynamic2", "Injunctive, dynamic2"}:
            codes.append("c_dyn wie im Code")
        if norm == "Static injunctive" and "c_inj" not in names:
            codes.append("x_target wie im Code")
        elif norm in {"Static injunctive", "Descriptive, injunctive, dynamic",
                    "Descriptive, injunctive, dynamic2", "Injunctive, dynamic2"}:
            codes.append("c_inj und x_target wie im Code")
        notes.append("Verhaltensdynamik ab t = 217; davor bleibt x auf dem Anfangswert.")
    notes.append("Code-Namen: " + " · ".join(codes))
    return rows, notes


def _ranking_formula_panel(metadata, parameters, width, prefix):
    """Render readable math as embedded vector paths, with accessible LaTeX."""
    rows, notes = _ranking_formula_content(metadata, parameters)
    height = 34 + 64 * len(rows) + 30 * len(notes)
    with plt.rc_context({"svg.fonttype": "path", "text.usetex": False,
                         "mathtext.fontset": "dejavusans"}):
        figure = plt.figure(figsize=(width / 72, height / 72), facecolor="white")
        try:
            for index, formula in enumerate(rows):
                figure.text(24 / width, 1 - (42 + 64 * index) / height,
                            "$" + formula + "$", fontsize=29, color="#172D44", va="center")
            for index, note in enumerate(notes):
                figure.text(24 / width, 1 - (26 + 64 * len(rows) + 30 * index) / height,
                            note, fontsize=20, color="#526579", va="center")
            buffer = StringIO()
            figure.savefig(buffer, format="svg")
            buffer.seek(0)
        finally:
            plt.close(figure)
    panel, _, rendered_height = _ranking_svg_panel(buffer, prefix, attribute="data-formula-panel")
    panel.set("role", "img")
    ET.SubElement(panel, "{http://www.w3.org/2000/svg}desc").text = "\n".join(rows + notes)
    return panel, rendered_height


def create_ranking_overview_svg(run_root: Path, scenario_dirs: Iterable[Path]) -> Path | None:
    """Combine the two existing SVGs per norm, unchanged, into one vector sheet.

    Each horizontal section contains groups/overall on the left and all saved
    targets on the right at their original relative scale. Input SVGs are
    embedded, not linked or rasterized, so the output is self-contained.
    The caller supplies the analysed norms to exclude stale/unavailable results.
    """
    ns = "http://www.w3.org/2000/svg"
    sections = []
    for index, directory in enumerate(scenario_dirs):
        directory = Path(directory)
        panels = [_ranking_svg_panel(directory / f"{stem}.svg", f"norm{index}_plot{part}_")
                  for part, stem in enumerate(RANKING_PLOT_STEMS)]
        metadata = json.loads((directory / "metadata.json").read_text(encoding="utf-8"))
        parameters_path = directory / metadata.get("parameters_file", "parameters.json")
        parameters = (json.loads(parameters_path.read_text(encoding="utf-8"))
                      if parameters_path.exists() else {})
        sections.append((metadata.get("scenario", directory.name), panels, metadata, parameters))
    if not sections:
        return None

    margin, gap, heading_height, section_gap = 36, 36, 54, 30
    column_width = max(panels[0][1] for _, panels, _, _ in sections)
    width = 2 * margin + column_width + gap + max(panels[1][1] for _, panels, _, _ in sections)
    formulas = [_ranking_formula_panel(metadata, parameters, width - 2 * margin,
                                       f"norm{index}_formula_")
                for index, (_, _, metadata, parameters) in enumerate(sections)]
    formula_gap = 24
    height = 110 + sum(heading_height + formula[1] + formula_gap + max(p[2] for p in panels) + section_gap
                       for (_, panels, _, _), formula in zip(sections, formulas))
    ET.register_namespace("", ns)
    ET.register_namespace("xlink", "http://www.w3.org/1999/xlink")
    sheet = ET.Element(f"{{{ns}}}svg", {
        "version": "1.1", "viewBox": f"0 0 {width:g} {height:g}",
        "width": "1600", "height": f"{1600 * height / width:g}",
        "role": "img", "aria-labelledby": "overview_title overview_description",
    })
    ET.SubElement(sheet, f"{{{ns}}}title", id="overview_title").text = "Sensitivitätsanalyse – alle Normen"
    ET.SubElement(sheet, f"{{{ns}}}desc", id="overview_description").text = (
        "Je Norm die Modellformel und beide vollständigen Balkenübersichten: links Gruppen und Gesamtscore, "
        "rechts die Zielvariablen. Alle Grafiken sind als Vektoren eingebettet."
    )
    ET.SubElement(sheet, f"{{{ns}}}rect", width=f"{width:g}", height=f"{height:g}", fill="#EAF0F5")

    def label(parent, x, y, content, size, bold=False):
        ET.SubElement(parent, f"{{{ns}}}text", {
            "x": f"{x:g}", "y": f"{y:g}", "font-family": "DejaVu Sans, sans-serif",
            "font-size": str(size), "font-weight": "700" if bold else "400", "fill": "#172D44",
        }).text = content

    label(sheet, margin, 44, "Sensitivitätsanalyse – alle Normen", 30, True)
    label(sheet, margin, 78,
          "Je Abschnitt: Modellformel oben · Gruppen und Gesamtscore links · Zielvariablen rechts", 19)
    top = 110
    for index, ((scenario, panels, _, _), (formula, formula_height)) in enumerate(zip(sections, formulas)):
        section = ET.SubElement(sheet, f"{{{ns}}}g", id=f"norm_section_{index}")
        label(section, margin, top + 32, f"{index + 1}. {scenario}", 25, True)
        formula.set("transform", f"translate({margin:g} {top + heading_height:g})")
        section.append(formula)
        plots_top = top + heading_height + formula_height + formula_gap
        for part, (panel, _, _) in enumerate(panels):
            left = margin if part == 0 else margin + column_width + gap
            panel.set("transform", f"translate({left:g} {plots_top:g})")
            section.append(panel)
        top = plots_top + max(p[2] for p in panels) + section_gap
    path = Path(run_root) / RANKING_OVERVIEW_FILENAME
    ET.ElementTree(sheet).write(path, encoding="utf-8", xml_declaration=True)
    return path


def create_parameter_ranking_barplots(run_root: Path) -> list[Path]:
    """Refresh per-norm PNG/SVG figures and a combined SVG from all saved rankings.

    Append runs include old and new norms when computing shared metric scales.
    CSV values and their saved rank order are preserved; no indices are recomputed.
    Empty/unavailable analyses are skipped, provisional ones are labelled, and
    undefined values are marked rather than drawn as zero. The combined sheet
    embeds both figures per norm; it does not compare common parameters between
    norms. Plot styling is local to this call.
    """
    records = []
    for ranking_path in sorted(Path(run_root).glob("*/parameter_ranking.csv")):
        metadata_path = ranking_path.with_name("metadata.json")
        if not metadata_path.exists():
            warnings.warn(f"Skipping ranking plots without metadata: {ranking_path.parent}", stacklevel=2)
            continue
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        ranking = pd.read_csv(ranking_path, sep=";")
        if ranking.empty or metadata.get("analysis", {}).get("status") == "unavailable":
            continue
        if "analysis_status" in ranking and ranking.analysis_status.eq("unavailable").all():
            continue
        output_names = metadata.get("outputs_for_ranking", [name for name in OUTPUT_LABELS if name in ranking])
        required = {"parameter", "rank", *RANKING_SCORES, *output_names}
        missing = required - set(ranking.columns)
        if missing:
            warnings.warn(f"Skipping incomplete ranking {ranking_path}: missing {sorted(missing)}", stacklevel=2)
            continue
        values = ranking.sort_values("rank", kind="stable").set_index("parameter")
        if not values.index.is_unique:
            raise ValueError(f"Duplicate parameters in {ranking_path}")
        numeric_columns = [*RANKING_SCORES, *output_names]
        values[numeric_columns] = values[numeric_columns].apply(pd.to_numeric, errors="raise")
        records.append((ranking_path.parent, {**metadata, "outputs_for_ranking": output_names}, values))
    if not records:
        return []
    limits = {metric: _ranking_limits(np.concatenate([
        values[metric].to_numpy(dtype=float) for _, _, values in records if metric in values
    ])) for metric in RANKING_LABELS if any(metric in values for _, _, values in records)}
    colors = dict(RANKING_PARAMETER_COLORS)
    unknown = sorted({p for _, _, values in records for p in values.index} - set(colors))
    palette = plt.get_cmap("tab20")
    colors.update({parameter: palette(index % 20) for index, parameter in enumerate(unknown)})
    created_paths = []
    with plt.rc_context(RANKING_STYLE):
        for scenario_dir, metadata, values in records:
            created_paths.extend(_scenario_ranking_barplots(scenario_dir, metadata, values, limits, colors))
    overview = create_ranking_overview_svg(run_root, [directory for directory, _, _ in records])
    if overview is not None:
        created_paths.append(overview)
    return created_paths
