"""Interval integrators sharing the solve_ivp result interface.

Add future methods to SOLVERS; model coupling and state validation stay in
model_equations.py. Output sampling never controls RK4 integration steps.
"""
from types import SimpleNamespace

import numpy as np
from scipy.integrate import solve_ivp


def bdf(fun, t_span, y0, t_eval, *, dt=None, on_step=None, retry=False):
    return _adaptive("BDF", fun, t_span, y0, t_eval, retry=retry)


def lsoda(fun, t_span, y0, t_eval, *, dt=None, on_step=None, retry=False):
    """SciPy LSODA, with the same accuracy and retry settings as BDF."""
    return _adaptive("LSODA", fun, t_span, y0, t_eval, retry=retry)


def _adaptive(method, fun, t_span, y0, t_eval, *, retry):
    options = dict(rtol=1e-7, atol=1e-9)
    if retry:
        options.update(rtol=1e-9, atol=1e-11,
                       max_step=min(0.05, t_span[1] - t_span[0]))
    return solve_ivp(fun, t_span, y0, method=method, t_eval=t_eval, **options)


def rk4(fun, t_span, y0, t_eval, *, dt, on_step=None, retry=False):
    """Classical RK4 with linear output interpolation and accepted-step history.

The last step is shortened only to land on a coupling/end boundary.
No adaptive retries are performed. Intermediate RK stages are not committed
to history; delayed queries within the active step use the model's fallback.
"""
    start, end = t_span
    times = [float(start)]
    states = [np.asarray(y0, dtype=float).copy()]
    index = 1
    while times[-1] < end:
        t, y = times[-1], states[-1]
        next_t = min(start + index * dt, end)
        if np.isclose(next_t, end, rtol=0, atol=16 * np.spacing(max(1., abs(end)))):
            next_t = end
        h = next_t - t
        if h <= 0:
            raise ValueError("dt is too small to advance time")
        k1 = fun(t, y)
        k2 = fun(t + h / 2, y + h * k1 / 2)
        k3 = fun(t + h / 2, y + h * k2 / 2)
        k4 = fun(next_t, y + h * k3)
        next_y = y + h * (k1 + 2*k2 + 2*k3 + k4) / 6
        if not np.all(np.isfinite(next_y)):
            raise RuntimeError(f"RK4 produced non-finite values at t={next_t}; reduce dt")
        times.append(next_t)
        states.append(next_y)
        if on_step is not None:
            on_step(next_t, next_y)
        index += 1
    nodes = np.asarray(states).T
    values = np.asarray([np.interp(t_eval, times, row) for row in nodes])
    return SimpleNamespace(t=np.asarray(t_eval), y=values, success=True,
                           message="", internal_t=np.asarray(times), internal_y=nodes)


SOLVERS = {"BDF": bdf, "LSODA": lsoda, "RK4": rk4}
ADAPTIVE_SOLVERS = {"BDF", "LSODA"}


def get_solver(name, dt):
    key = str(name).upper()
    if key not in SOLVERS:
        raise ValueError(f"Unknown solver {name!r}; choose from {', '.join(SOLVERS)}")
    if key == "RK4" and (dt is None or not np.isfinite(dt) or dt <= 0):
        raise ValueError("RK4 requires a finite positive dt (in years)")
    return key, SOLVERS[key]
