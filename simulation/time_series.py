"""Portable, atomic storage of aggregate trajectories for plotting without simulation."""
from __future__ import annotations

import json
import os
from pathlib import Path
import tempfile

import numpy as np
import pandas as pd

from model.model_equations import STATE_NAMES

TIME_ZERO_YEAR = 1800
ARCHIVE_VERSION = 1


def simulation_arrays(result):
    simulation = result["simulation"]
    arrays = {name: np.asarray(getattr(simulation, name), dtype=float)
              for name in ("t", *STATE_NAMES)}
    arrays.update({name: np.asarray(result[name], dtype=float)
                   for name in ("social_norm_term", "f_T")})
    if "agent_history" in result:
        history = result["agent_history"]
        indices = np.searchsorted(history["t"], arrays["t"], side="right") - 1
        arrays["mean_intention"] = np.asarray(history["behavioral_intention"]).mean(axis=1)[indices]
    return arrays


def arrays_to_dataframe(arrays):
    frame = pd.DataFrame(arrays)
    frame.insert(1, "year", frame["t"] + TIME_ZERO_YEAR)
    return frame


def _json_value(value):
    if isinstance(value, np.generic):
        return value.item()
    raise TypeError(f"Cannot serialize {type(value).__name__}")


def save_time_series(path: Path, result, metrics, context):
    """Publish a complete NPZ atomically; never expose partially written arrays."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    metadata = {"version": ARCHIVE_VERSION, "parameters": result["parameters"],
                "solver_settings": result["solver_settings"], "metrics": metrics, "context": context}
    arrays = simulation_arrays(result)
    arrays["metadata_json"] = np.asarray(json.dumps(metadata, default=_json_value, ensure_ascii=False))
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, prefix=f".{path.stem}_", suffix=".tmp",
                                         delete=False) as handle:
            temporary = Path(handle.name)
            np.savez_compressed(handle, **arrays)
        os.replace(temporary, path)
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()


def load_time_series(path: Path):
    """Read numeric arrays and JSON only; no pickled Python objects or current defaults."""
    with np.load(Path(path), allow_pickle=False) as archive:
        metadata = json.loads(str(archive["metadata_json"].item()))
        if metadata["version"] != ARCHIVE_VERSION:
            raise ValueError(f"Unsupported trajectory version: {metadata['version']}")
        arrays = {name: archive[name].copy() for name in archive.files if name != "metadata_json"}
    for name in ("t", *STATE_NAMES, "social_norm_term", "f_T"):
        if name not in arrays:
            raise ValueError(f"Missing trajectory column {name}: {path}")
    if any(values.ndim != 1 or len(values) != len(arrays["t"]) for values in arrays.values()):
        raise ValueError(f"Invalid trajectory array lengths: {path}")
    return arrays_to_dataframe(arrays), metadata


def load_record_time_series(record):
    """Accept a saved sensitivity archive or an existing batch CSV record."""
    archive_path = record.get("time_series_file")
    if isinstance(archive_path, str) and archive_path:
        frame, metadata = load_time_series(Path(archive_path))
        return frame, metadata["parameters"]
    run_dir = Path(str(record["run_dir"]))
    frame = pd.read_csv(run_dir / "time_series.csv", sep=";", float_precision="round_trip")
    parameters_path = run_dir / "parameters.json"
    parameters = json.loads(parameters_path.read_text(encoding="utf-8")) if parameters_path.exists() else {}
    return frame, parameters
