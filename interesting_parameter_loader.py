from __future__ import annotations

import argparse
import csv
from datetime import datetime
from io import BytesIO
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from batch_runner import (
    add_parameter_text_box,
    compute_run_metrics,
    ensure_directory,
    load_default_groups,
    sanitize_name,
    save_auxiliary_plot,
    save_json,
    save_social_norm_plot,
    save_temperature_plot,
    save_x_phase_space_plot,
    save_x_plot,
    simulation_to_dataframe,
)
from model_equations import load_scenarios, simulate
from symbolic_analysis import symbolic_social_norm_term
import matplotlib.pyplot as plt


DEFAULT_INPUT = Path("interesting_parameter_sets.csv")
DEFAULT_OUTPUT_ROOT = Path("plots")
DEFAULT_SIMULATION_TIME = 800
DEFAULT_METADATA_COLUMNS = {"social_norm", "classification", "comment", "reason"}


def _display_figure_in_notebook(fig: plt.Figure) -> None:
    """Render a figure inline without depending on Matplotlib's active backend."""
    try:
        from IPython.display import Image, display
    except ImportError as exc:
        plt.close(fig)
        raise RuntimeError(
            "Displaying plots without storing files requires IPython/Jupyter."
        ) from exc

    image_buffer = BytesIO()
    try:
        fig.savefig(image_buffer, format="png", dpi=150, bbox_inches="tight")
        display(Image(data=image_buffer.getvalue()))
    finally:
        image_buffer.close()
        plt.close(fig)


def _display_temperature_plot(frame, run_label, params, parameter_names) -> None:
    fig, ax = plt.subplots(figsize=(14, 6))
    ax.plot(frame["year"], frame["T"], label="Temperature")
    ax.set_xlabel("Time (year)")
    ax.set_ylabel("Temperature Anomaly (celsius)")
    ax.set_xlim(1900, float(frame["year"].iloc[-1]))
    ax.set_ylim(top=max(5, float(np.nanmax(frame["T"])) + 0.25))
    ax.set_title(run_label)
    ax.legend(loc="center left", bbox_to_anchor=(1.02, 0.5), fontsize=9)
    add_parameter_text_box(ax, params, parameter_names)
    fig.tight_layout()
    _display_figure_in_notebook(fig)


def _display_x_plot(frame, run_label, params, parameter_names) -> None:
    fig, ax = plt.subplots(figsize=(14, 6))
    ax.plot(frame["year"], frame["x"], label="x")
    ax.set_xlabel("Time (year)")
    ax.set_ylabel("Fraction of mitigators (X)")
    ax.set_xlim(1900, float(frame["year"].iloc[-1]))
    ax.set_ylim(-0.1, 1.1)
    ax.set_title(run_label)
    ax.legend(loc="center left", bbox_to_anchor=(1.02, 0.5), fontsize=9)
    add_parameter_text_box(ax, params, parameter_names)
    fig.tight_layout()
    _display_figure_in_notebook(fig)


def _display_x_phase_space_plot(frame, run_label, params, parameter_names) -> None:
    t_values = pd.to_numeric(frame["t"], errors="coerce").to_numpy(dtype=float)
    x_values = pd.to_numeric(frame["x"], errors="coerce").to_numpy(dtype=float)
    year_values = pd.to_numeric(frame["year"], errors="coerce").to_numpy(dtype=float)
    valid = np.isfinite(t_values) & np.isfinite(x_values) & np.isfinite(year_values)
    t_values = t_values[valid]
    x_values = x_values[valid]
    year_values = year_values[valid]
    if t_values.size < 2 or np.any(np.diff(t_values) <= 0):
        return

    dx_dt = np.gradient(x_values, t_values)
    fig, ax = plt.subplots(figsize=(10, 7))
    ax.plot(dx_dt, x_values, color="0.75", linewidth=0.8, zorder=1)
    marker_indices = np.linspace(
        0, t_values.size - 1, min(t_values.size, 5000), dtype=int
    )
    trajectory = ax.scatter(
        dx_dt[marker_indices],
        x_values[marker_indices],
        c=year_values[marker_indices],
        cmap="viridis",
        s=8,
        linewidths=0,
        zorder=2,
    )
    ax.scatter(
        dx_dt[0],
        x_values[0],
        color="green",
        marker="o",
        s=55,
        label="Start",
        zorder=3,
    )
    ax.scatter(
        dx_dt[-1],
        x_values[-1],
        color="red",
        marker="X",
        s=65,
        label="End",
        zorder=3,
    )
    ax.axvline(0, color="black", linewidth=0.8, linestyle="--")
    ax.set_xlabel("Rate of change dx/dt")
    ax.set_ylabel("Fraction of mitigators x(t)")
    ax.set_ylim(-0.1, 1.1)
    ax.set_title(f"{run_label} | Phase space")
    ax.legend(loc="lower right")
    add_parameter_text_box(ax, params, parameter_names)
    colorbar = fig.colorbar(trajectory, ax=ax)
    colorbar.set_label("Time (year)")
    fig.tight_layout()
    _display_figure_in_notebook(fig)


