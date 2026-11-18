"""One persisted Sobol A/B design, projected into valid per-scenario blocks."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import tempfile

import numpy as np
from SALib.sample import sobol

from analysis.parameter_ranges import shared_sampling_ranges


DESIGN_VERSION = 1


def design_spec(config):
    ranges = shared_sampling_ranges(config.parameter_ranges)
    return {"version": DESIGN_VERSION, "method": "shared_sobol_ab",
            "base_sample_size": config.base_sample_size, "seed": config.seed,
            "names": list(ranges), "bounds": list(ranges.values()),
            "calc_second_order": False}


def _checksum(a, b):
    digest = hashlib.sha256()
    for array in (a, b):
        digest.update(np.asarray(array, dtype="<f8").tobytes())
    return digest.hexdigest()


def prepare_shared_design(run_root, config):
    """Reuse saved values exactly; refuse mixing with legacy or changed designs."""
    root = Path(run_root)
    spec = design_spec(config)
    info_path, array_path = root / "sampling_design.json", root / "sampling_AB.npz"
    if info_path.exists():
        info = json.loads(info_path.read_text(encoding="utf-8"))
        if any(info.get(key) != value for key, value in spec.items()):
            raise ValueError("Existing run uses a different shared Sobol design (ranges, seed or sample size). Start a new run folder.")
        with np.load(array_path, allow_pickle=False) as arrays:
            a, b = arrays["A"].copy(), arrays["B"].copy()
        shape = (spec["base_sample_size"], len(spec["names"]))
        if a.shape != shape or b.shape != shape or _checksum(a, b) != info["sha256"]:
            raise ValueError("Stored shared Sobol A/B matrices are invalid or changed.")
        return a, b, info
    if array_path.exists() or any(root.glob("*/metadata.json")):
        raise ValueError("Run contains an incomplete or legacy sampling design. Start a new run folder; existing results are preserved.")
    root.mkdir(parents=True, exist_ok=True)
    problem = {"num_vars": len(spec["names"]), "names": spec["names"], "bounds": spec["bounds"]}
    full = sobol.sample(problem, spec["base_sample_size"], calc_second_order=False, seed=spec["seed"])
    blocks = full.reshape(spec["base_sample_size"], problem["num_vars"] + 2, problem["num_vars"])
    a, b = blocks[:, 0].copy(), blocks[:, -1].copy()
    info = {**spec, "sha256": _checksum(a, b), "arrays_file": array_path.name,
            "layout": "Each scenario: A, A with B parameter 0, ..., A with B parameter D-1, B; N*(D+2) rows.",
            "coordinate_scope": "All global range names, plus explicit extra range overrides; independent of scenario selection/order."}
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=root, suffix=".tmp", delete=False) as handle:
            temporary = Path(handle.name)
            np.savez_compressed(handle, A=a, B=b)
        os.replace(temporary, array_path)
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()
    info_path.write_text(json.dumps(info, indent=2), encoding="utf-8")
    return a, b, info


def scenario_samples(problem, a, b, design):
    """Construct standard Saltelli rows without swapping/replacing sampled columns later."""
    columns = [design["names"].index(name) for name in problem["names"]]
    for index, bounds in zip(columns, problem["bounds"]):
        if bounds != design["bounds"][index]:
            raise ValueError("Scenario bounds differ from the shared sampling design.")
    left, right = a[:, columns], b[:, columns]
    n, d = left.shape
    blocks = np.repeat(left[:, None, :], d + 2, axis=1)
    for j in range(d):
        blocks[:, j + 1, j] = right[:, j]
    blocks[:, -1] = right
    return blocks.reshape(n * (d + 2), d)
