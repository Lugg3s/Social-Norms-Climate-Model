from __future__ import annotations

import argparse
import json
import os
import sys
import traceback
from contextlib import contextmanager, redirect_stdout, redirect_stderr
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from time import monotonic
from typing import Any

import numpy as np
import pandas as pd
from SALib.analyze import sobol
from SALib.sample import sobol as sobol_sample

from model_equations import load_scenarios, resolve_parameters, simulate
from simulation_metrics import compute_run_metrics
from bounded_process_map import bounded_map


DEFAULT_SIMULATION_TIME = 1200
DEFAULT_OUTPUT_ROOT = Path("plots") / "sensitivity_results"
DEFAULT_TIME_FORMAT = "%Y-%m-%d_%H-%M-%S"
DEFAULT_BASE_SAMPLE_SIZE = 256
DEFAULT_OUTPUT_POINTS_PER_YEAR = 24
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
    sample_timeout_minutes: float = 20.0

    def __post_init__(self):
        if not np.isfinite(self.sample_timeout_minutes) or self.sample_timeout_minutes <= 0:
            raise ValueError("sample-timeout-minutes must be finite and positive")


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


def _run_tracked_sample(
    job: tuple[Any, ...],
    sample_index: int,
    diagnostics_dir: Path | None,
    phase: str = "sample",
    boundary_parameter: str | None = None,
) -> dict[str, float]:
    """Persist actual worker start/finish events in one file per simulation.

    A started record with no terminal record means that completion was not
    recorded: the job may still be running or its process may have stopped.
    The parent process enforces deadlines and records hard timeouts separately.
    """
    if diagnostics_dir is None:
        return _run_sample(job)
    scenario_params, parameter_names, sample, config = job
    overrides = {name: float(value) for name, value in zip(parameter_names, sample)}
    parameters = {**scenario_params, **overrides}
    diagnostics_dir.mkdir(parents=True, exist_ok=True)
    log_path = diagnostics_dir / f"{phase}_{sample_index:06d}.jsonl"
    started_at = datetime.now().astimezone().isoformat(timespec="milliseconds")
    started_clock = monotonic()
    identity = dict(sample_index=sample_index if phase == "sample" else None,
                    boundary_index=sample_index if phase == "boundary" else None,
                    phase=phase, boundary_parameter=boundary_parameter,
                    worker_pid=os.getpid(), started_at=started_at)
    label = f"sample_index={sample_index}" if phase == "sample" else f"boundary {boundary_parameter}=0"

    def write_event(event, mode="a"):
        # Closing the file flushes each event before computation/return.
        # Only this worker writes this file; no cross-process CSV append race.
        with log_path.open(mode, encoding="utf-8") as handle:
            handle.write(json.dumps({**identity, **event}, ensure_ascii=False) + "\n")

    write_event(dict(status="started", parameters=parameters,
                     sampled_parameters=overrides, config=vars(config)), mode="w")
    _log_sample_detail(f"[{datetime.now():%H:%M:%S}] Started {label} | PID {os.getpid()}")
    try:
        result = _run_sample(job)
    except BaseException as error:
        status = "interrupted" if isinstance(error, (KeyboardInterrupt, SystemExit)) else "failed"
        elapsed = monotonic() - started_clock
        write_event(dict(status=status,
                         finished_at=datetime.now().astimezone().isoformat(timespec="milliseconds"),
                         elapsed_seconds=elapsed, error_type=type(error).__name__,
                         error_message=str(error),
                         traceback="".join(traceback.format_exception(type(error), error, error.__traceback__))))
        print(f"[{datetime.now():%H:%M:%S}] {status.capitalize()} {label} | {elapsed:.1f}s", flush=True)
        raise
    elapsed = monotonic() - started_clock
    write_event(dict(status="completed",
                     finished_at=datetime.now().astimezone().isoformat(timespec="milliseconds"),
                     elapsed_seconds=elapsed))
    _log_sample_detail(f"[{datetime.now():%H:%M:%S}] Completed {label} | {elapsed:.1f}s")
    return result


def _write_failed_sample(
    failure_path: Path | None,
    sample_index: int,
    error: BaseException,
    parameters: dict[str, Any] | None = None,
) -> None:
    if failure_path is None:
        return
    failure_path.parent.mkdir(parents=True, exist_ok=True)
    row = {
        "sample_index": sample_index,
        "error_type": type(error).__name__,
        "error_message": str(error),
        "traceback": "".join(traceback.format_exception(type(error), error, error.__traceback__)),
        "parameters": json.dumps(parameters, ensure_ascii=False),
    }
    pd.DataFrame([row]).to_csv(failure_path, index=False, sep=";", mode="a",
                              header=not failure_path.exists())


