"""Assess nested sample-size stability from saved complete Saltelli designs."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import warnings

import numpy as np
import pandas as pd
from SALib.analyze import sobol


def review_sample_sizes(input_root, output_root=None, *, sizes=(256, 512, 1024, 2048),
                        num_resamples=500, seed=42, change_tolerance=.03, ci_tolerance=.05):
    """Use intact nested prefixes, never independent rows or a failure-filtered design.

    Tolerances are explicit exploratory precision goals, not significance tests.
    A constant output has undefined variance-based indices, not zero sensitivity.
    """
    root = Path(input_root).resolve()
    destination = Path(output_root).resolve() if output_root else root / "sample_size_review"
    sizes = sorted(set(sizes))
    if not sizes or any(n < 2 or n & (n - 1) for n in sizes):
        raise ValueError("Sample sizes must be powers of two, at least 2")
    if num_resamples < 2 or change_tolerance <= 0 or ci_tolerance <= 0:
        raise ValueError("Use at least two resamples and positive tolerances")
    folders = [root] if (root / "simulation_outputs.csv").exists() else sorted(
        p.parent for p in root.glob("*/simulation_outputs.csv"))
    rows, audits = [], []
    for folder in folders:
        metadata = json.loads((folder / "metadata.json").read_text(encoding="utf-8"))
        problem, n_full = metadata["problem"], metadata["base_sample_size"]
        if problem.get("groups") or metadata.get("calc_second_order", False):
            raise ValueError("This review supports ungrouped first/total-order designs only")
        scenario, d = metadata["scenario"], problem["num_vars"]
        outputs = pd.read_csv(folder / "simulation_outputs.csv", sep=";")
        samples = pd.read_csv(folder / "samples.csv", sep=";")
        expected = n_full * (d + 2)
        for frame in (samples, outputs):
            if len(frame) != expected or not np.array_equal(frame.sample_index, np.arange(expected)):
                raise ValueError(f"Missing, duplicated or reordered rows in {folder}")
        blocks = samples[problem["names"]].to_numpy().reshape(n_full, d + 2, d)
        for j in range(d):
            mixed = blocks[:, 0].copy()
            mixed[:, j] = blocks[:, -1, j]
            if not np.array_equal(mixed, blocks[:, j + 1]):
                raise ValueError(f"Invalid Saltelli block layout in {folder}")
        for n in sizes:
            if n > n_full:
                continue
            prefix = outputs.iloc[:n * (d + 2)]
            failures = int((prefix.status != "completed").sum())
            for target in metadata["outputs_for_ranking"]:
                y = prefix[target].to_numpy(dtype=float)
                status = ("incomplete" if failures or not np.isfinite(y).all() else
                          "constant" if np.ptp(y) <= 1e-12 else "estimated")
                ab = np.r_[y[::d + 2], y[d + 1::d + 2]]
                if status == "estimated" and np.ptp(ab) <= 1e-12:
                    status = "constant A/B denominator"
                audit = dict(scenario=scenario, output=target, base_sample_size=n,
                             status=status, failed_rows=failures,
                             AB_nonzero_count=int(np.count_nonzero(ab)), AB_count=len(ab))
                audits.append(audit)
                if status != "estimated":
                    continue
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore", RuntimeWarning)
                    indices = sobol.analyze(problem, y, calc_second_order=False,
                                            num_resamples=num_resamples, seed=seed)
                for j, parameter in enumerate(problem["names"]):
                    rows.append({**audit, "parameter": parameter,
                                 **{key: float(indices[key][j])
                                    for key in ("S1", "ST", "S1_conf", "ST_conf")}})
        print(f"Reviewed sample-size prefixes: {scenario}", flush=True)
    if not audits:
        raise FileNotFoundError(f"No saved sensitivity results in {root}")
    indices = pd.DataFrame(rows, columns=["scenario", "output", "base_sample_size", "status",
                                        "failed_rows", "AB_nonzero_count", "AB_count", "parameter",
                                        "S1", "ST", "S1_conf", "ST_conf"])
    summary = []
    for (scenario, target), group in pd.DataFrame(audits).groupby(["scenario", "output"], sort=False):
        previous = None
        for audit in group.sort_values("base_sample_size").to_dict("records"):
            n = audit["base_sample_size"]
            current = indices[(indices.scenario == scenario) & (indices.output == target)
                              & (indices.base_sample_size == n)].set_index("parameter")
            row = {**audit, "previous_size": None, "max_ST_change": np.nan,
                   "max_S1_change": np.nan, "max_ST_95_halfwidth": np.nan,
                   "max_S1_95_halfwidth": np.nan, "top3_ST_set_unchanged": None,
                   "precision_check": "Not assessable"}
            if not current.empty:
                row.update(max_ST_95_halfwidth=current.ST_conf.max(skipna=False),
                           max_S1_95_halfwidth=current.S1_conf.max(skipna=False))
                if previous is not None:
                    old_n, old = previous
                    diff = (current[["S1", "ST"]] - old[["S1", "ST"]]).abs()
                    row.update(previous_size=old_n, max_ST_change=diff.ST.max(),
                               max_S1_change=diff.S1.max(),
                               top3_ST_set_unchanged=set(current.ST.nlargest(3).index) == set(old.ST.nlargest(3).index))
                    passed = (np.isfinite(current[["S1_conf", "ST_conf"]].to_numpy()).all()
                              and max(row["max_ST_change"], row["max_S1_change"]) <= change_tolerance
                              and max(row["max_ST_95_halfwidth"], row["max_S1_95_halfwidth"]) <= ci_tolerance)
                    row["precision_check"] = "Meets exploratory tolerances" if passed else "Needs more precision"
                previous = n, current
            else:
                previous = None
            summary.append(row)
    destination.mkdir(parents=True, exist_ok=True)
    indices.to_csv(destination / "indices_by_sample_size.csv", sep=";", index=False)
    table = pd.DataFrame(summary)
    table.to_csv(destination / "sample_size_summary.csv", sep=";", index=False)
    (destination / "review_settings.json").write_text(json.dumps({
        "input_root": str(root), "sizes": sizes, "num_resamples": num_resamples, "seed": seed,
        "change_tolerance": change_tolerance, "ci_tolerance": ci_tolerance,
        "interpretation": "Nested prefixes of one scramble are dependent, not independent replications. "
        "Bootstrap 95% half-widths are diagnostic approximations; constant outputs are uninformative. "
        "Failure-filtered designs are not analysed. This does not test solver, horizon or ABM seed convergence.",
        "sources": ["https://salib.readthedocs.io/en/latest/_modules/SALib/analyze/sobol.html",
                    "https://docs.scipy.org/doc/scipy/reference/stats.qmc.html"],
    }, indent=2), encoding="utf-8")
    return table


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-root", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, default=None)
    parser.add_argument("--sizes", nargs="+", type=int, default=[256, 512, 1024, 2048])
    parser.add_argument("--num-resamples", type=int, default=500)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--change-tolerance", type=float, default=.03)
    parser.add_argument("--ci-tolerance", type=float, default=.05)
    args = parser.parse_args(argv)
    review_sample_sizes(**vars(args))


if __name__ == "__main__":
    main()
