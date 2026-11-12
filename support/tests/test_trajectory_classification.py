"""Finite-horizon regime rules, event persistence and descriptive denominators."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from types import SimpleNamespace

import numpy as np
import pandas as pd

from analysis.trajectory_classification import (
    CLASS_ORDER, COLLAPSE, HIGH, MIDDLE, DAMPED, PERSISTENT, UNRESOLVED, INVALID, FAILED,
    classify_trajectory,
)
from analysis.behaviour_classification_plots import class_frequencies, create_plots, save_classification_outputs
from analysis.simulation_metrics import _base_metrics
import analysis.sensitivity.sensitivity_analysis as sensitivity
import simulation.batch_runner as batch


class TrajectoryClassificationTests(unittest.TestCase):
    def setUp(self):
        self.t = np.linspace(217, 617, 4001)

    def test_stationary_end_levels_and_nonstationary_middle(self):
        for level, expected in [(0, COLLAPSE), (.05, COLLAPSE), (.3, MIDDLE), (.95, HIGH), (1, HIGH)]:
            with self.subTest(level=level):
                result = classify_trajectory(self.t, np.full_like(self.t, level))
                self.assertEqual(result['behaviour_class'], expected)
                self.assertFalse(result['classification_oscillation_detected'])
        drift = classify_trajectory(self.t, np.linspace(.1, .9, len(self.t)))
        self.assertEqual(drift['behaviour_class'], UNRESOLVED)
        self.assertEqual(drift['classification_end_state'], 'nonstationary')

    def test_history_excluded_and_short_observations_not_called_stationary(self):
        t = np.linspace(0, 617, 6171)
        x = np.where(t < 217, .5 + .4 * np.sin(t), .3)
        self.assertEqual(classify_trajectory(t, x)['behaviour_class'], MIDDLE)
        for t in ([0, 100], [217, 250]):
            self.assertEqual(classify_trajectory(t, [.3, .3])['behaviour_class'], UNRESOLVED)

    def test_two_cycles_required_and_growing_cycles_not_called_persistent(self):
        # One prominent cycle is insufficient, even though the tail is stationary.
        t = [217, 227, 237, 247, 257, 300, 400, 500]
        x = [.5, .8, .2, .8, .5, .5, .5, .5]
        result = classify_trajectory(t, x)
        self.assertEqual(result['classification_complete_cycles'], 1)
        self.assertEqual(result['behaviour_class'], MIDDLE)
        phase = self.t - 217
        growing = .5 + .35 * np.exp((phase - 400) / 100) * np.sin(2 * np.pi * phase / 12)
        self.assertEqual(classify_trajectory(self.t, growing)['behaviour_class'], UNRESOLVED)

    def test_damped_persistent_and_disappearing_oscillations(self):
        phase = self.t - 217
        persistent = .5 + .3 * np.sin(2 * np.pi * phase / 12)
        damped = .5 + .4 * np.exp(-phase / 80) * np.sin(2 * np.pi * phase / 12)
        self.assertEqual(classify_trajectory(self.t, persistent)['behaviour_class'], PERSISTENT)
        result = classify_trajectory(self.t, damped)
        self.assertEqual(result['behaviour_class'], DAMPED)
        self.assertEqual(result['classification_end_state'], 'intermediate')
        self.assertEqual(batch.classify(damped, self.t), DAMPED)

    def test_invalid_data_are_not_silently_bridged(self):
        for times, values in [([217, 300, 400], [.2, np.nan, .2]),
                              ([217, 217, 400], [.2, .2, .2]),
                              ([217, 400], [.2, 1.1])]:
            self.assertEqual(classify_trajectory(times, values)['behaviour_class'], INVALID)

    def test_collapse_event_requires_prior_high_and_duration(self):
        t = [217, 267, 277, 327, 337, 417, 517]
        result = classify_trajectory(t, [.9, .9, .1, .1, .9, .9, .9])
        self.assertTrue(result['collapse_detected'])
        self.assertTrue(result['recovery_detected'])
        self.assertAlmostEqual(result['collapse_time'], 275.75)
        self.assertAlmostEqual(result['collapse_confirmed_at'], 295.75)
        self.assertAlmostEqual(result['collapse_duration'], 7.5)
        self.assertFalse(result['low_until_end'])
        self.assertFalse(classify_trajectory([217, 517], [.3, 0])['collapse_detected'])
        pending = classify_trajectory([217, 300, 310, 315], [.9, .9, .1, .1])
        self.assertFalse(pending['collapse_detected'])
        self.assertTrue(pending['collapse_pending_at_end'])

    def test_agent_events_use_steps_and_real_years(self):
        times, values = [217, 247, 267, 317, 417], [.9, .1, .9, .9, .9]
        result = classify_trajectory(times, values, stepwise=True)
        self.assertTrue(result['collapse_detected'])
        self.assertEqual(result['collapse_time'], 247)
        self.assertEqual(result['collapse_confirmed_at'], 267)
        self.assertEqual(result['recovery_time'], 267)
        self.assertFalse(result['low_until_end'])
        coarse = classify_trajectory([217, 317, 417], [.3, .3, .3], stepwise=True)
        self.assertEqual(coarse['behaviour_class'], MIDDLE)
        self.assertAlmostEqual(coarse['classification_end_mean'], .3)

    def test_review_counterexamples_persistent_tail_and_irregular_thresholds(self):
        phase = self.t - 217
        wave = .5 + (.1 + .3 * np.exp(-phase / 40)) * np.sin(2 * np.pi * phase / 10)
        result = classify_trajectory(self.t, wave)
        self.assertEqual(result['behaviour_class'], PERSISTENT)
        self.assertTrue(result['classification_transient_damping'])
        rng = np.random.default_rng(42)
        for level, expected in [(.05, COLLAPSE), (.95, HIGH)]:
            for _ in range(10):
                times = np.r_[217, np.sort(rng.uniform(217, 617, 15)), 617]
                self.assertEqual(classify_trajectory(times, np.full_like(times, level))['behaviour_class'], expected)

    def test_minor_fast_wiggles_do_not_erase_large_slow_cycles(self):
        for interval in (.01, .1, 1):
            times = np.arange(217, 617 + interval / 2, interval)
            phase = times - 217
            values = .5 + .3 * np.sin(2 * np.pi * phase / 20) + .012 * np.sin(2 * np.pi * phase / .2)
            result = classify_trajectory(times, values)
            self.assertEqual(result['behaviour_class'], PERSISTENT)
            self.assertGreaterEqual(result['classification_complete_cycles'], 18)
        times = np.arange(217, 618)
        for low, high in [(.28, .30), (.30, .32)]:
            values = np.where(((times - 217) // 5) % 2 == 0, low, high)
            self.assertEqual(classify_trajectory(times, values, stepwise=True)['behaviour_class'], PERSISTENT)

    def test_events_rearm_and_report_censored_terminal_entries(self):
        repeated_low = classify_trajectory([217, 247, 277, 297, 327, 417],
                                          [.9, .1, .5, .1, .5, .5], stepwise=True)
        self.assertEqual(repeated_low['collapse_count'], 1)
        pending = classify_trajectory([217, 247, 300], [.9, .9, .1], stepwise=True)
        self.assertTrue(pending['collapse_pending_at_end'])
        self.assertFalse(pending['collapse_detected'])
        recovering = classify_trajectory([217, 247, 277, 300, 305],
                                         [.9, .1, .1, .9, .9], stepwise=True)
        self.assertTrue(recovering['recovery_pending_at_end'])
        self.assertFalse(recovering['recovery_detected'])
        already_recovered = classify_trajectory([217, 247, 277, 337, 350, 355],
                                               [.9, .1, .9, .5, .9, .9], stepwise=True)
        self.assertTrue(already_recovered['recovery_detected'])
        self.assertFalse(already_recovered['recovery_pending_at_end'])

    def test_archived_ode_and_agent_reclassification_preserves_sources(self):
        from model.model_equations import simulate
        from simulation.time_series import save_time_series
        from analysis.simulation_metrics import compute_run_metrics
        from analysis.sensitivity.sensitivity_batch_plots import _render_one
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for scenario in ('baseline', 'Observation-based / intention motivation (agents)'):
                params = sensitivity.resolve_parameters(scenario)
                if params['ABM']:
                    params['network_size'] = 5
                simulation = simulate(params, simulation_time=350, coupling_interval=5,
                                      output_points_per_year=1, constant_temperature_costs=True,
                                      n_agents=11, verbose=False)
                metrics = compute_run_metrics(simulation, params)
                folder = root / ('agents' if params['ABM'] else 'ode')
                folder.mkdir()
                archive = folder / 'sample_000000.npz'
                save_time_series(archive, simulation, {**metrics, 'behaviour_class': UNRESOLVED,
                                                     'classification_version': 0},
                                 {'phase': 'sample', 'sample_index': 0})
                rows = pd.DataFrame([{'sample_index': 0, 'status': 'completed',
                                      'time_series_file': archive.name},
                                     {'sample_index': 1, 'status': 'failed'}])
                rows.to_csv(folder / 'simulation_outputs.csv', sep=';', index=False)
                (folder / 'metadata.json').write_text(json.dumps({'scenario': scenario}))
                original = archive.read_bytes()
                with patch('model.model_equations.simulate', side_effect=AssertionError('must not simulate')):
                    saved = create_plots(folder, reclassify=True)[0]
                    exported = folder / 'batch'
                    exported.mkdir()
                    with patch.object(batch, 'save_run_plots'):
                        record = _render_one((archive, scenario, [], exported))
                classes = pd.read_csv(saved / 'behaviour_classes.csv', sep=';')
                self.assertEqual(classes.loc[0, 'behaviour_class'], metrics['behaviour_class'])
                self.assertEqual(classes.loc[1, 'behaviour_class'], FAILED)
                self.assertEqual(record['behaviour_class'], metrics['behaviour_class'])
                self.assertEqual(batch._classify_saved_run(pd.Series(record)), metrics['behaviour_class'])
                self.assertEqual(archive.read_bytes(), original)
                provenance = json.loads((saved / 'classification_metadata.json').read_text())
                self.assertEqual(provenance['definition']['version'], 1)

    def test_classification_does_not_change_sobol_outputs_or_inclusion(self):
        metrics = _base_metrics(self.t, np.zeros_like(self.t), np.full_like(self.t, .3),
                                np.zeros_like(self.t), {'epsilon_max': 7, 's': 50})
        prepared = sensitivity._prepare_sensitivity_outputs(metrics, 617)
        self.assertEqual(set(prepared), set(sensitivity.SENSITIVITY_OUTPUTS))
        self.assertNotIn('behaviour_class', prepared)
        rows = pd.DataFrame([{**metrics, **prepared, 'status': 'completed'}] * 6)
        before, info = sensitivity.complete_sobol_blocks({'num_vars': 1}, rows)
        rows['behaviour_class'] = INVALID
        after, changed = sensitivity.complete_sobol_blocks({'num_vars': 1}, rows)
        self.assertEqual(info, changed)
        np.testing.assert_array_equal(before[sensitivity.SENSITIVITY_OUTPUTS], after[sensitivity.SENSITIVITY_OUTPUTS])

    def test_sensitivity_worker_returns_class_even_without_archiving(self):
        params = sensitivity.resolve_parameters('baseline')
        result = dict(parameters=params, simulation=SimpleNamespace(t=self.t, T=np.zeros_like(self.t),
                      x=np.full_like(self.t, .3)), social_norm_term=np.zeros_like(self.t))
        with patch.object(sensitivity, 'simulate', return_value=result):
            outputs = sensitivity._run_sample((params, [], [], sensitivity.SensitivityConfig(save_time_series=False)))
        self.assertEqual(outputs['behaviour_class'], MIDDLE)

    def test_frequency_denominator_includes_failed_runs_and_zero_classes(self):
        rows = pd.DataFrame({'sample_index': [0, 1, 2, 3],
                             'behaviour_class': [HIGH, HIGH, COLLAPSE, None],
                             'status': ['completed', 'completed', 'completed', 'timed_out']})
        frequencies = class_frequencies(rows).set_index('behaviour_class')
        self.assertAlmostEqual(frequencies['relative_frequency'].sum(), 1)
        self.assertEqual(frequencies.loc[HIGH, 'relative_frequency'], .5)
        self.assertEqual(frequencies.loc[FAILED, 'relative_frequency'], .25)
        self.assertEqual(frequencies.loc[MIDDLE, 'count'], 0)
        with tempfile.TemporaryDirectory() as root:
            folder = Path(root) / 'example'
            folder.mkdir()
            rows.to_csv(folder / 'simulation_outputs.csv', sep=';', index=False)
            (folder / 'metadata.json').write_text(json.dumps({'scenario': 'Example norm'}))
            with patch('model.model_equations.simulate', side_effect=AssertionError('must not simulate')):
                paths = create_plots(Path(root))
            self.assertTrue((paths[0] / 'behaviour_class_frequencies.svg').exists())
            self.assertTrue((paths[0] / 'behaviour_classes.csv').exists())


if __name__ == '__main__':
    unittest.main()
