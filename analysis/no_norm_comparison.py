"""Paired, descriptive comparisons with the same model without norm influence."""
from __future__ import annotations

import numpy as np
import pandas as pd

from analysis.trajectory_classification import SETTINGS


PROFILE_PREFIX = "comparison_profile_"
PREFIX = "norm_comparison_"
TIME_TOLERANCE = 1e-4  # Years; numerical equality, not substantive equivalence.
SLOPE_RTOL = 1e-4
SLOPE_ATOL = 1e-8  # Fraction/year.
ANNUAL_CHANGE_ZERO_TOLERANCE = 1e-12
LEGACY_TIMING_LABELS = {
    "Only with norm reached": "Reached with norm; not reached in reference",
    "Only without norm reached": "Not reached with norm; reached in reference",
}
TIMING_ORDER = ["Earlier", "Later", "Equal", *LEGACY_TIMING_LABELS.values(),
                "Neither reached", "Not comparable"]
SLOPE_ORDER = ["Steeper", "Flatter", "Equal", "Opposite directions"]


def comparison_definition():
    return {
        "version": 4,
        "enabled_by_default": True,
        "scope": "Paired descriptive classifications only; excluded from Sobol targets and row validity.",
        "reference": "ODE: identical inputs with social_norm='No social norm'. ABM: identical agents, network, seed and annual decisions with social_norm_factor=0.",
        "reference_reuse": "Run-local cache keyed by effective control inputs, simulation settings, numerical versions and source/data hashes. Shared A/B coordinates make continuous references reusable across norms.",
        "climate": "Both runs evolve their own climate under the same settings and forcing; includes indirect climate feedback effects.",
        "start": SETTINGS.behaviour_start,
        "x0_threshold": SETTINGS.low_threshold,
        "x1_threshold": SETTINGS.high_threshold,
        "timing": "First threshold reach after the historical phase; no persistence requirement. Already reached at window start counts at that start.",
        "slope": "max(abs(x(y+1)-x(y))) over complete integer-year intervals after the historical phase, including oscillating trajectories. Save the sign/direction and earliest interval attaining the maximum. ODE: linear interpolation at years; ABM: actual behaviour held until the next decision. Opposite nonzero directions have their own category.",
        "annual_change_zero_tolerance": ANNUAL_CHANGE_ZERO_TOLERANCE,
        "incomplete_passage": "No threshold passage is required. Unavailable only if no complete calendar-year interval is observed or the trajectory is invalid. A constant trajectory has zero annual change.",
        "annual_change_plot": "Four categories over comparable pairs only. Unavailable comparisons remain in the per-run audit, are omitted from this plot, and their share of requested runs is annotated. Timing plots retain Not comparable and use all requested runs.",
        "time_equality_tolerance_years": TIME_TOLERANCE,
        "slope_equality_rtol": SLOPE_RTOL,
        "slope_equality_atol": SLOPE_ATOL,
        "binary_encoding": "True=earlier/steeper, False=later/flatter; missing for equal, non-reached or incomparable cases. Read the categorical status alongside it.",
        "failures": "Failed references do not invalidate the original simulation or its Sobol block.",
    }


def without_norm_parameters(params):
    """Keep all actual inputs; never import another scenario's defaults."""
    reference = dict(params)
    if reference["ABM"]:
        reference["social_norm_factor"] = 0.0
    else:
        reference["social_norm"] = "No social norm"
    return reference


def _crossing(t, x, threshold, above, stepwise):
    indices = np.flatnonzero(x >= threshold if above else x <= threshold)
    if not indices.size:
        return None
    i = int(indices[0])
    if i == 0 or stepwise:
        return float(t[i])
    return float(t[i - 1] + (threshold - x[i - 1]) *
                 (t[i] - t[i - 1]) / (x[i] - x[i - 1]))


def _annual_change(t, x, stepwise):
    """Compare complete calendar years, independently of stored sample spacing."""
    years = np.arange(np.ceil(t[0]), np.floor(t[-1]) + 1)
    if len(years) < 2:
        return None
    values = (x[np.searchsorted(t, years, side="right") - 1] if stepwise else
              np.interp(years, t, x))
    changes = np.diff(values)
    index = int(np.argmax(np.abs(changes)))
    change = float(changes[index])
    if abs(change) <= ANNUAL_CHANGE_ZERO_TOLERANCE:
        change = 0.0
    return {"slope": abs(change), "signed_annual_change": change,
            "direction": "Rising" if change > 0 else "Falling" if change < 0 else "Stationary",
            "slope_start": float(years[index]), "slope_end": float(years[index + 1])}


