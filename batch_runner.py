from __future__ import annotations

import argparse
import json
import math
import os
import traceback
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import datetime
from itertools import product
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
from matplotlib.animation import FFMpegWriter, FuncAnimation
from matplotlib.offsetbox import AnchoredText
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from model_equations import SimulationResult, load_scenarios, simulate


TIME_ZERO_YEAR = 1800
DEFAULT_SIMULATION_TIME = 400
DEFAULT_OUTPUT_ROOT = Path("plots")
DEFAULT_TIME_FORMAT = "%Y-%m-%d_%H-%M-%S"


@dataclass(frozen=True)
class ExperimentGroup:
    name: str
    scenarios: list[str]
    sweep_parameters: dict[str, list[Any]]
    static_parameters: dict[str, Any] = field(default_factory=dict)
    fixed_overrides: dict[str, Any] = field(default_factory=dict)
    simulation_time: int = DEFAULT_SIMULATION_TIME
    n_agents: int = 1000
    coupling_interval: float = 1.0
    output_points_per_year: int = 100
    seed: int = 42

GLOBAL_SWEEP_VALUES = [0, 0.5, 1, 2, 3, 5, 10]
X0_SWEEP_VALUES = [0, 0.2, 0.5, 0.8, 1]
TAU_SWEEP_VALUES = [0.5, 1, 2, 3, 5, 7, 10]

# Active experiments. Historical experiment definitions can be re-enabled here as needed.
DEFAULT_EXPERIMENT_GROUPS: list[ExperimentGroup] = [
    ExperimentGroup(
        name="Descriptive_injunctive_dynamic2_tau5",
        scenarios=["Descriptive, injunctive, dynamic2"],
        sweep_parameters={
            "c_inj": np.round(np.arange(0, 101, 10), 1).tolist(),
            "c_dyn": np.round(np.arange(0, 101, 10), 1).tolist(),
        },
        static_parameters={"tau": 5, "theta": 1},
    ),
    ExperimentGroup(
        name="Descriptive_injunctive_dynamic2_tau10",
        scenarios=["Descriptive, injunctive, dynamic2"],
        sweep_parameters={
            "tau": np.round(np.arange(0, 20, 2), 1).tolist(),
            "theta": np.round(np.arange(0, 20, 2), 1).tolist(),
        },
        static_parameters={"c_inj": 6, "c_dyn": 60},
    ),
    # ExperimentGroup(
    #     name="social_factors",
    #     scenarios=[
    #         "baseline",
    #         "Dynamic social norm",
    #         "Dynamic baseline",
    #         "Observation-based / intention motivation (agents)",
    #         "Belief-based / intention motivation",
    #         # "Belief-based / approval",
    #         "Observation based / approval (punish only one behaviour)",
    #         # "Observation based / approval (relative to mean)",
    #         "Static injunctive",
    #         "Descriptive, injunctive, dynamic",
    #     ],
    #     sweep_parameters={
    #         "social_norm_factor": GLOBAL_SWEEP_VALUES,
    #         "temperature_factor": GLOBAL_SWEEP_VALUES,
    #     },
    # ),
    # ExperimentGroup(
    #     name="x0_sensitivity",
    #     scenarios=[
    #         "baseline",
    #         "Dynamic social norm",
    #         "Dynamic baseline",
    #         "Belief-based / intention motivation",
    #         "Belief-based / approval",
    #         "Observation based / approval (punish only one behaviour)",
    #         "Static injunctive",
    #         "Descriptive, injunctive, dynamic",
    #     ],
    #     sweep_parameters={
    #         "x0": X0_SWEEP_VALUES,
    #     },
    # ),
    # ExperimentGroup(
    #     name="Descriptive_injunctive_dynamic",
    #     scenarios=[
    #         "Descriptive, injunctive, dynamic"
    #     ],
    #     sweep_parameters={
    #         "c_inj": np.round(np.arange(0, 10.1, 0.5), 1).tolist(),
    #         "c_dyn": np.round(np.arange(0, 10.1, 0.5), 1).tolist(),
    #     },
    # ),    
    #     ExperimentGroup(
    #     name="Descriptive_injunctive_dynamic_tau2",
    #     scenarios=[
    #         "Descriptive, injunctive, dynamic"
    #     ],
    #     static_parameters={
    #         "tau_ref": 2,
    #         "tau_STref": 2,
    #         "tau_xp": 2,
    #     },
    #     sweep_parameters={
    #         "c_inj": np.round(np.arange(0, 10.1, 0.5), 1).tolist(),
    #         "c_dyn": np.round(np.arange(0, 10.1, 0.5), 1).tolist(),
    #     },
    # ),
    # ExperimentGroup(
    #     name="Descriptive_injunctive_dynamic_tau5",
    #     scenarios=[
    #         "Descriptive, injunctive, dynamic"
    #     ],
    #     static_parameters={
    #         "tau_ref": 5,
    #         "tau_STref": 5,
    #         "tau_xp": 5,
    #     },
    #     sweep_parameters={
    #         "c_inj": np.round(np.arange(0, 10.1, 0.5), 1).tolist(),
    #         "c_dyn": np.round(np.arange(0, 10.1, 0.5), 1).tolist(),
    #     },
    # ),
    # ExperimentGroup(
    #     name="Descriptive_injunctive_dynamic2",
    #     scenarios=[
    #         "Descriptive, injunctive, dynamic2"
    #     ],
    #     sweep_parameters={
    #         "c_inj": np.round(np.arange(0, 10.1, 0.5), 1).tolist(),
    #         "c_dyn": np.round(np.arange(0, 10.1, 0.5), 1).tolist(),
    #     },
    # ),    
    # ExperimentGroup(
    #     name="Descriptive_injunctive_dynamic2_theta_tau",
    #     scenarios=[
    #         "Descriptive, injunctive, dynamic2"
    #     ],
    #     sweep_parameters={
    #         "theta": np.round(np.arange(0, 10.1, 1), 1).tolist(),
    #         "tau": np.round(np.arange(0, 10.1, 1), 1).tolist(),
    #     },
    # ),    
    # ExperimentGroup(
    #         name="dynamic_social_norm2_theta_tau",
    #         scenarios=[
    #             "Descriptive, injunctive, dynamic2"
    #         ],
    #         sweep_parameters={
    #             "theta": np.round(np.arange(0, 10.1, 1), 1).tolist(),
    #             "tau": np.round(np.arange(0, 10.1, 1), 1).tolist(),
    #         },
    #     ),     
    # ExperimentGroup(
    #     name="Static_injunctive_sensitivity",
    #     scenarios=[
    #         "Static injunctive",
    #         "Descriptive, injunctive, dynamic"
    #     ],
    #     sweep_parameters={
    #         "x_target": [0.1, 0.5, 0.8],
    #         "c_inj": np.round(np.arange(0, 10.1, 2), 1).tolist(),
    #         "c_dyn": np.round(np.arange(0, 10.1, 2), 1).tolist(),
    #         "tau_STref": [0.5, 4],
    #         "tau_xp": [0.5, 4],
    #         "tau_ref": [0.5, 4],
    #     },
    # ),
    # ExperimentGroup(
    #     name="dynamic_norm_trend",          # interessanter Verlauf für dynamic baseline bei tau_ref = 4, tau_STref = 0.5, tau_xp = 4
    #     scenarios=["Dynamic social norm", "Dynamic baseline"],
    #     sweep_parameters={
    #         "tau_ref": TAU_SWEEP_VALUES,
    #         "tau_STref": TAU_SWEEP_VALUES,
    #         "tau_xp": TAU_SWEEP_VALUES,
    #     },
    # ),



    # uninterresting
    # ExperimentGroup(
    #     name="Belief-based / intention motivation",
    #     scenarios=["Belief-based / intention motivation"],
    #     sweep_parameters={
    #         "N": [0, 0.05, 0.1, 0.2, 0.5],
    #     },
    # ),      
    # ExperimentGroup(
    #     name="approval_sensitivity",
    #     scenarios=["Observation based / approval (punish only one behaviour)"],
    #     sweep_parameters={
    #         "alpha": [0.25, 0.5, 1, 2, 4],         # sobald alpha * x0 > 1 steigt x initial
    #     },
    # ),
    # ExperimentGroup(
    #     name="agent_based_intention",
    #     scenarios=["Observation-based / intention motivation (agents)"],
    #     sweep_parameters={
    #         "threshold": [0.001, 0.01, 0.05, 0.1],
    #         "omega": [0.005, 0.01, 0.05, 0.1],
    #         "agent_susceptibility": [0.2, 0.5, 0.8, 1.0],
    #         "network_size": [20, 50, 100, 200],
    #     },
    #     n_agents=1000,
    # ),
]


