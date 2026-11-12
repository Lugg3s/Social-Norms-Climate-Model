"""Shared, finite-horizon behavioural classes for batch and sensitivity runs.

Thresholds are transparent project conventions, not calibrated empirical values.
Labels describe detected behaviour; they do not establish attractors or tipping.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

import numpy as np


CLASSIFICATION_VERSION = 1
MIN_COMPLETE_CYCLES = 2
COLLAPSE = "Collapse to 0 (no oscillation detected)"
HIGH = "Approach to 1 (no oscillation detected)"
MIDDLE = "Stable intermediate level (no oscillation detected)"
DAMPED = "Damped oscillations"
PERSISTENT = "Persistent oscillations (within observation window)"
UNRESOLVED = "Transitional / unresolved"
INVALID = "Not classified (invalid trajectory)"
FAILED = "Not classified (simulation failed or timed out)"
UNAVAILABLE = "Not classified (classification unavailable)"
CLASS_ORDER = (COLLAPSE, HIGH, MIDDLE, DAMPED, PERSISTENT, UNRESOLVED)
CLASS_COLORS = dict(zip(CLASS_ORDER, ("#d62728", "#2ca02c", "#e6a23c", "#2878b5", "#9467bd", "#7f8c8d")))
CLASS_COLORS.update({INVALID: "#444444", FAILED: "#bbbbbb", UNAVAILABLE: "#dddddd"})


@dataclass(frozen=True)
class ClassificationSettings:
    behaviour_start: float = 217.0
    end_window_years: float = 100.0
    stationary_range: float = 0.02
    low_threshold: float = 0.05
    high_threshold: float = 0.95
    log_amplitude_tolerance: float = 0.15
    event_high_threshold: float = 0.8
    event_low_threshold: float = 0.2
    event_persistence_years: float = 20.0


SETTINGS = ClassificationSettings()


def classification_definition() -> dict[str, Any]:
    return {
        "version": CLASSIFICATION_VERSION,
        "settings": asdict(SETTINGS),
        "classes": list(CLASS_ORDER),
        "scope": "Post-historical trajectory, t >= 217 years; no chaos or tipping-point inference.",
        "oscillation_detection": {
            "minimum_complete_cycles": MIN_COMPLETE_CYCLES,
            "minimum_peak_to_trough_swing": "max(0.02, 0.05 * range(x)) within each evaluated window",
            "turning_points": "Confirm reversals of this size before pairing extrema; sub-threshold counter-movements do not break large cycles.",
        },
        "precedence": "Detected oscillations: persistent end window first, then damping; otherwise stationary end-window level or unresolved.",
        "damping": "At least two full cycles; log(initial/final amplitude) >= 0.15 and positive fitted decay rate.",
        "persistent": "At least two full cycles in the last 100 years and abs(log amplitude ratio) <= 0.15 there; takes precedence over historical damping.",
        "stationary": "Full 100-year end window with range(x) <= 0.02; level uses its time-weighted mean.",
        "collapse_label": "Low stationary end level without detected oscillations; no preceding high level required.",
        "collapse_event": "Separately: >=20 years at x>=0.8, then >=20 years at x<=0.2; recovery requires >=20 years at x>=0.8 afterwards.",
        "censoring": "No permanent-collapse claim beyond the horizon; an unconfirmed final low/high episode is censored.",
        "interpolation": "Piecewise linear for ODE; zero-order hold for annual agent behaviour.",
        "assumptions": "Thresholds are project conventions; finite-horizon stationarity is not asymptotic stability.",
        "sobol": "Descriptive metadata only; not a Sobol output or a row-inclusion criterion.",
    }


def _window(t, x, start, end, stepwise):
    """Include exact window boundaries without inventing samples outside coverage."""
    interior = (t > start) & (t < end)
    times = np.r_[start, t[interior], end]
    if stepwise:
        values = x[np.searchsorted(t, times, side="right") - 1]
    else:
        values = np.interp(times, t, x)
    return times, values


def _mean(t, x, stepwise):
    area = np.sum(x[:-1] * np.diff(t)) if stepwise else np.trapezoid(x, t)
    return float(area / (t[-1] - t[0]))


def _episodes(t, x, threshold, above, stepwise):
    """Maximal intervals above/below a threshold on the stored interpolation."""
    intervals = []
    for i in range(len(t) - 1):
        left_ok = x[i] >= threshold if above else x[i] <= threshold
        right_ok = x[i + 1] >= threshold if above else x[i + 1] <= threshold
        left, right = float(t[i]), float(t[i + 1])
        if stepwise:
            if not left_ok:
                continue
        elif left_ok != right_ok:
            crossing = left + (threshold - x[i]) * (right - left) / (x[i + 1] - x[i])
            if left_ok:
                right = float(crossing)
            else:
                left = float(crossing)
        elif not left_ok:
            continue
        if right <= left:
            continue
        if intervals and abs(intervals[-1][1] - left) <= 1e-9:
            intervals[-1] = (intervals[-1][0], right)
        else:
            intervals.append((left, right))
    final_ok = x[-1] >= threshold if above else x[-1] <= threshold
    if final_ok and (not intervals or abs(intervals[-1][1] - t[-1]) > 1e-9):
        intervals.append((float(t[-1]), float(t[-1])))
    return intervals


def _collapse_events(t, x, stepwise):
    s = SETTINGS
    highs = _episodes(t, x, s.event_high_threshold, True, stepwise)
    lows = _episodes(t, x, s.event_low_threshold, False, stepwise)
    confirmed_highs = [(a, b) for a, b in highs if b - a >= s.event_persistence_years - 1e-9]
    events = []
    used_high = None
    for a, b in lows:
        preceding = [(u, v) for u, v in confirmed_highs if v <= a]
        if preceding and preceding[-1] != used_high and b - a >= s.event_persistence_years - 1e-9:
            events.append((a, b, preceding[-1][1]))
            used_high = preceding[-1]
    first = events[0] if events else None
    recovery = (next((a for a, _ in confirmed_highs if a > first[0]), None)
                if first else None)
    # A short low episode at the horizon may still become a confirmed event.
    pending_low = bool(x[-1] <= s.event_low_threshold and lows and abs(lows[-1][1] - t[-1]) <= 1e-9
                       and lows[-1][1] - lows[-1][0] < s.event_persistence_years
                       and any(b <= lows[-1][0] and (a, b) != used_high for a, b in confirmed_highs
                               if not events or a > events[-1][0]))
    pending_recovery = bool(events and highs and x[-1] >= s.event_high_threshold
                            and abs(highs[-1][1] - t[-1]) <= 1e-9
                            and highs[-1][0] > events[-1][0]
                            and not any(a > events[-1][0] for a, _ in confirmed_highs)
                            and highs[-1][1] - highs[-1][0] < s.event_persistence_years)
    return {
        "collapse_detected": bool(events),
        "collapse_count": len(events),
        "collapse_time": float(first[0]) if first else None,
        "collapse_confirmed_at": float(first[0] + s.event_persistence_years) if first else None,
        "collapse_duration": float(first[0] - first[2]) if first else None,
        "recovery_detected": recovery is not None,
        "recovery_time": float(recovery) if recovery is not None else None,
        "recovery_confirmed_at": float(recovery + s.event_persistence_years) if recovery is not None else None,
        "recovery_pending_at_end": pending_recovery,
        "low_until_end": bool(x[-1] <= s.event_low_threshold and events and abs(events[-1][1] - t[-1]) <= 1e-9),
        "collapse_pending_at_end": pending_low,
    }


def classify_trajectory(t_values, x_values, *, stepwise=False) -> dict[str, Any]:
    """Return one exclusive class plus auditable diagnostics and event flags.

    Keep invalid samples intact: silently deleting them could bridge missing data.
    The ordinary Sobol oscillation targets retain their existing definitions.
    """
    # Runtime import avoids a module cycle: the metric collector calls us too.
    from analysis.simulation_metrics import compute_oscillation_metrics

    result = {
        "behaviour_class": INVALID,
        "classification_version": CLASSIFICATION_VERSION,
        "classification_reason": "Invalid or incomplete trajectory",
        "classification_start": None,
        "classification_end": None,
        "classification_complete_cycles": None,
        "classification_median_period": None,
        "classification_oscillation_detected": None,
        "classification_end_window_complete": False,
        "classification_end_range": None,
        "classification_end_mean": None,
        "classification_end_state": "unresolved",
        "classification_damping_index": None,
        "classification_damping_rate": None,
        "classification_amplitude_ratio": None,
        "classification_end_complete_cycles": None,
        "classification_end_median_period": None,
        "classification_transient_damping": False,
        "collapse_detected": None, "collapse_count": None,
        "collapse_time": None, "collapse_confirmed_at": None, "collapse_duration": None,
        "recovery_detected": None, "recovery_time": None, "recovery_confirmed_at": None,
        "recovery_pending_at_end": None,
        "low_until_end": None, "collapse_pending_at_end": None,
    }
    t, x = np.asarray(t_values, dtype=float), np.asarray(x_values, dtype=float)
    if (t.ndim != 1 or x.ndim != 1 or len(t) != len(x) or len(t) < 2
            or not np.isfinite(t).all() or not np.isfinite(x).all()
            or not np.all(np.diff(t) > 0) or x.min() < -1e-7 or x.max() > 1 + 1e-7):
        return result
    result.update(behaviour_class=UNRESOLVED, classification_reason="Insufficient post-historical observation")
    start, end = max(SETTINGS.behaviour_start, float(t[0])), float(t[-1])
    if end <= start:
        return result
    t, x = _window(t, x, start, end, stepwise)
    result.update(classification_start=start, classification_end=end)
    result.update(_collapse_events(t, x, stepwise))
    # Preserve annual steps and their real durations; do not smooth agent data.
    oscillations = compute_oscillation_metrics(t, x, filter_minor_reversals=True)
    detected = oscillations["n_oscillations"] >= MIN_COMPLETE_CYCLES
    result.update(classification_complete_cycles=int(oscillations["n_oscillations"]),
                  classification_median_period=float(oscillations["median_period"]) if detected else None,
                  classification_oscillation_detected=bool(detected),
                  classification_damping_index=float(oscillations["damping_index"]) if detected else None,
                  classification_damping_rate=float(oscillations["damping_rate"]) if detected else None,
                  classification_amplitude_ratio=float(oscillations["amplitude_ratio"]) if detected else None)
    complete = end - start >= SETTINGS.end_window_years - 1e-9
    result["classification_end_window_complete"] = complete
    if not complete:
        return result
    tail_t, tail_x = _window(t, x, end - SETTINGS.end_window_years, end, stepwise)
    tail_mean, tail_range = _mean(tail_t, tail_x, stepwise), float(np.ptp(tail_x))
    stationary = tail_range <= SETTINGS.stationary_range + 1e-12
    state = ("low" if tail_mean <= SETTINGS.low_threshold + 1e-12 else
             "high" if tail_mean >= SETTINGS.high_threshold - 1e-12 else "intermediate") if stationary else "nonstationary"
    result.update(classification_end_range=tail_range, classification_end_mean=tail_mean,
                  classification_end_state=state)
    if not detected:
        if stationary:
            result.update(behaviour_class={"low": COLLAPSE, "high": HIGH, "intermediate": MIDDLE}[state],
                          classification_reason="No qualifying oscillations; stationary 100-year end window")
        else:
            result["classification_reason"] = "No qualifying oscillations; end window still varies"
        return result
    tail_osc = compute_oscillation_metrics(tail_t, tail_x, filter_minor_reversals=True)
    result["classification_end_complete_cycles"] = int(tail_osc["n_oscillations"])
    result["classification_end_median_period"] = (float(tail_osc["median_period"])
                                                 if np.isfinite(tail_osc["median_period"]) else None)
    history_damped = bool(oscillations["damping_index"] >= SETTINGS.log_amplitude_tolerance
                          and np.isfinite(oscillations["damping_rate"]) and oscillations["damping_rate"] > 0)
    if (tail_osc["n_oscillations"] >= MIN_COMPLETE_CYCLES
            and np.isfinite(tail_osc["amplitude_ratio"])
            and abs(tail_osc["damping_index"]) <= SETTINGS.log_amplitude_tolerance):
        result.update(behaviour_class=PERSISTENT,
                      classification_transient_damping=history_damped,
                      classification_reason="At least two end-window cycles without a clear amplitude trend")
    elif tail_osc["n_oscillations"] >= MIN_COMPLETE_CYCLES and tail_osc["damping_index"] < -SETTINGS.log_amplitude_tolerance:
        result["classification_reason"] = "Growing end-window oscillations"
    elif history_damped:
        result.update(behaviour_class=DAMPED, classification_reason="At least two cycles with declining amplitudes")
    else:
        result["classification_reason"] = ("Oscillatory history; fewer than two complete end-window cycles"
                                           if tail_osc["n_oscillations"] < MIN_COMPLETE_CYCLES else
                                           "Oscillatory history, but persistence or damping is unresolved")
    return result