def transition_profile(t_values, x_values, *, stepwise=False):
    """Small audit record, also available when full time-series saving is disabled."""
    fields = dict(status="Invalid trajectory", first_x0=None, first_x1=None,
                  slope=None, direction=None, slope_status="Unavailable",
                  signed_annual_change=None, slope_start=None, slope_end=None)
    t, x = np.asarray(t_values, float), np.asarray(x_values, float)
    if (t.ndim != 1 or x.ndim != 1 or len(t) != len(x) or len(t) < 2
            or not np.isfinite(t).all() or not np.isfinite(x).all()
            or not np.all(np.diff(t) > 0) or x.min() < -1e-7 or x.max() > 1 + 1e-7):
        return {PROFILE_PREFIX + key: value for key, value in fields.items()}
    start = max(SETTINGS.behaviour_start, float(t[0]))
    if t[-1] <= start:
        fields["status"] = "Insufficient observation"
    else:
        value = float(x[np.searchsorted(t, start, side="right") - 1]) if stepwise else float(np.interp(start, t, x))
        keep = t > start
        t, x = np.r_[start, t[keep]], np.r_[value, x[keep]]
        fields.update(status="Available",
                      first_x0=_crossing(t, x, SETTINGS.low_threshold, False, stepwise),
                      first_x1=_crossing(t, x, SETTINGS.high_threshold, True, stepwise),
                      slope_status="No complete calendar-year interval")
        annual = _annual_change(t, x, stepwise)
        if annual is not None:
            fields.update(annual, slope_status="Available")
    return {PROFILE_PREFIX + key: value for key, value in fields.items()}


def _number(row, name):
    value = row.get(PROFILE_PREFIX + name)
    return float(value) if value is not None and pd.notna(value) and np.isfinite(float(value)) else None


def compare_profiles(actual, reference):
    result = {PREFIX + "reference_status": reference.get("status", "unavailable")}
    available = (actual.get("status") == "completed" and reference.get("status") == "completed"
                 and actual.get(PROFILE_PREFIX + "status") == "Available"
                 and reference.get(PROFILE_PREFIX + "status") == "Available")
    for endpoint in ("x0", "x1"):
        left, right = _number(actual, "first_" + endpoint), _number(reference, "first_" + endpoint)
        binary = None
        if not available:
            label = "Not comparable"
        elif left is None and right is None:
            label = "Neither reached"
        elif right is None:
            label = LEGACY_TIMING_LABELS["Only with norm reached"]
        elif left is None:
            label = LEGACY_TIMING_LABELS["Only without norm reached"]
        elif abs(left - right) <= TIME_TOLERANCE:
            label = "Equal"
        else:
            binary = bool(left < right)
            label = "Earlier" if binary else "Later"
        result.update({PREFIX + endpoint + "_timing": label,
                       PREFIX + endpoint + "_earlier": binary,
                       PREFIX + endpoint + "_time": left,
                       PREFIX + endpoint + "_reference_time": right})
    left, right = _number(actual, "slope"), _number(reference, "slope")
    binary = None
    if not available or left is None or right is None:
        label = "Not comparable"
    elif left > 0 and right > 0 and actual.get(PROFILE_PREFIX + "direction") != reference.get(PROFILE_PREFIX + "direction"):
        label = "Opposite directions"
    elif np.isclose(left, right, rtol=SLOPE_RTOL, atol=SLOPE_ATOL):
        label = "Equal"
    else:
        binary = bool(left > right)
        label = "Steeper" if binary else "Flatter"
    result.update({PREFIX + "slope": label, PREFIX + "slope_steeper": binary,
                   PREFIX + "slope_value": left, PREFIX + "reference_slope_value": right,
                   PREFIX + "slope_direction": actual.get(PROFILE_PREFIX + "direction"),
                   PREFIX + "reference_slope_direction": reference.get(PROFILE_PREFIX + "direction"),
                   PREFIX + "slope_reason": actual.get(PROFILE_PREFIX + "slope_status"),
                   PREFIX + "reference_slope_reason": reference.get(PROFILE_PREFIX + "slope_status")})
    return result


