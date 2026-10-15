import json
from pathlib import Path
import re
import tempfile
import unittest
import xml.etree.ElementTree as ET

from analysis.regression_trees.regression_tree_plots import SVG_NS, create_regression_tree_overview


class RegressionTreeOverviewTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def write_results(self, reports):
        (self.root / "reports.json").write_text(json.dumps(reports), encoding="utf-8")
        for index, report in enumerate(reports):
            folder = self.root / report["scenario"] / report["target"]
            folder.mkdir(parents=True)
            (folder / "report.json").write_text(json.dumps(report), encoding="utf-8")
            if report["status"] == "fitted":
                (folder / "tree.svg").write_text(
                    f'<svg xmlns="{SVG_NS}" xmlns:xlink="http://www.w3.org/1999/xlink" '
                    'viewBox="0 0 864 511.2">'
                    '<defs><clipPath id="clip"><rect width="864" height="511.2"/></clipPath>'
                    '<path id="shared_path" d="M 10 100 L 200 200"/></defs>'
                    '<g id="figure_1"><g id="axes_1" clip-path="url(#clip)">'
                    '<use xlink:href="#shared_path"/>'
                    f'<text id="text_1" x="400" y="200">temperature_factor ≤ {index}?</text>'
                    '<text x="400" y="250">final_x: 55,2 %</text></g>'
                    '<text x="400" y="30">Repeated original heading</text></g></svg>', encoding="utf-8")

    @staticmethod
    def fitted(norm):
        return {"scenario": norm, "target": "final_x", "status": "fitted",
                "total_rows": 80, "eligible_rows": 80, "train_rows": 60, "test_rows": 20,
                "train_blocks": 12, "test_blocks": 4,
                "test_metrics": {"mae": 0.1}, "baseline_test_metrics": {"mae": 0.3},
                "beats_mean_baseline": True}

    def test_full_norm_target_grid_preserves_vectors_and_scopes_ids(self):
        reports = [self.fitted("Norm_B"),
                   {"scenario": "Norm_B", "target": "median_period", "status": "insufficient_data",
                    "reason": "Not enough groups", "total_rows": 80, "eligible_rows": 0,
                    "train_rows": 0, "test_rows": 0, "train_blocks": 0, "test_blocks": 0},
                   self.fitted("Norm_A"),
                   {"scenario": "Norm_A", "target": "median_period", "status": "constant_training_target"}]
        self.write_results(reports)
        sources = {path: path.read_bytes() for path in self.root.rglob("*") if path.is_file()}
        path = create_regression_tree_overview(self.root)
        svg = ET.parse(path).getroot()
        sections = [node for node in svg.iter() if node.get("data-scenario")]
        self.assertEqual([node.get("data-scenario") for node in sections], ["Norm_B", "Norm_A"])
        self.assertTrue(all([node.get("data-target") for node in section if node.get("data-target")]
                            == ["final_x", "median_period"] for section in sections))
        self.assertEqual(sum(node.get("data-tree-panel") is not None for node in svg.iter()), 2)
        text = " ".join(svg.itertext())
        self.assertIn("Kein Tree: zu wenig gültige Daten", text)
        self.assertIn("Kein Tree: Zielwert im Training konstant", text)
        self.assertIn("temperature_factor ≤ 0?", text)
        self.assertIn("temperature_factor ≤ 2?", text)
        self.assertIn("final_x: 55,2 %", text)
        self.assertNotIn("Repeated original heading", text)
        ids = [node.get("id") for node in svg.iter() if node.get("id")]
        self.assertEqual(len(ids), len(set(ids)))
        for node in svg.iter():
            self.assertNotEqual(node.tag, f"{{{SVG_NS}}}image")
            for key, value in node.attrib.items():
                for ref in re.findall(r"url\(#([^)]*)\)", value):
                    self.assertIn(ref, ids)
                if key.endswith("href"):
                    self.assertTrue(value.startswith("#"))
                    self.assertIn(value[1:], ids)
        for source, content in sources.items():
            self.assertEqual(source.read_bytes(), content)

    def test_no_fitted_trees_still_produces_status_overview(self):
        self.write_results([{"scenario": "Norm_A", "target": "damping_rate",
                             "status": "unavailable", "reason": "Missing columns"}])
        path = create_regression_tree_overview(self.root, self.root / "export" / "overview.svg")
        text = " ".join(ET.parse(path).getroot().itertext())
        self.assertIn("0 Trees", text)
        self.assertIn("Kein Tree: Zielvariable nicht verfügbar", text)
        self.assertIn("Missing columns", text)

    def test_missing_fitted_svg_is_not_silently_omitted(self):
        self.write_results([self.fitted("Norm_A")])
        (self.root / "Norm_A" / "final_x" / "tree.svg").unlink()
        with self.assertRaises(FileNotFoundError):
            create_regression_tree_overview(self.root)


if __name__ == "__main__":
    unittest.main()
