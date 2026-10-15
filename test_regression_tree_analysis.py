import json
from pathlib import Path
import tempfile
import unittest

import numpy as np
import pandas as pd
from sklearn.model_selection import GroupKFold

from regression_tree_analysis import (SENSITIVITY_TARGETS, TreeConfig, eligible_target, fit_target,
                                     group_holdout, load_scenario, run_analysis,
                                     _leaf_prediction, _leaf_spread, _leaf_standard_deviations)
from sensitivity_analysis import SENSITIVITY_OUTPUTS
from regression_tree_demo import write_demo


class RegressionTreeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = write_demo(self.root / "input")
        self.scenario = load_scenario(self.source)
        self.config = TreeConfig(depths=(2, 3), stability_repeats=2)

    def test_join_uses_sample_index_not_csv_row_order(self):
        path = self.source / "simulation_outputs.csv"
        frame = pd.read_csv(path, sep=";").sample(frac=1, random_state=3)
        frame.to_csv(path, sep=";", index=False)
        joined = load_scenario(self.source)
        np.testing.assert_allclose(joined.data.final_x, self.scenario.data.final_x)
        frame = pd.concat([frame, frame.iloc[:1]], ignore_index=True)
        frame.to_csv(path, sep=";", index=False)
        with self.assertRaisesRegex(ValueError, "duplicate"):
            load_scenario(self.source)

    def test_target_specific_filter_preserves_real_zero_damping(self):
        data = self.scenario.data.copy()
        damping_mask, _ = eligible_target(data, "damping_index")
        self.assertTrue(damping_mask[data.damping_index.eq(0) & data.n_oscillations.ge(2)].all())
        self.assertFalse(damping_mask[data.n_oscillations.eq(0)].any())
        final_mask, _ = eligible_target(data, "final_x")
        self.assertTrue(final_mask.all())
        data.loc[0, "median_period"] = np.nan
        period_mask, _ = eligible_target(data, "median_period")
        self.assertFalse(period_mask[0])
        self.assertTrue(eligible_target(data, "final_x")[0][0])
        data.loc[1, "n_oscillations"] = 1
        self.assertFalse(eligible_target(data, "median_period")[0][1])
        data.loc[2, "status"] = "timed_out"
        self.assertFalse(eligible_target(data, "final_x")[0][2])

    def test_all_active_sensitivity_targets_use_nonoscillating_and_zero_rows(self):
        self.assertEqual(tuple(SENSITIVITY_OUTPUTS), SENSITIVITY_TARGETS)
        data = self.scenario.data.drop(columns=['n_oscillations'])
        for target in SENSITIVITY_TARGETS:
            mask, _ = eligible_target(data, target)
            self.assertTrue(mask.all(), target)
        self.assertTrue(eligible_target(data, 'first_time_x95')[0][data.first_time_x95.eq(0)].all())
        self.assertTrue(eligible_target(data, 'bool_x95')[0][~data.bool_x95].all())
        data = data.copy()
        data.loc[0, 'x_mean'] = np.nan
        data.loc[1, 'status'] = 'timed_out'
        self.assertFalse(eligible_target(data, 'x_mean')[0][0])
        self.assertTrue(eligible_target(data, 'bool_x95')[0][0])
        for target in SENSITIVITY_TARGETS:
            self.assertFalse(eligible_target(data, target)[0][1])

    def test_boolean_leaf_mean_is_the_positive_training_share(self):
        split = group_holdout(self.scenario.data, self.config)
        for target in ['bool_x95', 'oscillation_occurrence']:
            report, payload = fit_target(self.scenario, target, self.config, split)
            self.assertEqual(report['status'], 'fitted')
            model = payload['model']
            training = self.scenario.data.iloc[split[0]]
            leaves = model.apply(training[self.scenario.feature_names].to_numpy())
            stds = _leaf_standard_deviations(self.scenario, target, report, model)
            for leaf in np.unique(leaves):
                values = training[target].to_numpy(dtype=float)[leaves == leaf]
                self.assertAlmostEqual(model.tree_.value[leaf, 0, 0], values.mean())
                self.assertAlmostEqual(stds[leaf], np.std(values))
            self.assertIn('25,0 %', _leaf_prediction(target, 0.25))
            self.assertIn('Anteil der Läufe mit Wert 1', _leaf_prediction(target, 0.25))
            self.assertIn('Prozentpunkte', _leaf_spread(target, 0.25))
        self.scenario.data['bool_x95'] = False
        report, payload = fit_target(self.scenario, 'bool_x95', self.config, split)
        self.assertEqual(report['status'], 'constant_training_target')
        self.assertIsNone(payload)

    def test_saved_legacy_rate_is_labelled_and_never_recomputed(self):
        self.scenario.metadata.pop('oscillations_per_500_years_definition')
        self.scenario.data.loc[0, 'n_oscillations'] = 1
        self.scenario.data.loc[0, 'oscillations_per_500_years'] = 500 / 600
        mask, _ = eligible_target(self.scenario.data, 'oscillations_per_500_years')
        self.assertTrue(mask.all())
        report, payload = fit_target(self.scenario, 'oscillations_per_500_years', self.config,
                                     group_holdout(self.scenario.data, self.config))
        self.assertIn('ältere Rate', report['saved_definition_note'])
        self.assertAlmostEqual(payload['predictions'].set_index('sample_index').loc[0, 'observed'], 500 / 600)

    def test_all_sensitivity_targets_export_with_their_original_names(self):
        output = self.root / 'sensitivity_targets'
        reports = run_analysis(self.source, output, targets=SENSITIVITY_TARGETS, config=self.config)
        self.assertEqual({r['target'] for r in reports}, set(SENSITIVITY_TARGETS))
        self.assertTrue(all(r['status'] == 'fitted' for r in reports))
        overview = (output / 'regressiontrees_alle_normen.svg').read_text(encoding='utf-8')
        for target in SENSITIVITY_TARGETS:
            self.assertIn(target, overview)
            svg = (output / 'input' / target / 'tree.svg').read_text(encoding='utf-8')
            self.assertIn(target, svg)
            self.assertIn('Std.-Abw.', svg)
        self.assertIn('einschließlich 0', (output / 'input' / 'first_time_x95' / 'tree.svg').read_text(encoding='utf-8'))

    def test_holdout_and_cv_keep_whole_sobol_blocks_together(self):
        train, test = group_holdout(self.scenario.data, self.config)
        groups = self.scenario.data.sobol_block.to_numpy()
        self.assertFalse(set(groups[train]) & set(groups[test]))
        report, payload = fit_target(self.scenario, "final_x", self.config, (train, test))
        self.assertEqual(report["status"], "fitted")
        self.assertLess(report["test_metrics"]["mae"], 0.1)
        self.assertTrue(report["beats_mean_baseline"])
        self.assertFalse(set(report["train_block_ids"]) & set(report["test_block_ids"]))
        self.assertEqual(set(payload["importances"].parameter), {"beta", "temperature_factor"})
        model = payload["model"]
        deviations = _leaf_standard_deviations(self.scenario, "final_x", report, model)
        leaf_ids = model.apply(self.scenario.data.iloc[train][self.scenario.feature_names].to_numpy())
        for leaf_id in np.unique(leaf_ids):
            values = self.scenario.data.iloc[train].final_x.to_numpy()[leaf_ids == leaf_id]
            self.assertAlmostEqual(deviations[leaf_id], np.std(values))
        for fit, validation in GroupKFold(n_splits=5).split(train, groups=groups[train]):
            self.assertFalse(set(groups[train][fit]) & set(groups[train][validation]))

    def test_test_targets_do_not_affect_tree_selection_or_fit(self):
        split = group_holdout(self.scenario.data, self.config)
        report, payload = fit_target(self.scenario, "final_x", self.config, split)
        deviations = _leaf_standard_deviations(self.scenario, "final_x", report, payload["model"])
        self.scenario.data.loc[split[1], "final_x"] += 100
        other, other_payload = fit_target(self.scenario, "final_x", self.config, split)
        self.assertEqual(report["best_parameters"], other["best_parameters"])
        self.assertEqual(report["cv_mae"], other["cv_mae"])
        np.testing.assert_array_equal(payload["model"].tree_.threshold, other_payload["model"].tree_.threshold)
        np.testing.assert_array_equal(payload["model"].tree_.value, other_payload["model"].tree_.value)
        self.assertEqual(deviations, _leaf_standard_deviations(
            self.scenario, "final_x", other, other_payload["model"]))

    def test_insufficient_and_constant_targets_are_reported_not_fitted(self):
        split = group_holdout(self.scenario.data, self.config)
        self.scenario.data["final_x"] = 0.5
        report, payload = fit_target(self.scenario, "final_x", self.config, split)
        self.assertEqual(report["status"], "constant_training_target")
        self.assertIsNone(payload)
        self.scenario.data["n_oscillations"] = 0
        report, payload = fit_target(self.scenario, "median_period", self.config, split)
        self.assertEqual(report["status"], "insufficient_data")
        self.assertIsNone(payload)

    def test_metadata_mismatch_is_rejected(self):
        path = self.source / "metadata.json"
        metadata = json.loads(path.read_text())
        metadata["outputs_for_ranking"] = ["missing_old_column"]
        path.write_text(json.dumps(metadata))
        with self.assertRaisesRegex(ValueError, "mixed code versions"):
            load_scenario(self.source)

    def test_tiny_numerical_variation_does_not_create_extra_splits(self):
        split = group_holdout(self.scenario.data, self.config)
        data = self.scenario.data
        data["final_x"] = np.where(data.temperature_factor >= 0.5, 1.0, 0.0) + 1e-8 * data.beta
        report, payload = fit_target(self.scenario, "final_x", self.config, split)
        self.assertEqual(report["leaves"], 2)
        self.assertEqual(report["actual_depth"], 1)

    def test_agent_peer_count_uses_effective_integer_input(self):
        metadata_path = self.source / "metadata.json"
        metadata = json.loads(metadata_path.read_text())
        metadata["problem"]["names"][0] = "network_size"
        metadata["agent_initialization"] = {"network_size_transform": "Nearest integer"}
        metadata_path.write_text(json.dumps(metadata))
        samples_path = self.source / "samples.csv"
        samples = pd.read_csv(samples_path, sep=";").rename(columns={"beta": "network_size"})
        samples["network_size"] = 1.4 + 5 * samples.network_size
        samples.to_csv(samples_path, sep=";", index=False)
        scenario = load_scenario(self.source)
        np.testing.assert_allclose(scenario.data.network_size, np.rint(samples.network_size))

    def test_exports_preserve_sources_and_show_conditional_counts(self):
        originals = {path: path.read_bytes() for path in self.source.iterdir()}
        reports = run_analysis(self.source, self.root / "result", targets=["final_x", "median_period"], config=self.config)
        self.assertTrue((self.root / "result" / "regressiontrees_alle_normen.svg").exists())
        self.assertTrue(all(r["status"] == "fitted" for r in reports))
        self.assertLess(reports[1]["eligible_rows"], reports[0]["eligible_rows"])
        for target in ("final_x", "median_period"):
            folder = self.root / "result" / "input" / target
            for name in ("tree.svg", "tree.png", "report.json", "rules.txt", "predictions.csv", "training_cv.csv"):
                self.assertTrue((folder / name).exists(), name)
            svg_text = (folder / "tree.svg").read_text(encoding="utf-8")
            self.assertIn("Std.-Abw.:", svg_text)
            self.assertIn("kein Konfidenzintervall", svg_text)
            self.assertIn("Prozentpunkte" if target == "final_x" else "Jahre", svg_text)
        overview_text = (self.root / "result" / "regressiontrees_alle_normen.svg").read_text(encoding="utf-8")
        self.assertIn("Std.-Abw.:", overview_text)
        for path, content in originals.items():
            self.assertEqual(path.read_bytes(), content)
        with self.assertRaises(FileExistsError):
            run_analysis(self.source, self.root / "result", targets=["final_x"], config=self.config)


if __name__ == "__main__":
    unittest.main()
