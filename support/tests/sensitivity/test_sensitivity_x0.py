"""A fixed initial mitigation share reaches every sensitivity-run input."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import numpy as np
import pandas as pd

import analysis.sensitivity.sensitivity_analysis as sensitivity
from model.model_equations import resolve_parameters


AGENT_SCENARIO = "Observation-based / intention motivation (agents)"


class SensitivityInitialShareTests(unittest.TestCase):
    def test_cli_preserves_scenario_initial_value_unless_explicitly_overridden(self):
        self.assertIsNone(sensitivity.parse_args([]).x0)
        self.assertIsNone(sensitivity.SensitivityConfig().x0)
        self.assertEqual(sensitivity.parse_args(["--x0", "0.05"]).x0, 0.05)
        for name in ("baseline", AGENT_SCENARIO, "No social norm"):
            with self.subTest(scenario=name):
                original = resolve_parameters(name)
                unchanged = sensitivity._scenario_parameters(name, sensitivity.SensitivityConfig())
                overridden = sensitivity._scenario_parameters(
                    name, sensitivity.SensitivityConfig(x0=0.05))
                self.assertEqual(unchanged, original)
                self.assertEqual(overridden["x0"], 0.05)
                self.assertEqual({k: v for k, v in overridden.items() if k != "x0"},
                                 {k: v for k, v in original.items() if k != "x0"})
                self.assertEqual(resolve_parameters(name), original)
                self.assertNotIn("x0", sensitivity.build_problem(name)["names"])

    def test_initial_share_must_be_finite_and_in_unit_interval(self):
        for value in (-0.001, 1.001, float("nan"), float("inf"), -float("inf")):
            with self.subTest(value=value), self.assertRaises(ValueError):
                sensitivity.SensitivityConfig(x0=value)
        for value in (0.0, 0.05, 1.0):
            with self.subTest(value=value):
                self.assertEqual(sensitivity.SensitivityConfig(x0=value).x0, value)

    def test_fixed_and_sampled_initial_share_cannot_be_combined(self):
        problem = {"num_vars": 2, "names": ["beta", "x0"], "bounds": [[0., 5.], [0., 1.]]}
        with patch.object(sensitivity, "build_problem", return_value=problem):
            with self.assertRaisesRegex(ValueError, "x0"):
                sensitivity._scenario_parameters("baseline", sensitivity.SensitivityConfig(x0=0.05))
            # An existing custom scenario may still sample x0 if no fixed flag is used.
            self.assertEqual(sensitivity._scenario_parameters("baseline", sensitivity.SensitivityConfig()),
                             resolve_parameters("baseline"))

    def test_main_records_requested_and_effective_initial_share(self):
        for value in (None, 0.05):
            with self.subTest(x0=value), tempfile.TemporaryDirectory() as directory:
                argv = ["sensitivity_analysis.py", "--output-root", directory,
                        "--base-sample-size", "2", "--workers", "1",
                        "--scenarios", "baseline", AGENT_SCENARIO]
                if value is not None:
                    argv += ["--x0", str(value)]
                with patch("sys.argv", argv), patch.object(sensitivity, "_run_scenarios") as run:
                    sensitivity.main()
                config = run.call_args.args[2]
                self.assertEqual(config.x0, value)
                arguments_path = next(Path(directory).glob("*/run_arguments.json"))
                entry = json.loads(arguments_path.read_text(encoding="utf-8"))["invocations"][0]
                self.assertEqual(entry["parsed_arguments"]["x0"], value)
                self.assertEqual(entry["effective_arguments"]["x0"], value)
                for name in ("baseline", AGENT_SCENARIO):
                    expected = resolve_parameters(name)["x0"] if value is None else value
                    self.assertEqual(entry["model_parameters_by_scenario"][name]["x0"], expected)
                    self.assertNotIn("x0", entry["parameter_ranges_by_scenario"][name])

    def test_override_is_saved_and_shared_by_samples_boundaries_and_references(self):
        config = sensitivity.SensitivityConfig(
            x0=0.05, base_sample_size=2, save_time_series=False,
            compare_without_norm=True)

        def outputs(base, problem, samples, actual_config, **kwargs):
            self.assertEqual(base["x0"], 0.05)
            self.assertEqual(actual_config, config)
            self.assertNotIn("x0", problem["names"])
            frame = pd.DataFrame({name: np.linspace(0.1, 0.9, len(samples))
                                  for name in sensitivity.SENSITIVITY_OUTPUTS})
            frame["status"] = "completed"
            return frame

        def boundaries(base, problem, actual_config, *args, **kwargs):
            self.assertEqual(base["x0"], 0.05)
            return pd.DataFrame()

        def comparisons(frame, base, problem, samples, actual_config, *args, **kwargs):
            self.assertEqual(base["x0"], 0.05)
            result = frame.copy()
            result["norm_comparison_reference_reused"] = True
            return result, 0

        with tempfile.TemporaryDirectory() as directory:
            with patch.object(sensitivity, "run_samples", side_effect=outputs) as samples, \
                 patch.object(sensitivity, "run_zero_boundary_cases", side_effect=boundaries) as boundary, \
                 patch.object(sensitivity, "add_no_norm_comparisons", side_effect=comparisons) as reference, \
                 patch("analysis.behaviour_classification_plots.save_classification_outputs"):
                output = sensitivity.run_sensitivity_analysis("baseline", Path(directory), config)
            saved = json.loads((output / "parameters.json").read_text(encoding="utf-8"))
            self.assertEqual(saved["x0"], 0.05)
            metadata = json.loads((output / "metadata.json").read_text(encoding="utf-8"))
            self.assertEqual(metadata["x0"], 0.05)
            sampled = pd.read_csv(output / "samples.csv", sep=";")
            self.assertNotIn("x0", sampled.columns)
            samples.assert_called_once()
            boundary.assert_called_once()
            reference.assert_called_once()

    def test_both_reference_models_keep_overridden_initial_share(self):
        config = sensitivity.SensitivityConfig(x0=0.05, save_time_series=False)
        metrics = {name: 0.3 for name in sensitivity.SENSITIVITY_OUTPUTS}
        metrics.update(time_to_elimination=float("nan"), bool_x95=False, n_oscillations=0)
        for name in ("baseline", AGENT_SCENARIO):
            with self.subTest(scenario=name):
                params = sensitivity._scenario_parameters(name, config)
                job = (params, ["beta"], np.array([1.2]), config)
                with patch.object(sensitivity, "simulate", return_value={}) as simulate, \
                     patch.object(sensitivity, "compute_run_metrics", return_value=metrics):
                    sensitivity._run_sample(job, without_norm=True)
                actual = simulate.call_args.kwargs["extension"]
                self.assertEqual(actual["x0"], 0.05)
                self.assertEqual(actual["beta"], 1.2)
                if actual["ABM"]:
                    self.assertEqual(actual["eta"], 0)
                else:
                    self.assertEqual(actual["social_norm"], "No social norm")

    @staticmethod
    def _existing_run(root, value):
        folder = root / "baseline"
        folder.mkdir()
        metadata = {
            "scenario": "baseline",
            "outputs_for_ranking": sensitivity.SENSITIVITY_OUTPUTS,
            "elimination_time_definition": {"method": "zero_if_not_reached"},
            "oscillations_per_500_years_definition": {
                "minimum_complete_cycles": sensitivity.OSCILLATION_MIN_COMPLETE_CYCLES,
                "method": "zero_below_minimum_otherwise_scaled_complete_cycle_count",
            },
        }
        (folder / "metadata.json").write_text(json.dumps(metadata), encoding="utf-8")
        (folder / "parameters.json").write_text(json.dumps({"x0": value}), encoding="utf-8")

    def test_append_compares_effective_values_not_whether_flag_was_provided(self):
        default = resolve_parameters("baseline")["x0"]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self._existing_run(root, default)
            for value in (None, default):
                with self.subTest(x0=value):
                    sensitivity._validate_append_scenarios(root, ["No social norm"], x0=value)
            with self.assertRaisesRegex(ValueError, "x0|initial"):
                sensitivity._validate_append_scenarios(root, ["No social norm"], x0=0.05)

    def test_append_rejects_implicit_default_after_an_overridden_run(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self._existing_run(root, 0.05)
            sensitivity._validate_append_scenarios(root, ["No social norm"], x0=0.05)
            with self.assertRaisesRegex(ValueError, "x0|initial"):
                sensitivity._validate_append_scenarios(root, ["No social norm"])

    def test_append_can_check_metadata_when_parameters_file_is_unavailable(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self._existing_run(root, 0.05)
            folder = root / "baseline"
            metadata = json.loads((folder / "metadata.json").read_text(encoding="utf-8"))
            metadata["x0"] = 0.05
            (folder / "metadata.json").write_text(json.dumps(metadata), encoding="utf-8")
            (folder / "parameters.json").unlink()
            sensitivity._validate_append_scenarios(root, ["No social norm"], x0=0.05)
            with self.assertRaisesRegex(ValueError, "x0|initial"):
                sensitivity._validate_append_scenarios(root, ["No social norm"], x0=0.3)

    def test_append_refuses_unverifiable_explicit_override_in_legacy_results(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self._existing_run(root, 0.3)
            (root / "baseline" / "parameters.json").unlink()
            sensitivity._validate_append_scenarios(root, ["No social norm"])
            with self.assertRaisesRegex(ValueError, "x0|initial"):
                sensitivity._validate_append_scenarios(root, ["No social norm"], x0=0.05)

    def test_append_validates_recorded_initial_share_before_scenario_artifacts_exist(self):
        with tempfile.TemporaryDirectory() as directory:
            argv = ["sensitivity_analysis.py", "--output-root", directory,
                    "--base-sample-size", "2", "--workers", "1",
                    "--scenarios", "baseline", "--x0", "0.05"]
            with patch("sys.argv", argv), patch.object(sensitivity, "_run_scenarios"):
                sensitivity.main()
            root = next(Path(directory).iterdir())
            self.assertFalse(list(root.glob("*/metadata.json")))
            sensitivity._validate_append_scenarios(root, ["No social norm"], x0=0.05)
            with self.assertRaisesRegex(ValueError, "x0|initial"):
                sensitivity._validate_append_scenarios(root, ["No social norm"])


if __name__ == "__main__":
    unittest.main()