KEY_METRICS = [
    "max_temperature",
    "final_temperature",
    "temperature_area",
    "time_to_peak_temperature",
    "final_x",
    "max_x",
    "min_x",
    "n_peaks",
    "n_troughs",
    "n_oscillations",
    "median_period",
    "amplitude_initial",
    "amplitude_final",
    "amplitude_ratio",
    "damping_rate",
    "oscillation_score",
    "x_area",
    "final_social_norm",
    "max_social_norm",
    "min_social_norm",
]


PHASE_ORDER = [
    "Kollaps auf 0",
    "volle S-Kurve auf 1",
    "Zwischenzustand",
    "gedaempft oszillierend",
    "stark oszillierend",
]

PHASE_COLORS = {
    "Kollaps auf 0": "#d62728",
    "volle S-Kurve auf 1": "#ff7f0e",
    "Zwischenzustand": "#2ca02c",
    "gedaempft oszillierend": "#1f77b4",
    "stark oszillierend": "#9467bd",
}


def count_extrema(traj, tail_frac=0.5):
    """Zaehlt lokale Extrema im letzten Teil der Trajektorie -> Oszillationsindikator."""
    traj = np.asarray(traj, dtype=float)
    tail = traj[int(len(traj) * tail_frac):]
    if tail.size < 3:
        return 0
    diffs = np.diff(tail)
    sign_changes = np.sum((diffs[:-1] * diffs[1:]) < 0)
    return int(sign_changes)


def classify(traj, tail_frac=0.5):
    """Classify x(t) directly from extrema in the trajectory tail and final x."""
    traj = np.asarray(traj, dtype=float)
    if traj.size == 0:
        return "Zwischenzustand"

    e = count_extrema(traj, tail_frac)
    final_x = traj[-1]
    if e >= 6:
        return "stark oszillierend"
    if e >= 2:
        return "gedaempft oszillierend"
    if final_x < 0.05:
        return "Kollaps auf 0"
    if final_x > 0.95:
        return "volle S-Kurve auf 1"
    return "Zwischenzustand"


