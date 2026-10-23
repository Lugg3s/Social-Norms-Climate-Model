"""Lossless storage, unchanged Sobol inputs, and plotting with no model execution."""
from dataclasses import replace
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import numpy as np
import pandas as pd

import analysis.sensitivity.sensitivity_analysis as sensitivity
import simulation.batch_runner as batch
from model.model_equations import resolve_parameters, simulate
from simulation.time_series import save_time_series, load_time_series
from analysis.simulation_metrics import compute_run_metrics
from analysis.sensitivity.sensitivity_batch_plots import render_saved_sensitivity, _sources


class TimeSeriesTests(unittest.TestCase):
    def test_default_and_opt_out_reach_the_runner(self):
        for disabled in (False, True):
            with tempfile.TemporaryDirectory() as directory:
                argv = ['sensi', '--output-root', directory]
                if disabled:
                    argv.append('--no-save-time-series')
                with patch('sys.argv', argv), patch.object(sensitivity, '_run_scenarios') as runner:
                    sensitivity.main()
                self.assertEqual(runner.call_args.args[2].save_time_series, not disabled)

    def test_roundtrip_is_exact_and_preserves_annual_agent_mean_intention(self):
        for scenario in ('baseline', 'Observation-based / intention motivation (agents)'):
            params = resolve_parameters(scenario)
            if params['ABM']:
                params.update(network_size=2)
            result = simulate(params, simulation_time=219, coupling_interval=1,
                              output_points_per_year=2, n_agents=7,
                              constant_temperature_costs=True, verbose=False)
            metrics = compute_run_metrics(result, params)
            with tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / 'sample_000000.npz'
                save_time_series(path, result, metrics, {'phase': 'sample', 'sample_index': 0})
                frame, metadata = load_time_series(path)
                expected = batch.simulation_to_dataframe(result, result['parameters'])
                pd.testing.assert_frame_equal(frame, expected, check_exact=True)
                self.assertEqual(metadata['parameters'], result['parameters'])
                self.assertTrue(metadata['solver_settings']['constant_temperature_costs'])
                with np.load(path, allow_pickle=False) as archive:
                    self.assertNotIn('behavioral_intention', archive.files)
                    self.assertNotIn('actual_behavior', archive.files)

    def test_failed_write_does_not_publish_a_partial_archive(self):
        result = simulate(simulation_time=1, verbose=False)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'sample_000000.npz'
            with patch('simulation.time_series.np.savez_compressed', side_effect=OSError('full disk')):
                with self.assertRaisesRegex(OSError, 'full disk'):
                    save_time_series(path, result, {}, {})
            self.assertEqual(list(Path(directory).iterdir()), [])

    def test_real_sensitivity_stores_each_sample_and_boundary_without_changing_metrics(self):
        config = sensitivity.SensitivityConfig(simulation_time=2, base_sample_size=2,
                                               workers=2, coupling_interval=1, output_points_per_year=2)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            sensitivity.run_sensitivity_analysis('baseline', root / 'saved', config)
            sensitivity.run_sensitivity_analysis('baseline', root / 'disabled', replace(config, save_time_series=False))
            saved = root / 'saved' / 'baseline'
            disabled = root / 'disabled' / 'baseline'
            info = json.loads((saved / 'time_series.json').read_text())
            archives = saved / info['directory']
            self.assertEqual(len(list(archives.glob('sample_*.npz'))), 12)
            self.assertEqual(len(list(archives.glob('boundary_*.npz'))), 4)
            self.assertFalse(json.loads((disabled / 'time_series.json').read_text())['enabled'])
            self.assertFalse(list(disabled.glob('time_series_*')))
            a = pd.read_csv(saved / 'simulation_outputs.csv', sep=';')
            b = pd.read_csv(disabled / 'simulation_outputs.csv', sep=';')
            pd.testing.assert_frame_equal(a.drop(columns='time_series_file'), b, check_exact=True)
            for relative in a['time_series_file']:
                _, metadata = load_time_series(saved / relative)
                self.assertEqual(metadata['context']['n_agents'], 1000)

    def test_missing_old_trajectories_and_unavailable_sample_ids_fail_explicitly(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with self.assertRaisesRegex(FileNotFoundError, 'without NPZs'):
                _sources(root, None, None, None, False)
            folder = root / 'baseline'
            folder.mkdir()
            (folder / 'time_series.json').write_text(json.dumps(
                {'scenario': 'baseline', 'enabled': True, 'directory': 'time_series_attempt'}))
            (folder / 'time_series_attempt').mkdir()
            with self.assertRaisesRegex(FileNotFoundError, 'Missing saved samples'):
                _sources(root, None, [834], None, False)

    def test_batch_export_has_pngs_mp4_and_3d_without_calling_simulate(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            folder = root / 'baseline'
            folder.mkdir()
            archive_dir = folder / 'time_series_attempt'
            archive_dir.mkdir()
            (folder / 'time_series.json').write_text(json.dumps(
                {'scenario': 'baseline', 'enabled': True, 'directory': archive_dir.name}))
            pd.DataFrame(columns=['sample_index', 'temperature_factor', 'beta']).to_csv(
                folder / 'samples.csv', sep=';', index=False)
            for index, beta in enumerate((0.2, 0.8)):
                params = {**resolve_parameters('baseline'), 'beta': beta, 'temperature_factor': 1 + index}
                result = simulate(params, simulation_time=220, coupling_interval=1,
                                  output_points_per_year=2, constant_temperature_costs=True, verbose=False)
                save_time_series(archive_dir / f'sample_{index:06d}.npz', result,
                                 compute_run_metrics(result, params), {'phase': 'sample', 'sample_index': index})
            with patch.object(batch, 'simulate', side_effect=AssertionError('must not simulate')), \
                 patch.object(sensitivity, 'simulate', side_effect=AssertionError('must not simulate')), \
                 patch.object(batch, 'KEY_METRICS', ['final_x']):
                output = render_saved_sensitivity(root, max_video_frames=3, animation_fps=2)
            destination = output / 'baseline'
            for name in ('temperature', 'x', 'x_phase_space', 'mitigation_incentives', 'mitigation', 'f_T'):
                self.assertTrue((destination / 'sample_000000' / f'{name}.png').exists(), name)
                self.assertGreater((destination / 'videos' / f'{name}.mp4').stat().st_size, 100, name)
            projection = destination / 'parameter_pairs' / 'pair_01'
            self.assertTrue((projection / 'x_3d.png').exists())
            self.assertGreater((projection / 'x_3d.mp4').stat().st_size, 100)
            self.assertTrue((projection / 'final_x.png').exists())
            self.assertEqual(json.loads((projection / 'parameters.json').read_text())['x'], 'temperature_factor')
            self.assertTrue((output / 'scenario_comparison.csv').exists())
            self.assertEqual(len(list(archive_dir.glob('*.npz'))), 2)

    def test_completed_status_filters_archives_and_missing_completed_files_are_reported(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            folder = root / 'baseline'
            archives = folder / 'time_series_attempt'
            archives.mkdir(parents=True)
            (folder / 'time_series.json').write_text(json.dumps(
                {'scenario': 'baseline', 'enabled': True, 'directory': archives.name}))
            pd.DataFrame({'sample_index': [0, 1], 'beta': [1, 2]}).to_csv(folder / 'samples.csv', sep=';', index=False)
            pd.DataFrame({'sample_index': [0, 1], 'status': ['completed', 'timed_out']}).to_csv(
                folder / 'simulation_outputs.csv', sep=';', index=False)
            for index in (0, 1):
                (archives / f'sample_{index:06d}.npz').touch()
            source = _sources(root, None, None, None, False)
            self.assertEqual([p.name for p in source[0][3]], ['sample_000000.npz'])
            with self.assertRaisesRegex(FileNotFoundError, 'Missing saved samples'):
                _sources(root, None, [1], None, False)
            (archives / 'sample_000000.npz').unlink()
            with self.assertRaisesRegex(FileNotFoundError, 'Missing saved samples'):
                _sources(root, None, None, None, False)

    def test_regular_batch_grids_keep_surfaces_and_irregular_points_remain_scatter(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            records = []
            for index, (a, b) in enumerate(((0, 0), (0, 1), (1, 0), (1, 1))):
                folder = root / f'run_{index}'
                folder.mkdir()
                pd.DataFrame({'year': [1900, 1950, 2000], 'x': [0.3, 0.4, 0.5]}).to_csv(
                    folder / 'time_series.csv', sep=';', index=False)
                records.append({'run_dir': str(folder), 'scenario': 'test', 'a': a, 'b': b})
            regular = batch.save_x_parameter_surface_animation(pd.DataFrame(records), root,
                                                                'a', 'b', 'test', make_video=False)
            self.assertEqual(regular['kind'], 'surface')
            irregular = batch.save_x_parameter_surface_animation(pd.DataFrame(records[:3]), root,
                                                                  'a', 'b', 'test', make_video=False)
            self.assertEqual(irregular['kind'], 'scatter')


if __name__ == '__main__':
    unittest.main()
