"""Peak warming is an active target; first-passage time remains auxiliary data."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import numpy as np
import pandas as pd
from SALib.sample import sobol as sample_sobol

import analysis.sensitivity.sensitivity_analysis as sensitivity
from analysis.simulation_metrics import _base_metrics


class SensitivityTargetTests(unittest.TestCase):
    @staticmethod
    def warming_then_cooling_metrics():
        return _base_metrics(
            [0, 100, 300, 600], [0.0, 4.5, 3.0, 1.5],
            [0.3, 0.3, 0.4, 0.6], [0.0, 0.0, 0.0, 0.0],
            {"epsilon_max": 7.0, "s": 50.0},
        )

    @staticmethod
    def finite_blocks():
        rows = pd.DataFrame({name: np.linspace(0.1, 0.9, 9)
                             for name in sensitivity.SENSITIVITY_OUTPUTS})
        rows["status"] = "completed"
        rows["first_time_x95"] = np.nan
        rows["time_to_elimination"] = np.nan
        return rows

    def test_peak_includes_earlier_warming_while_preserving_final_temperature(self):
        metrics = self.warming_then_cooling_metrics()
        outputs = sensitivity._prepare_sensitivity_outputs(metrics, 600)
        self.assertEqual(outputs["max_temperature"], 4.5)
        self.assertEqual(outputs["final_temperature"], 1.5)
        self.assertEqual(metrics["time_to_peak_temperature"], 100)
        self.assertTrue(np.isnan(metrics["time_to_elimination"]))
        self.assertEqual(outputs["first_time_x95"], 0.0)
        self.assertIn("max_temperature", sensitivity.SENSITIVITY_OUTPUTS)
        self.assertNotIn("first_time_x95", sensitivity.SENSITIVITY_OUTPUTS)
        self.assertEqual(sensitivity.OUTPUT_GROUPS["climate"],
                         ["final_temperature", "max_temperature", "cumulative_emissions"])
        self.assertEqual(sensitivity.OUTPUT_GROUPS["mitigation"], ["x_mean", "bool_x95"])

    def test_auxiliary_missing_times_do_not_discard_successful_sobol_blocks(self):
        rows = self.finite_blocks()
        retained, info = sensitivity.complete_sobol_blocks({"num_vars": 1}, rows)
        self.assertEqual(info["status"], "complete")
        self.assertEqual(info["retained_base_samples"], 3)
        self.assertEqual(info["included_sample_indices"], list(range(9)))
        pd.testing.assert_frame_equal(retained, rows)
        # Earlier archives need not provide this auxiliary column at all.
        without_time = rows.drop(columns="first_time_x95")
        retained, info = sensitivity.complete_sobol_blocks({"num_vars": 1}, without_time)
        self.assertEqual(info["retained_base_samples"], 3)
        pd.testing.assert_frame_equal(retained, without_time)

    def test_missing_peak_excludes_only_its_complete_sobol_block(self):
        rows = self.finite_blocks()
        rows.loc[4, "max_temperature"] = np.nan
        retained, info = sensitivity.complete_sobol_blocks({"num_vars": 1}, rows)
        self.assertEqual(info["status"], "provisional")
        self.assertEqual(info["excluded_block_indices"], [1])
        self.assertEqual(info["missing_sample_indices"], [4])
        self.assertEqual(info["excluded_sample_indices"], [3, 4, 5])
        pd.testing.assert_frame_equal(retained, rows.drop(index=[3, 4, 5]).reset_index(drop=True))

    def test_real_sobol_analysis_and_scores_use_peak_not_auxiliary_timing(self):
        problem = {"num_vars": 1, "names": ["beta"], "bounds": [[0.0, 1.0]]}
        beta = sample_sobol.sample(problem, 32, calc_second_order=False, seed=42)[:, 0]
        rows = pd.DataFrame({
            "x_mean": beta,
            "final_temperature": 1.0 + 0.5 * beta,
            "max_temperature": 3.0 + beta * beta,
            "cumulative_emissions": 100.0 * (1.0 - beta),
            "bool_x95": beta > 0.5,
            "oscillation_occurrence": beta < 0.25,
            "oscillations_per_500_years": np.where(beta < 0.25, 5.0, 0.0),
            "first_time_x95": np.nan,
            "status": "completed",
        })
        indices = sensitivity.analyze_outputs(problem, rows, seed=42)
        self.assertEqual(set(indices.output), set(sensitivity.SENSITIVITY_OUTPUTS))
        self.assertNotIn("first_time_x95", set(indices.output))
        peak_index = indices.loc[indices.output.eq("max_temperature"), "ST"].item()
        self.assertGreater(peak_index, 0.8)
        self.assertTrue(np.isfinite(indices[["S1", "ST"]].to_numpy()).all())
        scores = indices.set_index("output").ST
        for mode in ("simple_mean", "grouped_mean"):
            with self.subTest(score_mode=mode):
                ranking = sensitivity.build_parameter_ranking(indices, mode).iloc[0]
                self.assertNotIn("first_time_x95", ranking.index)
                self.assertEqual(ranking["max_temperature"], peak_index)
                climate_mean = scores[["final_temperature", "max_temperature", "cumulative_emissions"]].mean()
                self.assertAlmostEqual(ranking.climate, climate_mean)
                mitigation_mean = scores[["x_mean", "bool_x95"]].mean()
                dynamics_mean = scores[["oscillation_occurrence", "oscillations_per_500_years"]].mean()
                expected_overall = (scores.mean() if mode == "simple_mean" else
                                    np.mean([mitigation_mean, climate_mean, dynamics_mean]))
                self.assertAlmostEqual(ranking.overall_score, expected_overall)

    def test_saved_artifacts_keep_auxiliary_timing_and_record_peak_definition(self):
        metrics = self.warming_then_cooling_metrics()
        outputs = {**metrics, **sensitivity._prepare_sensitivity_outputs(metrics, 600),
                   "status": "completed"}

        def saved_samples(base, problem, samples, config, **kwargs):
            return pd.DataFrame([outputs] * len(samples))

        with tempfile.TemporaryDirectory() as directory:
            config = sensitivity.SensitivityConfig(base_sample_size=2,
                                                   save_time_series=False,
                                                   compare_without_norm=False)
            with patch.object(sensitivity, "run_samples", side_effect=saved_samples), \
                 patch.object(sensitivity, "run_zero_boundary_cases", return_value=pd.DataFrame()), \
                 patch("analysis.behaviour_classification_plots.save_classification_outputs"):
                folder = sensitivity.run_sensitivity_analysis("baseline", Path(directory), config)
            metadata = json.loads((folder / "metadata.json").read_text(encoding="utf-8"))
            self.assertIn("max_temperature", metadata["outputs_for_ranking"])
            self.assertNotIn("first_time_x95", metadata["outputs_for_ranking"])
            self.assertIn("first_time_x95", metadata["raw_metric_columns"])
            self.assertIn("saved_metric", metadata["elimination_time_definition"])
            self.assertNotIn("sobol_output", metadata["elimination_time_definition"])
            self.assertIn("historical", metadata["max_temperature_definition"]["statistic"])
            self.assertIn("resolution", metadata["max_temperature_definition"]["resolution_note"])
            saved = pd.read_csv(folder / "simulation_outputs.csv", sep=";")
            self.assertTrue(saved.first_time_x95.eq(0.0).all())
            self.assertTrue(saved.time_to_elimination.isna().all())
            self.assertTrue(saved.max_temperature.eq(4.5).all())
            self.assertTrue(saved.final_temperature.eq(1.5).all())
            indices = pd.read_csv(folder / "sobol_indices.csv", sep=";")
            self.assertNotIn("first_time_x95", set(indices.output))
            ranking = pd.read_csv(folder / "parameter_ranking.csv", sep=";")
            self.assertIn("max_temperature", ranking)
            self.assertNotIn("first_time_x95", ranking)


if __name__ == "__main__":
    unittest.main()
