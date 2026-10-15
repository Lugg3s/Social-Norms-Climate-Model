import unittest

import numpy as np
from scipy.integrate import solve_ivp

from model.model_equations import resolve_parameters, simulate
from model.solvers import bdf, get_solver, rk4


class SolverTests(unittest.TestCase):
    def test_rk4_order_and_fixed_nodes(self):
        errors = []
        for dt in (0.1, 0.05):
            sol = rk4(lambda t, y: y, (0., 1.), [1.], [0., 1.], dt=dt)
            np.testing.assert_allclose(np.diff(sol.internal_t), dt)
            errors.append(abs(sol.y[0, -1] - np.e))
        self.assertGreater(errors[0] / errors[1], 14)

    def test_short_boundary_step(self):
        sol = rk4(lambda t, y: np.ones_like(y), (0., 0.25), [0.],
                  [0., 0.07, 0.25], dt=0.1)
        np.testing.assert_allclose(sol.internal_t, [0., 0.1, 0.2, 0.25])
        np.testing.assert_allclose(sol.y[0], sol.t)

    def test_bdf_preserves_original_calls(self):
        fun = lambda t, y: -y
        for retry in (False, True):
            options = (dict(rtol=1e-9, atol=1e-11, max_step=0.05) if retry
                       else dict(rtol=1e-7, atol=1e-9))
            expected = solve_ivp(fun, (0., 1.), [1.], method="BDF",
                                 t_eval=[0., 0.5, 1.], **options)
            actual = bdf(fun, (0., 1.), [1.], [0., 0.5, 1.], retry=retry)
            np.testing.assert_array_equal(actual.y, expected.y)

    def test_validation(self):
        for name, dt in (("missing", None), ("RK4", None), ("RK4", 0),
                         ("RK4", float("nan"))):
            with self.assertRaises(ValueError):
                get_solver(name, dt)

    def test_adaptive_solvers_ignore_dt(self):
        for solver in ("BDF", "LSODA"):
            options = dict(solver=solver, simulation_time=0.1, verbose=False)
            expected = simulate(**options)["simulation"]
            for dt in (0.01, 0, -1):
                with self.subTest(solver=solver, dt=dt):
                    actual = simulate(**options, dt=dt)["simulation"]
                    np.testing.assert_array_equal(np.asarray(actual), np.asarray(expected))

    def test_lsoda_stiff_equation_and_retry(self):
        name, integrate = get_solver("lsoda", None)
        self.assertEqual(name, "LSODA")
        for retry in (False, True):
            sol = integrate(lambda t, y: -1000 * (y - np.cos(t)) - np.sin(t),
                            (0., 1.), [1.], np.linspace(0, 1, 21), retry=retry)
            self.assertTrue(sol.success, sol.message)
            np.testing.assert_allclose(sol.y[0], np.cos(sol.t), atol=1e-6)

    def test_lsoda_delayed_model(self):
        params = {**resolve_parameters("dynamic social norm2"), "rho": 2,
                  "tau": 0.2, "c_dyn": 0.5}
        options = dict(extension=params, simulation_time=220, simulate_only_x=True,
                       coupling_interval=1, output_points_per_year=10, verbose=False)
        expected = simulate(**options, solver="BDF")["simulation"]
        result = simulate(**options, solver="LSODA")
        self.assertEqual(result["solver_settings"]["solver"], "LSODA")
        np.testing.assert_allclose(result["simulation"].x, expected.x, atol=2e-6)

    def test_lsoda_full_model(self):
        options = dict(simulation_time=2, verbose=False)
        expected = simulate(**options, solver="BDF")["simulation"]
        actual = simulate(**options, solver="LSODA")["simulation"]
        np.testing.assert_allclose(np.asarray(actual)[1:], np.asarray(expected)[1:],
                                   rtol=2e-4, atol=2e-4)

    def test_model_comparison(self):
        options = dict(simulation_time=0.00000001, verbose=False)
        adaptive = simulate(**options)["simulation"]
        fixed = simulate(**options, solver="RK4", dt=0.0000000001)["simulation"]
        np.testing.assert_allclose(np.asarray(fixed)[1:], np.asarray(adaptive)[1:],
                                   rtol=2e-4, atol=2e-4)

    def test_theta_equals_dt_output_independence(self):
        params = {**resolve_parameters("dynamic social norm2"), "rho": 2,
                  "tau": 0.005, "c_dyn": 0.1}
        options = dict(extension=params, simulation_time=220, simulate_only_x=True, solver="RK4",
                       dt=0.01, coupling_interval=1, verbose=False)
        coarse = simulate(**options, output_points_per_year=10)["simulation"]
        fine = simulate(**options, output_points_per_year=100)["simulation"]
        np.testing.assert_allclose(coarse.x, fine.x[::10], rtol=0, atol=1e-14)


if __name__ == "__main__":
    unittest.main()
