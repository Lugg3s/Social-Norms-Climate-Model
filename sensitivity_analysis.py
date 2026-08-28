from __future__ import annotations

import argparse
import json
import os
import signal
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from SALib.analyze import sobol
from SALib.sample import sobol as sobol_sample

from model_equations import load_scenarios, simulate
from simulation_metrics import compute_run_metrics


DEFAULT_SIMULATION_TIME = 1500
DEFAULT_OUTPUT_ROOT = Path("sensitivity_results")
DEFAULT_BASE_SAMPLE_SIZE = 256
DEFAULT_OUTPUT_POINTS_PER_YEAR = 10
ELIMINATION_CENSOR_OFFSET = 10_000.0
OSCILLATION_WINDOW_YEARS = 500.0

COMMON_PARAMETER_BOUNDS: dict[str, tuple[float, float]] = {
    "social_norm_factor": (0.0, 10.0),
    "temperature_factor": (0.0, 10.0),
}

# Parameter ranges are intentionally broad enough to contain all values currently
# documented in interesting_parameter_sets.csv. Time-scale lower bounds follow the
# sensitivity-analysis convention discussed for this project.
NORM_SPECIFIC_PARAMETER_BOUNDS: dict[str, dict[str, tuple[float, float]]] = {
    "baseline": {
        "delta": (0.0, 100.0),
    },
    "Dynamic social norm": {
        "tau_ref": (0.1, 50.0),
        "tau_STref": (0.1, 10.0),
        "tau_xp": (0.1, 10.0),
    },
    "Belief-based / intention motivation": {
        "N": (0.0, 3.0),
    },
    "Observation based / approval (punish only one behaviour)": {
        "alpha": (0.0, 3.0),
    },
    "Static injunctive": {
        "c_inj": (0.0, 100.0),
        "x_target": (0.0, 1.0),
    },
    "Descriptive, injunctive, dynamic": {
        "delta": (0.0, 100.0),
        "c_inj": (0.0, 100.0),
        "x_target": (0.0, 1.0),
        "c_dyn": (0.0, 100.0),
        "tau_ref": (0.1, 50.0),
        "tau_STref": (0.1, 10.0),
        "tau_xp": (0.1, 10.0),
    },
    "Descriptive, injunctive, dynamic2": {
        "delta": (0.0, 100.0),
        "c_inj": (0.0, 100.0),
        "x_target": (0.0, 1.0),
        "c_dyn": (0.0, 100.0),
        "tau": (0.0, 100.0),
        "theta": (0.0, 10.0),
    },
    "Injunctive, dynamic2": {
        "c_inj": (0.0, 100.0),
        "x_target": (0.0, 1.0),
        "c_dyn": (0.0, 100.0),
        "tau": (0.0, 100.0),
        "theta": (0.0, 10.0),
    },
    "dynamic social norm2": {
        "c_dyn": (0.0, 100.0),
        "tau": (0.0, 100.0),
        "theta": (0.0, 10.0),
    },
}

SENSITIVITY_OUTPUTS = [
    "final_x",
    "final_temperature",
    "cumulative_emissions",
    "time_to_elimination_censored",
    "oscillation_amplitude",
    "oscillations_per_500_years",
    "damping_index",
]

OUTPUT_GROUPS = {
    "mitigation": ["final_x", "time_to_elimination_censored"],
    "climate": ["final_temperature", "cumulative_emissions"],
    "dynamics": [
        "oscillation_amplitude",
        "oscillations_per_500_years",
        "damping_index",
    ],
}


@dataclass(frozen=True)
class SensitivityConfig:
    simulation_time: int = DEFAULT_SIMULATION_TIME
    base_sample_size: int = DEFAULT_BASE_SAMPLE_SIZE
    workers: int = 1
    seed: int = 42
    coupling_interval: float = 1.0
    output_points_per_year: int = DEFAULT_OUTPUT_POINTS_PER_YEAR
    score_mode: str = "simple_mean"


