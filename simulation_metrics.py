from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from model_equations import emission_rate


ELIMINATION_THRESHOLD = 0.95


def _empty_oscillation_metrics() -> dict[str, float]:
    return {
        "n_peaks": 0.0,
        "n_troughs": 0.0,
        "n_prominent_half_cycles": 0.0,
        "n_oscillations": 0.0,
        "median_period": float("nan"),
        "oscillation_amplitude": 0.0,
        "amplitude_initial": float("nan"),
        "amplitude_final": float("nan"),
        "amplitude_ratio": float("nan"),
        "damping_rate": float("nan"),
        "damping_index": 0.0,
        "oscillation_score": 0.0,
    }


def _compute_oscillation_metrics(t_values: np.ndarray, x_values: np.ndarray) -> dict[str, float]:
    """Compute prominent peak/trough oscillation diagnostics for x(t)."""
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

    x_span = float(np.nanmax(x_values) - np.nanmin(x_values))
    min_prominent_amplitude = max(0.02, 0.05 * x_span)

    # Each adjacent peak/trough pair is one half-cycle. Keeping the pair aligned
    # with the extrema positions lets us distinguish half-cycles from complete
    # peak-to-peak or trough-to-trough oscillations.
    pair_amplitudes = np.full(max(0, extrema_indices.size - 1), np.nan, dtype=float)
    pair_times = np.full(max(0, extrema_indices.size - 1), np.nan, dtype=float)
    for idx in range(extrema_indices.size - 1):
        if extrema_types[idx] == extrema_types[idx + 1]:
            continue
        left_idx = extrema_indices[idx]
        right_idx = extrema_indices[idx + 1]
        pair_amplitudes[idx] = abs(float(x_values[right_idx] - x_values[left_idx]))
        pair_times[idx] = float((t_values[left_idx] + t_values[right_idx]) / 2.0)

    prominent_pair_mask = np.isfinite(pair_amplitudes) & (
        pair_amplitudes >= min_prominent_amplitude
    )
    prominent_amplitudes = pair_amplitudes[prominent_pair_mask]
    prominent_times = pair_times[prominent_pair_mask]

    # A complete oscillation requires two consecutive prominent half-cycles.
    # Count peak-to-peak and trough-to-trough cycles separately and use the
    # larger count so the same physical cycle is not counted twice.
    peak_cycles = 0
    trough_cycles = 0
    prominent_periods: list[float] = []
    for idx in range(extrema_indices.size - 2):
        alternating = (
            extrema_types[idx] != extrema_types[idx + 1]
            and extrema_types[idx] == extrema_types[idx + 2]
        )
        if not alternating:
            continue
        if not (prominent_pair_mask[idx] and prominent_pair_mask[idx + 1]):
            continue

        period = float(t_values[extrema_indices[idx + 2]] - t_values[extrema_indices[idx]])
        if period > 0:
            prominent_periods.append(period)
        if extrema_types[idx] > 0:
            peak_cycles += 1
        else:
            trough_cycles += 1

    n_oscillations = max(peak_cycles, trough_cycles)
    median_period = (
        float(np.median(prominent_periods)) if prominent_periods else float("nan")
    )
    oscillation_amplitude = (
        float(np.median(prominent_amplitudes))
        if prominent_amplitudes.size
        else 0.0
    )

    amplitude_initial = float("nan")
    amplitude_final = float("nan")
    amplitude_ratio = float("nan")
    damping_rate = float("nan")
    damping_index = 0.0

    n_prominent = int(prominent_amplitudes.size)
    if n_prominent >= 2:
        split_index = max(1, n_prominent // 2)
        amplitude_initial = float(np.median(prominent_amplitudes[:split_index]))
        amplitude_final = float(np.median(prominent_amplitudes[split_index:]))
        if amplitude_initial > 1e-12 and amplitude_final > 1e-12:
            amplitude_ratio = float(amplitude_final / amplitude_initial)
            damping_index = float(np.log(amplitude_initial / amplitude_final))

    if n_prominent >= 3:
        log_amplitudes = np.log(np.maximum(prominent_amplitudes, 1e-12))
        slope, _ = np.polyfit(prominent_times, log_amplitudes, 1)
        damping_rate = float(-slope)

    oscillation_score = float(n_oscillations * oscillation_amplitude)
    return {
        "n_peaks": float(peak_indices.size),
        "n_troughs": float(trough_indices.size),
        "n_prominent_half_cycles": float(n_prominent),
        "n_oscillations": float(n_oscillations),
        "median_period": median_period,
        "oscillation_amplitude": oscillation_amplitude,
        "amplitude_initial": amplitude_initial,
        "amplitude_final": amplitude_final,
        "amplitude_ratio": amplitude_ratio,
        "damping_rate": damping_rate,
        "damping_index": damping_index,
        "oscillation_score": oscillation_score,
    }


def compute_oscillation_metrics(
    t_values: np.ndarray,
    x_values: np.ndarray,
) -> dict[str, float]:
    """Public wrapper used by batch classification and sensitivity analysis."""
    return _compute_oscillation_metrics(
        np.asarray(t_values, dtype=float),
        np.asarray(x_values, dtype=float),
    )


def _first_threshold_crossing_time(
    t_values: np.ndarray,
    x_values: np.ndarray,
    threshold: float = ELIMINATION_THRESHOLD,
) -> float:
    above = np.flatnonzero(x_values >= threshold)
    if above.size == 0:
        return float("nan")
    first_index = int(above[0])
    if first_index == 0:
        return float(t_values[0])

    t0 = float(t_values[first_index - 1])
    t1 = float(t_values[first_index])
    x0 = float(x_values[first_index - 1])
    x1 = float(x_values[first_index])
    if abs(x1 - x0) < 1e-12:
        return t1
    fraction = float(np.clip((threshold - x0) / (x1 - x0), 0.0, 1.0))
    return t0 + fraction * (t1 - t0)


def _prescribed_emission_rate(t_values: np.ndarray, params: dict[str, Any]) -> np.ndarray:
    rates = np.empty_like(t_values, dtype=float)
    for index, time_value in enumerate(t_values):
        t_int = int(time_value)
        if t_int < 217:
            rates[index] = emission_rate[t_int]
        else:
            rates[index] = (
                ((t_int - 217) * params["epsilon_max"]) / (t_int - 217 + params["s"])
            ) + emission_rate[217]
    return rates


def _base_metrics(
    t_values,
    temperature,
    x_values,
    social_norm,
    params: dict[str, Any] | None = None,
) -> dict[str, Any]:
    t_values = np.asarray(t_values, dtype=float)
    temperature = np.asarray(temperature, dtype=float)
    x_values = np.asarray(x_values, dtype=float)
    social_norm = np.asarray(social_norm, dtype=float)

    max_temperature_index = int(np.nanargmax(temperature))
    time_to_elimination = _first_threshold_crossing_time(t_values, x_values)
    threshold_reached = bool(np.any(x_values >= ELIMINATION_THRESHOLD))
    elimination_success = bool(x_values[-1] >= ELIMINATION_THRESHOLD)

    cumulative_emissions = float("nan")
    if params is not None and {"epsilon_max", "s"}.issubset(params):
        prescribed_emissions = _prescribed_emission_rate(t_values, params)
        effective_emissions = prescribed_emissions * (1.0 - x_values)
        cumulative_emissions = float(np.trapz(effective_emissions, t_values))

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
        "threshold_reached": threshold_reached,
        "time_to_elimination": time_to_elimination,
        "elimination_success": elimination_success,
        "cumulative_emissions": cumulative_emissions,
    }
    metrics.update(_compute_oscillation_metrics(t_values, x_values))
    return metrics


def compute_run_metrics(result: dict[str, Any], params: dict[str, Any]) -> dict[str, Any]:
    simulation = result["simulation"]
    resolved_params = result.get("parameters", params)
    return _base_metrics(
        np.asarray(simulation.t, dtype=float),
        np.asarray(simulation.T, dtype=float),
        np.asarray(simulation.x, dtype=float),
        np.asarray(result.get("social_norm_term", []), dtype=float),
        params=resolved_params,
    )


def compute_metrics_from_saved_time_series(frame: pd.DataFrame) -> dict[str, Any]:
    params: dict[str, Any] = {}
    for parameter_name in ("epsilon_max", "s"):
        if parameter_name in frame.columns and not frame[parameter_name].empty:
            params[parameter_name] = float(frame[parameter_name].iloc[0])

    return _base_metrics(
        pd.to_numeric(frame["t"], errors="coerce").to_numpy(dtype=float),
        pd.to_numeric(frame["T"], errors="coerce").to_numpy(dtype=float),
        pd.to_numeric(frame["x"], errors="coerce").to_numpy(dtype=float),
        pd.to_numeric(frame["social_norm_term"], errors="coerce").to_numpy(dtype=float),
        params=params if params else None,
    )

