import json
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pandas as pd

from analysis.no_norm_comparison import (
    PROFILE_PREFIX as P, PREFIX as C, transition_profile, compare_profiles,
    without_norm_parameters, save_comparison_frequencies,
)
from model.model_equations import resolve_parameters
from analysis.sensitivity import sensitivity_analysis as sensi
from simulation.time_series import load_time_series


def completed(t, x, **kwargs):
    return {"status": "completed", **transition_profile(t, x, **kwargs)}


class NoNormComparisonTests(unittest.TestCase):
    def test_same_thresholds_exact_interpolated_first_reach_and_history_excluded(self):
        profile = transition_profile([0, 216, 217, 227, 237], [1, 1, .5, 1, 0])
        self.assertAlmostEqual(profile[P + "first_x1"], 226)
        self.assertAlmostEqual(profile[P + "first_x0"], 236.5)
        already_low = transition_profile([0, 217, 220], [0, .01, .1])
        self.assertEqual(already_low[P + "first_x0"], 217)

    def test_annual_threshold_times_are_not_interpolated(self):
        continuous = transition_profile([217, 218, 219], [.3, 1, 0])
        annual = transition_profile([217, 218, 219], [.3, 1, 0], stepwise=True)
        self.assertLess(continuous[P + "first_x1"], 218)
        self.assertEqual(annual[P + "first_x1"], 218)
        self.assertEqual(annual[P + "first_x0"], 219)

    def test_all_timing_categories_and_nullable_binary(self):
        base = {"status": "completed", P + "status": "Available"}
        for left, right, label, binary in [
            (230, 240, "Earlier", True), (240, 230, "Later", False),
            (230, 230.000001, "Equal", None), (230, None, "Only with norm reached", None),
            (None, 230, "Only without norm reached", None), (None, None, "Neither reached", None),
        ]:
            with self.subTest(label=label):
                actual = {**base, P + "first_x1": left}
                reference = {**base, P + "first_x1": right}
                result = compare_profiles(actual, reference)
                self.assertEqual(result[C + "x1_timing"], label)
                self.assertIs(result[C + "x1_earlier"], binary)
                self.assertEqual(result[C + "x1_time"], left)

    def test_largest_annual_change_is_independent_of_onset(self):
        fast = completed([217, 220, 230, 240, 250], [0, .1, .9, .99, 1])
        slow = completed([217, 220, 240, 260, 280], [0, .1, .9, .99, 1])
        delayed = completed([217, 230, 240, 250, 260], [0, .1, .9, .99, 1])
        self.assertAlmostEqual(fast[P + "slope"], .08)
        self.assertEqual(compare_profiles(fast, slow)[C + "slope"], "Steeper")
        self.assertIs(compare_profiles(slow, fast)[C + "slope_steeper"], False)
        self.assertEqual(compare_profiles(fast, delayed)[C + "slope"], "Equal")

    def test_falling_transitions_compare_speed_magnitude(self):
        fast = completed([217, 220, 230, 240], [1, .9, .1, 0])
        slow = completed([217, 220, 240, 260], [1, .9, .1, 0])
        self.assertEqual(fast[P + "direction"], "Falling")
        self.assertAlmostEqual(fast[P + "slope"], .08)
        self.assertEqual(compare_profiles(fast, slow)[C + "slope"], "Steeper")

    def test_threshold_passage_is_not_required_but_oscillations_are_excluded(self):
        partial = completed([217, 230, 240], [.3, .8, .85])
        self.assertAlmostEqual(partial[P + "slope"], .5 / 13)
        self.assertIsNone(partial[P + "first_x1"])
        oscillating = completed([217, 230, 240], [0, .9, 1], oscillatory=True)
        complete = completed([217, 230, 240], [0, .9, 1])
        self.assertIsNone(oscillating[P + "slope"])
        self.assertEqual(compare_profiles(oscillating, complete)[C + "slope"], "Not comparable")
        decreasing = completed([217, 230, 240], [1, .1, 0])
        self.assertEqual(compare_profiles(complete, decreasing)[C + "slope"], "Opposite directions")

    def test_largest_annual_change_keeps_reversals_and_annual_jumps(self):
        interrupted = completed([217, 220, 225, 230, 240], [0, .2, 0, .1, .9])
        self.assertAlmostEqual(interrupted[P + "slope"], .08)
        annual = completed([217, 218, 219], [0, 1, 1], stepwise=True)
        self.assertEqual(annual[P + "slope"], 1)
        self.assertEqual(annual[P + "slope_status"], "Available")

    def test_default_start_and_subannual_spikes_use_calendar_year_changes(self):
        # A subannual 60-point spike returns before the next annual value.
        t = [0, 216, 217, 217.1, 217.2, 218, 219, 220]
        x = [1, 1, .3, .9, .3, .4, .6, .7]
        profile = transition_profile(t, x)
        self.assertAlmostEqual(profile[P + "slope"], .2)
        self.assertEqual(profile[P + "slope_start"], 218)
        self.assertEqual(profile[P + "slope_end"], 219)
        self.assertEqual(profile[P + "direction"], "Rising")
        dense_t = np.linspace(217, 220, 601)
        dense = transition_profile(dense_t, np.interp(dense_t, t, x))
        self.assertAlmostEqual(dense[P + "slope"], profile[P + "slope"])

    def test_agent_yearly_changes_do_not_smear_decisions(self):
        coarse = transition_profile([217, 218, 219], [.3, .8, .6], stepwise=True)
        dense = transition_profile([217, 217.5, 218, 218.5, 219],
                                   [.3, .3, .8, .8, .6], stepwise=True)
        self.assertAlmostEqual(coarse[P + "slope"], .5)
        self.assertEqual(coarse, dense)

    def test_constant_trajectories_and_incomplete_years(self):
        stationary = completed([217, 218, 219], [.3, .3, .3])
        rising = completed([217, 218, 219], [.3, .5, .6])
        self.assertEqual(stationary[P + "slope"], 0)
        self.assertEqual(stationary[P + "direction"], "Stationary")
        self.assertEqual(compare_profiles(stationary, stationary)[C + "slope"], "Equal")
        self.assertEqual(compare_profiles(rising, stationary)[C + "slope"], "Steeper")
        for t in ([217, 217.9], [217.5, 218.5]):
            self.assertIsNone(transition_profile(t, [.3, .8])[P + "slope"])
        falling = transition_profile([217, 218, 219], [.3, .2, .25])
        self.assertAlmostEqual(falling[P + "signed_annual_change"], -.1)
        self.assertEqual(falling[P + "direction"], "Falling")

    def test_invalid_short_and_failed_references_are_not_neither_reached(self):
        actual = completed([217, 220], [.3, .4])
        for reference in ({"status": "timed_out"}, {"status": "failed"},
                          completed([0, 1], [.3, .4]), completed([217, 219, 218], [.3, .4, .5])):
            with self.subTest(reference=reference):
                result = compare_profiles(actual, reference)
                self.assertEqual(result[C + "x0_timing"], "Not comparable")
                self.assertIsNone(result[C + "x0_earlier"])

    def test_parameters_preserve_the_engine_and_all_physical_inputs(self):
        for name in ("Descriptive, injunctive, dynamic2", "Observation-based / intention motivation (agents)"):
            actual = resolve_parameters(name)
            reference = without_norm_parameters(actual)
            changed = {key for key in reference if reference[key] != actual[key]}
            self.assertEqual(changed, {"eta"} if actual["ABM"] else {"social_norm"})
            resolve_parameters(reference)

    def test_reference_diagnostics_archive_seed_and_agent_control(self):
        params = resolve_parameters("Observation-based / intention motivation (agents)")
        params.update(network_size=2, eta=.5)
        config = sensi.SensitivityConfig(simulation_time=219, n_agents=7,
                                         coupling_interval=1, output_points_per_year=2)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            job = (params, ["eta"], np.array([.8]), config)
            sensi._run_tracked_sample(job, 17, root / "diagnostics", "reference", None, root / "series")
            events = [json.loads(line) for line in (root / "diagnostics/reference_000017.jsonl").read_text().splitlines()]
            self.assertEqual(events[0]["sample_index"], 17)
            self.assertEqual(events[0]["parameters"]["eta"], 0)
            _, metadata = load_time_series(root / "series/reference_000017.npz")
            self.assertTrue(metadata["parameters"]["ABM"])
            self.assertEqual(metadata["parameters"]["eta"], 0)
            self.assertEqual(metadata["solver_settings"]["seed"], config.seed)

    def test_reference_failure_preserves_original_sobol_success_and_rows(self):
        records = pd.DataFrame([{**completed([217, 230], [.3, 1]), "sample_index": 0,
                                 **{key: .5 for key in sensi.SENSITIVITY_OUTPUTS}},
                                {**completed([217, 230], [.3, .4]), "sample_index": 1,
                                 **{key: .2 for key in sensi.SENSITIVITY_OUTPUTS}}])
        references = pd.DataFrame([{"status": "timed_out"}, completed([217, 230], [.3, .4])])
        with tempfile.TemporaryDirectory() as directory, patch.object(sensi, "run_samples", return_value=references):
            paired, count = sensi.add_no_norm_comparisons(
                records, resolve_parameters("baseline"), {"names": ["beta"]}, np.array([[1.], [2.]]),
                sensi.SensitivityConfig(), Path(directory), None, None)
            self.assertEqual(count, 2)
            self.assertEqual(paired.loc[0, C + "x1_timing"], "Not comparable")
            pd.testing.assert_frame_equal(paired[sensi.SENSITIVITY_OUTPUTS], records[sensi.SENSITIVITY_OUTPUTS])
            self.assertEqual(paired["status"].tolist(), ["completed", "completed"])

    def test_self_reference_reuses_runs_and_frequencies_include_all_rows(self):
        records = pd.DataFrame([{**completed([217, 230], [.3, 1]), "sample_index": 0},
                                {"sample_index": 1, "status": "failed"}])
        with tempfile.TemporaryDirectory() as directory, patch.object(sensi, "run_samples") as run:
            root = Path(directory)
            paired, count = sensi.add_no_norm_comparisons(records, resolve_parameters("No social norm"),
                                                         {"names": []}, np.zeros((2, 0)), sensi.SensitivityConfig(), root, None, None)
            run.assert_not_called()
            self.assertEqual(count, 0)
            self.assertEqual(paired.loc[0, C + "x1_timing"], "Equal")
            frequencies = save_comparison_frequencies(paired, root, "No social norm")
            self.assertTrue(np.allclose(frequencies.groupby("comparison")["relative_frequency"].sum(), 1))
            self.assertTrue((root / "without_norm_comparison_frequencies.svg").is_file())

    def test_nonconsecutive_successful_sample_ids_stay_paired(self):
        records = pd.DataFrame([
            {**completed([217, 230], [.3, 1]), "sample_index": 0},
            {"sample_index": 1, "status": "failed"},
            {**completed([217, 230], [.3, .4]), "sample_index": 2},
        ])
        references = pd.DataFrame([completed([217, 230], [.3, 1]), completed([217, 230], [.3, .4])])
        with tempfile.TemporaryDirectory() as directory, patch.object(sensi, "run_samples", return_value=references) as run:
            paired, _ = sensi.add_no_norm_comparisons(records, resolve_parameters("baseline"),
                                                     {"names": ["beta"]}, np.array([[1.], [2.], [3.]]), sensi.SensitivityConfig(),
                                                     Path(directory), None, None)
            self.assertEqual(list(run.call_args.kwargs["sample_indices"]), [0, 2])
            self.assertEqual(paired[C + "x1_timing"].tolist(), ["Equal", "Not comparable", "Neither reached"])
            stored = pd.read_csv(Path(directory) / "without_norm_outputs.csv", sep=";")
            self.assertEqual(stored["sample_index"].tolist(), [0, 1, 2])

    def test_reference_timeout_records_actual_disabled_agent_weight(self):
        params = resolve_parameters("Observation-based / intention motivation (agents)")
        task = ((params, ["eta"], np.array([.9]), sensi.SensitivityConfig()),
                23, None, "reference", None, None)
        record = sensi._record_timeout(task, {"elapsed_seconds": 1200})
        self.assertEqual(record["phase"], "reference")
        self.assertEqual(record["sample_index"], 23)
        self.assertEqual(record["parameters"]["eta"], 0)

    def test_zero_norm_strength_gives_equal_real_posthistorical_timing(self):
        params = {**resolve_parameters("baseline"), "social_norm_factor": 0.0, "kappa": .5}
        config = sensi.SensitivityConfig(simulation_time=220, coupling_interval=1,
                                         output_points_per_year=2, constant_temperature_costs=True)
        job = (params, ["temperature_factor", "beta"], np.array([5., .1]), config)
        actual = {**sensi._run_sample(job), "status": "completed"}
        reference = {**sensi._run_sample(job, without_norm=True), "status": "completed"}
        comparison = compare_profiles(actual, reference)
        self.assertEqual(comparison[C + "x1_timing"], "Equal")
        self.assertIsNotNone(comparison[C + "x1_time"])
        self.assertEqual(comparison[C + "x0_timing"], "Neither reached")
        self.assertEqual(comparison[C + "slope"], "Equal")
        self.assertIsNotNone(actual[P + "slope"])

    def test_historical_plot_keeps_its_original_slope_definition(self):
        paired = pd.DataFrame([compare_profiles(completed([217, 218], [.3, .6]),
                                                completed([217, 218], [.3, .5]))])
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            save_comparison_frequencies(paired, path, "baseline", definition={"version": 2})
            self.assertIn("10%–90% transition speed", (path / "without_norm_comparison_frequencies.svg").read_text(encoding="utf-8"))
            save_comparison_frequencies(paired, path, "baseline")
            self.assertIn("Largest annual change in x", (path / "without_norm_comparison_frequencies.svg").read_text(encoding="utf-8"))

    def test_cli_defaults_and_opt_out(self):
        self.assertTrue(sensi.parse_args([]).compare_without_norm)
        self.assertFalse(sensi.parse_args(["--no-compare-without-norm"]).compare_without_norm)

    def test_real_sensi_persists_comparisons_without_changing_sobol(self):
        config = sensi.SensitivityConfig(simulation_time=2, base_sample_size=2, workers=1,
                                         coupling_interval=1, output_points_per_year=2, save_time_series=False)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            enabled = sensi.run_sensitivity_analysis("baseline", root / "on", config)
            disabled = sensi.run_sensitivity_analysis("baseline", root / "off", replace(config, compare_without_norm=False))
            a = pd.read_csv(enabled / "sobol_indices.csv", sep=";")
            b = pd.read_csv(disabled / "sobol_indices.csv", sep=";")
            pd.testing.assert_frame_equal(a, b, check_exact=True)
            comparisons = pd.read_csv(enabled / "behaviour_classes.csv", sep=";")
            self.assertEqual(len(comparisons), 12)
            self.assertTrue(comparisons[C + "x1_timing"].eq("Not comparable").all())
            metadata = json.loads((enabled / "metadata.json").read_text())
            self.assertEqual(metadata["without_norm_comparison"]["number_of_additional_runs"], 10)
            self.assertFalse((disabled / "without_norm_outputs.csv").exists())


if __name__ == "__main__":
    unittest.main()