def _display_social_norm_plot(frame, run_label, params, parameter_names) -> None:
    fig, ax = plt.subplots(figsize=(14, 6))
    series = frame["social_norm_term"].to_numpy(dtype=float)
    if np.all(np.isnan(series)):
        series = np.zeros_like(series)
    ax.plot(frame["year"], series, label="social_norm_term")
    ax.axhline(0, color="black", linewidth=0.8, linestyle="--")
    ax.set_xlabel("Time (year)")
    ax.set_ylabel("Social norm value")
    ax.set_xlim(1900, float(frame["year"].iloc[-1]))
    ax.set_title(run_label)
    ax.legend(loc="center left", bbox_to_anchor=(1.02, 0.5), fontsize=9)
    add_parameter_text_box(ax, params, parameter_names)
    fig.tight_layout()
    _display_figure_in_notebook(fig)


def _display_auxiliary_plot(frame, run_label, params, parameter_names) -> None:
    fig, ax = plt.subplots(figsize=(14, 6))
    ax.plot(frame["year"], frame["x"], label="x", linewidth=2)
    ax.plot(frame["year"], frame["x_p"], label="x_p", linestyle="--")
    ax.plot(frame["year"], frame["x_ref"], label="x_ref", linestyle=":")
    ax.set_xlabel("Time (year)")
    ax.set_ylabel("Auxiliary states")
    ax.set_xlim(1900, float(frame["year"].iloc[-1]))
    ax.set_ylim(0, 1)
    ax.set_title(run_label)
    ax.legend(loc="center left", bbox_to_anchor=(1.02, 0.5))
    add_parameter_text_box(ax, params, parameter_names)
    fig.tight_layout()
    _display_figure_in_notebook(fig)


def _display_all_run_plots(frame, run_label, params, parameter_names) -> None:
    _display_temperature_plot(frame, run_label, params, parameter_names)
    _display_x_plot(frame, run_label, params, parameter_names)
    _display_x_phase_space_plot(frame, run_label, params, parameter_names)
    _display_social_norm_plot(frame, run_label, params, parameter_names)
    if not np.all(frame["x_p"] == frame["x_p"].iloc[0]) or not np.all(
        frame["x_ref"] == frame["x_ref"].iloc[0]
    ):
        _display_auxiliary_plot(frame, run_label, params, parameter_names)


def _coerce_parameter_value(value: Any) -> Any:
    if pd.isna(value):
        return None
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return None
        lowered = stripped.lower()
        if lowered in {"-", "—", "hier weitermachen"}:
            return None
        if lowered == "true":
            return True
        if lowered == "false":
            return False
        try:
            numeric = float(stripped)
        except ValueError:
            return stripped
        return int(numeric) if numeric.is_integer() else numeric
    if isinstance(value, np.generic):
        value = value.item()
    if isinstance(value, float) and value.is_integer():
        return int(value)
    return value


def _read_parameter_csv(path: Path) -> pd.DataFrame:
    """Read the CSV and append accidental extra fields to the reason column."""
    records: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8", newline="") as file:
        for row in csv.DictReader(file):
            extra_fields = row.pop(None, [])
            if extra_fields:
                reason_parts = [row.get("reason", ""), *extra_fields]
                row["reason"] = ", ".join(
                    str(part).strip() for part in reason_parts if str(part).strip()
                )
            records.append(row)
    return pd.DataFrame(records)


def load_interesting_parameter_sets(path: Path | str = DEFAULT_INPUT) -> list[dict[str, Any]]:
    """Load interesting parameter sets while treating unknown non-metadata columns as model parameters."""
    path = Path(path)
    frame = _read_parameter_csv(path)
    if "social_norm" not in frame.columns:
        raise ValueError("interesting parameter CSV must contain a 'social_norm' column")

    parameter_columns = [column for column in frame.columns if column not in DEFAULT_METADATA_COLUMNS]
    entries: list[dict[str, Any]] = []

    for row_index, row in frame.iterrows():
        scenario_name = str(row.get("social_norm", "")).strip()
        if not scenario_name or scenario_name.lower() == "nan":
            continue

        parameters: dict[str, Any] = {}
        for column in parameter_columns:
            value = _coerce_parameter_value(row[column])
            if value is not None:
                parameters[column] = value

        entries.append(
            {
                "row_index": int(row_index),
                "social_norm": scenario_name,
                "classification": "" if pd.isna(row.get("classification")) else str(row.get("classification", "")),
                "comment": "" if pd.isna(row.get("comment")) else str(row.get("comment", "")),
                "reason": "" if pd.isna(row.get("reason")) else str(row.get("reason", "")),
                "parameters": parameters,
            }
        )

    return entries


