from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from batch_runner import (
    compute_run_metrics,
    ensure_directory,
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


DEFAULT_INPUT = Path("interesting_parameter_sets.csv")
DEFAULT_OUTPUT_ROOT = Path("plots")
DEFAULT_SIMULATION_TIME = 800
DEFAULT_METADATA_COLUMNS = {"social_norm", "classification", "comment"}


def _coerce_parameter_value(value: Any) -> Any:
    if pd.isna(value):
        return None
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return None
        lowered = stripped.lower()
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


def load_interesting_parameter_sets(path: Path = DEFAULT_INPUT) -> list[dict[str, Any]]:
    """Load interesting parameter sets while treating unknown non-metadata columns as model parameters."""
    frame = pd.read_csv(path)
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
                "parameters": parameters,
            }
        )

    return entries


def run_interesting_parameter_sets(
    input_path: Path = DEFAULT_INPUT,
    output_root: Path = DEFAULT_OUTPUT_ROOT,
    simulation_time: int = DEFAULT_SIMULATION_TIME,
) -> Path:
    entries = load_interesting_parameter_sets(input_path)
    scenarios = load_scenarios()
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    run_root = ensure_directory(output_root / f"{timestamp}_interesting_parameter_sets")

    summary_rows: list[dict[str, Any]] = []

    for entry_number, entry in enumerate(entries, start=1):
        scenario_name = entry["social_norm"]
        if scenario_name not in scenarios:
            raise KeyError(f"Unknown scenario in {input_path}: {scenario_name}")

        overrides = dict(entry["parameters"])
        params = {**scenarios[scenario_name], **overrides}
        parameter_names = list(overrides.keys())
        run_name = f"{entry_number:03d}_{sanitize_name(scenario_name)}"
        run_dir = ensure_directory(run_root / run_name)

        print(f"[{entry_number}/{len(entries)}] Running {scenario_name} with {overrides}")
        result = simulate(params, simulation_time=simulation_time)
        metrics = compute_run_metrics(result, params)
        frame = simulation_to_dataframe(result, params)
        frame.to_csv(run_dir / "time_series.csv", index=False, sep=";")

        run_label = scenario_name
        save_temperature_plot(frame, run_dir, run_label, params, parameter_names)
        save_x_plot(frame, run_dir, run_label, params, parameter_names)
        save_x_phase_space_plot(frame, run_dir, run_label, params, parameter_names)
        save_social_norm_plot(frame, run_dir, run_label, params, parameter_names)
        if not np.all(frame["x_p"] == frame["x_p"].iloc[0]) or not np.all(
            frame["x_ref"] == frame["x_ref"].iloc[0]
        ):
            save_auxiliary_plot(frame, run_dir, run_label, params, parameter_names)

        metadata = {
            "social_norm": scenario_name,
            "classification": entry["classification"],
            "comment": entry["comment"],
            "overrides": overrides,
            "parameters": params,
            "metrics": metrics,
        }
        save_json(run_dir / "metadata.json", metadata)
        summary_rows.append(
            {
                "social_norm": scenario_name,
                "classification": entry["classification"],
                "comment": entry["comment"],
                **overrides,
                **metrics,
                "run_dir": str(run_dir),
            }
        )

    pd.DataFrame(summary_rows).to_csv(run_root / "summary.csv", index=False, sep=";")
    return run_root


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run and plot parameter combinations stored in interesting_parameter_sets.csv."
    )
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--simulation-time", type=int, default=DEFAULT_SIMULATION_TIME)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    run_root = run_interesting_parameter_sets(
        input_path=args.input,
        output_root=args.output_root,
        simulation_time=args.simulation_time,
    )
    print(f"Interesting parameter plots completed: {run_root}")


if __name__ == "__main__":
    main()
