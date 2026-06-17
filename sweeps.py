import numpy as np

from model_equations import simulate
from metrics import auc, tipping_year


def sweep_auc_diff_over_k_rmax(k_values, r_max_values, t_critical=3, index=2):
    """Compute matrix of AUC differences between runs with and without
    runaway dynamics over grids of `k` and `r_max`."""
    result = np.zeros((len(r_max_values), len(k_values)))

    for i, r_max in enumerate(r_max_values):
        for j, k in enumerate(k_values):
            time1, _, _, _, _, temp1, _ = simulate(k, 1, 1, r_max, t_critical, index)
            time2, _, _, _, _, temp2, _ = simulate(k, 1, 1, 0, t_critical, index)
            result[i, j] = auc(temp1, time1) - auc(temp2, time2)

    return result


def sweep_auc_over_beta_rmax(beta_values, r_max_values, k=0.01, delta=1, t_critical=2, index=2):
    """Compute AUC for temperature over grids of `beta` and `r_max`."""
    result = np.zeros((len(r_max_values), len(beta_values)))

    for i, r_max in enumerate(r_max_values):
        for j, beta in enumerate(beta_values):
            time1, _, _, _, _, temp1, _ = simulate(k, beta, delta, r_max, t_critical, index)
            result[i, j] = auc(temp1, time1)

    return result


def sweep_auc_diff_over_delta_rmax(delta_values, r_max_values, k=0.01, beta=1, t_critical=3, index=2):
    """Compute AUC differences between runaway and no-runaway across `delta`
    and `r_max` parameter grids."""
    result = np.zeros((len(r_max_values), len(delta_values)))

    for i, r_max in enumerate(r_max_values):
        for j, delta in enumerate(delta_values):
            time1, _, _, _, _, temp1, _ = simulate(k, beta, delta, r_max, t_critical, index)
            time2, _, _, _, _, temp2, _ = simulate(k, beta, delta, 0, t_critical, index)
            result[i, j] = auc(temp1, time1) - auc(temp2, time2)

    return result


def sweep_auc_diff_over_k_tcritical(k_values, t_critical_values, r_max=5, index=2):
    """Compute AUC differences across `k` and critical temperature grids."""
    result = np.zeros((len(t_critical_values), len(k_values)))

    for i, t_critical in enumerate(t_critical_values):
        for j, k in enumerate(k_values):
            time1, _, _, _, _, temp1, _ = simulate(k, 1, 1, r_max, t_critical, index)
            time2, _, _, _, _, temp2, _ = simulate(k, 1, 1, 0, t_critical, index)
            result[i, j] = auc(temp1, time1) - auc(temp2, time2)

    return result


def sweep_tipping_year_over_k_rmax(k_values, r_max_values, t_critical=3, index=2, threshold=1.1):
    """Compute the year of tipping (if any) for grids of `k` and `r_max`.
    Results are `nan` where tipping does not occur."""
    result = np.full((len(r_max_values), len(k_values)), np.nan, dtype=float)

    for i, r_max in enumerate(r_max_values):
        for j, k in enumerate(k_values):
            _, _, _, _, _, temp1, _ = simulate(k, 1, 1, r_max, t_critical, index)
            _, _, _, _, _, temp2, _ = simulate(k, 1, 1, 0, t_critical, index)
            year = tipping_year(temp1, temp2, threshold=threshold)
            if year is not None:
                result[i, j] = year

    return result


def sweep_peak_temp_over_k_rmax(k_values, r_max_values, t_critical=3, index=2):
    """Return peak temperature reached for each (`k`, `r_max`) combination."""
    result = np.zeros((len(r_max_values), len(k_values)))

    for i, r_max in enumerate(r_max_values):
        for j, k in enumerate(k_values):
            _, _, _, _, _, temp1, _ = simulate(k, 1, 1, r_max, t_critical, index)
            result[i, j] = np.max(temp1)

    return result


def sweep_auc_diff_over_beta_rmax(beta_values, r_max_values, k=0.1, delta=3, t_critical=2, index=2):
    """Compute AUC differences between runoff and baseline across `beta` and
    `r_max` parameter grids (alternate default parameters)."""
    result = np.zeros((len(r_max_values), len(beta_values)))

    for i, r_max in enumerate(r_max_values):
        for j, beta in enumerate(beta_values):
            time1, _, _, _, _, temp1, _ = simulate(k, beta, delta, r_max, t_critical, index)
            time2, _, _, _, _, temp2, _ = simulate(k, beta, delta, 0, t_critical, index)
            result[i, j] = auc(temp1, time1) - auc(temp2, time2)

    return result
