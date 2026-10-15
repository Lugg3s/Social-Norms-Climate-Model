"""Check delayed-history reuse against an independent, uncached history."""
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import numpy as np

import model.model_equations as model


class HistoryCacheTests(unittest.TestCase):
    def test_history_updates_and_pruning_for_all_solvers(self):
        for solver in ("BDF", "LSODA", "RK4"):
            with self.subTest(solver=solver):
                times, values = [0.], [.3]

                def delayed(q, t, x):
                    if q > times[-1]:
                        return values[-1] + (q-times[-1])/(t-times[-1]) * (x-values[-1])
                    return np.interp(q, times, values)

                def integrate(fun, span, y0, t_eval, *, on_step=None, **kwargs):
                    start, end = span
                    # Repeated queries exercise reuse; successive intervals
                    # and RK nodes exercise invalidation. Short delays also
                    # force the model to prune history during this run.
                    for offset in (.25, .5, .75, 1.):
                        t = start + offset
                        state = y0.copy()
                        state[5] += .1 * offset
                        x = state[5]
                        norm = (delayed(t-.25, t, x) - delayed(t-.75, t, x)) / .5
                        expected = .05 * x * (1-x) * norm
                        for _ in range(2):
                            self.assertAlmostEqual(fun(t, state)[5], expected, places=14)
                        if solver == "RK4" and offset in (.5, 1.):
                            on_step(t, state)
                            times.append(t)
                            values.append(x)
                    states = np.repeat(y0[:, None], len(t_eval), axis=1)
                    states[5] += .1 * (t_eval-start)
                    if solver != "RK4":
                        first = 0 if len(times) == 1 else 1
                        times.extend(t_eval[first:].tolist())
                        values.extend(states[5, first:].tolist())
                    return SimpleNamespace(t=t_eval, y=states, success=True)

                params = dict(social_norm="dynamic social norm2", x0=.3, kappa=.05,
                              rho=2, tau=.25, c_dyn=1, beta=0,
                              temperature_factor=0, social_norm_factor=1)
                params = {**model.resolve_parameters("baseline"), **params}
                with patch.object(model, "get_solver", return_value=(solver, integrate)), \
                     patch.object(model, "_make_time_breaks", return_value=np.arange(217., 222.)):
                    model.simulate(params, simulation_time=221, coupling_interval=1,
                                   output_points_per_year=4, simulate_only_x=True,
                                   solver=solver, dt=.5 if solver == "RK4" else None,
                                   verbose=False)


if __name__ == "__main__":
    unittest.main()
