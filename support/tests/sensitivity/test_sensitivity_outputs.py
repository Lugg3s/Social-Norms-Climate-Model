import json
import tempfile
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

import analysis.sensitivity.sensitivity_analysis as sensitivity
from analysis.simulation_metrics import _base_metrics


class SensitivityOutputTests(unittest.TestCase):
    @staticmethod
    def metrics(times, values, *, agents=False):
        params = {"epsilon_max": 7.0, "s": 50.0}
        if agents:
            params["agent_decision_model"] = "annual_intention_threshold"
        return _base_metrics(times, np.zeros(len(times)), values,
                             np.zeros(len(times)), params)

    def test_x_mean_weights_irregular_time_intervals(self):
        # Linear x(t)=t/10: the arithmetic sample mean would incorrectly be 0.4.
        metrics = self.metrics([0, 2, 10], [0, 0.2, 1])
        self.assertAlmostEqual(metrics["x_area"], 5)
        self.assertAlmostEqual(metrics["x_mean"], 0.5)
        dense = self.metrics([0, 1, 2, 4, 8, 10], [0, 0.1, 0.2, 0.4, 0.8, 1])
        self.assertAlmostEqual(dense["x_mean"], metrics["x_mean"])

    def test_agent_mean_holds_actual_behavior_until_decision(self):
        coarse = self.metrics([217, 218, 220], [0.2, 0.8, 0], agents=True)
        dense = self.metrics([217, 217.5, 218, 218.5, 219, 220],
                             [0.2, 0.2, 0.8, 0.8, 0.8, 0], agents=True)
        self.assertAlmostEqual(coarse["x_mean"], (0.2 + 2 * 0.8) / 3)
        self.assertAlmostEqual(dense["x_mean"], coarse["x_mean"])

    def test_no_elimination_is_zero_without_losing_raw_nan(self):
        metrics = self.metrics([0, 1200], [0.3, 0.4])
        outputs = sensitivity._prepare_sensitivity_outputs(metrics, 1200)
        self.assertTrue(np.isnan(metrics["time_to_elimination"]))
        self.assertEqual(outputs["first_time_x95"], 0)
        self.assertFalse(outputs["bool_x95"])
        self.assertAlmostEqual(outputs["x_mean"], 0.35)
        self.assertEqual(set(outputs), set(sensitivity.SENSITIVITY_OUTPUTS))

    def test_crossing_at_horizon_keeps_actual_time(self):
        metrics = self.metrics([0, 1200], [0.3, 0.95])
        outputs = sensitivity._prepare_sensitivity_outputs(metrics, 1200)
        self.assertEqual(outputs["first_time_x95"], 1200)
        self.assertTrue(outputs["bool_x95"])

    def test_oscillation_occurrence_requires_two_complete_prominent_cycles(self):
        cases = [
            ([0.5] * 11, False),
            ([0.5, 0.8, 0.2, 0.8, 0.5], False),
            ([0.5, 0.8, 0.2, 0.8, 0.2, 0.8, 0.5], True),
            ([0.5, 0.505, 0.495, 0.505, 0.495, 0.505, 0.5], False),
        ]
        for values, expected in cases:
            with self.subTest(values=values):
                metrics = self.metrics(list(range(len(values))), values)
                outputs = sensitivity._prepare_sensitivity_outputs(metrics, len(values) - 1)
                self.assertIs(outputs["oscillation_occurrence"], expected)
                expected_rate = (metrics["n_oscillations"] * 500 / (len(values) - 1)
                                 if expected else 0.0)
                self.assertAlmostEqual(outputs["oscillations_per_500_years"], expected_rate)
        self.assertIn("oscillation_occurrence", sensitivity.OUTPUT_GROUPS["dynamics"])

    def test_oscillation_rate_scales_only_after_minimum_cycles(self):
        for count, expected in [(0, 0.0), (1, 0.0), (2, 5 / 3), (3, 2.5)]:
            with self.subTest(count=count):
                self.assertAlmostEqual(
                    sensitivity._oscillations_per_window({"n_oscillations": count}, 600),
                    expected,
                )
        self.assertEqual(sensitivity._oscillations_per_window({"n_oscillations": 2}, 0), 0.0)

    def test_transient_crossing_keeps_first_passage(self):
        metrics = self.metrics([0, 10, 20], [0.9, 1, 0.4])
        outputs = sensitivity._prepare_sensitivity_outputs(metrics, 20)
        self.assertAlmostEqual(outputs["first_time_x95"], 5)
        self.assertTrue(outputs["bool_x95"])
        self.assertFalse(metrics["elimination_success"])

    def test_non_eliminating_runs_remain_in_complete_sobol_blocks(self):
        metrics = self.metrics([0, 1200], [0.3, 0.4])
        outputs = sensitivity._prepare_sensitivity_outputs(metrics, 1200)
        frame = pd.DataFrame([{**metrics, **outputs, "status": "completed"}] * 6)
        retained, info = sensitivity.complete_sobol_blocks({"num_vars": 1}, frame)
        self.assertEqual(info["status"], "complete")
        self.assertEqual(len(retained), 6)
        self.assertTrue(retained["time_to_elimination"].isna().all())

    def test_append_rejects_old_definitions_and_accepts_current_ones(self):
        with tempfile.TemporaryDirectory() as root:
            folder = Path(root) / "baseline"
            folder.mkdir()
            metadata_path = folder / "metadata.json"
            metadata_path.write_text(json.dumps({"elimination_censor_offset": 10000}),
                                     encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "different output definitions"):
                sensitivity._validate_append_scenarios(Path(root), ["Dynamic social norm"])
            metadata_path.write_text(json.dumps({
                "outputs_for_ranking": sensitivity.SENSITIVITY_OUTPUTS,
                "elimination_time_definition": {"method": "right_censored_at_horizon"},
            }), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "different output definitions"):
                sensitivity._validate_append_scenarios(Path(root), ["Dynamic social norm"])
            metadata_path.write_text(json.dumps({
                "outputs_for_ranking": sensitivity.SENSITIVITY_OUTPUTS,
                "elimination_time_definition": {"method": "zero_if_not_reached"},
            }), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "different output definitions"):
                sensitivity._validate_append_scenarios(Path(root), ["Dynamic social norm"])
            metadata_path.write_text(json.dumps({
                "outputs_for_ranking": sensitivity.SENSITIVITY_OUTPUTS,
                "elimination_time_definition": {"method": "zero_if_not_reached"},
                "oscillations_per_500_years_definition": {
                    "minimum_complete_cycles": sensitivity.OSCILLATION_MIN_COMPLETE_CYCLES,
                    "method": "zero_below_minimum_otherwise_scaled_complete_cycle_count",
                },
            }), encoding="utf-8")
            sensitivity._validate_append_scenarios(Path(root), ["Dynamic social norm"])
            with self.assertRaises(FileExistsError):
                sensitivity._validate_append_scenarios(Path(root), ["baseline"])


if __name__ == "__main__":
    unittest.main()
