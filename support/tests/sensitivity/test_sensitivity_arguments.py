"""Effective CLI settings survive defaults, failed runs, and append operations."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import analysis.sensitivity.sensitivity_analysis as sensitivity


class RunArgumentsTests(unittest.TestCase):
    def test_defaults_include_resolved_workers_scenarios_and_json_ranges(self):
        with tempfile.TemporaryDirectory() as directory:
            argv = ["sensitivity_analysis.py", "--output-root", directory]
            with patch("sys.argv", argv), patch.object(sensitivity.os, "cpu_count", return_value=8), \
                 patch.object(sensitivity, "_run_scenarios"), \
                 patch.object(sensitivity, "default_sensitivity_scenarios",
                              return_value=["baseline", "No social norm"]):
                sensitivity.main()
            path = next(Path(directory).glob("*/run_arguments.json"))
            entry = json.loads(path.read_text(encoding="utf-8"))["invocations"][0]
            parsed, effective = entry["parsed_arguments"], entry["effective_arguments"]
            self.assertEqual(set(parsed), set(vars(sensitivity.parse_args(argv[1:]))))
            self.assertTrue(set(parsed) <= set(effective))
            self.assertIsNone(parsed["workers"])
            self.assertIsNone(parsed["scenarios"])
            self.assertEqual(effective["workers"], 7)
            self.assertEqual(effective["scenarios"], ["No social norm", "baseline"])
            self.assertEqual(effective["simulation_time"], sensitivity.DEFAULT_SIMULATION_TIME)
            self.assertTrue(effective["save_time_series"])
            self.assertTrue(effective["compare_without_norm"])
            self.assertEqual(entry["parameter_ranges_by_scenario"]["baseline"]["beta"], [0., 5.])
            self.assertEqual(entry["cli_arguments"], argv[1:])
            self.assertEqual(entry["run_directory"], str(path.parent.resolve()))

    def test_explicit_values_are_saved_before_a_failed_simulation(self):
        with tempfile.TemporaryDirectory() as directory:
            argv = ["sensitivity_pipeline.py", "--output-root", directory,
                    "--scenarios", "baseline", "--base-sample-size", "2", "--workers", "2",
                    "--parameter-range", "beta", "1", "3", "--constant-temperature-costs",
                    "--no-save-time-series", "--no-compare-without-norm"]

            def fail(names, root, config, **kwargs):
                entry = json.loads((root / "run_arguments.json").read_text(encoding="utf-8"))["invocations"][0]
                effective = entry["effective_arguments"]
                self.assertEqual(effective["parameter_ranges"], {"beta": [1., 3.]})
                self.assertEqual(entry["parameter_ranges_by_scenario"]["baseline"]["beta"], [1., 3.])
                self.assertEqual(effective["workers"], config.workers)
                self.assertTrue(effective["constant_temperature_costs"])
                self.assertFalse(effective["save_time_series"])
                self.assertFalse(effective["compare_without_norm"])
                self.assertEqual(entry["entry_point"], argv[0])
                raise RuntimeError("simulation interrupted")

            with patch("sys.argv", argv), patch.object(sensitivity, "_run_scenarios", side_effect=fail):
                with self.assertRaisesRegex(RuntimeError, "simulation interrupted"):
                    sensitivity.main()

    def test_append_preserves_original_arguments(self):
        with tempfile.TemporaryDirectory() as directory:
            base = ["sensitivity_analysis.py", "--output-root", directory,
                    "--base-sample-size", "2", "--workers", "1"]
            with patch("sys.argv", base + ["--scenarios", "baseline"]), \
                 patch.object(sensitivity, "_run_scenarios"):
                sensitivity.main()
            path = next(Path(directory).glob("*/run_arguments.json"))
            original = json.loads(path.read_text(encoding="utf-8"))["invocations"][0]
            append = base + ["--append-existing-folder", path.parent.name,
                             "--scenarios", "No social norm", "--no-save-time-series"]
            with patch("sys.argv", append), patch.object(sensitivity, "_run_scenarios"):
                sensitivity.main()
            entries = json.loads(path.read_text(encoding="utf-8"))["invocations"]
            self.assertEqual(len(entries), 2)
            self.assertEqual(entries[0], original)
            self.assertEqual(entries[1]["effective_arguments"]["scenarios"], ["No social norm"])
            self.assertEqual(entries[1]["effective_arguments"]["append_existing_folder"], path.parent.name)
            self.assertFalse(entries[1]["effective_arguments"]["save_time_series"])


if __name__ == "__main__":
    unittest.main()
