import json
import multiprocessing as mp
import os
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pandas as pd

from utils.bounded_process_map import bounded_map
import analysis.sensitivity.sensitivity_analysis as sensitivity
from model.model_equations import resolve_parameters
from analysis.sensitivity.sensitivity_plots import create_goal_variable_violin_boxplots


def timed_task(seconds):
    time.sleep(seconds)
    return os.getpid()


class TimeoutTests(unittest.TestCase):
    def test_dynamic2_sensitivity_enforces_tau_and_factor_bounds(self):
        for scenario_name in ["Descriptive, injunctive, dynamic2", "Injunctive, dynamic2"]:
            problem = sensitivity.build_problem(scenario_name)
            self.assertNotIn("theta", problem["names"])
            for name, minimum in (("tau", 0), ("rho", 1)):
                lower, upper = problem["bounds"][problem["names"].index(name)]
                self.assertGreater(lower, minimum)
                self.assertGreater(upper, lower)

    def test_goal_variable_violin_boxplots_use_completed_samples(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            for scenario_name, offset in [("baseline", 0.0), ("dynamic_norm", 1.0)]:
                scenario_dir = root / scenario_name
                scenario_dir.mkdir()
                frame = pd.DataFrame({
                    output: [index + offset for index in range(3)]
                    for output in sensitivity.SENSITIVITY_OUTPUTS
                })
                frame["status"] = ["completed", "completed", "failed"]
                frame.to_csv(scenario_dir / "simulation_outputs.csv", sep=";", index=False)

            paths = create_goal_variable_violin_boxplots(root, sensitivity.SENSITIVITY_OUTPUTS)

            self.assertEqual(len(paths), len(sensitivity.SENSITIVITY_OUTPUTS))
            self.assertTrue(all(path.exists() for path in paths))

    def test_append_mode_does_not_overwrite_existing_scenario(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            scenario_dir = root / "baseline"
            scenario_dir.mkdir()
            (scenario_dir / "metadata.json").write_text("existing", encoding="utf-8")
            with self.assertRaises(FileExistsError):
                sensitivity.run_sensitivity_analysis(
                    "baseline", root, sensitivity.SensitivityConfig(base_sample_size=2),
                    overwrite_existing=False,
                )

    def test_hung_worker_is_stopped_and_replaced(self):
        before = {p.pid for p in mp.active_children()}
        outcomes = dict(bounded_map(timed_task, [10., .01, .01], 1, .2))
        self.assertEqual(outcomes[0]["status"], "timed_out")
        self.assertEqual(outcomes[1]["status"], "completed")
        self.assertEqual(outcomes[2]["status"], "completed")
        self.assertNotEqual(outcomes[0]["worker_pid"], outcomes[1]["worker_pid"])
        self.assertEqual(outcomes[1]["worker_pid"], outcomes[2]["worker_pid"])
        self.assertEqual({p.pid for p in mp.active_children()}, before)

    def test_other_worker_continues(self):
        outcomes = dict(bounded_map(timed_task, [10., .01, .01, .01], 2, .5))
        self.assertEqual(outcomes[0]["status"], "timed_out")
        self.assertTrue(all(outcomes[i]["status"] == "completed" for i in (1, 2, 3)))

    def test_invalid_deadlines(self):
        for value in [0, -1, float("nan"), float("inf")]:
            with self.assertRaises(ValueError):
                sensitivity.SensitivityConfig(sample_timeout_minutes=value)

    def test_complete_blocks_preserve_order_and_indices(self):
        problem = {"num_vars": 2, "names": ["a", "b"], "bounds": [[0, 1], [0, 1]]}
        outputs = pd.DataFrame({name: np.arange(16, dtype=float) ** 2
                                for name in sensitivity.SENSITIVITY_OUTPUTS})
        outputs["status"] = "completed"
        outputs.loc[5, "status"] = "timed_out"
        outputs.loc[5, sensitivity.SENSITIVITY_OUTPUTS] = np.nan
        kept, info = sensitivity.complete_sobol_blocks(problem, outputs)
        expected = outputs.drop(index=[4, 5, 6, 7]).reset_index(drop=True)
        pd.testing.assert_frame_equal(kept, expected)
        self.assertEqual(info["status"], "provisional")
        self.assertEqual(info["retained_base_samples"], 3)
        self.assertEqual(info["missing_sample_indices"], [5])
        pd.testing.assert_frame_equal(sensitivity.analyze_outputs(problem, kept, 42),
                                      sensitivity.analyze_outputs(problem, expected, 42))

    def test_timeout_logging_and_continuation(self):
        config = sensitivity.SensitivityConfig()
        problem = {"names": ["social_norm_factor"]}
        metrics = {name: 1. for name in sensitivity.SENSITIVITY_OUTPUTS}
        def fake_map(*args):
            yield 0, dict(status="timed_out", elapsed_seconds=1200.,
                          worker_pid=123, started_at="test-start")
            yield 1, dict(status="completed", result=metrics)
        with tempfile.TemporaryDirectory() as folder:
            with patch.object(sensitivity, "bounded_map", side_effect=fake_map):
                outputs = sensitivity.run_samples({**resolve_parameters("baseline"), "social_norm_factor": 0.}, problem,
                    np.array([[2.], [3.]]), config, diagnostics_dir=Path(folder))
            record = json.loads((Path(folder) / "timeouts.jsonl").read_text())
            self.assertEqual(record["parameters"]["social_norm_factor"], 2.)
            self.assertEqual(record["sample_index"], 0)
            self.assertIn("finished_at", record)
            self.assertEqual(outputs["status"].tolist(), ["timed_out", "completed"])
            self.assertTrue(outputs.loc[0, sensitivity.SENSITIVITY_OUTPUTS].isna().all())

    def test_integration_failures_are_recorded_and_skipped(self):
        def fake_map(*args):
            for index in (0, 1):
                yield index, dict(status="failed", error_type="RuntimeError",
                    error_message="ODE integration failed: Required step size is less than spacing between numbers.",
                    traceback="solver traceback")
            yield 2, dict(status="completed", result={name: 1. for name in sensitivity.SENSITIVITY_OUTPUTS})
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "failed_sample.csv"
            with patch.object(sensitivity, "bounded_map", side_effect=fake_map):
                outputs = sensitivity.run_samples({**resolve_parameters("baseline"), "social_norm_factor": 0.}, {"names": ["social_norm_factor"]},
                    np.array([[2.], [3.], [4.]]), sensitivity.SensitivityConfig(), failure_path=path)
            self.assertEqual(outputs["status"].tolist(), ["failed", "failed", "completed"])
            failures = pd.read_csv(path, sep=";")
            self.assertEqual(failures["sample_index"].tolist(), [0, 1])
            self.assertEqual(json.loads(failures.iloc[1]["parameters"])["social_norm_factor"], 3.)
            self.assertTrue(outputs.loc[:1, sensitivity.SENSITIVITY_OUTPUTS].isna().all().all())

    def test_fraction_boundary_failures_are_recorded_and_skipped(self):
        def fake_map(*args):
            yield 0, dict(
                status="failed",
                error_type="RuntimeError",
                error_message=(
                    "Numerical integration left the valid fraction interval [0, 1] "
                    "in interval (411.0, 412.0): x: min=0.999999, max=1"
                ),
                traceback="solver traceback",
            )

        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "failed_sample.csv"
            with patch.object(sensitivity, "bounded_map", side_effect=fake_map):
                outputs = sensitivity.run_samples(
                    {**resolve_parameters("baseline"), "social_norm_factor": 0.}, {"names": ["social_norm_factor"]}, np.array([[2.]]),
                    sensitivity.SensitivityConfig(), failure_path=path,
                )
            self.assertEqual(outputs.loc[0, "status"], "failed")
            self.assertEqual(outputs.loc[0, sensitivity.SIMULATION_SUCCESS_OUTPUT], 0)
            self.assertTrue(outputs.loc[0, sensitivity.SENSITIVITY_OUTPUTS].isna().all())

    def test_unexpected_errors_still_raise(self):
        def fake_map(*args):
            yield 0, dict(status="failed", error_type="ValueError",
                          error_message="unexpected bug", traceback="test traceback")
        with patch.object(sensitivity, "bounded_map", side_effect=fake_map):
            with self.assertRaisesRegex(RuntimeError, "unexpected bug"):
                sensitivity.run_samples({}, {"names": ["social_norm_factor"]}, np.array([[2.]]),
                                        sensitivity.SensitivityConfig())

    def test_scenario_with_no_complete_blocks_still_writes_reports(self):
        def missing_samples(base, problem, samples, config, **kwargs):
            frame = pd.DataFrame(np.nan, index=range(len(samples)),
                                 columns=sensitivity.SENSITIVITY_OUTPUTS)
            frame["status"] = "timed_out"
            return frame
        with tempfile.TemporaryDirectory() as folder:
            with patch.object(sensitivity, "run_samples", side_effect=missing_samples), \
                 patch.object(sensitivity, "run_zero_boundary_cases", return_value=pd.DataFrame()):
                path = sensitivity.run_sensitivity_analysis("baseline", Path(folder),
                    sensitivity.SensitivityConfig(base_sample_size=2))
            info = json.loads((path / "analysis_status.json").read_text())
            self.assertEqual(info["status"], "unavailable")
            self.assertTrue(pd.read_csv(path / "parameter_ranking.csv", sep=";").empty)
            self.assertTrue(pd.read_csv(path / "sobol_indices.csv", sep=";").empty)
            expected_runs = 2 * (sensitivity.build_problem("baseline")["num_vars"] + 2)
            self.assertEqual(len(pd.read_csv(path / "simulation_outputs.csv", sep=";")), expected_runs)
            status = pd.read_csv(path / "simulation_status.csv", sep=";")
            self.assertEqual(status["simulation_success"].tolist(), [0] * expected_runs)

    def test_scenario_marks_provisional_rankings(self):
        def partial_samples(base, problem, samples, config, **kwargs):
            frame = pd.DataFrame({name: np.arange(len(samples), dtype=float) ** 2
                                  for name in sensitivity.SENSITIVITY_OUTPUTS})
            frame["status"] = "completed"
            frame.loc[6, "status"] = "timed_out"
            frame.loc[6, sensitivity.SENSITIVITY_OUTPUTS] = np.nan
            return frame
        with tempfile.TemporaryDirectory() as folder:
            with patch.object(sensitivity, "run_samples", side_effect=partial_samples), \
                 patch.object(sensitivity, "run_zero_boundary_cases", return_value=pd.DataFrame()):
                path = sensitivity.run_sensitivity_analysis("baseline", Path(folder),
                    sensitivity.SensitivityConfig(base_sample_size=4))
            for name in ["parameter_ranking.csv", "sobol_indices.csv"]:
                frame = pd.read_csv(path / name, sep=";")
                self.assertTrue(frame["analysis_status"].eq("provisional").all())
                self.assertTrue(frame["retained_base_samples"].eq(3).all())
                self.assertTrue(frame["analysis_warning"].str.contains("bias").all())
            info = json.loads((path / "analysis_status.json").read_text())
            block_size = sensitivity.build_problem("baseline")["num_vars"] + 2
            block_start = (6 // block_size) * block_size
            self.assertEqual(info["excluded_sample_indices"],
                             list(range(block_start, block_start + block_size)))


if __name__ == "__main__":
    unittest.main()
