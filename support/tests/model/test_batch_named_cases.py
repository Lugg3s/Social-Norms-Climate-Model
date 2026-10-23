"""Explicit batch cases must reproduce selected samples without a Cartesian sweep."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import pandas as pd

from model.model_equations import resolve_parameters
import simulation.batch_runner as batch
from utils.paths import CONFIG_DIR


class NamedBatchCasesTests(unittest.TestCase):
    def setUp(self):
        self.group = next(g for g in batch.load_default_groups() if g.name == 'dynamic2_top5_sensi128')
        self.snapshot = json.loads((CONFIG_DIR / 'batch_dynamic2_top5_sensi128.json').read_text(encoding='utf-8'))

    def test_exact_five_complete_cases_and_saved_numerical_settings(self):
        cases = batch.build_group_combinations(self.group)
        self.assertEqual(len(cases), 5)
        labels = [batch.group_run_name(self.group, self.group.scenarios[0], case) for case in cases]
        self.assertEqual(labels, ['sample_000834', 'sample_000282', 'sample_000279', 'sample_000284', 'sample_000276'])
        self.assertEqual(self.group.simulation_time, 600)
        self.assertEqual(self.group.coupling_interval, .1)
        self.assertEqual(self.group.output_points_per_year, 24)
        self.assertEqual(self.group.seed, 42)
        self.assertFalse(self.group.constant_temperature_costs)
        for case in cases:
            self.assertEqual(len(case), 10)
            params = resolve_parameters({**resolve_parameters('baseline'), 'f_max': 999,
                                         **self.group.fixed_overrides, **case})
            self.assertEqual(params['f_max'], 5)
            self.assertNotIn('theta', params)
        self.assertEqual(set(batch.get_group_parameter_names(self.group)), set(cases[0]))

    def test_normal_cartesian_groups_still_work_and_mixed_modes_fail(self):
        normal = batch.ExperimentGroup('test', ['baseline'], {'beta': [1, 2], 'kappa': [.1, .2]})
        self.assertEqual(len(batch.build_group_combinations(normal)), 4)
        mixed = batch.ExperimentGroup('test', ['baseline'], {'beta': [1, 2]}, parameter_sets={'one': {'beta': 1}})
        with self.assertRaises(ValueError):
            batch.build_group_combinations(mixed)

    def test_runner_schedules_exactly_five_and_records_the_case_manifest(self):
        def fake_run(**kwargs):
            return {'status': 'ok', 'scenario': kwargs['scenario_name'], 'group': self.group.name,
                    'run_name': batch.group_run_name(self.group, kwargs['scenario_name'], kwargs['sweep_values']),
                    **kwargs['sweep_values']}

        with tempfile.TemporaryDirectory() as directory, \
                patch.object(batch, 'run_single_combination', side_effect=fake_run) as run, \
                patch.object(batch, 'save_group_comparison_plots'), \
                patch.object(batch, 'save_approach_comparison_plot'), \
                patch.object(batch, 'build_scenario_comparison_table', return_value=pd.DataFrame()), \
                patch.object(batch, 'save_overall_comparison_plots'):
            root = batch.run_groups([self.group.name], output_root=Path(directory), workers=1)
            self.assertEqual(run.call_count, 5)
            manifest = json.loads((root / 'manifest.json').read_text(encoding='utf-8'))
            self.assertEqual(manifest['groups'][0]['parameter_sets'], self.snapshot['parameter_sets'])
            self.assertEqual(manifest['groups'][0]['fixed_overrides'], self.snapshot['base_parameters'])
            for call, case in zip(run.call_args_list, batch.build_group_combinations(self.group)):
                self.assertEqual(call.kwargs['sweep_values'], case)


if __name__ == '__main__':
    unittest.main()