def save_comparison_frequencies(outputs, destination, scenario, *, definition=None):
    """Show timing for all rows and annual changes for comparable pairs only."""
    import matplotlib.pyplot as plt
    from matplotlib.ticker import PercentFormatter
    from pathlib import Path
    import textwrap

    timing = TIMING_ORDER
    definition = comparison_definition() if definition is None else definition
    annual = definition.get("version", 2) >= 3
    slope = SLOPE_ORDER if annual else [*SLOPE_ORDER, "Not comparable"]
    slope_title = "Largest annual change in x" if annual else "10%–90% transition speed"
    panels = [("x0_timing", f"First reach of x ≤ {SETTINGS.low_threshold:.0%}", timing),
              ("x1_timing", f"First reach of x ≥ {SETTINGS.high_threshold:.0%}", timing),
              ("slope", slope_title, slope)]
    rows = []
    model_column = PREFIX + "reference_model"
    models = outputs[model_column].dropna().unique() if model_column in outputs else []
    model = str(models[0]) if len(models) == 1 else "No social norm"
    fig, axes = plt.subplots(3, 1, figsize=(14, 16))
    for ax, (name, title, order) in zip(axes, panels):
        counts = outputs[PREFIX + name].fillna("Not comparable").replace(LEGACY_TIMING_LABELS).value_counts()
        allowed = set(order) | {"Not comparable"}
        if set(counts.index) - allowed:
            raise ValueError(f"Unknown without-norm comparison category: {set(counts.index) - allowed}")
        comparable_only = annual and name == "slope"
        excluded = int(counts.get("Not comparable", 0)) if comparable_only else 0
        denominator = len(outputs) - excluded
        for label in order:
            count = int(counts.get(label, 0))
            rows.append(dict(comparison=name, category=label, count=count,
                             total_requested_runs=len(outputs),
                             frequency_denominator=denominator, excluded_runs=excluded,
                             relative_frequency=count / denominator if denominator else
                             float("nan") if comparable_only else 0.0))
        heights = [counts.get(label, 0) / denominator if denominator else 0.0 for label in order]
        ax.bar(range(len(order)), heights, color=["#999999" if label == "Not comparable" else "#4c78a8"
                                                for label in order])
        for i, height in enumerate(heights if denominator else []):
            ax.annotate(f"{height:.1%}", (i, height), xytext=(0, -6 if height > .94 else 4),
                        textcoords="offset points", ha="center", va="top" if height > .94 else "bottom")
        ax.set_xticks(range(len(order)), [textwrap.fill(label, 18) for label in order])
        ax.set_ylim(0, 1)
        ax.yaxis.set_major_formatter(PercentFormatter(1))
        ax.set_ylabel("Share of comparable runs" if comparable_only else "Share of all requested runs")
        if comparable_only and not denominator:
            ax.text(.5, .5, "No comparable runs", transform=ax.transAxes, ha="center")
        if comparable_only and excluded:
            ax.text(.02, .96, f"Unavailable comparisons omitted: {excluded / len(outputs):.1%} of requested runs",
                    transform=ax.transAxes, va="top", fontsize=9)
        ax.set_title(title + "\nReference: " + model)
        ax.grid(axis="y", alpha=.2)
        ax.set_axisbelow(True)
    fig.suptitle(f"{scenario}\nReference comparisons | {len(outputs):,} requested runs", fontsize=15)
    if annual:
        oscillation_note = ("including oscillations" if definition.get("version", 2) >= 4 else
                            "saved results excluded oscillations")
        slope_note = (f"Annual changes use complete calendar-year intervals ({oscillation_note}); "
                      "percentages use comparable pairs only.")
    else:
        slope_note = "Transition speed uses complete passages in matching directions."
    weight = "eta" if "with eta=0" in definition.get("reference", "") else "social_norm_factor"
    fig.text(.5, .01, "First reaches after 2017; missing thresholds are separate categories. "
             + slope_note + "\n"
             f"ABM reference: {weight} = 0 with the same agents and annual decisions. "
             "Descriptive sample shares, not real-world probabilities.", ha="center", fontsize=9)
    fig.tight_layout(rect=(0, .045, 1, .95), h_pad=3)
    destination = Path(destination)
    frequencies = pd.DataFrame(rows)
    frequencies.to_csv(destination / "without_norm_comparison_frequencies.csv", sep=";", index=False)
    for suffix in ("svg", "png"):
        fig.savefig(destination / f"without_norm_comparison_frequencies.{suffix}", dpi=180)
    plt.close(fig)
    return frequencies
