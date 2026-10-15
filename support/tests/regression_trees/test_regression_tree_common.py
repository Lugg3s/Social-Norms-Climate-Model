import json
from pathlib import Path
import tempfile
import unittest

import numpy as np
import pandas as pd

from analysis.regression_trees.regression_tree_analysis import (
    AGENT_SCENARIO, TreeConfig, common_parameter_scenarios, fit_target, group_holdout,
    load_scenario, run_analysis,
)
from analysis.regression_trees.regression_tree_demo import write_demo


class CommonParameterTreeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.sources = [write_demo(self.root / 'input' / name) for name in ('norm_a', 'norm_b')]
        for folder, name in zip(self.sources, ('Norm A', 'Norm B')):
            path = folder / 'metadata.json'
            metadata = json.loads(path.read_text())
            metadata['scenario'] = name
            if name == 'Norm A':
                # This parameter exists only in A; the valid two-input Sobol layout is unchanged.
                metadata['problem']['names'][0] = 'norm_specific'
                samples_path = folder / 'samples.csv'
                pd.read_csv(samples_path, sep=';').rename(columns={'beta': 'norm_specific'}).to_csv(
                    samples_path, sep=';', index=False)
            path.write_text(json.dumps(metadata), encoding='utf-8')
        self.scenarios = [load_scenario(folder) for folder in self.sources]
        self.config = TreeConfig(depths=(2,), cv_folds=3, stability_repeats=1)

    def test_intersection_excludes_norm_specific_inputs_and_norm_identity(self):
        common, restricted, pooled = common_parameter_scenarios(self.scenarios)
        self.assertEqual(common, ['temperature_factor'])
        self.assertTrue(all(s.feature_names == common for s in restricted))
        self.assertEqual(pooled.feature_names, common)
        self.assertNotIn('norm_specific', pooled.data)
        self.assertNotIn('beta', pooled.data)
        self.assertEqual(set(pooled.data.source_scenario), {'Norm A', 'Norm B'})
        self.assertEqual(len(pooled.data), sum(len(s.data) for s in self.scenarios))
        self.assertEqual(self.scenarios[0].feature_names, ['norm_specific', 'temperature_factor'])

    def test_shared_blocks_stay_together_in_pooled_holdout(self):
        _, _, pooled = common_parameter_scenarios(self.scenarios)
        split = group_holdout(pooled.data, self.config)
        train = pooled.data.iloc[split[0]]
        test = pooled.data.iloc[split[1]]
        self.assertFalse(set(train.sobol_block) & set(test.sobol_block))
        for norm in pooled.metadata['source_norms']:
            self.assertEqual(set(train.loc[train.source_scenario.eq(norm), 'sobol_block']), set(train.sobol_block))
            self.assertEqual(set(test.loc[test.source_scenario.eq(norm), 'sobol_block']), set(test.sobol_block))
        report, payload = fit_target(pooled, 'final_x', self.config, split)
        self.assertEqual(report['status'], 'fitted')
        self.assertEqual(report['feature_names'], ['temperature_factor'])
        self.assertEqual(set(report['norm_composition']), {'Norm A', 'Norm B'})
        self.assertFalse(payload['predictions'][['source_scenario', 'sample_index']].duplicated().any())
        self.assertLess(report['test_metrics']['mae'], report['baseline_test_metrics']['mae'])
        for node_feature in payload['model'].tree_.feature:
            self.assertIn(int(node_feature), [-2, 0])

    def test_common_exports_include_both_overviews_and_preserve_sources(self):
        originals = {p: p.read_bytes() for folder in self.sources for p in folder.iterdir()}
        output = self.root / 'result'
        reports = run_analysis(self.root / 'input', output, targets=['final_x'], config=self.config,
                               analysis_modes=['pooled_common', 'per_norm_common'])
        self.assertEqual(len(reports), 3)
        self.assertTrue(all(r['status'] == 'fitted' for r in reports))
        for group in ('pooled', 'per_norm'):
            folder = output / '_common_parametes' / group
            self.assertTrue((folder / 'regressiontrees_alle_normen.svg').exists())
            self.assertTrue((folder / 'summary.csv').exists())
            for rules_path in folder.glob('*/*/rules.txt'):
                rules = rules_path.read_text()
                self.assertIn('temperature_factor', rules)
                self.assertNotIn('norm_specific', rules)
                self.assertNotIn('beta', rules)
                self.assertNotIn('source_scenario', rules)
        manifest = json.loads((output / 'manifest.json').read_text())
        self.assertEqual(manifest['common_feature_names'], ['temperature_factor'])
        for file, content in originals.items():
            self.assertEqual(file.read_bytes(), content)

    def test_default_multi_norm_analysis_keeps_original_trees_and_adds_common_trees(self):
        reports = run_analysis(self.root / 'input', self.root / 'all', targets=['final_x'], config=self.config)
        self.assertEqual(len(reports), 5)
        self.assertEqual([r['analysis_mode'] for r in reports].count('per_norm'), 2)
        self.assertTrue((self.root / 'all' / 'regressiontrees_alle_normen.svg').exists())
        self.assertTrue((self.root / 'all' / '_common_parametes' / 'pooled' / 'regressiontrees_alle_normen.svg').exists())

    def test_oscillation_eligibility_is_applied_per_row_in_pooled_data(self):
        _, _, pooled = common_parameter_scenarios(self.scenarios)
        split = group_holdout(pooled.data, self.config)
        report, payload = fit_target(pooled, 'median_period', self.config, split)
        self.assertEqual(report['status'], 'fitted')
        self.assertEqual(report['eligible_rows'], int(pooled.data.n_oscillations.ge(2).sum()))
        identities = payload['predictions'][['source_scenario', 'sample_index']]
        selected = identities.merge(pooled.data, on=['source_scenario', 'sample_index'], validate='one_to_one')
        self.assertTrue(selected.n_oscillations.ge(2).all())
        self.assertTrue(np.isfinite(selected.median_period).all())

    def test_agent_comparison_restores_ode_inputs_and_excludes_agent_rows(self):
        path = self.sources[0] / 'metadata.json'
        metadata = json.loads(path.read_text())
        metadata['scenario'] = AGENT_SCENARIO
        path.write_text(json.dumps(metadata), encoding='utf-8')
        third = write_demo(self.root / 'input' / 'norm_c')
        path = third / 'metadata.json'
        metadata = json.loads(path.read_text())
        metadata['scenario'] = 'Norm C'
        path.write_text(json.dumps(metadata), encoding='utf-8')
        originals = {p: p.read_bytes() for folder in [*self.sources, third] for p in folder.iterdir()}
        output = self.root / 'agent_comparison'
        reports = run_analysis(self.root / 'input', output, targets=['final_x'], config=self.config,
                               analysis_modes=['pooled_common', 'per_norm_common'])
        self.assertEqual(len(reports), 7)  # (1 pooled + 3 norms) and (1 pooled + 2 norms).
        manifest = json.loads((output / 'manifest.json').read_text())
        self.assertEqual(manifest['common_variants']['with_agents']['common_feature_names'], ['temperature_factor'])
        self.assertEqual(manifest['common_variants']['without_agents']['common_feature_names'], ['beta', 'temperature_factor'])
        for variant, folder, count in [
            ('with_agents', output / '_common_parametes', 3),
            ('without_agents', output / '_common_parametes' / 'without_agents', 2),
        ]:
            expected = manifest['common_variants'][variant]['common_feature_names']
            for group in ['pooled', 'per_norm']:
                group_dir = folder / group
                group_manifest = json.loads((group_dir / 'manifest.json').read_text())
                self.assertEqual(len(group_manifest['sources']), count)
                overview = (group_dir / 'regressiontrees_alle_normen.svg').read_text(encoding='utf-8')
                self.assertIn(manifest['common_variants'][variant]['label'], overview)
                group_reports = json.loads((group_dir / 'reports.json').read_text())
                self.assertTrue(all(r['analysis_variant'] == variant for r in group_reports))
                self.assertTrue(all(r['feature_names'] == expected for r in group_reports))
            predictions = pd.read_csv(folder / 'pooled' / 'all_norms' / 'final_x' / 'predictions.csv', sep=';')
            self.assertEqual(AGENT_SCENARIO in set(predictions.source_scenario), variant == 'with_agents')
            train = set(predictions.loc[predictions.partition.eq('train'), 'sobol_block'])
            test = set(predictions.loc[predictions.partition.eq('test'), 'sobol_block'])
            self.assertTrue(train)
            self.assertTrue(test)
            self.assertFalse(train & test)
        for file, content in originals.items():
            self.assertEqual(file.read_bytes(), content)

    def test_incompatible_horizons_and_empty_intersection_are_rejected(self):
        self.scenarios[1].metadata['simulation_time'] = 1200
        with self.assertRaisesRegex(ValueError, 'same simulation horizon'):
            common_parameter_scenarios(self.scenarios)
        self.scenarios[1].metadata['simulation_time'] = 600
        self.scenarios[1].feature_names = ['other_input']
        with self.assertRaisesRegex(ValueError, 'no shared sampled input'):
            common_parameter_scenarios(self.scenarios)


if __name__ == '__main__':
    unittest.main()
