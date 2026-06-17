import numpy as np


def auc(y, x):
    """Return the area under curve for `y` sampled at points `x` using
    the trapezoidal rule."""
    dx = x[1] - x[0]
    return np.trapz(y, dx=dx)


def tipping_year(temp_with_runaway, temp_baseline, start_year=1800, samples_per_year=100, threshold=1.1):
    """Return the calendar year when `temp_with_runaway` first exceeds
    `threshold * temp_baseline`. Returns `None` if threshold is never met."""
    condition = temp_with_runaway[1:] >= threshold * temp_baseline[1:]
    if not np.any(condition):
        return None

    first_idx = np.argmax(condition) + 1
    return start_year + (first_idx / samples_per_year)
