import hashlib
import json
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path
from unittest.mock import patch

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

import sensitivity_analysis as sensitivity
import sensitivity_plots as plots


class RankingBarplotTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.addCleanup(plt.close, "all")

    def write_norm(self, name, scale=1.0, mode="simple_mean", provisional=False):
        folder = self.root / name
        folder.mkdir()
        indices = pd.DataFrame([
            {"parameter": parameter, "output": output, "ST": scale * (i + 1) / 10 + offset}
            for parameter, offset in [("social_norm_factor", 0), ("temperature_factor", 0.2)]
            for i, output in enumerate(sensitivity.SENSITIVITY_OUTPUTS)
        ])
        ranking = sensitivity.build_parameter_ranking(indices, mode)
        ranking.insert(0, "scenario", name)
        if provisional:
            ranking["analysis_status"] = "provisional"
            ranking["retained_base_samples"] = 12
        ranking.to_csv(folder / "parameter_ranking.csv", sep=";", index=False)
        metadata = {
            "scenario": name, "base_sample_size": 16, "simulation_time": 80,
            "outputs_for_ranking": sensitivity.SENSITIVITY_OUTPUTS,
            "elimination_time_definition": {"method": "zero_if_not_reached"},
            "score_mode": mode,
            "output_groups": sensitivity.OUTPUT_GROUPS,
            "analysis": {"status": "provisional" if provisional else "complete",
                         "retained_base_samples": 12 if provisional else 16},
        }
        (folder / "metadata.json").write_text(json.dumps(metadata), encoding="utf-8")
        return folder

    def test_png_and_svg_contain_all_outputs_and_saved_values(self):
        folder = self.write_norm("baseline")
        before = {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in folder.iterdir()}
        old_style = plt.rcParams["svg.fonttype"]
        paths = plots.create_parameter_ranking_barplots(self.root)
        self.assertEqual(len(paths), 5)
        self.assertTrue(all(p.exists() for p in paths))
        self.assertEqual(plt.rcParams["svg.fonttype"], old_style)
        self.assertEqual(plt.get_fignums(), [])
        self.assertFalse(list(self.root.glob("*normvergleich*")))
        for path, digest in before.items():
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), digest)
        svg = ET.parse(folder / "ranking_balken_zielvariablen.svg").getroot()
        ns = {"s": "http://www.w3.org/2000/svg"}
        texts = [element.text for element in svg.findall(".//s:text", ns)]
        for output in sensitivity.SENSITIVITY_OUTPUTS:
            label = plots.RANKING_LABELS[output]
            self.assertIn(label, texts)
        self.assertEqual(len(svg.findall(".//s:clipPath", ns)), len(sensitivity.SENSITIVITY_OUTPUTS))
        ranking = pd.read_csv(folder / "parameter_ranking.csv", sep=";")
        for value in ranking[sensitivity.SENSITIVITY_OUTPUTS].to_numpy().ravel():
            self.assertIn(f"{value:.3f}".replace(".", ","), texts)
        self.assertTrue(any("0 = nie erreicht" in (text or "") for text in texts))
        pixels = plt.imread(folder / "ranking_balken_zielvariablen.png")
        self.assertEqual(pixels.shape[1], 4500)
        self.assertEqual(pixels.shape[0], 1035 * ((len(sensitivity.SENSITIVITY_OUTPUTS) + 4) // 4))
        overview = ET.parse(self.root / plots.RANKING_OVERVIEW_FILENAME).getroot()
        panels = overview.findall("s:g/s:g[@data-ranking-panel]", ns)
        self.assertEqual(len(panels), 2)
        for stem, panel in zip(plots.RANKING_PLOT_STEMS, panels):
            original = ET.parse(folder / f"{stem}.svg").getroot()
            self.assertEqual([e.text for e in original.findall(".//s:text", ns)],
                             [e.text for e in panel.findall(".//s:text", ns)])
            self.assertEqual([e.attrib.get("d") for e in original.findall(".//s:path", ns)],
                             [e.attrib.get("d") for e in panel.findall(".//s:path", ns)])

    def test_legacy_charts_keep_original_outputs_and_penalty(self):
        old_outputs = ["final_x", "final_temperature", "cumulative_emissions",
                       "time_to_elimination_censored", "oscillation_amplitude",
                       "oscillations_per_500_years", "damping_index"]
        old_groups = {"mitigation": ["final_x", "time_to_elimination_censored"],
                      "climate": ["final_temperature", "cumulative_emissions"],
                      "dynamics": ["oscillation_amplitude", "oscillations_per_500_years", "damping_index"]}
        with patch.object(sensitivity, "SENSITIVITY_OUTPUTS", old_outputs), \
             patch.object(sensitivity, "OUTPUT_GROUPS", old_groups):
            folder = self.write_norm("legacy")
        metadata_path = folder / "metadata.json"
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        metadata.pop("elimination_time_definition")
        metadata["elimination_censor_offset"] = 900
        metadata_path.write_text(json.dumps(metadata), encoding="utf-8")
        original = {path: path.read_bytes() for path in folder.iterdir()}
        captured = {}

        def capture(figure, directory, stem):
            captured[stem] = ([axis.get_title(loc="left") for axis in figure.axes],
                              [text.get_text() for text in figure.texts])
            plt.close(figure)
            return []

        with patch.object(plots, "_save_ranking_figure", side_effect=capture), \
             patch.object(plots, "create_ranking_overview_svg", return_value=None):
            plots.create_parameter_ranking_barplots(self.root)
        titles, texts = captured[plots.RANKING_PLOT_STEMS[1]]
        self.assertEqual(len([title for title in titles if title]), 7)
        self.assertIn("Erste Schwelle mit Ersatzwert", titles)
        self.assertTrue(any("Ersatzwert 980" in text for text in texts))
        self.assertTrue(any("7 Zielvariablen" in text for text in texts))
        for path, content in original.items():
            self.assertEqual(path.read_bytes(), content)

    def test_horizon_censored_charts_keep_original_definition(self):
        folder = self.write_norm("capped")
        metadata_path = folder / "metadata.json"
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        metadata["elimination_time_definition"] = {"method": "right_censored_at_horizon"}
        ranking_path = folder / "parameter_ranking.csv"
        ranking = pd.read_csv(ranking_path, sep=";").rename(columns={"first_time_x95": "time_to_elimination_censored", "bool_x95": "threshold_reached"})
        ranking.to_csv(ranking_path, sep=";", index=False)
        metadata["outputs_for_ranking"] = ["time_to_elimination_censored" if name == "first_time_x95" else "threshold_reached" if name == "bool_x95" else name for name in metadata["outputs_for_ranking"]]
        metadata_path.write_text(json.dumps(metadata), encoding="utf-8")
        captured = {}

        def capture(figure, directory, stem):
            captured[stem] = ([axis.get_title(loc="left") for axis in figure.axes],
                              [text.get_text() for text in figure.texts])
            plt.close(figure)
            return []

        with patch.object(plots, "_save_ranking_figure", side_effect=capture), \
             patch.object(plots, "create_ranking_overview_svg", return_value=None):
            plots.create_parameter_ranking_barplots(self.root)
        titles, texts = captured[plots.RANKING_PLOT_STEMS[1]]
        self.assertIn("Erste Schwelle (zensiert bei T)", titles)
        self.assertTrue(any("bei 80 Jahren zensiert" in text for text in texts))

    def test_append_refreshes_old_and_new_norms_with_shared_limits_and_metadata(self):
        old = self.write_norm("old")
        old_bytes = (old / "parameter_ranking.csv").read_bytes()
        snapshots = {}

        def capture(figure, directory, stem):
            snapshots[directory.name, stem] = {
                "limits": [axis.get_xlim() for axis in figure.axes],
                "widths": [[bar.get_width() for bar in axis.patches] for axis in figure.axes],
                "texts": [t.get_text() for t in figure.texts]
                         + [t.get_text() for axis in figure.axes for t in axis.texts],
            }
            plt.close(figure)
            return []

        def append_norm(name, root, config, overwrite_existing):
            self.assertFalse(overwrite_existing)
            self.assertEqual(root, self.root)
            folder = self.write_norm(name, scale=10, mode="grouped_mean", provisional=True)
            ranking = pd.read_csv(folder / "parameter_ranking.csv", sep=";")
            ranking.loc[0, "x_mean"] = np.nan
            ranking.loc[1, "x_mean"] = -0.1
            ranking.to_csv(folder / "parameter_ranking.csv", sep=";", index=False)
            return folder

        with patch.object(plots, "_save_ranking_figure", side_effect=capture), \
             patch.object(plots, "create_ranking_overview_svg", return_value=None) as overview:
            plots.create_parameter_ranking_barplots(self.root)
            old_limit = snapshots["old", plots.RANKING_PLOT_STEMS[0]]["limits"][0]
            snapshots.clear()
            with patch.object(sensitivity, "run_sensitivity_analysis", side_effect=append_norm), \
                 patch.object(plots, "create_goal_variable_violin_boxplots", return_value=[]):
                sensitivity._run_scenarios(["new"], self.root, sensitivity.SensitivityConfig(),
                                           overwrite_existing=False)
        self.assertEqual(overview.call_args_list[0].args[1], [old])
        self.assertEqual(overview.call_args_list[1].args[1], [self.root / "new", old])
        self.assertEqual(len(snapshots), 4)
        for stem in plots.RANKING_PLOT_STEMS:
            self.assertEqual(snapshots["old", stem]["limits"], snapshots["new", stem]["limits"])
        self.assertGreater(snapshots["old", plots.RANKING_PLOT_STEMS[0]]["limits"][0][1], old_limit[1])
        texts = snapshots["new", plots.RANKING_PLOT_STEMS[0]]["texts"]
        self.assertTrue(any("Mittel der 3 Gruppenscores" in t for t in texts))
        self.assertTrue(any("VORLÄUFIG: 12" in t for t in texts))
        self.assertTrue(any("N = 16" in t and "80 Jahre" in t for t in texts))
        target = snapshots["new", plots.RANKING_PLOT_STEMS[1]]
        self.assertIn("n. v.", target["texts"])
        self.assertEqual(target["widths"][0], [-0.1])
        self.assertTrue(any(width > 1 for widths in target["widths"] for width in widths))
        self.assertEqual((old / "parameter_ranking.csv").read_bytes(), old_bytes)

    def test_empty_unavailable_and_incomplete_folders_are_skipped(self):
        (self.root / "interrupted").mkdir()
        folder = self.root / "empty"
        folder.mkdir()
        pd.DataFrame(columns=["parameter", "rank", "overall_score"]).to_csv(
            folder / "parameter_ranking.csv", sep=";", index=False)
        (folder / "metadata.json").write_text('{"analysis": {"status": "unavailable"}}')
        self.assertEqual(plots.create_parameter_ranking_barplots(self.root), [])
        folder = self.root / "incomplete"
        folder.mkdir()
        pd.DataFrame([{"parameter": "x", "rank": 1}]).to_csv(
            folder / "parameter_ranking.csv", sep=";", index=False)
        (folder / "metadata.json").write_text('{}')
        with self.assertWarnsRegex(UserWarning, "Skipping incomplete ranking"):
            self.assertEqual(plots.create_parameter_ranking_barplots(self.root), [])

    def test_overview_embeds_unique_ids_and_refreshes_sections_on_append(self):
        # Deliberately identical IDs, as occur in separate Matplotlib documents.
        source = '''<svg xmlns="http://www.w3.org/2000/svg"
            xmlns:xlink="http://www.w3.org/1999/xlink" viewBox="0 0 100 80">
            <defs><clipPath id="clip"><rect width="100" height="80"/></clipPath>
            <path id="marker" d="M 0 0 L 1 1"/></defs>
            <g id="axes_1" clip-path="url(#clip)">
            <use xlink:href="#marker"/><text x="5" y="20">unique content</text></g></svg>'''
        first = self.write_norm("first")
        second = self.write_norm("second")
        for directory in [first, second]:
            for stem in plots.RANKING_PLOT_STEMS:
                (directory / f"{stem}.svg").write_text(source, encoding="utf-8")
        path = plots.create_ranking_overview_svg(self.root, [first])
        plots.create_ranking_overview_svg(self.root, [first, second])
        tree = ET.parse(path)
        ns = {"s": "http://www.w3.org/2000/svg"}
        self.assertEqual(len(tree.findall("s:g", ns)), 2)
        self.assertEqual(len(tree.findall("s:g/s:g[@data-ranking-panel]", ns)), 4)
        self.assertFalse(tree.findall(".//s:svg", ns))
        ids = [e.attrib["id"] for e in tree.iter() if "id" in e.attrib]
        self.assertEqual(len(ids), len(set(ids)))
        for use in tree.findall(".//s:use", ns):
            self.assertIn(use.attrib["{http://www.w3.org/1999/xlink}href"][1:], ids)
        for group in tree.findall(".//s:g[@clip-path]", ns):
            self.assertIn(group.attrib["clip-path"][5:-1], ids)
        self.assertFalse(tree.findall(".//s:image", ns))
        for directory in [first, second]:
            for stem in plots.RANKING_PLOT_STEMS:
                self.assertEqual((directory / f"{stem}.svg").read_text(encoding="utf-8"), source)

    def test_formulas_show_all_agent_decision_parameters_and_continuous_bi(self):
        rows, notes = plots._ranking_formula_content(
            {"scenario": "Observation-based / intention motivation (agents)"}, {})
        equation = "\n".join(rows)
        self.assertIn(r"BI_i(t)=A_i(t)+\eta q_i(t)", equation)
        self.assertIn(r"\mathbf{1}_{q_i(t)\geq\phi}", equation)
        self.assertIn(r"b_i(t)=\mathbf{1}_{BI_i(t)\geq\psi}", equation)
        self.assertIn(r"\mathrm{Uniform}(0,2\beta)", equation)
        self.assertIn(r"\mathtt{network\_size}", equation)
        self.assertIn(r"\mathtt{temperature\_factor}", equation)
        self.assertNotIn(r"\dot{x}", equation)
        self.assertTrue(any("BI bleibt kontinuierlich" in note for note in notes))

    def test_formulas_distinguish_current_delay_factor_from_saved_free_theta(self):
        metadata = {"scenario": "Descriptive, injunctive, dynamic2"}
        current, notes = plots._ranking_formula_content(metadata, {"rho": 2, "theta": 4})
        self.assertIn(r"\theta=\tau\rho", "\n".join(current))
        legacy, legacy_notes = plots._ranking_formula_content(metadata, {"theta": 4, "delta": 1})
        self.assertNotIn(r"\rho", "\n".join(legacy))
        self.assertIn(r"x(t-\tau-\theta)", "\n".join(legacy))
        self.assertIn(r"\delta", legacy[1])
        self.assertTrue(any("historische Parameterdefinition" in note for note in legacy_notes))

    def test_saved_dynamic_scaling_is_not_replaced_by_current_equation(self):
        metadata = {"scenario": "Descriptive, injunctive, dynamic",
                    "problem": {"names": ["delta", "tau_STref"]}}
        rows, _ = plots._ranking_formula_content(metadata, {})
        self.assertIn(r"\tau_{\mathrm{STref}}", rows[1])
        self.assertIn(r"\delta", rows[1])
        self.assertIn(r"c_{\mathrm{dyn}}", rows[1])
        self.assertTrue(any(r"\tau_{xp}" in row for row in rows))
        self.assertTrue(any(r"\tau_{\mathrm{ref}}" in row for row in rows))

    def test_legacy_dynamic_time_scale_divides_the_entire_relative_change(self):
        values = {"x": .6, "x_p": .8, "x_ref": .4, "delta": 2,
                  "c_dyn": 3, "c_inj": 2, "x_target": .7, "tau_STref": 2}
        for norm, expected in [("dynamic social norm", .5),
                               ("dynamic baseline", .6),
                               ("Descriptive, injunctive, dynamic", 2.1)]:
            with self.subTest(norm=norm):
                term = plots._ranking_social_norm_term(norm, set(values))
                actual = term.subs({symbol: values[symbol.name] for symbol in term.free_symbols})
                self.assertAlmostEqual(float(actual), expected)

    def test_overview_embeds_a_formula_with_accessible_source_for_each_norm(self):
        folder = self.write_norm("baseline")
        plots.create_parameter_ranking_barplots(self.root)
        tree = ET.parse(self.root / plots.RANKING_OVERVIEW_FILENAME)
        ns = {"s": "http://www.w3.org/2000/svg"}
        formula = tree.find("s:g/s:g[@data-formula-panel]", ns)
        self.assertIsNotNone(formula)
        self.assertIn("S=2 x - 1", formula.find("s:desc", ns).text)
        self.assertFalse(tree.findall(".//s:image", ns))
        self.assertEqual(len(tree.findall("s:g/s:g[@data-ranking-panel]", ns)), 2)
        self.assertTrue((folder / "parameter_ranking.csv").exists())


if __name__ == "__main__":
    unittest.main()