def sanitize_name(value: Any) -> str:
    text = str(value)
    replacements = {
        " ": "_",
        "/": "_",
        "\\": "_",
        ":": "_",
        "=": "_",
        ",": "_",
        "(": "",
        ")": "",
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    while "__" in text:
        text = text.replace("__", "_")
    return text.strip("_") or "value"


def format_value_for_slug(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        if math.isfinite(value):
            if float(value).is_integer():
                return str(int(value))
            return ("{:.4g}".format(value)).replace("-", "m").replace(".", "p")
        return str(value)
    return sanitize_name(value)


def ensure_directory(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def save_json(path: Path, payload: dict[str, Any]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, ensure_ascii=True)


def create_run_name(scenario_name: str, sweep_values: dict[str, Any]) -> str:
    parts = [sanitize_name(scenario_name)]
    for parameter_name, parameter_value in sweep_values.items():
        parts.append(f"{sanitize_name(parameter_name)}-{format_value_for_slug(parameter_value)}")
    return "__".join(parts)


def build_sweep_combinations(sweep_parameters: dict[str, list[Any]]) -> list[dict[str, Any]]:
    parameter_names = list(sweep_parameters.keys())
    parameter_values = [list(values) for values in sweep_parameters.values()]
    return [dict(zip(parameter_names, combo)) for combo in product(*parameter_values)]


def make_output_root(base_output_root: Path = DEFAULT_OUTPUT_ROOT) -> Path:
    timestamp = datetime.now().strftime(DEFAULT_TIME_FORMAT)
    return ensure_directory(base_output_root / f"{timestamp}_night_batch")


def simulation_to_dataframe(result: dict[str, Any], params: dict[str, Any]) -> pd.DataFrame:
    simulation = result["simulation"]
    if not isinstance(simulation, SimulationResult):
        raise TypeError("Expected result['simulation'] to be a SimulationResult")

    frame = pd.DataFrame(
        {
            "t": simulation.t,
            "year": simulation.t + TIME_ZERO_YEAR,
            "C_at": simulation.C_at,
            "C_oc": simulation.C_oc,
            "C_v": simulation.C_v,
            "C_so": simulation.C_so,
            "T": simulation.T,
            "x": simulation.x,
            "x_p": simulation.x_p,
            "x_ref": simulation.x_ref,
            "social_norm_term": np.asarray(
                result.get("social_norm_term", np.full_like(simulation.t, np.nan, dtype=float)),
                dtype=float,
            ),
        }
    )
    for key, value in params.items():
        frame[key] = value
    return frame


def _empty_oscillation_metrics() -> dict[str, float]:
    return {
        "n_peaks": 0.0,
        "n_troughs": 0.0,
        "n_oscillations": 0.0,
        "median_period": float("nan"),
        "amplitude_initial": float("nan"),
        "amplitude_final": float("nan"),
        "amplitude_ratio": float("nan"),
        "damping_rate": float("nan"),
        "oscillation_score": 0.0,
    }


def _compute_oscillation_metrics(t_values: np.ndarray, x_values: np.ndarray) -> dict[str, float]:
    """Keep detailed oscillation metrics for diagnostics; phase classification uses classify()."""
    if t_values.size < 5 or x_values.size < 5:
        return _empty_oscillation_metrics()

    dx = np.diff(x_values)
    sign_dx = np.sign(dx)
    for idx in range(1, sign_dx.size):
        if sign_dx[idx] == 0:
            sign_dx[idx] = sign_dx[idx - 1]
    for idx in range(sign_dx.size - 2, -1, -1):
        if sign_dx[idx] == 0:
            sign_dx[idx] = sign_dx[idx + 1]

    if sign_dx.size < 2:
        return _empty_oscillation_metrics()

    peak_indices = np.where((sign_dx[:-1] > 0) & (sign_dx[1:] < 0))[0] + 1
    trough_indices = np.where((sign_dx[:-1] < 0) & (sign_dx[1:] > 0))[0] + 1

    extrema_types = np.concatenate(
        [np.ones(peak_indices.size, dtype=int), -np.ones(trough_indices.size, dtype=int)]
    )
    extrema_indices = np.concatenate([peak_indices, trough_indices])
    if extrema_indices.size == 0:
        return _empty_oscillation_metrics()

    order = np.argsort(extrema_indices)
    extrema_indices = extrema_indices[order]
    extrema_types = extrema_types[order]

    segment_amplitudes: list[float] = []
    segment_times: list[float] = []
    for idx in range(extrema_indices.size - 1):
        if extrema_types[idx] == extrema_types[idx + 1]:
            continue
        left_idx = extrema_indices[idx]
        right_idx = extrema_indices[idx + 1]
        segment_amplitudes.append(abs(float(x_values[right_idx] - x_values[left_idx])))
        segment_times.append(float((t_values[left_idx] + t_values[right_idx]) / 2.0))

    if not segment_amplitudes:
        metrics = _empty_oscillation_metrics()
        metrics["n_peaks"] = float(peak_indices.size)
        metrics["n_troughs"] = float(trough_indices.size)
        return metrics

    x_span = float(np.nanmax(x_values) - np.nanmin(x_values))
    min_prominent_amplitude = max(0.02, 0.05 * x_span)
    amplitudes = np.asarray(segment_amplitudes, dtype=float)
    times = np.asarray(segment_times, dtype=float)
    prominent_mask = amplitudes >= min_prominent_amplitude
    prominent_amplitudes = amplitudes[prominent_mask]
    prominent_times = times[prominent_mask]

    periods: list[float] = []
    if peak_indices.size >= 2:
        periods.extend(np.diff(t_values[peak_indices]).astype(float).tolist())
    if trough_indices.size >= 2:
        periods.extend(np.diff(t_values[trough_indices]).astype(float).tolist())

    median_period = float(np.median(periods)) if periods else float("nan")
    amplitude_initial = float("nan")
    amplitude_final = float("nan")
    amplitude_ratio = float("nan")
    damping_rate = float("nan")

    n_prominent = int(prominent_amplitudes.size)
    if n_prominent >= 2:
        split_index = max(1, n_prominent // 2)
        amplitude_initial = float(np.median(prominent_amplitudes[:split_index]))
        amplitude_final = float(np.median(prominent_amplitudes[split_index:]))
        if amplitude_initial > 1e-9:
            amplitude_ratio = float(amplitude_final / amplitude_initial)

    if n_prominent >= 3:
        log_amplitudes = np.log(np.maximum(prominent_amplitudes, 1e-12))
        slope, _ = np.polyfit(prominent_times, log_amplitudes, 1)
        damping_rate = float(-slope)

    oscillation_score = (
        float(n_prominent * np.nanmedian(prominent_amplitudes)) if n_prominent > 0 else 0.0
    )
    return {
        "n_peaks": float(peak_indices.size),
        "n_troughs": float(trough_indices.size),
        "n_oscillations": float(n_prominent),
        "median_period": median_period,
        "amplitude_initial": amplitude_initial,
        "amplitude_final": amplitude_final,
        "amplitude_ratio": amplitude_ratio,
        "damping_rate": damping_rate,
        "oscillation_score": oscillation_score,
    }


def _base_metrics(t_values, temperature, x_values, social_norm) -> dict[str, Any]:
    max_temperature_index = int(np.nanargmax(temperature))
    metrics = {
        "max_temperature": float(np.nanmax(temperature)),
        "final_temperature": float(temperature[-1]),
        "temperature_area": float(np.trapz(temperature, t_values)),
        "time_to_peak_temperature": float(t_values[max_temperature_index]),
        "final_x": float(x_values[-1]),
        "max_x": float(np.nanmax(x_values)),
        "min_x": float(np.nanmin(x_values)),
        "x_area": float(np.trapz(x_values, t_values)),
        "final_social_norm": float(social_norm[-1]) if social_norm.size else float("nan"),
        "max_social_norm": float(np.nanmax(social_norm)) if social_norm.size else float("nan"),
        "min_social_norm": float(np.nanmin(social_norm)) if social_norm.size else float("nan"),
    }
    metrics.update(_compute_oscillation_metrics(np.asarray(t_values), np.asarray(x_values)))
    return metrics


def compute_run_metrics(result: dict[str, Any]) -> dict[str, Any]:
    simulation = result["simulation"]
    return _base_metrics(
        np.asarray(simulation.t, dtype=float),
        np.asarray(simulation.T, dtype=float),
        np.asarray(simulation.x, dtype=float),
        np.asarray(result.get("social_norm_term", []), dtype=float),
    )


def compute_metrics_from_saved_time_series(frame: pd.DataFrame) -> dict[str, Any]:
    return _base_metrics(
        pd.to_numeric(frame["t"], errors="coerce").to_numpy(dtype=float),
        pd.to_numeric(frame["T"], errors="coerce").to_numpy(dtype=float),
        pd.to_numeric(frame["x"], errors="coerce").to_numpy(dtype=float),
        pd.to_numeric(frame["social_norm_term"], errors="coerce").to_numpy(dtype=float),
    )


def add_parameter_text_box(
    ax: plt.Axes,
    params: dict[str, Any],
    parameter_names: list[str],
    loc: str = "upper right",
) -> None:
    lines = []
    for parameter_name in parameter_names:
        if parameter_name not in params:
            continue
        value = params[parameter_name]
        if isinstance(value, float) and math.isfinite(value):
            value_text = f"{value:.4g}"
        else:
            value_text = str(value)
        lines.append(f"{parameter_name} = {value_text}")
    if not lines:
        return
    anchored_text = AnchoredText(
        "\n".join(lines), loc=loc, prop={"size": 9}, frameon=True, borderpad=0.8
    )
    anchored_text.patch.set_alpha(0.9)
    ax.add_artist(anchored_text)


def save_temperature_plot(frame, run_dir, run_label, params, sweep_parameters) -> None:
    fig, ax = plt.subplots(figsize=(14, 6))
    ax.plot(frame["year"], frame["T"], label="Temperature")
    ax.set_xlabel("Time (year)")
    ax.set_ylabel("Temperature Anomaly (celsius)")
    ax.set_xlim(1900, float(frame["year"].iloc[-1]))
    ax.set_ylim(top=max(5, float(np.nanmax(frame["T"])) + 0.25))
    ax.set_title(run_label)
    ax.legend(loc="center left", bbox_to_anchor=(1.02, 0.5), fontsize=9)
    add_parameter_text_box(ax, params, sweep_parameters)
    fig.tight_layout()
    fig.savefig(run_dir / "temperature.png", dpi=300)
    plt.close(fig)


def save_x_plot(frame, run_dir, run_label, params, sweep_parameters) -> None:
    fig, ax = plt.subplots(figsize=(14, 6))
    ax.plot(frame["year"], frame["x"], label="x")
    ax.set_xlabel("Time (year)")
    ax.set_ylabel("Fraction of mitigators (X)")
    ax.set_xlim(1900, float(frame["year"].iloc[-1]))
    ax.set_ylim(-0.1, 1.1)
    ax.set_title(run_label)
    ax.legend(loc="center left", bbox_to_anchor=(1.02, 0.5), fontsize=9)
    add_parameter_text_box(ax, params, sweep_parameters)
    fig.tight_layout()
    fig.savefig(run_dir / "x.png", dpi=300)
    plt.close(fig)


def save_social_norm_plot(frame, run_dir, run_label, params, sweep_parameters) -> None:
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
    add_parameter_text_box(ax, params, sweep_parameters)
    fig.tight_layout()
    fig.savefig(run_dir / "social_norm.png", dpi=300)
    plt.close(fig)


def save_auxiliary_plot(frame, run_dir, run_label, params, sweep_parameters) -> None:
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
    add_parameter_text_box(ax, params, sweep_parameters)
    fig.tight_layout()
    fig.savefig(run_dir / "auxiliary_states.png", dpi=300)
    plt.close(fig)


def get_group_parameter_names(group: ExperimentGroup) -> list[str]:
    return list(dict.fromkeys(list(group.sweep_parameters) + list(group.static_parameters)))


def save_run_outputs(run_dir, run_label, params, result, metrics, sweep_parameters) -> None:
    ensure_directory(run_dir)
    frame = simulation_to_dataframe(result, params)
    frame.to_csv(run_dir / "time_series.csv", index=False)
    save_json(run_dir / "metadata.json", {"run_label": run_label, "parameters": params, "metrics": metrics})
    save_temperature_plot(frame, run_dir, run_label, params, sweep_parameters)
    save_x_plot(frame, run_dir, run_label, params, sweep_parameters)
    save_social_norm_plot(frame, run_dir, run_label, params, sweep_parameters)
    if not np.all(frame["x_p"] == frame["x_p"].iloc[0]) or not np.all(
        frame["x_ref"] == frame["x_ref"].iloc[0]
    ):
        save_auxiliary_plot(frame, run_dir, run_label, params, sweep_parameters)


def save_run_time_series_only(run_dir: Path, params: dict[str, Any], result: dict[str, Any]) -> None:
    ensure_directory(run_dir)
    simulation_to_dataframe(result, params).to_csv(run_dir / "time_series.csv", index=False)


def append_failure_record(run_dir: Path, run_label: str, error: Exception) -> None:
    save_json(
        run_dir / "failure.json",
        {
            "run_label": run_label,
            "error_type": type(error).__name__,
            "error_message": str(error),
            "traceback": traceback.format_exc(),
        },
    )


def run_single_combination(
    base_params: dict[str, Any],
    sweep_values: dict[str, Any],
    group: ExperimentGroup,
    run_root: Path,
    scenario_name: str,
    overwrite: bool = False,
    save_outputs_per_run: bool = False,
    current_run: int | None = None,
    total_runs: int | None = None,
) -> dict[str, Any]:
    params = {**base_params, **group.fixed_overrides, **group.static_parameters, **sweep_values}
    run_name = create_run_name(scenario_name, sweep_values)
    run_dir = run_root / group.name / sanitize_name(scenario_name) / run_name
    ensure_directory(run_dir)

    time_series_path = run_dir / "time_series.csv"
    if time_series_path.exists() and not overwrite:
        existing_frame = pd.read_csv(time_series_path)
        required_columns = {"t", "T", "x", "social_norm_term"}
        if required_columns.issubset(existing_frame.columns):
            existing_metrics = compute_metrics_from_saved_time_series(existing_frame)
            return {
                "status": "skipped",
                "group": group.name,
                "scenario": scenario_name,
                "run_name": run_name,
                "run_dir": str(run_dir),
                **sweep_values,
                **existing_metrics,
            }

    try:
        if current_run is not None and total_runs is not None:
            print(f"[{current_run}/{total_runs}] Running {group.name} | {scenario_name} | {run_name}")
        elif current_run is None and total_runs is None:
            print(f"Running {group.name} | {scenario_name} | {run_name}")

        result = simulate(
            params,
            simulation_time=group.simulation_time,
            n_agents=group.n_agents,
            coupling_interval=group.coupling_interval,
            output_points_per_year=group.output_points_per_year,
            seed=group.seed,
        )
        metrics = compute_run_metrics(result)
        if save_outputs_per_run:
            save_run_outputs(
                run_dir,
                f"{group.name} | {scenario_name}",
                params,
                result,
                metrics,
                get_group_parameter_names(group),
            )
        else:
            save_run_time_series_only(run_dir, params, result)

        return {
            "status": "ok",
            "group": group.name,
            "scenario": scenario_name,
            "run_name": run_name,
            "run_dir": str(run_dir),
            **sweep_values,
            **metrics,
        }
    except Exception as error:
        append_failure_record(run_dir, f"{group.name} | {scenario_name} | {run_name}", error)
        return {
            "status": "failed",
            "group": group.name,
            "scenario": scenario_name,
            "run_name": run_name,
            "run_dir": str(run_dir),
            **sweep_values,
            "error_type": type(error).__name__,
            "error_message": str(error),
        }


def _classify_saved_run(record: pd.Series, tail_frac: float = 0.5) -> str:
    run_dir = record.get("run_dir")
    if not isinstance(run_dir, str):
        return "Zwischenzustand"
    time_series_path = Path(run_dir) / "time_series.csv"
    if not time_series_path.exists():
        return "Zwischenzustand"
    frame = pd.read_csv(time_series_path, usecols=["x"])
    trajectory = pd.to_numeric(frame["x"], errors="coerce").dropna().to_numpy(dtype=float)
    return classify(trajectory, tail_frac=tail_frac)


def save_phase_map_for_two_parameters(
    summary_df: pd.DataFrame,
    group_dir: Path,
    x_param: str,
    y_param: str,
    tail_frac: float = 0.5,
) -> None:
    required_columns = {"run_dir", x_param, y_param}
    if not required_columns.issubset(summary_df.columns):
        return

    phase_df = summary_df.copy()
    phase_df["phase"] = phase_df.apply(
        lambda row: _classify_saved_run(row, tail_frac=tail_frac), axis=1
    )
    pivot = phase_df.pivot_table(
        index=y_param, columns=x_param, values="phase", aggfunc="first"
    ).sort_index(axis=0).sort_index(axis=1)
    if pivot.empty:
        return

    phase_to_idx = {label: idx for idx, label in enumerate(PHASE_ORDER)}
    phase_array = np.vectorize(
        lambda label: phase_to_idx.get(str(label), phase_to_idx["Zwischenzustand"])
    )(pivot.to_numpy())

    cmap = matplotlib.colors.ListedColormap([PHASE_COLORS[label] for label in PHASE_ORDER])
    fig, ax = plt.subplots(figsize=(10, 7))
    image = ax.imshow(
        phase_array,
        origin="lower",
        aspect="auto",
        cmap=cmap,
        vmin=0,
        vmax=len(PHASE_ORDER) - 1,
    )
    ax.set_xticks(range(len(pivot.columns)))
    ax.set_xticklabels(
        [format_value_for_slug(value) for value in pivot.columns], rotation=45, ha="right"
    )
    ax.set_yticks(range(len(pivot.index)))
    ax.set_yticklabels([format_value_for_slug(value) for value in pivot.index])
    ax.set_xlabel(x_param)
    ax.set_ylabel(y_param)
    ax.set_title(f"Phase map over {x_param} and {y_param}")
    cbar = fig.colorbar(image, ax=ax, ticks=list(range(len(PHASE_ORDER))))
    cbar.ax.set_yticklabels(PHASE_ORDER)
    cbar.set_label("Phase regime")
    fig.tight_layout()
    fig.savefig(group_dir / f"comparison_phase_map_{x_param}_vs_{y_param}.png", dpi=300)
    plt.close(fig)


def save_heatmap_for_two_parameters(summary_df, group_dir, metric_name, x_param, y_param) -> None:
    pivot = summary_df.pivot_table(
        index=y_param, columns=x_param, values=metric_name, aggfunc="mean"
    ).sort_index(axis=0).sort_index(axis=1)
    if pivot.empty:
        return
    fig, ax = plt.subplots(figsize=(10, 7))
    image = ax.imshow(pivot.to_numpy(), origin="lower", aspect="auto")
    ax.set_xticks(range(len(pivot.columns)))
    ax.set_xticklabels([format_value_for_slug(v) for v in pivot.columns], rotation=45, ha="right")
    ax.set_yticks(range(len(pivot.index)))
    ax.set_yticklabels([format_value_for_slug(v) for v in pivot.index])
    ax.set_xlabel(x_param)
    ax.set_ylabel(y_param)
    ax.set_title(f"{metric_name} over {x_param} and {y_param}")
    fig.colorbar(image, ax=ax, label=metric_name)
    fig.tight_layout()
    fig.savefig(group_dir / f"comparison_{metric_name}_heatmap.png", dpi=300)
    plt.close(fig)


def save_metric_vs_parameters(summary_df, group_dir, metric_name, sweep_parameters) -> None:
    if not sweep_parameters:
        return
    fig, axes = plt.subplots(
        len(sweep_parameters), 1, figsize=(12, 4 * len(sweep_parameters)), squeeze=False
    )
    for axis, parameter_name in zip(axes.flatten(), sweep_parameters):
        axis.scatter(
            pd.to_numeric(summary_df[parameter_name], errors="coerce"),
            pd.to_numeric(summary_df[metric_name], errors="coerce"),
            alpha=0.65,
        )
        axis.set_xlabel(parameter_name)
        axis.set_ylabel(metric_name)
        axis.set_title(f"{metric_name} vs {parameter_name}")
        axis.grid(True, alpha=0.2)
    fig.tight_layout()
    fig.savefig(group_dir / f"comparison_{metric_name}_vs_parameters.png", dpi=300)
    plt.close(fig)


def save_correlation_heatmap(summary_df: pd.DataFrame, group_dir: Path) -> None:
    numeric_df = summary_df.select_dtypes(include=[np.number]).copy()
    if numeric_df.shape[1] < 2:
        return
    correlation = numeric_df.corr(numeric_only=True)
    fig, ax = plt.subplots(
        figsize=(max(8, 0.65 * len(correlation.columns)), max(6, 0.65 * len(correlation.columns)))
    )
    image = ax.imshow(correlation.to_numpy(), vmin=-1, vmax=1, cmap="coolwarm")
    ax.set_xticks(range(len(correlation.columns)))
    ax.set_xticklabels(correlation.columns, rotation=45, ha="right")
    ax.set_yticks(range(len(correlation.index)))
    ax.set_yticklabels(correlation.index)
    ax.set_title("Correlation heatmap")
    fig.colorbar(image, ax=ax, label="Pearson correlation")
    fig.tight_layout()
    fig.savefig(group_dir / "comparison_correlation_heatmap.png", dpi=300)
    plt.close(fig)


def save_overlaid_time_series_plot(
    summary_df,
    group_dir,
    metric_name,
    output_name,
    ylabel,
    sweep_parameters,
    y_limits=None,
) -> None:
    fig, ax = plt.subplots(figsize=(14, 6))
    plotted_lines = 0
    maximum_value = -np.inf
    last_year = None
    for _, record in summary_df.iterrows():
        run_dir = record.get("run_dir")
        if not isinstance(run_dir, str):
            continue
        time_series_path = Path(run_dir) / "time_series.csv"
        if not time_series_path.exists():
            continue
        frame = pd.read_csv(time_series_path)
        if metric_name not in frame.columns or "year" not in frame.columns:
            continue
        values = pd.to_numeric(frame[metric_name], errors="coerce")
        if values.isna().all():
            continue
        label = ", ".join(
            f"{p}={format_value_for_slug(record[p])}"
            for p in sweep_parameters
            if p in record.index
        ) or str(record.get("scenario", "run"))
        ax.plot(frame["year"], values, label=label)
        plotted_lines += 1
        maximum_value = max(maximum_value, float(values.max()))
        last_year = float(frame["year"].iloc[-1])

    if plotted_lines == 0:
        plt.close(fig)
        return

    ax.set_xlabel("Time (year)")
    ax.set_ylabel(ylabel)
    ax.set_xlim(1900, last_year)
    if y_limits is not None:
        ax.set_ylim(*y_limits)
    elif metric_name == "T":
        ax.set_ylim(top=max(5, maximum_value + 0.25))
    if metric_name == "social_norm_term":
        ax.axhline(0, color="black", linewidth=0.8, linestyle="--")
    ax.set_title("All parameter combinations")
    ax.legend(loc="center left", bbox_to_anchor=(1.02, 0.5), fontsize=9)
    fig.tight_layout()
    fig.savefig(group_dir / output_name, dpi=300)
    plt.close(fig)


def save_x_parameter_surface_animation(
    summary_df: pd.DataFrame,
    group_dir: Path,
    x_param: str,
    y_param: str,
    scenario_name: str,
    max_frames: int = 240,
) -> None:
    required_columns = {"run_dir", x_param, y_param, "scenario"}
    if not required_columns.issubset(summary_df.columns):
        return
    scenario_df = summary_df[summary_df["scenario"] == scenario_name].copy()
    trajectories = {}
    for _, record in scenario_df.iterrows():
        time_series_path = Path(str(record.get("run_dir", ""))) / "time_series.csv"
        if not time_series_path.exists():
            continue
        frame = pd.read_csv(time_series_path, usecols=["year", "x"])
        if frame.empty:
            continue
        trajectories[(float(record[x_param]), float(record[y_param]))] = (
            frame["year"].to_numpy(dtype=float),
            frame["x"].to_numpy(dtype=float),
        )
    if not trajectories:
        return

    x_values = np.array(sorted({key[0] for key in trajectories}), dtype=float)
    y_values = np.array(sorted({key[1] for key in trajectories}), dtype=float)
    if len(x_values) < 2 or len(y_values) < 2:
        return
    lengths = {len(values[0]) for values in trajectories.values()}
    if len(lengths) != 1:
        return

    reference_years = next(iter(trajectories.values()))[0]
    surface = np.full((len(y_values), len(x_values), len(reference_years)), np.nan)
    x_indices = {value: i for i, value in enumerate(x_values)}
    y_indices = {value: i for i, value in enumerate(y_values)}
    for (px, py), (_, trajectory) in trajectories.items():
        surface[y_indices[py], x_indices[px], :] = trajectory
    if np.isnan(surface).any():
        return

    frame_indices = np.unique(
        np.linspace(0, len(reference_years) - 1, min(max_frames, len(reference_years)), dtype=int)
    )
    X, Y = np.meshgrid(x_values, y_values)
    safe_name = sanitize_name(scenario_name)

    def configure_axes(axis, frame_index):
        axis.set_xlabel(x_param)
        axis.set_ylabel(y_param)
        axis.set_zlabel("x")
        axis.set_zlim(-0.1, 1.1)
        axis.set_title(
            f"{scenario_name}: x over {x_param} and {y_param} | year {reference_years[frame_index]:.1f}"
        )

    final_fig = plt.figure(figsize=(11, 8))
    final_axis = final_fig.add_subplot(111, projection="3d")
    final_axis.plot_surface(X, Y, surface[:, :, -1], cmap="viridis", vmin=0, vmax=1, edgecolor="none")
    configure_axes(final_axis, len(reference_years) - 1)
    final_fig.tight_layout()
    final_fig.savefig(group_dir / f"x_surface_{safe_name}.png", dpi=300)
    plt.close(final_fig)

    animation_fig = plt.figure(figsize=(11, 8))
    animation_axis = animation_fig.add_subplot(111, projection="3d")

    def update(frame_index):
        animation_axis.clear()
        animation_axis.plot_surface(
            X, Y, surface[:, :, frame_index], cmap="viridis", vmin=0, vmax=1, edgecolor="none"
        )
        configure_axes(animation_axis, frame_index)
        return (animation_axis,)

    animation = FuncAnimation(animation_fig, update, frames=frame_indices, blit=False)
    video_path = group_dir / f"x_surface_{safe_name}.mp4"
    try:
        animation.save(video_path, writer=FFMpegWriter(fps=12, bitrate=1800), dpi=120)
    except (FileNotFoundError, RuntimeError) as error:
        print(f"Could not create {video_path}: {error}")
    finally:
        plt.close(animation_fig)


def save_group_comparison_plots(summary_df: pd.DataFrame, group_dir: Path, group: ExperimentGroup) -> None:
    summary_df.to_csv(group_dir / "summary_metrics.csv", index=False)
    sweep_parameters = list(group.sweep_parameters.keys())

    save_correlation_heatmap(summary_df, group_dir)
    for metric_name in KEY_METRICS:
        if metric_name in summary_df.columns:
            save_metric_vs_parameters(summary_df, group_dir, metric_name, sweep_parameters)

    save_overlaid_time_series_plot(
        summary_df, group_dir, "x", "x.png", "Fraction of mitigators (X)", sweep_parameters, (-0.1, 1.1)
    )
    save_overlaid_time_series_plot(
        summary_df, group_dir, "T", "temperature.png", "Temperature Anomaly (celsius)", sweep_parameters
    )
    save_overlaid_time_series_plot(
        summary_df, group_dir, "social_norm_term", "social_norm.png", "Social norm value", sweep_parameters
    )

    if len(sweep_parameters) == 2:
        for scenario_name in summary_df.get("scenario", pd.Series(dtype=str)).dropna().unique():
            save_x_parameter_surface_animation(
                summary_df, group_dir, sweep_parameters[0], sweep_parameters[1], scenario_name
            )
        save_phase_map_for_two_parameters(
            summary_df, group_dir, sweep_parameters[0], sweep_parameters[1]
        )
        for metric_name in KEY_METRICS:
            if metric_name in summary_df.columns:
                save_heatmap_for_two_parameters(
                    summary_df, group_dir, metric_name, sweep_parameters[0], sweep_parameters[1]
                )


def save_approach_comparison_plot(summary_df: pd.DataFrame, group_dir: Path, scenario_name: str) -> None:
    scenario_summary = summary_df[summary_df["scenario"] == scenario_name].copy()
    if scenario_summary.empty:
        return
    candidates = [
        "max_temperature",
        "final_temperature",
        "final_x",
        "final_social_norm",
        "time_to_peak_temperature",
    ]
    metrics = [metric for metric in candidates if metric in scenario_summary.columns]
    if not metrics:
        return
    fig, axes = plt.subplots(len(metrics), 1, figsize=(12, 3.5 * len(metrics)), squeeze=False)
    for axis, metric_name in zip(axes.flatten(), metrics):
        values = pd.to_numeric(scenario_summary[metric_name], errors="coerce").dropna().to_numpy()
        if values.size:
            axis.boxplot(values, vert=True)
        axis.set_ylabel(metric_name)
        axis.set_xticks([1])
        axis.set_xticklabels([sanitize_name(scenario_name)], rotation=15, ha="right")
        axis.grid(True, axis="y", alpha=0.2)
    fig.suptitle(f"{scenario_name}: summary across all parameter combinations")
    fig.tight_layout(rect=(0, 0, 1, 0.97))
    fig.savefig(group_dir / f"approach_summary_{sanitize_name(scenario_name)}.png", dpi=300)
    plt.close(fig)


def save_overall_comparison_plots(all_summaries: pd.DataFrame, run_root: Path) -> None:
    if all_summaries.empty:
        return
    candidates = ["max_temperature", "final_temperature", "final_x", "final_social_norm"]
    metrics = [metric for metric in candidates if metric in all_summaries.columns]
    if not metrics:
        return
    fig, axes = plt.subplots(len(metrics), 1, figsize=(12, 4 * len(metrics)), squeeze=False)
    for axis, metric_name in zip(axes.flatten(), metrics):
        grouped = []
        labels = []
        for group_name, subset in all_summaries.groupby("group"):
            values = pd.to_numeric(subset[metric_name], errors="coerce").dropna().to_numpy()
            if values.size:
                grouped.append(values)
                labels.append(group_name)
        if grouped:
            axis.boxplot(grouped, tick_labels=labels, vert=True)
        axis.set_title(f"{metric_name} by group")
        axis.tick_params(axis="x", rotation=25)
        axis.grid(True, axis="y", alpha=0.2)
    fig.tight_layout()
    fig.savefig(run_root / "overall_metric_comparison.png", dpi=300)
    plt.close(fig)


def load_default_groups() -> list[ExperimentGroup]:
    return DEFAULT_EXPERIMENT_GROUPS


def _resolve_worker_count(workers: int | None) -> int:
    if workers is not None:
        if workers < 1:
            raise ValueError("workers must be at least 1")
        return workers
    return max(1, (os.cpu_count() or 1) - 1)


def _run_parallel_job(job: tuple[Any, ...]) -> dict[str, Any]:
    (
        base_params,
        sweep_values,
        group,
        run_root,
        scenario_name,
        overwrite,
        save_outputs_per_run,
    ) = job
    return run_single_combination(
        base_params=base_params,
        sweep_values=sweep_values,
        group=group,
        run_root=run_root,
        scenario_name=scenario_name,
        overwrite=overwrite,
        save_outputs_per_run=save_outputs_per_run,
        current_run=-1,
        total_runs=-1,
    )


def run_groups(
    selected_group_names: list[str] | None = None,
    output_root: Path = DEFAULT_OUTPUT_ROOT,
    overwrite: bool = False,
    save_outputs_per_run: bool = False,
    workers: int | None = None,
) -> Path:
    run_root = make_output_root(output_root)
    available_scenarios = load_scenarios()
    groups = load_default_groups()
    if selected_group_names:
        selected = set(selected_group_names)
        groups = [group for group in groups if group.name in selected]

    worker_count = _resolve_worker_count(workers)

    save_json(
        run_root / "manifest.json",
        {
            "created_at": datetime.now().isoformat(),
            "selected_groups": [group.name for group in groups],
            "available_scenarios": list(available_scenarios.keys()),
            "workers": worker_count,
            "groups": [
                {
                    "name": group.name,
                    "scenarios": group.scenarios,
                    "sweep_parameters": group.sweep_parameters,
                    "static_parameters": group.static_parameters,
                    "fixed_overrides": group.fixed_overrides,
                    "simulation_time": group.simulation_time,
                    "n_agents": group.n_agents,
                    "coupling_interval": group.coupling_interval,
                    "output_points_per_year": group.output_points_per_year,
                    "seed": group.seed,
                }
                for group in groups
            ],
        },
    )

    jobs: list[tuple[Any, ...]] = []
    group_scenarios: dict[str, list[str]] = {}

    for group in groups:
        group_dir = ensure_directory(run_root / group.name)
        scenarios_to_run = [scenario for scenario in group.scenarios if scenario in available_scenarios]
        group_scenarios[group.name] = scenarios_to_run
        missing_scenarios = [scenario for scenario in group.scenarios if scenario not in available_scenarios]
        if missing_scenarios:
            save_json(
                group_dir / "missing_scenarios.json",
                {"missing_scenarios": missing_scenarios, "available_scenarios": list(available_scenarios)},
            )

        sweep_combinations = build_sweep_combinations(group.sweep_parameters)
        for scenario_name in scenarios_to_run:
            base_params = available_scenarios[scenario_name]
            for sweep_values in sweep_combinations:
                jobs.append(
                    (
                        base_params,
                        sweep_values,
                        group,
                        run_root,
                        scenario_name,
                        overwrite,
                        save_outputs_per_run,
                    )
                )

    total_runs = len(jobs)
    all_records: list[dict[str, Any]] = []

    if worker_count == 1:
        for current_run, job in enumerate(jobs, start=1):
            (
                base_params,
                sweep_values,
                group,
                job_run_root,
                scenario_name,
                job_overwrite,
                job_save_outputs,
            ) = job
            record = run_single_combination(
                base_params=base_params,
                sweep_values=sweep_values,
                group=group,
                run_root=job_run_root,
                scenario_name=scenario_name,
                overwrite=job_overwrite,
                save_outputs_per_run=job_save_outputs,
                current_run=current_run,
                total_runs=total_runs,
            )
            all_records.append(record)
    else:
        print(f"Running {total_runs} simulations with {worker_count} worker processes")
        with ProcessPoolExecutor(max_workers=worker_count) as executor:
            future_to_job = {executor.submit(_run_parallel_job, job): job for job in jobs}
            for completed_runs, future in enumerate(as_completed(future_to_job), start=1):
                record = future.result()
                all_records.append(record)
                print(
                    f"[{completed_runs}/{total_runs}] Completed "
                    f"{record.get('group')} | {record.get('scenario')} | {record.get('run_name')}"
                )

    all_group_summaries: list[pd.DataFrame] = []
    for group in groups:
        group_dir = ensure_directory(run_root / group.name)
        group_records = [record for record in all_records if record.get("group") == group.name]
        if not group_records:
            continue

        group_summary = pd.DataFrame(group_records)
        sort_columns = ["scenario"] + [
            parameter_name
            for parameter_name in group.sweep_parameters
            if parameter_name in group_summary.columns
        ]
        group_summary = group_summary.sort_values(sort_columns, kind="stable").reset_index(drop=True)

        save_group_comparison_plots(group_summary, group_dir, group)
        for scenario_name in group_scenarios[group.name]:
            save_approach_comparison_plot(group_summary, group_dir, scenario_name)
        all_group_summaries.append(group_summary)

    combined_summary = (
        pd.concat(all_group_summaries, ignore_index=True) if all_group_summaries else pd.DataFrame()
    )
    if not combined_summary.empty:
        combined_summary.to_csv(run_root / "all_runs_summary.csv", index=False)
        save_overall_comparison_plots(combined_summary, run_root)

    save_json(run_root / "run_index.json", {"records": all_records})
    return run_root


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run parameter sweeps and save CSVs plus plots for each combination."
    )
    parser.add_argument(
        "--groups",
        nargs="*",
        default=None,
        help="Optional list of experiment group names to run. If omitted, all default groups are selected.",
    )
    parser.add_argument(
        "--output-root",
        type=Path,
        default=DEFAULT_OUTPUT_ROOT,
        help="Base output directory for batch results.",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Re-run combinations even if a completed run directory already exists.",
    )
    parser.add_argument(
        "--save-outputs-per-run",
        action="store_true",
        help="Save time series and plots for each individual run, in addition to summary metrics.",
        default=False,
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=None,
        help="Number of parallel worker processes. Default: CPU count minus one. Use 1 for serial execution.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    run_root = run_groups(
        selected_group_names=args.groups if args.groups else None,
        output_root=args.output_root,
        overwrite=args.overwrite,
        save_outputs_per_run=args.save_outputs_per_run,
        workers=args.workers,
    )
    print(f"Batch run completed: {run_root}")


if __name__ == "__main__":
    main()