def build_problem(scenario_name: str) -> dict[str, Any]:
    if scenario_name not in NORM_SPECIFIC_PARAMETER_BOUNDS:
        raise KeyError(f"No sensitivity parameter definition for scenario: {scenario_name}")

    parameter_bounds = {
        **COMMON_PARAMETER_BOUNDS,
        **NORM_SPECIFIC_PARAMETER_BOUNDS[scenario_name],
    }
    return {
        "num_vars": len(parameter_bounds),
        "names": list(parameter_bounds.keys()),
        "bounds": [list(bounds) for bounds in parameter_bounds.values()],
    }


def _oscillations_per_window(metrics: dict[str, Any], simulation_time: float) -> float:
    if simulation_time <= 0:
        return 0.0
    return float(metrics["n_oscillations"]) * OSCILLATION_WINDOW_YEARS / float(simulation_time)


def _prepare_sensitivity_outputs(metrics: dict[str, Any], simulation_time: float) -> dict[str, float]:
    time_to_elimination = float(metrics["time_to_elimination"])
    if not np.isfinite(time_to_elimination):
        time_to_elimination = float(simulation_time) + ELIMINATION_CENSOR_OFFSET

    oscillation_amplitude = float(metrics["oscillation_amplitude"])
    if not np.isfinite(oscillation_amplitude):
        oscillation_amplitude = 0.0

    damping_index = float(metrics["damping_index"])
    if not np.isfinite(damping_index):
        damping_index = 0.0

    return {
        "final_x": float(metrics["final_x"]),
        "final_temperature": float(metrics["final_temperature"]),
        "cumulative_emissions": float(metrics["cumulative_emissions"]),
        "time_to_elimination_censored": time_to_elimination,
        "oscillation_amplitude": oscillation_amplitude,
        "oscillations_per_500_years": _oscillations_per_window(metrics, simulation_time),
        "damping_index": damping_index,
    }


def _run_sample(job: tuple[Any, ...]) -> dict[str, float]:
    scenario_params, parameter_names, sample, config = job
    params = dict(scenario_params)
    params.update(dict(zip(parameter_names, sample)))
    result = simulate(
        extension=params,
        simulation_time=config.simulation_time,
        seed=config.seed,
        coupling_interval=config.coupling_interval,
        output_points_per_year=config.output_points_per_year,
        verbose=False,
    )
    metrics = compute_run_metrics(result, params)
    sensitivity_outputs = _prepare_sensitivity_outputs(metrics, config.simulation_time)
    return {**metrics, **sensitivity_outputs}


def _resolve_worker_count(workers: int | None) -> int:
    if workers is not None:
        if workers < 1:
            raise ValueError("workers must be at least 1")
        return workers
    return max(1, (os.cpu_count() or 1) - 1)


def _ignore_sigint_in_worker() -> None:
    """Let the main process handle Ctrl+C; workers are terminated explicitly."""
    signal.signal(signal.SIGINT, signal.SIG_IGN)


def _terminate_executor_workers(executor: ProcessPoolExecutor) -> None:
    """Immediately terminate running worker processes during an interrupted sensitivity run."""
    processes = list(getattr(executor, "_processes", {}).values())
    for process in processes:
        if process.is_alive():
            process.terminate()
    for process in processes:
        process.join(timeout=1.0)



