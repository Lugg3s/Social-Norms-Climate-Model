"""Plot saved behavioural classes; optionally reclassify archived trajectories."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import textwrap

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import PercentFormatter
import numpy as np
import pandas as pd

from analysis.trajectory_classification import (
    CLASS_ORDER, CLASS_COLORS, FAILED, INVALID, UNAVAILABLE,
    classification_definition, classify_trajectory,
)


def class_frequencies(outputs: pd.DataFrame) -> pd.DataFrame:
    """Denominator is all requested Sobol rows, including failed/unclassified rows."""
    if "behaviour_class" not in outputs:
        raise ValueError("No saved behaviour_class column; use --reclassify with saved time series")
    classes = outputs["behaviour_class"].fillna(UNAVAILABLE).copy()
    if "status" in outputs:
        classes.loc[~outputs["status"].eq("completed")] = FAILED
    order = [*CLASS_ORDER, *[label for label in (INVALID, FAILED, UNAVAILABLE) if label in set(classes)]]
    unknown = set(classes) - set(order)
    if unknown:
        raise ValueError(f"Unknown behavioural classes: {sorted(unknown)}")
    counts = classes.value_counts()
    return pd.DataFrame([{
        "behaviour_class": label, "count": int(counts.get(label, 0)),
        "total_requested_runs": len(outputs),
        "relative_frequency": float(counts.get(label, 0) / len(outputs)) if len(outputs) else 0.0,
    } for label in order])


def save_classification_outputs(outputs: pd.DataFrame, destination: Path, scenario: str):
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=True)
    columns = [name for name in outputs if name in {
        "sample_index", "status", "behaviour_class", "time_series_file", "low_until_end",
    } or name.startswith(("classification_", "collapse_", "recovery_"))]
    outputs[columns].to_csv(destination / "behaviour_classes.csv", sep=";", index=False)
    frequencies = class_frequencies(outputs)
    frequencies.to_csv(destination / "behaviour_class_frequencies.csv", sep=";", index=False)
    fig, ax = plt.subplots(figsize=(max(13, 2.1 * len(frequencies)), 8))
    positions = np.arange(len(frequencies))
    proportions = frequencies["relative_frequency"].to_numpy()
    ax.bar(positions, proportions, width=0.7,
           color=[CLASS_COLORS[name] for name in frequencies["behaviour_class"]])
    for position, proportion, count in zip(positions, proportions, frequencies["count"]):
        inside = proportion > .94
        ax.annotate(f"{proportion:.1%}\nn = {count:,}", (position, proportion),
                    xytext=(0, -6 if inside else 5), textcoords="offset points", ha="center",
                    va="top" if inside else "bottom", color="white" if inside else "#263238")
    ax.set_xticks(positions)
    ax.set_xticklabels([textwrap.fill(name, 25, break_long_words=False)
                        for name in frequencies["behaviour_class"]], fontsize=10)
    ax.set_ylim(0, 1)
    ax.yaxis.set_major_formatter(PercentFormatter(1))
    ax.set_ylabel("Relative frequency across all requested runs")
    ax.set_xlabel("Behavioural class")
    ax.set_title(f"{scenario}\nBehavioural classification | {len(outputs):,} requested runs", pad=18)
    ax.grid(axis="y", alpha=.25)
    ax.set_axisbelow(True)
    fig.text(.5, .015,
             "Descriptive shares of sampled parameter ranges; not real-world probabilities. "
             "Failed runs are shown separately.\n"
             "Classification excludes pre-2017 history; stationary levels refer to a 100-year end window.",
             ha="center", fontsize=9)
    fig.tight_layout(rect=(0, .055, 1, 1))
    for suffix in ("png", "svg"):
        fig.savefig(destination / f"behaviour_class_frequencies.{suffix}", dpi=200)
    plt.close(fig)
    return frequencies


def _reclassify(folder, outputs):
    from simulation.time_series import load_time_series
    rows = []
    for _, row in outputs.iterrows():
        if row["status"] != "completed":
            rows.append({"behaviour_class": FAILED})
            continue
        if not isinstance(row.get("time_series_file"), str):
            raise FileNotFoundError(f"No archived time series for sample {row['sample_index']} in {folder}")
        path = (folder / row["time_series_file"]).resolve()
        if not path.is_relative_to(folder.resolve()):
            raise ValueError(f"Archive outside scenario folder: {path}")
        frame, metadata = load_time_series(path)
        stepwise = metadata["parameters"].get("agent_decision_model") == "annual_intention_threshold"
        rows.append(classify_trajectory(frame["t"], frame["x"], stepwise=stepwise))
    classifications = pd.DataFrame(rows, index=outputs.index)
    return pd.concat([outputs.drop(columns=classifications.columns, errors="ignore"), classifications], axis=1)


def create_plots(input_root: Path, output_root: Path | None = None, *, scenarios=None, reclassify=False):
    input_root = Path(input_root).resolve()
    folders = ([input_root] if (input_root / "simulation_outputs.csv").exists() else
               sorted(path.parent for path in input_root.glob("*/simulation_outputs.csv")))
    destination = Path(output_root).resolve() if output_root is not None else input_root / "behaviour_classification"
    reports, matched = [], set()
    for folder in folders:
        metadata = json.loads((folder / "metadata.json").read_text(encoding="utf-8"))
        scenario = metadata["scenario"]
        selected = set(scenarios or []) & {scenario, folder.name}
        if scenarios and not selected:
            continue
        matched.update(selected)
        outputs = pd.read_csv(folder / "simulation_outputs.csv", sep=";")
        if reclassify:
            outputs = _reclassify(folder, outputs)
        target = destination / folder.name
        save_classification_outputs(outputs, target, scenario)
        definition = classification_definition() if reclassify else metadata.get("behaviour_classification")
        (target / "classification_metadata.json").write_text(json.dumps({
            "scenario": scenario, "source": str(folder), "reclassified": reclassify,
            "definition": definition,
            "denominator": "All requested Sobol samples; zero-boundary runs excluded; failures shown separately.",
        }, indent=2), encoding="utf-8")
        reports.append(target)
    if set(scenarios or []) - matched:
        raise ValueError(f"Scenarios not found: {sorted(set(scenarios) - matched)}")
    if not reports:
        raise FileNotFoundError(f"No sensitivity results found in {input_root}")
    return reports


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-root", type=Path, required=True, help="Sensitivity run or single scenario folder.")
    parser.add_argument("--output-root", type=Path, default=None,
                        help="Default: <input-root>/behaviour_classification; source files remain unchanged.")
    parser.add_argument("--scenarios", nargs="+", default=None, help="Default: all available scenarios.")
    parser.add_argument("--reclassify", action="store_true",
                        help="Default: false. Recompute classes from saved NPZ trajectories, without simulation.")
    args = parser.parse_args(argv)
    for path in create_plots(**vars(args)):
        print(path)


if __name__ == "__main__":
    main()