def _resolve_scenario_name(name: str, scenarios: dict[str, dict[str, Any]]) -> str:
    """Resolve exact scenario names as well as batch group names used in the CSV."""
    aliases: dict[str, str] = {}
    for scenario_name in scenarios:
        aliases[scenario_name.casefold()] = scenario_name
        aliases[sanitize_name(scenario_name).casefold()] = scenario_name
    for group in load_default_groups():
        if len(group.scenarios) == 1:
            aliases[group.name.casefold()] = group.scenarios[0]
            aliases[sanitize_name(group.name).casefold()] = group.scenarios[0]

    lookup = name.casefold()
    if lookup not in aliases:
        lookup = sanitize_name(name).casefold()
    if lookup not in aliases:
        raise KeyError(f"Unknown scenario or experiment group: {name}")
    return aliases[lookup]


def run_interesting_parameter_sets(
    input_path: Path | str = DEFAULT_INPUT,
    output_root: Path | str = DEFAULT_OUTPUT_ROOT,
    simulation_time: int = DEFAULT_SIMULATION_TIME,
    store_files: bool = True,
) -> Path | None:
    input_path = Path(input_path)
    output_root = Path(output_root)
    entries = load_interesting_parameter_sets(input_path)
    scenarios = load_scenarios()
    run_root: Path | None = None
    if store_files:
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        run_root = ensure_directory(output_root / f"{timestamp}_interesting_parameter_sets")

    summary_rows: list[dict[str, Any]] = []

    for entry_number, entry in enumerate(entries, start=1):
        source_name = entry["social_norm"]
        scenario_name = _resolve_scenario_name(source_name, scenarios)

        overrides = dict(entry["parameters"])
        params = {**scenarios[scenario_name], **overrides}
        parameter_names = list(overrides.keys())
        run_name = f"{entry_number:03d}_{sanitize_name(scenario_name)}"
        run_dir = ensure_directory(run_root / run_name) if run_root is not None else Path(".")

        print(f"[{entry_number}/{len(entries)}] Running {scenario_name} with {overrides}")
        print(f"  Comment: {entry['comment'] or '-'}")
        social_norm_term = symbolic_social_norm_term(params["social_norm"])
        print(f"  Social norm term: {social_norm_term if social_norm_term is not None else 'agent-based / stochastic'}")
        if entry["reason"]:
            print(f"  Reason: {entry['reason']}")
        result = simulate(params, simulation_time=simulation_time)
        metrics = compute_run_metrics(result, params)
        frame = simulation_to_dataframe(result, params)
        if store_files:
            frame.to_csv(run_dir / "time_series.csv", index=False, sep=";")

        run_label = scenario_name
        if store_files:
            save_temperature_plot(frame, run_dir, run_label, params, parameter_names)
            save_x_plot(frame, run_dir, run_label, params, parameter_names)
            save_x_phase_space_plot(frame, run_dir, run_label, params, parameter_names)
            save_social_norm_plot(frame, run_dir, run_label, params, parameter_names)
            if not np.all(frame["x_p"] == frame["x_p"].iloc[0]) or not np.all(
                frame["x_ref"] == frame["x_ref"].iloc[0]
            ):
                save_auxiliary_plot(frame, run_dir, run_label, params, parameter_names)
        else:
            _display_all_run_plots(frame, run_label, params, parameter_names)

        metadata = {
            "social_norm": scenario_name,
            "classification": entry["classification"],
            "comment": entry["comment"],
            "reason": entry["reason"],
            "overrides": overrides,
            "parameters": params,
            "metrics": metrics,
        }
        if store_files:
            save_json(run_dir / "metadata.json", metadata)
        summary_rows.append(
            {
                "social_norm": scenario_name,
                "classification": entry["classification"],
                "comment": entry["comment"],
                "reason": entry["reason"],
                **overrides,
                **metrics,
                "run_dir": str(run_dir) if store_files else "",
            }
        )

    if run_root is not None:
        pd.DataFrame(summary_rows).to_csv(run_root / "summary.csv", index=False, sep=";")
    return run_root


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run and plot parameter combinations stored in interesting_parameter_sets.csv."
    )
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--simulation-time", type=int, default=DEFAULT_SIMULATION_TIME)
    parser.add_argument(
        "--no-store-files",
        action="store_true",
        help="Display plots without creating output files.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    run_root = run_interesting_parameter_sets(
        input_path=args.input,
        output_root=args.output_root,
        simulation_time=args.simulation_time,
        store_files=not args.no_store_files,
    )
    if run_root is None:
        print("Interesting parameter plots completed without storing files.")
    else:
        print(f"Interesting parameter plots completed: {run_root}")


if __name__ == "__main__":
    main()
