"""Checks for the constrained Dynamic2 observation window."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pandas as pd
from SALib.sample import sobol

from simulation.batch_runner import ExperimentGroup, create_run_name, run_single_combination
from model.model_equations import DELAY_NORMS, load_scenarios, resolve_parameters, simulate
from analysis.sensitivity.sensitivity_analysis import build_problem
from analysis.symbolic_analysis import symbolic_social_norm_term


class Dynamic2ConstraintTests(unittest.TestCase):
    def test_scenarios_and_sampled_inputs_always_have_larger_window(self):
        for name, params in load_scenarios().items():
            if params.get("social_norm") in DELAY_NORMS:
                resolved = resolve_parameters(name)
                self.assertGreater(resolved["theta"], resolved["tau"])
                self.assertEqual(resolved["theta"], resolved["tau"] * resolved["rho"])
        for norm in sorted(DELAY_NORMS):
            problem = build_problem(norm)
            self.assertNotIn("theta", problem["names"])
            samples = sobol.sample(problem, 4, calc_second_order=False, seed=42)
            for sample in samples:
                resolved = resolve_parameters({**resolve_parameters("baseline"), "social_norm": norm,
                                               **dict(zip(problem["names"], sample))})
                self.assertGreater(resolved["theta"], resolved["tau"])

    def test_invalid_and_legacy_inputs_fail_before_integration(self):
        for norm in sorted(DELAY_NORMS):
            for name, values in (("tau", (0, -1, np.nan, np.inf)),
                                 ("rho", (0, 1, -1, np.nan, np.inf))):
                for value in values:
                    with self.subTest(norm=norm, name=name, value=value):
                        with self.assertRaises(ValueError):
                            simulate({**resolve_parameters("baseline"), "social_norm": norm, "tau": 1, "rho": 2,
                                      name: value}, simulation_time=1, verbose=False)
            with self.assertRaises(KeyError):
                resolve_parameters({**resolve_parameters("baseline"), "social_norm": norm, "tau": 1, "theta": 2})
            with self.assertRaisesRegex(ValueError, "renamed to rho"):
                resolve_parameters({**resolve_parameters("baseline"), "social_norm": norm, "tau": 1, "a": 3})
        with self.assertRaisesRegex(ValueError, "finite theta"):
            resolve_parameters({**resolve_parameters("baseline"), "social_norm": "dynamic social norm2", "tau": 1e308, "rho": 2})

    def test_derived_window_is_recalculated_after_tau_or_factor_changes(self):
        params = resolve_parameters("dynamic social norm2")
        params.update(tau=3, rho=4)
        resolved = resolve_parameters(params)
        self.assertEqual(resolved["theta"], 12)
        symbols = {str(s) for s in symbolic_social_norm_term("dynamic social norm2").free_symbols}
        self.assertIn("rho", symbols)
        self.assertIn("tau", symbols)
        self.assertNotIn("theta", symbols)

    def test_missing_window_inputs_raise_native_key_errors(self):
        for name in ("tau", "rho"):
            params = resolve_parameters("dynamic social norm2")
            del params[name]
            with self.subTest(parameter=name), self.assertRaises(KeyError) as error:
                resolve_parameters(params)
            self.assertEqual(error.exception.args, (name,))

    def test_simulated_norm_history_uses_the_derived_window(self):
        for norm in sorted(DELAY_NORMS):
            with self.subTest(norm=norm):
                params = dict(social_norm=norm, tau=.25, rho=3, c_dyn=2,
                              c_inj=.5, x_target=.7, beta=0, temperature_factor=0)
                params = {**resolve_parameters("baseline"), **params}
                result = simulate(params, simulation_time=221, coupling_interval=.5,
                                  output_points_per_year=4, simulate_only_x=True, verbose=False)
                self.assertEqual(result["parameters"]["theta"], .75)
                t, x = result["simulation"].t, result["simulation"].x
                expected = 2 * (np.interp(t-.25, t, x) - np.interp(t-1, t, x)) / .75
                if norm != "dynamic social norm2":
                    expected += .5 * (.7-x)
                if norm == "Descriptive, injunctive, dynamic2":
                    expected += 2*x-1
                np.testing.assert_allclose(result["social_norm_term"], expected, atol=1e-14)

    def test_batch_does_not_reuse_legacy_window_results(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            run_dir = root / "test" / "dynamic_social_norm2" / create_run_name("dynamic social norm2", {})
            run_dir.mkdir(parents=True)
            pd.DataFrame({name: [0., 1.] for name in ("t", "T", "x", "social_norm_term", "f_T")}).to_csv(
                run_dir / "time_series.csv", sep=";", index=False)
            (run_dir / "parameters.json").write_text(json.dumps(
                {"social_norm": "dynamic social norm2", "tau": 1, "theta": 1}), encoding="utf-8")
            group = ExperimentGroup("test", ["dynamic social norm2"], {})
            with patch('simulation.batch_runner.simulate') as run:
                with self.assertRaisesRegex(ValueError, "Saved Dynamic2 results"):
                    run_single_combination(resolve_parameters("dynamic social norm2"), {}, group,
                                           root, "dynamic social norm2")
                run.assert_not_called()


if __name__ == "__main__":
    unittest.main()
