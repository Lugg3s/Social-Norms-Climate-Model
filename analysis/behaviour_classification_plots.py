"""Plot saved behavioural classes; optionally reclassify archived trajectories."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import textwrap
import xml.etree.ElementTree as ET

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import PercentFormatter
import numpy as np
import pandas as pd

from analysis.trajectory_classification import (
    CLASS_ORDER, CLASS_COLORS, FAILED, INVALID, UNAVAILABLE, LEGACY_CLASS_LABELS,
    classification_definition, classify_trajectory,
)


OVERVIEW_FILENAME = "klassifikationen_alle_normen.svg"
SVG_NS = "http://www.w3.org/2000/svg"
XLINK_NS = "http://www.w3.org/1999/xlink"


def _overview_panel(path, prefix):
    """Embed existing vectors with unique IDs and intact local references."""
    source = ET.parse(path).getroot()
    x, y, width, height = map(float, source.attrib["viewBox"].split())
    identifiers = {node.attrib["id"]: prefix + node.attrib["id"]
                   for node in source.iter() if "id" in node.attrib}
    for node in source.iter():
        for key, value in list(node.attrib.items()):
            if key == "id":
                node.set(key, identifiers[value])
            elif key in ("href", f"{{{XLINK_NS}}}href") and value.startswith("#"):
                node.set(key, "#" + identifiers.get(value[1:], value[1:]))
            else:
                node.set(key, re.sub(r"url\(#([^)]*)\)",
                                    lambda match: f"url(#{identifiers.get(match[1], match[1])})", value))
    panel = ET.Element(f"{{{SVG_NS}}}g", {"data-classification-panel": path.stem})
    content = ET.SubElement(panel, f"{{{SVG_NS}}}g", {"transform": f"translate({-x:g} {-y:g})"})
    content.extend(list(source))
    return panel, width, height


def create_classification_overview_svg(run_root: Path, scenario_dirs=None) -> Path | None:
    """Combine saved class and reference-comparison charts without simulations."""
    run_root = Path(run_root)
    directories = (sorted(path.parent for path in run_root.glob("*/behaviour_class_frequencies.svg"))
                   if scenario_dirs is None else list(map(Path, scenario_dirs)))
    sections = []
    for directory in directories:
        behaviour = directory / "behaviour_class_frequencies.svg"
        if not behaviour.exists():
            continue
        metadata_path = directory / "metadata.json"
        if not metadata_path.exists():
            metadata_path = directory / "classification_metadata.json"
        metadata = json.loads(metadata_path.read_text(encoding="utf-8")) if metadata_path.exists() else {}
        comparison = directory / "without_norm_comparison_frequencies.svg"
        sections.append((metadata.get("scenario", directory.name), behaviour,
                         comparison if comparison.exists() and metadata.get("scenario", directory.name) != "No social norm" else None))
    sections.sort(key=lambda item: (item[0] != "No social norm", item[0].casefold()))
    if not sections:
        return None

    panels = [[_overview_panel(path, f"norm{index}_plot{column}_") if path is not None else None
               for column, path in enumerate((behaviour, comparison))]
              for index, (_, behaviour, comparison) in enumerate(sections)]
    margin, gap, heading_height, section_gap = 30, 30, 54, 36
    left_width = max(row[0][1] for row in panels)
    has_comparisons = any(row[1] is not None for row in panels)
    right_width = max((row[1][1] for row in panels if row[1] is not None), default=0)
    width = 2 * margin + left_width + (gap + right_width if has_comparisons else 0)
    height = 130 + sum(heading_height + max(panel[2] for panel in row if panel is not None)
                       + section_gap for row in panels)
    ET.register_namespace("", SVG_NS)
    ET.register_namespace("xlink", XLINK_NS)
    sheet = ET.Element(f"{{{SVG_NS}}}svg", {
        "version": "1.1", "viewBox": f"0 0 {width:g} {height:g}",
        # Retain native plot size so labels remain readable when browsing.
        "width": f"{width * 96 / 72:g}px", "height": f"{height * 96 / 72:g}px",
        "role": "img", "aria-labelledby": "overview_title overview_description",
    })
    ET.SubElement(sheet, f"{{{SVG_NS}}}title", id="overview_title").text = "Behavioural classifications — all norms"
    ET.SubElement(sheet, f"{{{SVG_NS}}}desc", id="overview_description").text = (
        "One section per norm: behavioural classes on the left; saved without-norm timing "
        "and change comparisons on the right when available. Each chart uses all requested "
        "sample rows of its norm as denominator, including failures. Original metric labels "
        "and finite-observation definitions are retained. All plots are embedded vectors."
    )
    ET.SubElement(sheet, f"{{{SVG_NS}}}rect", width=f"{width:g}", height=f"{height:g}", fill="#edf2f6")

    def label(parent, x, y, text, size=20, bold=False):
        ET.SubElement(parent, f"{{{SVG_NS}}}text", {
            "x": f"{x:g}", "y": f"{y:g}", "font-family": "DejaVu Sans, sans-serif",
            "font-size": str(size), "font-weight": "700" if bold else "400", "fill": "#172b42",
        }).text = text

    label(sheet, margin, 40, "Behavioural classifications — all norms", 28, True)
    label(sheet, margin, 73, "Left: behavioural classes | Right: without-norm comparisons, when available")
    label(sheet, margin, 104, "Per-norm shares of all requested runs; not real-world probabilities.", 17)
    top = 130
    for index, ((scenario, _, _), row) in enumerate(zip(sections, panels)):
        section = ET.SubElement(sheet, f"{{{SVG_NS}}}g", {"data-scenario": scenario, "id": f"norm_section_{index}"})
        label(section, margin, top + 32, f"{index + 1}. {scenario}", 24, True)
        for column, panel in enumerate(row):
            if panel is not None:
                node = panel[0]
                node.set("transform", f"translate({margin + column * (left_width + gap):g} {top + heading_height:g})")
                section.append(node)
            elif column == 1 and has_comparisons and scenario != "No social norm":
                label(section, margin + left_width + gap, top + heading_height + 36,
                      "Without-norm comparison unavailable for this norm.", 18)
        top += heading_height + max(panel[2] for panel in row if panel is not None) + section_gap
    path = run_root / OVERVIEW_FILENAME
    ET.ElementTree(sheet).write(path, encoding="utf-8", xml_declaration=True)
    return path


def class_frequencies(outputs: pd.DataFrame) -> pd.DataFrame:
    """Denominator is all requested Sobol rows, including failed/unclassified rows."""
    if "behaviour_class" not in outputs:
        raise ValueError("No saved behaviour_class column; use --reclassify with saved time series")
    classes = outputs["behaviour_class"].fillna(UNAVAILABLE).replace(LEGACY_CLASS_LABELS)
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


def create_cross_norm_classification_plots(run_root: Path, scenario_dirs=None) -> list[Path]:
    """One vertical percentage chart per category, using saved denominators.

    Missing comparison files are excluded, never interpreted as zero events.
    Legacy labels are aliases only; saved trajectories are not reclassified.
    """
    from analysis.no_norm_comparison import LEGACY_TIMING_LABELS, TIMING_ORDER, SLOPE_ORDER

    root = Path(run_root)
    directories = (sorted(path.parent for path in root.glob("*/behaviour_class_frequencies.csv"))
                   if scenario_dirs is None else list(map(Path, scenario_dirs)))
    groups = {}
    for folder in directories:
        metadata_path = folder / "metadata.json"
        if not metadata_path.exists():
            metadata_path = folder / "classification_metadata.json"
        metadata = json.loads(metadata_path.read_text(encoding="utf-8")) if metadata_path.exists() else {}
        scenario = metadata.get("scenario", folder.name)
        for stem in ("behaviour_class_frequencies", "without_norm_comparison_frequencies"):
            if scenario == "No social norm" and stem == "without_norm_comparison_frequencies":
                continue
            path = folder / (stem + ".csv")
            if not path.exists():
                continue
            frame = pd.read_csv(path, sep=";")
            if stem == "behaviour_class_frequencies":
                frame["category"] = frame["behaviour_class"].replace(LEGACY_CLASS_LABELS)
                parts = [("behaviour", frame)]
            else:
                frame["category"] = frame["category"].replace(LEGACY_TIMING_LABELS)
                parts = list(frame.groupby("comparison", sort=False))
            for kind, part in parts:
                totals = part["total_requested_runs"].unique()
                if len(totals) != 1 or totals[0] <= 0:
                    raise ValueError(f"Invalid requested-run denominator: {path}")
                counts = part.groupby("category")["count"].sum()
                if (counts < 0).any() or counts.sum() != totals[0]:
                    raise ValueError(f"Category counts do not sum to requested runs: {path}")
                groups.setdefault(kind, []).append((scenario, int(totals[0]), counts))

    orders = {"behaviour": [*CLASS_ORDER, INVALID, FAILED, UNAVAILABLE],
              "x0_timing": TIMING_ORDER, "x1_timing": TIMING_ORDER, "slope": SLOPE_ORDER}
    titles = {"behaviour": "Behavioural class", "x0_timing": "First time x ≤ 5%",
              "x1_timing": "First time x ≥ 95%", "slope": "Change comparison"}
    paths = []
    for kind, entries in groups.items():
        entries.sort(key=lambda row: (row[0] != "No social norm", row[0].casefold()))
        present = set().union(*(set(row[2].index) for row in entries))
        if present - set(orders[kind]):
            raise ValueError(f"Unknown categories for {kind}: {present - set(orders[kind])}")
        for index, category in enumerate(orders[kind]):
            if category not in present:
                continue
            heights = [counts.get(category, 0) / total for _, total, counts in entries]
            fig, ax = plt.subplots(figsize=(max(12, 1.5 * len(entries)), 8))
            ax.bar(range(len(entries)), heights, color=CLASS_COLORS.get(category, "#4c78a8"), width=.7)
            for position, height in enumerate(heights):
                ax.annotate(f"{height:.1%}",
                            (position, height), xytext=(0, -6 if height > .94 else 5),
                            textcoords="offset points", ha="center",
                            va="top" if height > .94 else "bottom",
                            color="white" if height > .94 else "#263238", fontsize=9)
            ax.set_xticks(range(len(entries)), [textwrap.fill(name, 24, break_long_words=False)
                                               for name, _, _ in entries], rotation=35, ha="right")
            ax.set_ylim(0, 1)
            ax.yaxis.set_major_formatter(PercentFormatter(1))
            ax.set_ylabel("Share of all requested runs within each norm")
            ax.set_xlabel("Social norm")
            ax.set_title(titles[kind] + "\n" + category, pad=18)
            ax.grid(axis="y", alpha=.25)
            ax.set_axisbelow(True)
            conditions = ("\nFor this class: no oscillation detected; x varies by at most 2 percentage points over the last 100 years."
                          if kind == "behaviour" and category in CLASS_ORDER[:2] else "")
            fig.text(.5, .015, "Saved classifications; failures remain in each norm's denominator. "
                     "Missing comparison datasets are excluded.\n"
                     "Descriptive shares of sampled parameter ranges; not real-world probabilities." + conditions,
                     ha="center", fontsize=9)
            fig.tight_layout(rect=(0, .085 if conditions else .065, 1, 1))
            slug = re.sub(r"[^A-Za-z0-9]+", "_", category).strip("_").lower()
            path = root / f"classification_{kind}_{index + 1:02d}_{slug}.png"
            temporary = path.with_suffix(".tmp.png")
            try:
                fig.savefig(temporary, dpi=180)
                temporary.replace(path)
            finally:
                plt.close(fig)
                temporary.unlink(missing_ok=True)
            paths.append(path)
    return paths


def save_classification_outputs(outputs: pd.DataFrame, destination: Path, scenario: str, *, comparison=None):
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=True)
    columns = [name for name in outputs if name in {
        "sample_index", "status", "behaviour_class", "time_series_file", "low_until_end",
    } or name.startswith(("classification_", "collapse_", "recovery_", "norm_comparison_"))]
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
             "Low/high average classes: no oscillation detected; x varies by at most 2 percentage points over the last 100 years.\n"
             "Classification excludes pre-2017 history.",
             ha="center", fontsize=9)
    fig.tight_layout(rect=(0, .075, 1, 1))
    for suffix in ("png", "svg"):
        fig.savefig(destination / f"behaviour_class_frequencies.{suffix}", dpi=200)
    plt.close(fig)
    if "norm_comparison_x1_timing" in outputs and scenario != "No social norm":
        from analysis.no_norm_comparison import save_comparison_frequencies
        save_comparison_frequencies(outputs, destination, scenario, definition=comparison)
    elif scenario == "No social norm":
        for suffix in ("png", "svg"):
            (destination / f"without_norm_comparison_frequencies.{suffix}").unlink(missing_ok=True)
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
        save_classification_outputs(outputs, target, scenario,
                                    comparison=metadata.get("without_norm_comparison", {"version": 2}))
        definition = classification_definition() if reclassify else metadata.get("behaviour_classification")
        (target / "classification_metadata.json").write_text(json.dumps({
            "scenario": scenario, "source": str(folder), "reclassified": reclassify,
            "definition": definition,
            "without_norm_comparison": metadata.get("without_norm_comparison"),
            "without_norm_comparison_source": "Saved paired comparison columns; not recomputed by --reclassify.",
            "denominator": "All requested Sobol samples; zero-boundary runs excluded; failures shown separately.",
        }, indent=2), encoding="utf-8")
        reports.append(target)
    if set(scenarios or []) - matched:
        raise ValueError(f"Scenarios not found: {sorted(set(scenarios) - matched)}")
    if not reports:
        raise FileNotFoundError(f"No sensitivity results found in {input_root}")
    create_classification_overview_svg(destination, reports)
    create_cross_norm_classification_plots(destination, reports)
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
    reports = create_plots(**vars(args))
    for path in reports:
        print(path)
    print(reports[0].parent / OVERVIEW_FILENAME)


if __name__ == "__main__":
    main()
