from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Iterable

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


OUTPUT_LABELS = {
    "final_x": "Final mitigation share (x)",
    "final_temperature": "Final temperature",
    "cumulative_emissions": "Cumulative emissions",
    "time_to_elimination_censored": "Time to elimination (censored)",
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
