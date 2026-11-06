"""Checks for the constrained Dynamic2 observation window."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pandas as pd
from SALib.sample import sobol

from simulation.batch_runner import ExperimentGroup, create_run_name, run_single_combination, sanitize_name
from model.model_equations import DELAY_NORMS, load_scenarios, resolve_parameters, simulate
from analysis.sensitivity.sensitivity_analysis import build_problem, zero_boundary_parameters
from analysis.parameter_ranges import default_sensitivity_scenarios
from analysis.symbolic_analysis import SUPPORTED_NORMS, symbolic_social_norm_term
from analysis.sensitivity.sensitivity_plots import _ranking_social_norm_term
from analysis.sensitivity.sensitivity_numerical_probe import migrate_archived_dynamic2


class Dynamic2ConstraintTests(unittest.TestCase):
    def test_descriptive_weight_is_explicit_and_old_scenario_is_retired(self):
        for name, params in load_scenarios().items():
            self.assertNotEqual(params['social_norm'], 'Injunctive, dynamic2')
            if params['social_norm'] == 'Descriptive, injunctive, dynamic2':
                self.assertEqual(params['c_desc'], 1, name)
        for registry in (SUPPORTED_NORMS, DELAY_NORMS, default_sensitivity_scenarios()):
            self.assertNotIn('Injunctive, dynamic2', registry)
        problem = build_problem('Descriptive, injunctive, dynamic2')
        self.assertEqual(problem['bounds'][problem['names'].index('c_desc')], [0., 1.])
        self.assertNotIn('c_desc', zero_boundary_parameters(problem))
        self.assertIn('c_inj', zero_boundary_parameters(problem))
        params = resolve_parameters('Descriptive, injunctive, dynamic2')
        del params['c_desc']
        with self.assertRaises(KeyError) as error:
            simulate(params, simulation_time=1, verbose=False)
        self.assertEqual(error.exception.args, ('c_desc',))

    def test_zero_weight_disables_descriptive_drive_during_integration(self):
        params = resolve_parameters('Descriptive, injunctive, dynamic2')
        params.update(c_inj=0, c_dyn=0, beta=0, temperature_factor=0, x0=.3)
        for weight in (0, .4, 1):
            result = simulate({**params, 'c_desc': weight}, simulation_time=220,
                              coupling_interval=.5, simulate_only_x=True, verbose=False)
            x_values = result['simulation'].x
            np.testing.assert_allclose(result['social_norm_term'], weight*(2*x_values-1))
            if weight == 0:
                np.testing.assert_allclose(x_values, .3, atol=1e-14)
            else:
                self.assertLess(x_values[-1], .3)

    def test_archived_delay_equations_keep_their_original_coefficient(self):
        import sympy as sp
        norm = 'Descriptive, injunctive, dynamic2'
        current = symbolic_social_norm_term(norm)
        c_desc = next(s for s in current.free_symbols if s.name == 'c_desc')
        for source, weight in ((norm, 1), ('Injunctive, dynamic2', 0)):
            self.assertEqual(sp.simplify(_ranking_social_norm_term(source, {'rho'}) - current.subs(c_desc, weight)), 0)
            original = {'social_norm': source, 'c_dyn': 2}
            migrated = migrate_archived_dynamic2(original)
            self.assertEqual(migrated['c_desc'], weight)
            self.assertEqual(migrated['social_norm'], norm)
            self.assertNotIn('c_desc', original)
        self.assertEqual(_ranking_social_norm_term(norm, {'rho', 'c_desc'}), current)
        self.assertEqual(migrate_archived_dynamic2({'social_norm': norm, 'c_desc': .3})['c_desc'], .3)

    def test_scenarios_and_sampled_inputs_always_have_larger_window(self):
        for name, params in load_scenarios().items():
            if params.get("social_norm") in DELAY_NORMS:
                resolved = resolve_parameters(name)
                self.assertNotIn("theta", resolved)
                self.assertGreater(resolved["tau"] * resolved["rho"], resolved["tau"])
        for norm in sorted(DELAY_NORMS):
            problem = build_problem(norm)
            self.assertNotIn("theta", problem["names"])
            samples = sobol.sample(problem, 4, calc_second_order=False, seed=42)
            for sample in samples:
                resolved = resolve_parameters({**resolve_parameters("baseline"), "social_norm": norm,
                                               **dict(zip(problem["names"], sample))})
                self.assertNotIn("theta", resolved)
                self.assertGreater(resolved["tau"] * resolved["rho"], resolved["tau"])

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
        with self.assertRaisesRegex(ValueError, "finite observation window"):
            resolve_parameters({**resolve_parameters("baseline"), "social_norm": "dynamic social norm2", "tau": 1e308, "rho": 2})

    def test_window_uses_tau_and_rho_without_retaining_redundant_theta(self):
        params = resolve_parameters("dynamic social norm2")
        params.update(tau=3, rho=4, theta=999)
        resolved = resolve_parameters(params)
        self.assertNotIn("theta", resolved)
        self.assertEqual(resolved["tau"] * resolved["rho"], 12)
        self.assertEqual(params["theta"], 999)  # Loading old input does not mutate it.
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
                              c_desc=.4, c_inj=.5, x_target=.7, beta=0, temperature_factor=0)
                params = {**resolve_parameters("baseline"), **params}
                result = simulate(params, simulation_time=221, coupling_interval=.5,
                                  output_points_per_year=4, simulate_only_x=True, verbose=False)
                self.assertNotIn("theta", result["parameters"])
                t, x = result["simulation"].t, result["simulation"].x
                expected = 2 * (np.interp(t-.25, t, x) - np.interp(t-1, t, x)) / .75
                if norm != "dynamic social norm2":
                    expected += .5 * (.7-x)
                if norm == "Descriptive, injunctive, dynamic2":
                    expected += .4*(2*x-1)
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

    def test_batch_does_not_reuse_different_or_missing_descriptive_weight(self):
        params = resolve_parameters('Descriptive, injunctive, dynamic2')
        group = ExperimentGroup('test', ['Descriptive, injunctive, dynamic2'], {})
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            run_dir = root / 'test' / sanitize_name(group.scenarios[0]) / create_run_name(group.scenarios[0], {})
            run_dir.mkdir(parents=True)
            pd.DataFrame({name: [0., 1.] for name in ('t', 'T', 'x', 'social_norm_term', 'f_T')}).to_csv(
                run_dir / 'time_series.csv', sep=';', index=False)
            for previous in (None, 0):
                saved = {**params}
                if previous is None:
                    del saved['c_desc']
                else:
                    saved['c_desc'] = previous
                (run_dir / 'parameters.json').write_text(json.dumps(saved), encoding='utf-8')
                with patch('simulation.batch_runner.simulate') as run:
                    with self.assertRaisesRegex(ValueError, 'c_desc'):
                        run_single_combination(params, {}, group, root, group.scenarios[0])
                    run.assert_not_called()


if __name__ == "__main__":
    unittest.main()
