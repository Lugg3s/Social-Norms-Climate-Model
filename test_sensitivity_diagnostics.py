import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pandas as pd

import sensitivity_analysis as sensitivity
from model_equations import resolve_parameters


class SampleDiagnosticsTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.directory = Path(self.temporary.name)
        self.config = sensitivity.SensitivityConfig(simulation_time=1)
        self.job = (resolve_parameters("baseline"), ["social_norm_factor"], np.array([2.]), self.config)

    def events(self, name="sample_000007.jsonl"):
        return [json.loads(line) for line in (self.directory / name).read_text().splitlines()]

    def test_start_is_written_before_computation(self):
        def compute(job):
            events = self.events()
            self.assertEqual([event["status"] for event in events], ["started"])
            self.assertEqual(events[0]["parameters"]["social_norm_factor"], 2.)
            self.assertEqual(events[0]["sampled_parameters"], {"social_norm_factor": 2.})
            self.assertEqual(events[0]["sample_index"], 7)
            self.assertEqual(events[0]["worker_pid"], os.getpid())
            self.assertIn("started_at", events[0])
            return {"final_x": .3}

        with patch.object(sensitivity, "_run_sample", side_effect=compute):
            result = sensitivity._run_tracked_sample(self.job, 7, self.directory)
        self.assertEqual(result, {"final_x": .3})
        events = self.events()
        self.assertEqual(events[-1]["status"], "completed")
        self.assertIn("finished_at", events[-1])
        self.assertGreaterEqual(events[-1]["elapsed_seconds"], 0)

    def test_failure_is_persisted_and_reraised(self):
        with patch.object(sensitivity, "_run_sample", side_effect=ValueError("test failure")):
            with self.assertRaisesRegex(ValueError, "test failure"):
                sensitivity._run_tracked_sample(self.job, 7, self.directory)
        self.assertEqual(self.events()[-1]["status"], "failed")
        self.assertEqual(self.events()[-1]["error_type"], "ValueError")
        self.assertIn("test failure", self.events()[-1]["traceback"])

    def test_interruption_is_persisted_and_reraised(self):
        with patch.object(sensitivity, "_run_sample", side_effect=KeyboardInterrupt):
            with self.assertRaises(KeyboardInterrupt):
                sensitivity._run_tracked_sample(self.job, 7, self.directory)
        self.assertEqual(self.events()[-1]["status"], "interrupted")

    def test_boundary_logs_and_results(self):
        params = resolve_parameters("baseline")
        problem = {"names": ["social_norm_factor"], "bounds": [[0., 2.]]}
        expected = sensitivity.run_zero_boundary_cases(params, problem, self.config)
        actual = sensitivity.run_zero_boundary_cases(params, problem, self.config, self.directory)
        pd.testing.assert_frame_equal(actual, expected, check_exact=True)
        event = self.events("boundary_000000.jsonl")[0]
        self.assertEqual(event["parameters"]["social_norm_factor"], 0.)
        self.assertEqual(event["boundary_parameter"], "social_norm_factor")
        self.assertIsNone(event["sample_index"])

    def test_parallel_logs_preserve_results_and_sample_order(self):
        params = resolve_parameters("baseline")
        problem = {"names": ["social_norm_factor"]}
        samples = np.array([[1.], [2.]])
        expected = sensitivity.run_samples(params, problem, samples, self.config)
        config = sensitivity.SensitivityConfig(simulation_time=1, workers=2)
        actual = sensitivity.run_samples(params, problem, samples, config,
                                         diagnostics_dir=self.directory)
        pd.testing.assert_frame_equal(actual, expected, check_exact=True)
        for index, sample in enumerate(samples):
            events = self.events(f"sample_{index:06d}.jsonl")
            self.assertEqual([e["status"] for e in events], ["started", "completed"])
            self.assertNotEqual(events[0]["worker_pid"], os.getpid())
            self.assertEqual(events[0]["parameters"]["social_norm_factor"], sample[0])
            self.assertEqual(events[0]["sample_index"], index)


if __name__ == "__main__":
    unittest.main()
