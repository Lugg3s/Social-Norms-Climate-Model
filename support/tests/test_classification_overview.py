"""Shared classification sheet: exact saved vectors, source safety and integration."""
import json
from pathlib import Path
import re
import tempfile
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET

import pandas as pd
import matplotlib.pyplot as plt

from analysis.behaviour_classification_plots import (
    OVERVIEW_FILENAME, SVG_NS, XLINK_NS, create_classification_overview_svg, create_plots,
    create_cross_norm_classification_plots, class_frequencies,
)
from analysis.trajectory_classification import HIGH, FAILED
from analysis.sensitivity import sensitivity_analysis as sensitivity


class ClassificationOverviewTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)

    def norm(self, directory, scenario, *, comparison=True):
        folder = self.root / directory
        folder.mkdir()
        (folder / 'metadata.json').write_text(json.dumps({'scenario': scenario}), encoding='utf-8')
        pd.DataFrame({'sample_index': [0, 1], 'behaviour_class': [HIGH, FAILED],
                      'status': ['completed', 'failed']}).to_csv(folder / 'simulation_outputs.csv', sep=';', index=False)
        source = f'''<svg xmlns="{SVG_NS}" xmlns:xlink="{XLINK_NS}" viewBox="0 0 900 500">
<defs><clipPath id="clip"><rect width="800" height="400"/></clipPath>
<path id="glyph" d="M 0 0 L 1 1"/></defs>
<g id="bars" clip-path="url(#clip)"><use xlink:href="#glyph"/>
<text x="30" y="30">{scenario}: 50.0%</text></g></svg>'''
        (folder / 'behaviour_class_frequencies.svg').write_text(source, encoding='utf-8')
        if comparison:
            (folder / 'without_norm_comparison_frequencies.svg').write_text(
                source.replace('900 500', '1000 1100'), encoding='utf-8')
        return folder

    def test_preserves_vectors_sources_and_unique_references(self):
        for folder, name in [('baseline', 'Observation-based / imitation'), ('No_social_norm', 'No social norm')]:
            self.norm(folder, name)
        originals = {path: path.read_bytes() for path in self.root.glob('*/*')}
        with patch('model.model_equations.simulate', side_effect=AssertionError('must not simulate')):
            path = create_classification_overview_svg(self.root)
        sheet = ET.parse(path).getroot()
        sections = sheet.findall(f'{{{SVG_NS}}}g[@data-scenario]')
        self.assertEqual([node.get('data-scenario') for node in sections],
                         ['No social norm', 'Observation-based / imitation'])
        self.assertEqual(len(sheet.findall(f'.//{{{SVG_NS}}}g[@data-classification-panel]')), 3)
        self.assertFalse(sheet.findall(f'.//{{{SVG_NS}}}image'))
        ids = [node.get('id') for node in sheet.iter() if node.get('id')]
        self.assertEqual(len(ids), len(set(ids)))
        for node in sheet.iter():
            for key, value in node.attrib.items():
                if key.endswith('href'):
                    self.assertIn(value[1:], ids)
                for reference in re.findall(r'url\(#([^)]+)\)', value):
                    self.assertIn(reference, ids)
        self.assertGreater(float(sheet.get('width').removesuffix('px')), 1900)
        self.assertEqual(sheet.find(f'{{{SVG_NS}}}title').text, 'Behavioural classifications — all norms')
        for source, original in originals.items():
            self.assertEqual(source.read_bytes(), original)

    def test_empty_and_missing_optional_comparisons(self):
        self.assertIsNone(create_classification_overview_svg(self.root))
        first = self.norm('first', 'First norm', comparison=False)
        self.norm('second', 'Second norm')
        path = create_classification_overview_svg(self.root)
        self.assertIn('Without-norm comparison unavailable', path.read_text(encoding='utf-8'))
        create_classification_overview_svg(self.root, [first])
        sheet = ET.parse(path).getroot()
        self.assertEqual(len(sheet.findall(f'{{{SVG_NS}}}g[@data-scenario]')), 1)
        self.assertEqual(len(sheet.findall(f'.//{{{SVG_NS}}}g[@data-classification-panel]')), 1)

    def test_saved_plot_command_respects_selection_and_preserves_inputs(self):
        selected = self.norm('selected', 'Selected norm')
        self.norm('excluded', 'Excluded norm')
        originals = {path: path.read_bytes() for path in self.root.glob('*/*')}
        with patch('model.model_equations.simulate', side_effect=AssertionError('must not simulate')):
            reports = create_plots(self.root, scenarios=['Selected norm'])
        self.assertEqual([path.name for path in reports], ['selected'])
        sheet = ET.parse(reports[0].parent / OVERVIEW_FILENAME).getroot()
        self.assertEqual([node.get('data-scenario') for node in sheet.findall(f'{{{SVG_NS}}}g[@data-scenario]')],
                         ['Selected norm'])
        for source, original in originals.items():
            self.assertEqual(source.read_bytes(), original)
        frequencies = pd.read_csv(reports[0] / 'behaviour_class_frequencies.csv', sep=';')
        self.assertAlmostEqual(frequencies['relative_frequency'].sum(), 1)
        self.assertEqual(frequencies.set_index('behaviour_class').loc[FAILED, 'relative_frequency'], .5)

    def test_sensitivity_completion_includes_existing_scenarios(self):
        self.norm('old', 'Existing norm')
        current = self.norm('new', 'New norm')
        pd.DataFrame({'parameter': ['beta'], 'score': [1.]}).to_csv(current / 'parameter_ranking.csv', sep=';', index=False)
        with patch.object(sensitivity, 'run_sensitivity_analysis', return_value=current), \
             patch('analysis.sensitivity.sensitivity_plots.create_parameter_ranking_barplots', return_value=[]), \
             patch('analysis.sensitivity.sensitivity_plots.create_goal_variable_violin_boxplots', return_value=[]):
            sensitivity._run_scenarios(['new'], self.root, sensitivity.SensitivityConfig(), overwrite_existing=False)
        sheet = ET.parse(self.root / OVERVIEW_FILENAME).getroot()
        self.assertEqual(len(sheet.findall(f'{{{SVG_NS}}}g[@data-scenario]')), 2)

    def test_legacy_labels_and_cross_norm_denominators(self):
        folders = [self.norm('a', 'A'), self.norm('b', 'B', comparison=False),
                   self.norm('No_social_norm', 'No social norm')]
        # Old classes are translated, with failed rows kept in the denominator.
        outputs = pd.DataFrame({'behaviour_class': ['Approach to 1 (no oscillation detected)', HIGH],
                                'status': ['completed', 'failed']})
        frequencies = class_frequencies(outputs)
        self.assertEqual(frequencies.set_index('behaviour_class').loc[HIGH, 'relative_frequency'], .5)
        for folder in folders:
            frequencies.to_csv(folder / 'behaviour_class_frequencies.csv', sep=';', index=False)
        pd.DataFrame([
            dict(comparison='x1_timing', category='Only with norm reached', count=1,
                 total_requested_runs=2, relative_frequency=.5),
            dict(comparison='x1_timing', category='Neither reached', count=1,
                 total_requested_runs=2, relative_frequency=.5),
        ]).to_csv(folders[0] / 'without_norm_comparison_frequencies.csv', sep=';', index=False)
        (folders[2] / 'without_norm_comparison_frequencies.csv').write_bytes(
            (folders[0] / 'without_norm_comparison_frequencies.csv').read_bytes())
        figures = []
        def capture(fig, path, **kwargs):
            figures.append(fig)
            Path(path).write_bytes(b'preview')
        with patch.object(plt.Figure, 'savefig', autospec=True,
                          side_effect=capture):
            paths = create_cross_norm_classification_plots(self.root)
        high = next(fig.axes[0] for fig in figures if HIGH in fig.axes[0].get_title())
        self.assertEqual([bar.get_height() for bar in high.containers[0]], [.5, .5, .5])
        self.assertEqual(high.containers[0].orientation, 'vertical')
        comparison = next(fig.axes[0] for fig in figures
                          if 'Reached with norm; not reached in reference' in fig.axes[0].get_title())
        self.assertEqual(len(comparison.containers[0]), 1)  # B has no reference dataset.
        self.assertEqual(comparison.containers[0][0].get_height(), .5)
        for fig in figures:
            self.assertTrue(all(re.fullmatch(r"\d+\.\d%", text.get_text())
                                for text in fig.axes[0].texts))
        self.assertTrue(all(path.parent == self.root and path.suffix == '.png' for path in paths))


if __name__ == '__main__':
    unittest.main()