def run_samples(
    scenario_params: dict[str, Any],
    problem: dict[str, Any],
    samples: np.ndarray,
    config: SensitivityConfig,
) -> pd.DataFrame:
    jobs = [
        (scenario_params, problem["names"], sample, config)
        for sample in samples
    ]

    if config.workers == 1:
        records = [_run_sample(job) for job in jobs]
        return pd.DataFrame(records)

    records: list[dict[str, Any] | None] = [None] * len(jobs)
    executor = ProcessPoolExecutor(
        max_workers=config.workers,
        initializer=_ignore_sigint_in_worker,
    )
    future_to_index = {}
    try:
        future_to_index = {
            executor.submit(_run_sample, job): index
            for index, job in enumerate(jobs)
        }
        for completed_runs, future in enumerate(as_completed(future_to_index), start=1):
            index = future_to_index[future]
            records[index] = future.result()
            if completed_runs % max(1, len(jobs) // 100) == 0 or completed_runs == len(jobs):
                print(f"  [{completed_runs}/{len(jobs)}] sensitivity simulations completed")
    except KeyboardInterrupt:
        print("\nSensitivity run interrupted. Terminating worker processes...")
        _terminate_executor_workers(executor)
        executor.shutdown(wait=True, cancel_futures=False)
        raise
    else:
        executor.shutdown(wait=True)

    if any(record is None for record in records):
        raise RuntimeError("At least one sensitivity simulation did not return a result.")
    return pd.DataFrame(records)


def analyze_outputs(
    problem: dict[str, Any],
    outputs: pd.DataFrame,
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for output_name in SENSITIVITY_OUTPUTS:
        values = outputs[output_name].to_numpy(dtype=float)
        if not np.all(np.isfinite(values)):
            raise ValueError(f"Non-finite values in Sobol output: {output_name}")

        if np.nanmax(values) - np.nanmin(values) <= 1e-12:
            for parameter_name in problem["names"]:
                rows.append(
                    {
                        "output": output_name,
                        "parameter": parameter_name,
                        "S1": 0.0,
                        "S1_conf": 0.0,
                        "ST": 0.0,
                        "ST_conf": 0.0,
                    }
                )
            continue

        result = sobol.analyze(
            problem,
            values,
            calc_second_order=False,
            print_to_console=False,
        )
        for index, parameter_name in enumerate(problem["names"]):
            rows.append(
                {
                    "output": output_name,
                    "parameter": parameter_name,
                    "S1": float(result["S1"][index]),
                    "S1_conf": float(result["S1_conf"][index]),
                    "ST": float(result["ST"][index]),
                    "ST_conf": float(result["ST_conf"][index]),
                }
            )
    return pd.DataFrame(rows)


def build_parameter_ranking(sobol_results: pd.DataFrame, score_mode: str) -> pd.DataFrame:
    st_table = sobol_results.pivot(index="parameter", columns="output", values="ST")

    if score_mode == "simple_mean":
        overall_score = st_table[SENSITIVITY_OUTPUTS].mean(axis=1)
    elif score_mode == "grouped_mean":
        group_scores = pd.DataFrame(index=st_table.index)
        for group_name, output_names in OUTPUT_GROUPS.items():
            group_scores[group_name] = st_table[output_names].mean(axis=1)
        overall_score = group_scores.mean(axis=1)
    else:
        raise ValueError("score_mode must be 'simple_mean' or 'grouped_mean'")

    ranking = st_table.copy()
    ranking["overall_score"] = overall_score
    ranking["max_ST"] = st_table[SENSITIVITY_OUTPUTS].max(axis=1)
    ranking["strongest_output"] = st_table[SENSITIVITY_OUTPUTS].idxmax(axis=1)
    ranking = ranking.sort_values("overall_score", ascending=False, kind="stable")
    ranking.insert(0, "rank", np.arange(1, len(ranking) + 1))
    return ranking.reset_index()


def run_sensitivity_analysis(
    scenario_name: str,
    output_root: Path,
    config: SensitivityConfig,
) -> Path:
    scenarios = load_scenarios()
    if scenario_name not in scenarios:
        raise KeyError(f"Unknown scenario: {scenario_name}")
    if scenarios[scenario_name].get("ABM", False):
        raise ValueError("The agent-based scenario is excluded from this Sobol analysis for now.")

    problem = build_problem(scenario_name)
    samples = sobol_sample.sample(
        problem,
        config.base_sample_size,
        calc_second_order=False,
        seed=config.seed,
    )

    scenario_dir = output_root / scenario_name.replace("/", "_").replace(" ", "_")
    scenario_dir.mkdir(parents=True, exist_ok=True)

    sample_frame = pd.DataFrame(samples, columns=problem["names"])
    sample_frame.to_csv(scenario_dir / "samples.csv", index=False)

    outputs = run_samples(scenarios[scenario_name], problem, samples, config)
    simulation_outputs = pd.concat(
        [sample_frame.reset_index(drop=True), outputs.reset_index(drop=True)],
        axis=1,
    )
    simulation_outputs.to_csv(scenario_dir / "simulation_outputs.csv", index=False)

    sobol_results = analyze_outputs(problem, outputs)
    sobol_results.insert(0, "scenario", scenario_name)
    sobol_results.to_csv(scenario_dir / "sobol_indices.csv", index=False)

    ranking = build_parameter_ranking(sobol_results, config.score_mode)
    ranking.insert(0, "scenario", scenario_name)
    ranking.to_csv(scenario_dir / "parameter_ranking.csv", index=False)

    metadata = {
        "scenario": scenario_name,
        "problem": problem,
        "simulation_time": config.simulation_time,
        "base_sample_size": config.base_sample_size,
        "number_of_model_runs": int(len(samples)),
        "workers": config.workers,
        "seed": config.seed,
        "coupling_interval": config.coupling_interval,
        "output_points_per_year": config.output_points_per_year,
        "score_mode": config.score_mode,
        "elimination_censor_offset": ELIMINATION_CENSOR_OFFSET,
        "oscillation_window_years": OSCILLATION_WINDOW_YEARS,
        "outputs_for_ranking": SENSITIVITY_OUTPUTS,
        "raw_metric_columns": [
            column for column in outputs.columns if column not in SENSITIVITY_OUTPUTS
        ],
        "output_groups": OUTPUT_GROUPS,
        "top_2_parameters": ranking.head(2)["parameter"].tolist(),
    }
    with (scenario_dir / "metadata.json").open("w", encoding="utf-8") as handle:
        json.dump(metadata, handle, indent=2, ensure_ascii=False)

    return scenario_dir


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Sobol sensitivity analysis for social-norm scenarios.")
    parser.add_argument(
        "--scenarios",
        nargs="+",
        default=list(NORM_SPECIFIC_PARAMETER_BOUNDS),
        help="Scenario names to analyze. Default: all configured non-agent scenarios.",
    )
    parser.add_argument("--simulation-time", type=int, default=DEFAULT_SIMULATION_TIME)
    parser.add_argument("--base-sample-size", type=int, default=DEFAULT_BASE_SAMPLE_SIZE)
    parser.add_argument(
        "--workers",
        type=int,
        default=None,
        help="Parallel worker processes. Default: CPU count minus one; use 1 for serial execution.",
    )
    parser.add_argument(
        "--output-points-per-year",
        type=int,
        default=DEFAULT_OUTPUT_POINTS_PER_YEAR,
        help="Stored solver evaluation points per simulated year.",
    )
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument(
        "--score-mode",
        choices=["simple_mean", "grouped_mean"],
        default="simple_mean",
        help="Rule used to combine output-specific total-order Sobol indices.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    worker_count = _resolve_worker_count(args.workers)
    if args.output_points_per_year < 1:
        raise ValueError("output-points-per-year must be at least 1")

    config = SensitivityConfig(
        simulation_time=args.simulation_time,
        base_sample_size=args.base_sample_size,
        workers=worker_count,
        seed=args.seed,
        output_points_per_year=args.output_points_per_year,
        score_mode=args.score_mode,
    )

    overall_top_rows: list[pd.DataFrame] = []
    for scenario_name in args.scenarios:
        scenario_dir = run_sensitivity_analysis(scenario_name, args.output_root, config)
        ranking = pd.read_csv(scenario_dir / "parameter_ranking.csv")
        overall_top_rows.append(ranking.head(2))
        print(f"Completed sensitivity analysis: {scenario_name} -> {scenario_dir}")

    if overall_top_rows:
        args.output_root.mkdir(parents=True, exist_ok=True)
        pd.concat(overall_top_rows, ignore_index=True).to_csv(
            args.output_root / "overall_top_parameters.csv",
            index=False,
        )


if __name__ == "__main__":
    main()
