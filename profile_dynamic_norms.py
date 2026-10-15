"""Profile model runs without changing equations, resolution, or tolerances.

Runs one case at a time. Reports include cProfile call times and per-interval
solver effort. Cumulative times overlap; they must not be added together.
"""
from __future__ import annotations

import argparse
import cProfile
import csv
import json
import pstats
from datetime import datetime
from pathlib import Path
from time import perf_counter
from unittest.mock import patch

import numpy as np

import model_equations as model
from sensitivity_analysis import SensitivityConfig, _run_sample, build_problem


def profile_case(label, params, config, destination, max_seconds):
    destination.mkdir(parents=True, exist_ok=False)
    profiler = cProfile.Profile()
    intervals = []
    original_get_solver = model.get_solver
    started = perf_counter()
    status, error = "completed", None

    def instrumented_get_solver(name, dt):
        key, integrate = original_get_solver(name, dt)

        def measured(fun, span, y0, **kwargs):
            interval_started = perf_counter()
            row = dict(t0=float(span[0]), t1=float(span[1]),
                       retry=bool(kwargs.get("retry", False)), rhs_calls=0,
                       last_rhs_time=float(span[0]), nfev=0, njev=0, nlu=0)
            intervals.append(row)

            def measured_rhs(t, y):
                row["rhs_calls"] += 1
                row["last_rhs_time"] = float(t)
                if row["rhs_calls"] % 128 == 1 and perf_counter()-started > max_seconds:
                    raise TimeoutError(f"Profiling limit of {max_seconds:g} seconds reached")
                return fun(t, y)

            try:
                result = integrate(measured_rhs, span, y0, **kwargs)
                for field in ("nfev", "njev", "nlu"):
                    row[field] = int(getattr(result, field, 0))
                row["success"] = bool(result.success)
                return result
            finally:
                row["seconds"] = perf_counter()-interval_started

        return key, measured

    metrics = None
    try:
        with patch.object(model, "get_solver", instrumented_get_solver):
            profiler.enable()
            metrics = _run_sample((params, [], np.array([]), config))
    except TimeoutError as exc:
        status, error = "time_limit", str(exc)
    except Exception as exc:
        status, error = "failed", f"{type(exc).__name__}: {exc}"
    finally:
        profiler.disable()
        wall_seconds = perf_counter()-started
        profiler.dump_stats(str(destination/"profile.prof"))

    stats = pstats.Stats(profiler)
    functions = []
    for (filename, line, name), (primitive, calls, self_time, cumulative, _) in stats.stats.items():
        functions.append(dict(file=filename, line=line, function=name,
                              calls=calls, primitive_calls=primitive,
                              self_seconds=self_time, cumulative_seconds=cumulative))
    functions.sort(key=lambda row: row["cumulative_seconds"], reverse=True)
    with (destination/"functions.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(functions[0]))
        writer.writeheader()
        writer.writerows(functions)
    with (destination/"intervals.csv").open("w", newline="", encoding="utf-8") as handle:
        columns = ["t0", "t1", "retry", "rhs_calls", "last_rhs_time", "nfev", "njev", "nlu", "success", "seconds"]
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        writer.writerows(intervals)
    with (destination/"profile.txt").open("w", encoding="utf-8") as handle:
        pstats.Stats(profiler, stream=handle).sort_stats("cumulative").print_stats(40)
        pstats.Stats(profiler, stream=handle).sort_stats("tottime").print_stats(40)
    summary = dict(label=label, status=status, error=error, wall_seconds=wall_seconds,
                   config=vars(config), parameters=params, intervals=len(intervals),
                   retries=sum(row["retry"] for row in intervals),
                   rhs_calls=sum(row["rhs_calls"] for row in intervals),
                   nfev=sum(row["nfev"] for row in intervals),
                   njev=sum(row["njev"] for row in intervals),
                   nlu=sum(row["nlu"] for row in intervals),
                   last_rhs_time=intervals[-1]["last_rhs_time"] if intervals else None,
                   slowest_intervals=sorted(intervals, key=lambda row: row["seconds"], reverse=True)[:10],
                   note="Profiler and counters add overhead. Time-limited results are partial; solver counters exclude unfinished calls.")
    (destination/"summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(f"{label}: {status}, {wall_seconds:.2f}s, {summary['rhs_calls']} RHS calls, "
          f"{summary['retries']} retries", flush=True)
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scenarios", nargs="+", default=["baseline", "Dynamic social norm", "Descriptive, injunctive, dynamic2"])
    parser.add_argument("--simulation-time", type=int, default=400)
    parser.add_argument("--coupling-interval", type=float, default=1.)
    parser.add_argument("--output-points-per-year", type=int, default=24)
    parser.add_argument("--max-seconds", type=float, default=60., help="Per-case profiling limit; partial profiles are saved.")
    parser.add_argument("--zero-boundaries", action="store_true", help="Also profile each exact-zero boundary check.")
    parser.add_argument("--samples-file", type=Path, help="Profile selected rows of an existing sensitivity samples.csv; requires one scenario.")
    parser.add_argument("--sample-indices", nargs="+", type=int, default=[0])
    parser.add_argument("--output-root", type=Path, default=Path("profiling_results"))
    args = parser.parse_args()
    if min(args.simulation_time, args.coupling_interval, args.output_points_per_year, args.max_seconds) <= 0:
        parser.error("Durations, resolution, and time limit must be positive")
    if args.samples_file and len(args.scenarios) != 1:
        parser.error("--samples-file requires exactly one scenario")
    root = args.output_root/datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    config = SensitivityConfig(simulation_time=args.simulation_time,
                               coupling_interval=args.coupling_interval,
                               output_points_per_year=args.output_points_per_year)
    cases = []
    for scenario in args.scenarios:
        params = model.resolve_parameters(scenario)
        if args.samples_file:
            import pandas as pd
            saved_parameters = args.samples_file.with_name("parameters.json")
            if saved_parameters.exists():
                params = json.loads(saved_parameters.read_text(encoding="utf-8"))
            frame = pd.read_csv(args.samples_file, sep=";").set_index("sample_index")
            names = build_problem(scenario)["names"]
            for index in args.sample_indices:
                cases.append((f"{scenario} sample {index}", {**params, **frame.loc[index, names].to_dict()}))
        else:
            cases.append((scenario, params))
        if args.zero_boundaries:
            problem = build_problem(scenario)
            for name, bounds in zip(problem["names"], problem["bounds"]):
                if bounds[0] == 0:
                    cases.append((f"{scenario} {name}=0", {**params, name: 0.}))
    print(f"Profiling {len(cases)} cases, one process, output: {root}", flush=True)
    summaries = []
    for index, (label, params) in enumerate(cases):
        print(f"[{index+1}/{len(cases)}] {label}", flush=True)
        summaries.append(profile_case(label, params, config, root/f"case_{index:02d}", args.max_seconds))
        (root/"summary.json").write_text(json.dumps(summaries, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
