"""Configuration edits must reach both analyses without changing model inputs."""
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

import numpy as np

from analysis import bifurcation_diagram as diagram
from analysis import parameter_ranges as ranges
from analysis.sensitivity import sensitivity_analysis as sensitivity
from model import model_equations as model
from utils.paths import CONFIG_DIR


class ParameterRangeTests(unittest.TestCase):
    def configuration(self):
        return json.loads((CONFIG_DIR / "scenarios.json").read_text(encoding="utf-8"))

    def test_single_json_edit_updates_both_analyses_and_cli_wins(self):
        data = self.configuration()
        data["parameter_ranges"]["bounds"]["beta"] = [.25, 1.75]
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)
            (path / "scenarios.json").write_text(json.dumps(data), encoding="utf-8")
            with patch.object(ranges, "CONFIG_DIR", path), patch.object(model, "CONFIG_DIR", path):
                problem = sensitivity.build_problem("baseline")
                self.assertEqual(problem["bounds"][problem["names"].index("beta")], [.25, 1.75])
                values = diagram.scenario_grids(["baseline"], "beta")["baseline"]
                np.testing.assert_allclose(values, np.linspace(.25, 1.75, 100))
                overridden = sensitivity.build_problem("baseline", {"beta": [2, 3]})
                self.assertEqual(overridden["bounds"][overridden["names"].index("beta")], [2, 3])
                values = diagram.scenario_grids(["baseline"], "beta", interval=[2, 3], num_points=7)
                np.testing.assert_allclose(values["baseline"], np.linspace(2, 3, 7))
                values = diagram.scenario_grids(["baseline"], "beta", values=[9, 8])
                self.assertEqual(values["baseline"], [9, 8])
                self.assertEqual(model.resolve_parameters("baseline")["beta"], data["baseline"]["defaults"]["beta"])

    def test_scenario_defaults_select_inputs_but_all_norms_share_global_ranges(self):
        self.assertEqual(ranges.get_parameter_ranges("Descriptive, injunctive, dynamic2 (custom)"),
                         ranges.get_parameter_ranges("Descriptive, injunctive, dynamic2"))
        config = self.configuration()
        config["parameter_ranges"]["bounds"]["beta"] = [2, 4]
        del config["dynamic social norm2"]["defaults"]["beta"]
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)
            (path / "scenarios.json").write_text(json.dumps(config), encoding="utf-8")
            with patch.object(ranges, "CONFIG_DIR", path), patch.object(model, "CONFIG_DIR", path):
                grids = diagram.scenario_grids(["baseline", "dynamic social norm2"], "beta", num_points=3)
                self.assertEqual(grids["baseline"], [2, 3, 4])
                self.assertEqual(grids["dynamic social norm2"], [2, 3, 4])
                self.assertIn("beta", sensitivity.build_problem("baseline")["names"])
                self.assertNotIn("beta", sensitivity.build_problem("dynamic social norm2")["names"])
                self.assertEqual(ranges.get_parameter_range("beta"), [2, 4])
                self.assertNotIn("beta", model.load_scenarios()["dynamic social norm2"])

    def test_range_metadata_is_not_a_model_scenario_or_parameter(self):
        data = self.configuration()
        loaded = model.load_scenarios()
        self.assertEqual(set(loaded), set(data) - {"ignore", "parameter_ranges", "common_parameters"})
        for name, parameters in loaded.items():
            self.assertEqual(parameters, {**data["common_parameters"], **data[name]["defaults"],
                                         "social_norm": data[name]["social_norm"], "ABM": data[name]["ABM"]})
            self.assertNotIn("parameter_ranges", parameters)
            self.assertNotIn("defaults", parameters)

    def test_non_norm_overrides_can_be_fixed_or_included_with_a_range(self):
        data = self.configuration()
        data["Static injunctive"]["defaults"].update(C_at0=640, x0=.4)
        # A global range alone must not sample a shared parameter in every scenario.
        data["parameter_ranges"]["bounds"]["x0"] = [0, 1]
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)
            (path / "scenarios.json").write_text(json.dumps(data), encoding="utf-8")
            with patch.object(ranges, "CONFIG_DIR", path), patch.object(model, "CONFIG_DIR", path):
                parameters = model.resolve_parameters("Static injunctive")
                self.assertEqual(parameters["C_at0"], 640)
                self.assertEqual(parameters["x0"], .4)
                problem = sensitivity.build_problem("Static injunctive")
                self.assertNotIn("C_at0", problem["names"])
                self.assertIn("x0", problem["names"])
                self.assertNotIn("x0", sensitivity.build_problem("baseline")["names"])
                explicit = sensitivity.build_problem("Static injunctive", {"C_at0": [600, 700]})
                self.assertEqual(explicit["bounds"][explicit["names"].index("C_at0")], [600, 700])

    def test_behavior_inputs_are_explicit_and_not_inherited_from_baseline(self):
        data = self.configuration()
        for key in ("kappa", "social_norm_factor", "beta", "temperature_factor"):
            self.assertNotIn(key, data["common_parameters"])
        params = model.resolve_parameters("Observation-based / intention motivation (agents)")
        self.assertNotIn("kappa", params)
        self.assertNotIn("social_norm_factor", params)
        self.assertIn("beta", params)
        self.assertIn("temperature_factor", params)

    def test_agent_ranges_exclude_unused_ode_weights(self):
        problem = sensitivity.build_problem("Observation-based / intention motivation (agents)")
        self.assertNotIn("social_norm_factor", problem["names"])
        self.assertNotIn("kappa", problem["names"])
        with self.assertRaises(KeyError):
            sensitivity.build_problem("baseline", {"betaa": [0, 1]})

    def test_missing_json_ranges_do_not_fall_back_to_python_defaults(self):
        data = self.configuration()
        del data["parameter_ranges"]
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)
            (path / "scenarios.json").write_text(json.dumps(data), encoding="utf-8")
            with patch.object(ranges, "CONFIG_DIR", path), self.assertRaises(KeyError):
                sensitivity.build_problem("baseline")

    def test_repeatable_sobol_cli_override_and_endpoint_count(self):
        with patch.object(sys, "argv", ["sensitivity", "--parameter-range", "beta", "1", "2",
                                        "--parameter-range", "kappa", "0.1", "0.2"]):
            args = sensitivity.parse_args()
        self.assertEqual(ranges.parse_range_overrides(args.parameter_ranges),
                         {"beta": [1, 2], "kappa": [.1, .2]})
        args = diagram.parse_args(["--num-points", "7"])
        self.assertIsNone(args.parameter_values)
        self.assertIsNone(args.parameter_range)
        self.assertEqual(args.num_points, 7)
        with self.assertRaises(ValueError):
            ranges.parse_range_overrides([["beta", "0", "1"], ["beta", "2", "3"]])


if __name__ == "__main__":
    unittest.main()
