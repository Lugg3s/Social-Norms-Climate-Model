"""Scatter x at a fixed end time against one varied parameter per scenario.

This is a finite-time endpoint sweep: one independent simulation per parameter
value, restarting from configured initial conditions with other inputs and the
seed fixed. It does not perform branch continuation or recover all attractors
of an oscillating system.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import textwrap

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import PercentFormatter
import numpy as np
import pandas as pd

from model.model_equations import load_scenarios, resolve_parameters, simulate, simulation_years
from model.solvers import get_solver
from utils.bounded_process_map import bounded_map
from utils.paths import PROJECT_ROOT, RUNS_DIR


DEFAULT_OUTPUT_ROOT = RUNS_DIR / "bifurcation_diagrams"
TIME_ZERO_YEAR = int(simulation_years[0])


@dataclass(frozen=True)
class SweepConfig:
    simulation_time: float = 600
    workers: int = 1
    seed: int = 42
    n_agents: int = 1000
    coupling_interval: float = 0.1
    output_points_per_year: int = 24
    solver: str = "BDF"
    dt: float | None = None
    constant_temperature_costs: bool = False
    simulate_only_x: bool = False
    sample_timeout_minutes: float = 20

    def __post_init__(self):
        for name in ("simulation_time", "coupling_interval", "sample_timeout_minutes"):
            if not np.isfinite(getattr(self, name)) or getattr(self, name) <= 0:
                raise ValueError(f"{name} must be finite and positive")
        for name in ("workers", "n_agents", "output_points_per_year"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int) or value < 1:
                raise ValueError(f"{name} must be a positive integer")
        get_solver(self.solver, self.dt)


def parameter_grid(values=None, interval=None) -> list[float]:
    """Use an explicit value list or an inclusive MIN MAX COUNT grid."""
    if (values is None) == (interval is None):
        raise ValueError("Specify exactly one of parameter-values and parameter-range")
    if interval is not None:
        start, stop, count = interval
        if not np.all(np.isfinite(interval)) or count != int(count) or count < 2:
            raise ValueError("parameter-range needs finite MIN MAX and an integer COUNT >= 2")
        if start >= stop:
            raise ValueError("parameter-range requires MIN < MAX")
        values = np.linspace(start, stop, int(count))
    result = np.asarray(list(values), dtype=float)
    if result.ndim != 1 or not result.size or not np.all(np.isfinite(result)):
        raise ValueError("parameter-values must be a non-empty finite one-dimensional list")
    return result.tolist()


def build_tasks(scenarios, parameter_name, parameter_values, config):
    """Copy a scenario for every point; vary only the named model parameter."""
    if not isinstance(parameter_name, str) or not parameter_name:
        raise ValueError("Choose exactly one parameter name")
    available = load_scenarios()
    tasks, bases = [], {}
    for scenario in dict.fromkeys(scenarios):
        base = resolve_parameters(available[scenario])
        original = base[parameter_name]  # Unknown model inputs must not be silently inserted.
        if isinstance(original, bool) or not isinstance(original, (int, float)):
            raise ValueError(f"{parameter_name} is not a numeric model parameter in {scenario}")
        bases[scenario] = base
        for value in parameter_values:
            if parameter_name == "network_size" and (value != int(value) or not 0 <= value < config.n_agents):
                raise ValueError("network_size values must be integers from 0 to n_agents - 1")
            parameters = resolve_parameters({**base, parameter_name: value})
            tasks.append(dict(scenario=scenario, parameter_value=value, parameters=parameters,
                              config=asdict(config)))
    if not tasks:
        raise ValueError("Select at least one scenario and parameter value")
    return tasks, bases


def run_endpoint(task):
    result = simulate(extension=task["parameters"], verbose=False,
                      **{name: value for name, value in task["config"].items()
                         if name not in {"workers", "sample_timeout_minutes"}})["simulation"]
    end_time, end_x = float(result.t[-1]), float(result.x[-1])
    if not np.isclose(end_time, task["config"]["simulation_time"], rtol=0, atol=1e-8):
        raise RuntimeError("Simulation did not reach the requested end time")
    if not np.isfinite(end_x) or not 0 <= end_x <= 1:
        raise RuntimeError("Final mitigation share must be finite and within [0, 1]")
    return {"final_x": end_x, "end_time": end_time, "end_year": TIME_ZERO_YEAR + end_time}


def endpoint_plot(frame, scenario, parameter_name, simulation_time):
    """One scenario, one varied parameter, and no connecting/interpolating line."""
    completed = frame.loc[frame.status == "completed"].sort_values("parameter_value")
    fig, ax = plt.subplots(figsize=(10, 6), layout="constrained")
    ax.scatter(completed.parameter_value, completed.final_x, s=28, color="tab:blue")
    ax.set_xlabel(parameter_name)
    ax.set_ylabel(f"Mitigation share x at t = {simulation_time:g} years\n"
                  f"(calendar year {TIME_ZERO_YEAR + simulation_time:g})")
    ax.yaxis.set_major_formatter(PercentFormatter(xmax=1))
    ax.set_ylim(-0.025, 1.025)
    ax.grid(alpha=0.25)
    ax.set_axisbelow(True)
    ax.set_title(textwrap.fill(scenario, width=70) + "\nFinite-time endpoint diagram")
    failed = frame.status.isin(["failed", "timed_out"]).sum()
    pending = (frame.status == "pending").sum()
    fig.supxlabel(f"Completed: {len(completed)}/{len(frame)}; "
                  f"failed/timed out: {failed}; unfinished: {pending}\n"
                  "Other parameters and seed fixed; independent initialisation", fontsize=9)
    return fig


def run_analysis(parameter_name, parameter_values, scenarios=None,
                 output_root=DEFAULT_OUTPUT_ROOT, config=None):
    config = SweepConfig() if config is None else config
    values = parameter_grid(values=parameter_values)
    tasks, bases = build_tasks(["baseline"] if scenarios is None else scenarios,
                              parameter_name, values, config)
    root = Path(output_root) / datetime.now().strftime("%Y-%m-%d_%H-%M-%S_%f")
    root.mkdir(parents=True, exist_ok=False)
    sources = [Path(__file__), PROJECT_ROOT / "model/model_equations.py",
               PROJECT_ROOT / "model/agent.py", PROJECT_ROOT / "model/solvers.py",
               PROJECT_ROOT / "config/scenarios.json", PROJECT_ROOT / "data/global.1751_2017.csv"]
    metadata = dict(
        created_at=datetime.now().astimezone().isoformat(), parameter_name=parameter_name,
        parameter_values=values, parameters_varied_per_plot=1, scenarios=bases,
        simulation=asdict(config), time_zero_year=TIME_ZERO_YEAR,
        end_time=config.simulation_time, end_year=TIME_ZERO_YEAR + config.simulation_time,
        definition="One finite-time endpoint per independently initialized parameter value; "
                   "other inputs and seed fixed; no continuation, multistability or "
                   "asymptotic-branch inference.",
        source_sha256={str(path.relative_to(PROJECT_ROOT)): hashlib.sha256(path.read_bytes()).hexdigest()
                       for path in sources},
    )
    (root / "metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    rows = [dict(run_index=i, scenario=task["scenario"], parameter_name=parameter_name,
                 parameter_value=task["parameter_value"], final_x=np.nan,
                 end_time=np.nan, end_year=np.nan, status="pending", error="")
            for i, task in enumerate(tasks)]

    def checkpoint():
        temporary = root / "results.csv.tmp"
        pd.DataFrame(rows).to_csv(temporary, sep=";", index=False)
        temporary.replace(root / "results.csv")

    checkpoint()
    print(f"One-parameter sweep: {parameter_name}, {len(tasks)} runs -> {root}", flush=True)
    try:
        for completed, (index, outcome) in enumerate(
                bounded_map(run_endpoint, tasks, workers=config.workers,
                            timeout_seconds=60 * config.sample_timeout_minutes), start=1):
            rows[index].update(status=outcome["status"],
                               elapsed_seconds=outcome.get("elapsed_seconds"),
                               error=outcome.get("error_message", ""))
            if outcome["status"] == "completed":
                rows[index].update(outcome["result"])
            else:
                with (root / "errors.jsonl").open("a", encoding="utf-8") as handle:
                    handle.write(json.dumps({"run_index": index, **outcome}) + "\n")
            checkpoint()
            print(f"[{completed}/{len(tasks)}] {tasks[index]['scenario']}: "
                  f"{parameter_name}={tasks[index]['parameter_value']:g} "
                  f"{outcome['status']}", flush=True)
    finally:
        checkpoint()
        frame = pd.DataFrame(rows)
        for number, scenario in enumerate(bases, start=1):
            folder = root / f"scenario_{number:02d}"
            folder.mkdir(exist_ok=True)
            subset = frame.loc[frame.scenario == scenario]
            subset.to_csv(folder / "results.csv", sep=";", index=False)
            fig = endpoint_plot(subset, scenario, parameter_name, config.simulation_time)
            try:
                for extension in ("png", "svg"):
                    fig.savefig(folder / f"final_x_vs_{parameter_name}.{extension}", dpi=200)
            finally:
                plt.close(fig)
    print(f"Saved endpoint diagrams: {root}", flush=True)
    return root


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scenarios", nargs="+", default=["baseline"],
                        help="Exact scenario names; each gets a separate plot (default: baseline).")
    parser.add_argument("--parameter-name", default="beta",
                        help="The single parameter varied per plot (default: beta).")
    grid = parser.add_mutually_exclusive_group(required=True)
    grid.add_argument("--parameter-values", nargs="+", type=float,
                      help="Explicit values, e.g. 0 0.5 1 2 3 4 5.")
    grid.add_argument("--parameter-range", nargs=3, type=float, metavar=("MIN", "MAX", "COUNT"),
                      help="Inclusive evenly spaced grid; COUNT must be an integer >= 2.")
    parser.add_argument("--simulation-time", type=float, default=600)
    parser.add_argument("--workers", type=int, default=None,
                        help="Worker processes; default: CPU count minus one.")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--n-agents", type=int, default=1000)
    parser.add_argument("--coupling-interval", type=float, default=0.1)
    parser.add_argument("--output-points-per-year", type=int, default=24)
    parser.add_argument("--solver", choices=["BDF", "LSODA", "RK4"], default="BDF")
    parser.add_argument("--dt", type=float, help="Required integration step in years for RK4.")
    parser.add_argument("--constant-temperature-costs", action="store_true")
    parser.add_argument("--simulate-only-x", action="store_true",
                        help="Freeze carbon stocks; the model's temperature equation still evolves.")
    parser.add_argument("--sample-timeout-minutes", type=float, default=20)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    return parser.parse_args(argv)


def main():
    args = parse_args()
    values = parameter_grid(args.parameter_values, args.parameter_range)
    settings = {name: getattr(args, name) for name in SweepConfig.__dataclass_fields__}
    if settings["workers"] is None:
        settings["workers"] = max(1, (os.cpu_count() or 1) - 1)
    run_analysis(args.parameter_name, values, args.scenarios, args.output_root,
                 SweepConfig(**settings))


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        raise SystemExit(130)