def _resolve_worker_count(workers: int | None) -> int:
    if workers is not None:
        if workers < 1:
            raise ValueError("workers must be at least 1")
        return workers
    return max(1, (os.cpu_count() or 1) - 1)


def _log_sample_progress(completed: int, total: int, started_at: float) -> None:
    """Print progress, elapsed time, and an estimated remaining duration."""
    if total <= 0:
        return
    log_interval = max(1, total // 20)
    if completed != 1 and completed % log_interval != 0 and completed != total:
        return

    elapsed = monotonic() - started_at
    rate = completed / elapsed if elapsed > 0 else 0.0
    remaining = (total - completed) / rate if rate > 0 else float("nan")
    percentage = 100.0 * completed / total
    eta_text = f"{remaining / 60:.1f} min remaining" if np.isfinite(remaining) else "ETA unavailable"
    print(
        f"  Simulations: {completed}/{total} ({percentage:.1f}%) | "
        f"elapsed {elapsed / 60:.1f} min | {eta_text}",
        flush=True,
    )



def _execute_sample_task(task):
    return _run_tracked_sample(*task)


def _record_timeout(task, outcome):
    job, index, diagnostics_dir, phase, boundary_parameter = task
    base_params, names, sample, config = job
    overrides = {name: float(value) for name, value in zip(names, sample)}
    record = {
        "status": "timed_out", "phase": phase,
        "sample_index": index if phase == "sample" else None,
        "boundary_index": index if phase == "boundary" else None,
        "boundary_parameter": boundary_parameter,
        "parameters": {**base_params, **overrides}, "sampled_parameters": overrides,
        "config": vars(config), **outcome,
        "finished_at": datetime.now().astimezone().isoformat(timespec="milliseconds"),
        "timeout_minutes": config.sample_timeout_minutes,
        "message": "Simulation exceeded its wall-clock limit. Its worker was terminated; continuing with other combinations.",
    }
    if diagnostics_dir is not None:
        diagnostics_dir.mkdir(parents=True, exist_ok=True)
        # The worker has been stopped and joined before the parent writes here.
        with (diagnostics_dir / f"{phase}_{index:06d}.jsonl").open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
        with (diagnostics_dir / "timeouts.jsonl").open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
    print(f"[{datetime.now():%H:%M:%S}] TIMED OUT {phase} index={index} "
          f"after {outcome['elapsed_seconds'] / 60:.1f} min | parameters={overrides}", flush=True)
    return record


def run_samples(
    scenario_params: dict[str, Any],
    problem: dict[str, Any],
    samples: np.ndarray,
    config: SensitivityConfig,
    failure_path: Path | None = None,
    diagnostics_dir: Path | None = None,
) -> pd.DataFrame:
    tasks = [((scenario_params, problem["names"], sample, config), index,
              diagnostics_dir, "sample", None) for index, sample in enumerate(samples)]
    records = [None] * len(tasks)
    started_at = monotonic()
    results = bounded_map(_execute_sample_task, tasks, config.workers,
                          config.sample_timeout_minutes * 60)
    try:
        for completed, (index, outcome) in enumerate(results, start=1):
            if outcome["status"] == "completed":
                records[index] = {**outcome["result"], "status": "completed"}
            elif outcome["status"] == "timed_out":
                _record_timeout(tasks[index], outcome)
                records[index] = {**{name: np.nan for name in SENSITIVITY_OUTPUTS},
                                  "status": "timed_out"}
            else:
                error = RuntimeError(f"Sample {index}: {outcome['error_type']}: "
                                     f"{outcome['error_message']}\n{outcome['traceback']}")
                parameters = {**scenario_params, **dict(zip(problem["names"],
                                                           map(float, samples[index])))}
                _write_failed_sample(failure_path, index, error, parameters)
                # Recover only from the model's explicit integration failure.
                # Programming errors and interruptions must remain visible/fatal.
                if (outcome["error_type"] != "RuntimeError" or
                        not outcome["error_message"].startswith("ODE integration failed:")):
                    raise error
                records[index] = {**{name: np.nan for name in SENSITIVITY_OUTPUTS},
                                  "status": "failed", "error_message": outcome["error_message"]}
                print(f"[{datetime.now():%H:%M:%S}] Skipping sample_index={index}: "
                      f"{outcome['error_message']} | continuing with remaining samples", flush=True)
            _log_sample_progress(completed, len(tasks), started_at)
    finally:
        results.close()
    return pd.DataFrame(records)


def run_zero_boundary_cases(
    base_params: dict[str, Any],
    problem: dict[str, Any],
    config: SensitivityConfig,
    diagnostics_dir: Path | None = None,
) -> pd.DataFrame:
    """Evaluate exact zero boundaries serially, each with the same hard timeout."""
    names = [name for name, bounds in zip(problem["names"], problem["bounds"])
             if float(bounds[0]) == 0.]
    tasks = [((base_params, [name], np.array([0.]), config), index,
              diagnostics_dir, "boundary", name) for index, name in enumerate(names)]
    records = []
    results = bounded_map(_execute_sample_task, tasks, 1, config.sample_timeout_minutes * 60)
    try:
        for index, outcome in results:
            row = {"boundary_parameter": names[index], "boundary_value": 0.}
            if outcome["status"] == "completed":
                row.update(status="ok", **outcome["result"])
            elif outcome["status"] == "timed_out":
                _record_timeout(tasks[index], outcome)
                row.update(status="timed_out", error_message="Wall-clock limit exceeded")
            else:
                row.update(status="failed", error_type=outcome["error_type"],
                           error_message=outcome["error_message"])
            records.append(row)
    finally:
        results.close()
    return pd.DataFrame(records)


def complete_sobol_blocks(problem, outputs):
    """Retain complete A/AB/B blocks; never shift rows or impute missing values.

    Conditional deletion can bias the original Sobol estimand. Results after
    exclusions are exploratory and must be labelled provisional.
    """
    block_size = problem["num_vars"] + 2  # calc_second_order=False, no groups
    if len(outputs) % block_size:
        raise ValueError("Output row count does not match complete Sobol block layout")
    valid = np.isfinite(outputs[SENSITIVITY_OUTPUTS].to_numpy(dtype=float)).all(axis=1)
    if "status" in outputs:
        valid &= outputs["status"].eq("completed").to_numpy()
    block_valid = valid.reshape(-1, block_size).all(axis=1)
    keep = np.repeat(block_valid, block_size)
    retained = int(block_valid.sum())
    excluded = np.flatnonzero(~block_valid).tolist()
    info = {
        "status": ("unavailable" if retained < 2 else "provisional" if excluded else "complete"),
        "block_size": block_size, "requested_base_samples": len(block_valid),
        "retained_base_samples": retained, "excluded_block_indices": excluded,
        "missing_sample_indices": np.flatnonzero(~valid).tolist(),
        "excluded_sample_indices": np.flatnonzero(~keep).tolist(),
        "included_sample_indices": np.flatnonzero(keep).tolist(),
        "warning": ("Too few complete Sobol blocks to calculate indices." if retained < 2 else
                    "PROVISIONAL: incomplete blocks were excluded. Parameter-dependent timeouts or numerical failures can bias indices; confidence intervals do not account for this selection bias. Rerun missing combinations for full-design results." if excluded else
                    "Complete requested design; statistical convergence still depends on sample size."),
    }
    return outputs.loc[keep].reset_index(drop=True), info


def analyze_outputs(
    problem: dict[str, Any],
    outputs: pd.DataFrame,
    seed: int,
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
            seed=seed,
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
    group_scores = pd.DataFrame(index=st_table.index)
    for group_name, output_names in OUTPUT_GROUPS.items():
        group_scores[group_name] = st_table[output_names].mean(axis=1)

    if score_mode == "simple_mean":
        overall_score = st_table[SENSITIVITY_OUTPUTS].mean(axis=1)
    elif score_mode == "grouped_mean":
        overall_score = group_scores.mean(axis=1)
    else:
        raise ValueError("score_mode must be 'simple_mean' or 'grouped_mean'")

    ranking = pd.concat([st_table, group_scores], axis=1)
    ranking["overall_score"] = overall_score
    ranking["max_ST"] = st_table[SENSITIVITY_OUTPUTS].max(axis=1)
    ranking["strongest_output"] = st_table[SENSITIVITY_OUTPUTS].idxmax(axis=1)
    ranking = ranking.sort_values("overall_score", ascending=False, kind="stable")
    ranking.insert(0, "rank", np.arange(1, len(ranking) + 1))
    return ranking.reset_index()


def run_sensitivity_analysis(
    scenario_name: str,
    run_root: Path,
    config: SensitivityConfig,
    overwrite_existing: bool = True,
) -> Path:
    scenarios = load_scenarios()
    if scenario_name not in scenarios:
        raise KeyError(f"Unknown scenario: {scenario_name}")
    if scenarios[scenario_name].get("ABM", False):
        raise ValueError("The agent-based scenario is excluded from this Sobol analysis for now.")

    problem = build_problem(scenario_name)
    scenario_dir = run_root / scenario_name.replace("/", "_").replace(" ", "_")
    scenario_dir.mkdir(parents=True, exist_ok=True)

    if not overwrite_existing and any(scenario_dir.iterdir()):
        raise FileExistsError(
            f"Scenario results already exist and will not be overwritten: {scenario_dir}"
        )

    base_params = resolve_parameters(scenario_name)
    samples = sobol_sample.sample(
        problem,
        config.base_sample_size,
        calc_second_order=False,
        seed=config.seed,
    )
    print(
        f"  Sobol sample generated: {len(samples)} model runs for "
        f"{problem['num_vars']} parameters",
        flush=True,
    )

    # Remove files from an incomplete prior attempt if this run directory is reused.
    for filename in (
        "samples.csv",
        "simulation_outputs.csv",
        "sobol_indices.csv",
        "parameter_ranking.csv",
        "metadata.json",
        "failed_sample.csv",
        "zero_boundary_cases.csv",
        "parameters.json",
        "diagnostics.json",
        "analysis_status.json",
        "sample_inclusion.csv",
    ):
        path = scenario_dir / filename
        if path.exists():
            path.unlink()

    with (scenario_dir / "parameters.json").open("w", encoding="utf-8") as handle:
        json.dump(base_params, handle, indent=2, ensure_ascii=False)

    sample_frame = pd.DataFrame(samples, columns=problem["names"])
    sample_frame.insert(0, "sample_index", np.arange(len(sample_frame), dtype=int))
    sample_frame.to_csv(scenario_dir / "samples.csv", index=False, sep=";")

    # Keep attempts separate so unfinished records from a reused run directory
    # cannot be mistaken for samples running in the current attempt.
    diagnostics_dir = scenario_dir / (
        "sample_diagnostics_" + datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    )
    diagnostics_dir.mkdir(parents=True, exist_ok=False)
    diagnostics_info = {
        "directory": diagnostics_dir.name,
        "format": "One JSONL file per sample or boundary check; start and terminal events.",
        "sample_index": "Zero-based index matching samples.csv and simulation_outputs.csv.",
        "unfinished_record": "A start without a terminal event indicates running or interrupted/crashed work.",
        "timeouts_file": "timeouts.jsonl (created when a timeout occurs; includes full parameters)",
        "sample_timeout_minutes": config.sample_timeout_minutes,
    }
    (scenario_dir / "diagnostics.json").write_text(
        json.dumps(diagnostics_info, indent=2), encoding="utf-8"
    )
    print(f"  Per-simulation diagnostics: {diagnostics_dir}", flush=True)

    boundary_cases = run_zero_boundary_cases(base_params, problem, config, diagnostics_dir)
    print(f"  Zero-boundary checks completed: {len(boundary_cases)}", flush=True)
    if not boundary_cases.empty:
        boundary_cases.to_csv(scenario_dir / "zero_boundary_cases.csv", index=False, sep=";")

    outputs = run_samples(
        base_params,
        problem,
        samples,
        config,
        failure_path=scenario_dir / "failed_sample.csv",
        diagnostics_dir=diagnostics_dir,
    )
    print("  Calculating Sobol indices and parameter ranking...", flush=True)
    simulation_outputs = outputs.reset_index(drop=True).copy()
    simulation_outputs.insert(
        0,
        "sample_index",
        np.arange(len(simulation_outputs), dtype=int),
    )
    simulation_outputs.to_csv(scenario_dir / "simulation_outputs.csv", index=False, sep=";")

    analysis_outputs, analysis_info = complete_sobol_blocks(problem, outputs)
    print(f"  Analysis status: {analysis_info['status']}. {analysis_info['warning']}", flush=True)
    inclusion = sample_frame.copy()
    inclusion["status"] = outputs["status"].to_numpy()
    inclusion["block_index"] = inclusion["sample_index"] // analysis_info["block_size"]
    inclusion["included_in_complete_blocks"] = inclusion["sample_index"].isin(
        analysis_info["included_sample_indices"]
    )
    inclusion.to_csv(scenario_dir / "sample_inclusion.csv", index=False, sep=";")
    if analysis_info["status"] == "unavailable":
        sobol_results = pd.DataFrame(columns=["output", "parameter", "S1", "S1_conf", "ST", "ST_conf"])
        ranking = pd.DataFrame(columns=["parameter", "rank", "overall_score"])
    else:
        sobol_results = analyze_outputs(problem, analysis_outputs, seed=config.seed)
        ranking = build_parameter_ranking(sobol_results, config.score_mode)
        analysis_info["nonfinite_estimates"] = bool(
            not np.isfinite(sobol_results[["S1", "S1_conf", "ST", "ST_conf"]]).all().all()
        )
        if analysis_info["nonfinite_estimates"]:
            analysis_info["warning"] += " Some estimates or confidence intervals are undefined; increase the sample size."
            print(f"  WARNING: {analysis_info['warning']}", flush=True)
    (scenario_dir / "analysis_status.json").write_text(
        json.dumps(analysis_info, indent=2), encoding="utf-8"
    )
    for frame in (sobol_results, ranking):
        frame["analysis_status"] = analysis_info["status"]
        frame["retained_base_samples"] = analysis_info["retained_base_samples"]
        frame["analysis_warning"] = analysis_info["warning"]
    sobol_results.insert(0, "scenario", scenario_name)
    sobol_results.to_csv(scenario_dir / "sobol_indices.csv", index=False, sep=";")

    ranking.insert(0, "scenario", scenario_name)
    ranking.to_csv(scenario_dir / "parameter_ranking.csv", index=False, sep=";")

    metadata = {
        "scenario": scenario_name,
        "problem": problem,
        "simulation_time": config.simulation_time,
        "base_sample_size": config.base_sample_size,
        "number_of_model_runs": int(len(samples)),
        "number_of_zero_boundary_runs": int(len(boundary_cases)),
        "workers": config.workers,
        "seed": config.seed,
        "coupling_interval": config.coupling_interval,
        "output_points_per_year": config.output_points_per_year,
        "score_mode": config.score_mode,
        "parameters_file": "parameters.json",
        "diagnostics": diagnostics_info,
        "sample_timeout_minutes": config.sample_timeout_minutes,
        "analysis": analysis_info,
        "samples_file": "samples.csv",
        "simulation_outputs_file": "simulation_outputs.csv",
        "parameter_reconstruction_note": (
            "Reconstruct each model input as parameters.json updated with the "
            "sample-specific values from samples.csv for the same sample_index."
        ),
        "elimination_censor_offset": ELIMINATION_CENSOR_OFFSET,
        "oscillation_window_years": OSCILLATION_WINDOW_YEARS,
        "zero_boundary_parameters": (
            boundary_cases["boundary_parameter"].tolist()
            if not boundary_cases.empty
            else []
        ),
        "zero_boundary_cases_note": (
            "Exact zero-boundary cases are diagnostic runs and are not included "
            "in the Sobol indices."
        ),
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
        default=None,
        help=(
            "Scenario names to analyze. If omitted, all Sobol-compatible social-norm "
            "scenarios from scenarios.json are used."
        ),
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
    parser.add_argument("--sample-timeout-minutes", type=float, default=20.0,
                        help="Wall-clock limit per simulation, including boundary checks (default: 20 minutes).")
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument(
        "--append-existing-folder",
        type=Path,
        default=None,
        help="Use this existing run folder below --output-root and append selected scenarios to it.",
    )
    parser.add_argument(
        "--score-mode",
        choices=["simple_mean", "grouped_mean"],
        default="simple_mean",
        help="Rule used to combine output-specific total-order Sobol indices.",
    )
    return parser.parse_args()


def _log_sample_detail(message):
    if hasattr(sys.stdout, "write_log_only"):
        sys.stdout.write_log_only(message + "\n")


class _TeeStream:
    def __init__(self, console, logfile):
        self.console = console
        self.logfile = logfile

    def write(self, text):
        self.console.write(text)
        self.logfile.write(text)
        self.logfile.flush()
        return len(text)

    def flush(self):
        self.console.flush()
        self.logfile.flush()

    def write_log_only(self, text):
        self.logfile.write(text)
        self.logfile.flush()


@contextmanager
def sensitivity_console_log(path):
    """Mirror parent and forwarded worker messages to a continuously flushed log."""
    with path.open("a", encoding="utf-8") as logfile:
        with redirect_stdout(_TeeStream(sys.stdout, logfile)), \
             redirect_stderr(_TeeStream(sys.stderr, logfile)):
            try:
                yield
            except BaseException:
                # The interpreter prints the uncaught error after redirection ends.
                # Persist it here without printing it twice in the terminal.
                traceback.print_exc(file=logfile)
                logfile.flush()
                raise


def _existing_rankings(run_root: Path) -> list[pd.DataFrame]:
    rankings = []
    for ranking_path in run_root.glob("*/parameter_ranking.csv"):
        rankings.append(pd.read_csv(ranking_path, sep=";"))
    return rankings


def _scenario_directory(run_root: Path, scenario_name: str) -> Path:
    return run_root / scenario_name.replace("/", "_").replace(" ", "_")


def _validate_append_scenarios(run_root: Path, scenario_names) -> None:
    for scenario_name in scenario_names:
        scenario_dir = _scenario_directory(run_root, scenario_name)
        if scenario_dir.exists() and any(scenario_dir.iterdir()):
            raise FileExistsError(
                f"Scenario results already exist and will not be overwritten: {scenario_dir}"
            )


def main() -> None:
    args = parse_args()
    available_scenarios = load_scenarios()
    scenario_names = args.scenarios
    if scenario_names is None:
        scenario_names = [
            scenario_name
            for scenario_name in available_scenarios
            if scenario_name in NORM_SPECIFIC_PARAMETER_BOUNDS
        ]

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
        sample_timeout_minutes=args.sample_timeout_minutes,
    )

    if args.append_existing_folder is not None:
        run_root = args.output_root / args.append_existing_folder
        if not run_root.is_dir():
            raise FileNotFoundError(
                f"Requested run folder does not exist: {run_root}"
            )
        _validate_append_scenarios(run_root, scenario_names)
    else:
        timestamp = datetime.now().strftime(DEFAULT_TIME_FORMAT)
        run_root = args.output_root / timestamp
        run_root.mkdir(parents=True, exist_ok=False)

    with sensitivity_console_log(run_root / "sensitivity_analysis.log"):
        _run_scenarios(
            scenario_names,
            run_root,
            config,
            overwrite_existing=args.append_existing_folder is None,
        )


def _run_scenarios(scenario_names, run_root, config, overwrite_existing=True):

    overall_top_rows: list[pd.DataFrame] = [
        ranking.head(2) for ranking in _existing_rankings(run_root)
    ]
    total_scenarios = len(scenario_names)
    print(
        f"Starting sensitivity analysis for {total_scenarios} scenarios with "
        f"{config.workers} worker process(es). Output: {run_root}",
        flush=True,
    )
    overall_started_at = monotonic()
    for scenario_index, scenario_name in enumerate(scenario_names, start=1):
        scenario_started_at = monotonic()
        print(
            f"[{scenario_index}/{total_scenarios}] Starting scenario: {scenario_name}",
            flush=True,
        )
        scenario_dir = run_sensitivity_analysis(
            scenario_name,
            run_root,
            config,
            overwrite_existing=overwrite_existing,
        )
        ranking = pd.read_csv(scenario_dir / "parameter_ranking.csv", sep=";")
        overall_top_rows.append(ranking.head(2))
        print(
            f"[{scenario_index}/{total_scenarios}] Completed scenario: {scenario_name} "
            f"in {(monotonic() - scenario_started_at) / 60:.1f} min -> {scenario_dir}",
            flush=True,
        )

    if overall_top_rows:
        pd.concat(overall_top_rows, ignore_index=True).to_csv(
            run_root / "overall_top_parameters.csv",
            index=False,
            sep=";",
        )
    from sensitivity_plots import create_goal_variable_violin_boxplots

    plot_paths = create_goal_variable_violin_boxplots(run_root, SENSITIVITY_OUTPUTS)
    print(f"Created {len(plot_paths)} goal-variable violin-boxplot(s).", flush=True)
    print(
        f"Sensitivity analysis completed in {(monotonic() - overall_started_at) / 60:.1f} min.",
        flush=True,
    )


if __name__ == "__main__":
    main()
