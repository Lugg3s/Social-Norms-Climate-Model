"""Durable run-local reference reuse; only the parent process accesses SQLite."""
from __future__ import annotations

import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import sqlite3

import numpy as np

from model.model_equations import load_scenarios
from simulation.settings import simulation_kwargs
from analysis.no_norm_comparison import without_norm_parameters


def _safe(value):
    if isinstance(value, dict):
        return {key: _safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_safe(item) for item in value]
    if isinstance(value, np.generic):
        value = value.item()
    if isinstance(value, float) and not np.isfinite(value):
        return None
    return value


def _key_numbers(value):
    if isinstance(value, dict):
        return {key: _key_numbers(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_key_numbers(item) for item in value]
    if isinstance(value, (int, float, np.number)) and not isinstance(value, (bool, np.bool_)):
        return float(value)
    return _safe(value)


def reference_model(params):
    return "Agent model without social influence" if params["ABM"] else "No social norm"


class ReferenceCache:
    def __init__(self, root, config):
        self.root, self.config = Path(root).resolve(), config
        self.root.mkdir(parents=True, exist_ok=True)
        scenarios = load_scenarios()
        control_names = set(scenarios["No social norm"])
        self.ignored_ode_names = set().union(*(set(row) for row in scenarios.values())) - control_names
        project = Path(__file__).resolve().parents[2]
        sources = [*sorted((project / "model").glob("*.py")),
                   project / "analysis/simulation_metrics.py",
                   project / "analysis/trajectory_classification.py",
                   project / "analysis/no_norm_comparison.py", Path(__file__),
                   project / "data/global.1751_2017.csv"]
        versions = "|".join(importlib.metadata.version(name) for name in ("numpy", "scipy"))
        self.signature = hashlib.sha256(versions.encode() + b"".join(path.read_bytes() for path in sources)).hexdigest()
        self.connection = sqlite3.connect(self.root / "reference_cache.sqlite3")
        self.connection.execute("CREATE TABLE IF NOT EXISTS reference_results (key TEXT PRIMARY KEY, payload TEXT NOT NULL)")

    def __enter__(self):
        return self

    def __exit__(self, *args):
        try:
            if args[0] is None:
                self.connection.commit()
            else:
                self.connection.rollback()
        finally:
            self.connection.close()

    def key(self, params):
        reference = without_norm_parameters(params)
        if not reference["ABM"]:
            reference = {key: value for key, value in reference.items() if key not in self.ignored_ode_names}
        identity = {"version": 1, "parameters": reference, "simulation_settings": simulation_kwargs(self.config),
                    "source_signature": self.signature,
                    "sample_timeout_minutes": self.config.sample_timeout_minutes}
        encoded = json.dumps(_key_numbers(identity), sort_keys=True, allow_nan=False, separators=(",", ":"))
        return hashlib.sha256(encoded.encode()).hexdigest()

    def put(self, key, result, scenario_dir, sample_index):
        previous = self.connection.execute("SELECT payload FROM reference_results WHERE key=?", (key,)).fetchone()
        row = dict(result)
        archive = row.pop("time_series_file", None)
        archive = ((Path(scenario_dir) / archive).resolve().relative_to(self.root).as_posix()
                   if isinstance(archive, str) else None)
        if previous is not None:
            old = json.loads(previous[0])
            if old["result"]["status"] == "completed" and (
                    row["status"] != "completed" or old["archive"] is not None or archive is None):
                return  # Preserve a successful source, except to add a newly requested archive.
        row.pop("sample_index", None)
        row = {name: value for name, value in row.items() if not name.startswith("norm_comparison_")}
        payload = {"result": row, "source_scenario": Path(scenario_dir).name,
                   "source_sample_index": int(sample_index), "archive": archive}
        self.connection.execute("INSERT OR REPLACE INTO reference_results VALUES (?, ?)",
                                (key, json.dumps(_safe(payload), allow_nan=False)))

    def get(self, key, scenario_dir, *, require_archive=None):
        record = self.connection.execute("SELECT payload FROM reference_results WHERE key=?", (key,)).fetchone()
        if record is None:
            return None
        payload = json.loads(record[0])
        row = payload["result"]
        needs_archive = self.config.save_time_series if require_archive is None else require_archive
        if row["status"] == "completed" and needs_archive and payload["archive"] is None:
            return None  # An archive was requested but the old run saved metrics only.
        if payload["archive"] is not None and self.config.save_time_series:
            path = (self.root / payload["archive"]).resolve()
            if not path.is_relative_to(self.root) or not path.is_file():
                raise FileNotFoundError(f"Missing or invalid cached reference archive: {path}")
            row["time_series_file"] = Path(os.path.relpath(path, Path(scenario_dir).resolve())).as_posix()
        row.update(reference_key=key, reference_source_scenario=payload["source_scenario"],
                   reference_source_sample_index=payload["source_sample_index"])
        return row
