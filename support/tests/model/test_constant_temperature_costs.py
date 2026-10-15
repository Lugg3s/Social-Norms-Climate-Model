"""The optional constant response must reach ODEs, annual agents and diagnostics."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np

import analysis.sensitivity.sensitivity_analysis as sensitivity
from model.model_equations import resolve_parameters, simulate
from analysis.sensitivity.sensitivity_plots import _ranking_formula_content


AGENTS = "Observation-based / intention motivation (agents)"


class ConstantTemperatureCostsTests(unittest.TestCase):
    def test_cli_flag_is_optional_and_reaches_the_runner(self):
        with patch('sys.argv', ['sensitivity_analysis.py']):
            self.assertFalse(sensitivity.parse_args().constant_temperature_costs)
        with tempfile.TemporaryDirectory() as folder:
            argv = ['sensitivity_analysis.py', '--constant-temperature-costs',
                    '--scenarios', 'baseline', '--workers', '1', '--output-root', folder]
            with patch('sys.argv', argv), patch.object(sensitivity, '_run_scenarios') as runner:
                sensitivity.main()
            self.assertTrue(runner.call_args.args[2].constant_temperature_costs)

    def test_ode_matches_constant_payoff_logistic_solution(self):
        params = {**resolve_parameters('baseline'), 'social_norm_factor': 0,
                  'temperature_factor': 1.2, 'beta': .2, 'kappa': .2, 'x0': .3}
        options = dict(simulation_time=220, coupling_interval=1, output_points_per_year=4,
                       simulate_only_x=True, verbose=False, constant_temperature_costs=True)
        result = simulate(params, **options)
        time = result['simulation'].t
        expected = 1 / (1 + (1 - .3) / .3 * np.exp(-.2 * (1.2 - .2) * np.maximum(time - 217, 0)))
        np.testing.assert_allclose(result['simulation'].x, expected, rtol=0, atol=2e-6)
        np.testing.assert_array_equal(result['f_T'], np.ones_like(time))
        # Even a very different sigmoid must have no effect in this mode.
        changed = simulate({**params, 'f_max': 20, 'omega': .1, 'T_c': -10}, **options)
        np.testing.assert_array_equal(result['simulation'].x, changed['simulation'].x)

    def test_default_and_explicit_false_keep_the_sigmoid(self):
        params = resolve_parameters('baseline')
        options = dict(simulation_time=3, coupling_interval=1, output_points_per_year=2, verbose=False)
        result = simulate(params, **options)
        explicit = simulate(params, **options, constant_temperature_costs=False)
        np.testing.assert_array_equal(np.asarray(result['simulation']), np.asarray(explicit['simulation']))
        temperature = result['simulation'].T
        expected = params['f_max'] / (1 + np.exp(-params['omega'] * (temperature - params['T_c'])))
        np.testing.assert_array_equal(result['f_T'], expected)
        self.assertGreater(np.ptp(temperature), 0)
        constant = simulate(params, **options, constant_temperature_costs=True)
        self.assertGreater(np.ptp(constant['simulation'].T), 0)
        np.testing.assert_array_equal(constant['f_T'], np.ones_like(constant['simulation'].t))

    def test_agents_use_constant_response_without_clipping_intentions(self):
        params = {**resolve_parameters(AGENTS), 'beta': 0, 'temperature_factor': .6,
                  'eta': 0, 'phi': .5, 'psi': .5, 'network_size': 3}
        options = dict(simulation_time=218, n_agents=11, coupling_interval=1,
                       output_points_per_year=2, simulate_only_x=True, verbose=False)
        constant = simulate(params, **options, constant_temperature_costs=True)
        regular = simulate(params, **options)
        np.testing.assert_allclose(constant['agent_history']['behavioral_intention'], .6, rtol=0, atol=1e-15)
        np.testing.assert_array_equal(constant['agent_history']['actual_behavior'][1:], 1)
        np.testing.assert_array_equal(regular['agent_history']['actual_behavior'][1:], 0)
        np.testing.assert_array_equal(constant['f_T'], np.ones_like(constant['simulation'].t))

    def test_samples_and_zero_boundary_checks_forward_and_record_the_mode(self):
        params = resolve_parameters('baseline')
        config = sensitivity.SensitivityConfig(constant_temperature_costs=True)
        metrics = {name: .3 for name in sensitivity.SENSITIVITY_OUTPUTS}
        metrics.update(time_to_elimination=float('nan'), bool_x95=False, n_oscillations=0)
        # Execute boundary tasks here so the simulation mock is visible; actual
        # spawned workers are covered by the serial/parallel agent comparison.
        def inline_map(function, tasks, workers, timeout):
            for index, task in enumerate(tasks):
                yield index, {'status': 'completed', 'result': function(task)}

        with tempfile.TemporaryDirectory() as folder, \
             patch.object(sensitivity, 'simulate', return_value={}) as model, \
             patch.object(sensitivity, 'bounded_map', side_effect=inline_map), \
             patch.object(sensitivity, 'compute_run_metrics', return_value=metrics):
            job = (params, ['temperature_factor'], np.array([2.]), config)
            directory = Path(folder)
            sensitivity._run_tracked_sample(job, 0, directory)
            sensitivity.run_zero_boundary_cases(params, {'names': ['temperature_factor'],
                                                        'bounds': [[0., 5.]]}, config, directory)
            self.assertEqual(model.call_count, 2)
            self.assertTrue(all(call.kwargs['constant_temperature_costs'] for call in model.call_args_list))
            for path in directory.glob('*.jsonl'):
                event = json.loads(path.read_text().splitlines()[0])
                self.assertTrue(event['config']['constant_temperature_costs'])

    def test_append_accepts_only_matching_modes_including_old_sigmoid_metadata(self):
        metadata = {'outputs_for_ranking': sensitivity.SENSITIVITY_OUTPUTS,
                    'elimination_time_definition': {'method': 'zero_if_not_reached'},
                    'oscillations_per_500_years_definition': {
                        'minimum_complete_cycles': 2,
                        'method': 'zero_below_minimum_otherwise_scaled_complete_cycle_count'}}
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder); (root / 'baseline').mkdir()
            path = root / 'baseline' / 'metadata.json'
            path.write_text(json.dumps(metadata))
            sensitivity._validate_append_scenarios(root, ['Dynamic social norm'])
            with self.assertRaisesRegex(ValueError, 'different constant-temperature-costs mode'):
                sensitivity._validate_append_scenarios(root, ['Dynamic social norm'], constant_temperature_costs=True)
            metadata['constant_temperature_costs'] = True
            path.write_text(json.dumps(metadata))
            sensitivity._validate_append_scenarios(root, ['Dynamic social norm'], constant_temperature_costs=True)
            with self.assertRaisesRegex(ValueError, 'different constant-temperature-costs mode'):
                sensitivity._validate_append_scenarios(root, ['Dynamic social norm'])

    def test_ranking_formulas_display_the_response_used_for_both_model_types(self):
        for scenario in ['baseline', AGENTS]:
            with self.subTest(scenario=scenario):
                rows, notes = _ranking_formula_content({'scenario': scenario, 'constant_temperature_costs': True},
                                                       resolve_parameters(scenario))
                self.assertIn('f_T(T)=1', rows)
                self.assertFalse(any(r'\exp' in row for row in rows))
                self.assertTrue(any('temperature_factor' in note for note in notes))


if __name__ == '__main__':
    unittest.main()
