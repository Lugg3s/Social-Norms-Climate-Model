import json
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pandas as pd
from SALib.sample import sobol as sampler
from SALib.analyze import sobol as analyzer

from analysis.parameter_ranges import default_sensitivity_scenarios
from analysis.sensitivity.shared_sampling import prepare_shared_design, scenario_samples
from analysis.sensitivity.reference_cache import ReferenceCache
from analysis.sensitivity import sensitivity_analysis as sensi
from analysis.sensitivity.sensitivity_review import validate_design
from analysis.no_norm_comparison import PROFILE_PREFIX as P
from model.model_equations import resolve_parameters


class SharedSamplingTests(unittest.TestCase):
    def design(self, n=16):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        config = sensi.SensitivityConfig(base_sample_size=n, save_time_series=False)
        return Path(temporary.name), config, prepare_shared_design(Path(temporary.name), config)

    def test_each_norm_retains_exact_saltelli_structure_and_run_counts(self):
        _, config, (a, b, design) = self.design()
        total = 0
        for name in default_sensitivity_scenarios():
            problem = sensi.build_problem(name)
            samples = scenario_samples(problem, a, b, design)
            frame = pd.DataFrame(samples, columns=problem["names"])
            frame.insert(0, "sample_index", range(len(frame)))
            outputs = pd.DataFrame({"sample_index": range(len(frame)), "status": "completed"})
            validate_design(frame, outputs, problem, config.base_sample_size)
            total += len(samples)
        self.assertEqual(total, 79 * config.base_sample_size)

    def test_shared_coordinates_cover_all_continuous_norm_references_exactly(self):
        _, _, (a, b, design) = self.design()
        names = ["temperature_factor", "beta", "kappa"]
        control_problem = sensi.build_problem("No social norm")
        control = scenario_samples(control_problem, a, b, design)
        control_keys = {tuple(row[control_problem["names"].index(key)] for key in names) for row in control}
        for name in default_sensitivity_scenarios():
            if resolve_parameters(name)["ABM"]:
                continue
            problem = sensi.build_problem(name)
            samples = scenario_samples(problem, a, b, design)
            keys = {tuple(row[problem["names"].index(key)] for key in names) for row in samples}
            self.assertLessEqual(keys, control_keys)

    def test_projection_equals_the_corresponding_salib_master_blocks(self):
        _, config, (a, b, design) = self.design()
        master = {"num_vars": len(design["names"]), "names": design["names"], "bounds": design["bounds"]}
        full = sampler.sample(master, config.base_sample_size, calc_second_order=False, seed=config.seed)
        full = full.reshape(config.base_sample_size, master["num_vars"] + 2, master["num_vars"])
        problem = sensi.build_problem("Descriptive, injunctive, dynamic2")
        columns = [design["names"].index(name) for name in problem["names"]]
        expected = full[:, [0, *[column + 1 for column in columns], master["num_vars"] + 1]][:, :, columns]
        np.testing.assert_array_equal(scenario_samples(problem, a, b, design),
                                      expected.reshape(-1, problem["num_vars"]))

    def test_saved_design_is_reused_and_changes_or_corruption_are_rejected(self):
        root, config, (a, b, design) = self.design()
        with patch("analysis.sensitivity.shared_sampling.sobol.sample", side_effect=AssertionError("must reuse")):
            again_a, again_b, again_info = prepare_shared_design(root, config)
        np.testing.assert_array_equal(a, again_a)
        np.testing.assert_array_equal(b, again_b)
        self.assertEqual(design, again_info)
        for changed in (replace(config, seed=43), replace(config, base_sample_size=32),
                        replace(config, parameter_ranges={"beta": [1, 4]})):
            with self.assertRaisesRegex(ValueError, "different shared Sobol"):
                prepare_shared_design(root, changed)
        np.savez(root / "sampling_AB.npz", A=a + .1, B=b)
        with self.assertRaisesRegex(ValueError, "invalid or changed"):
            prepare_shared_design(root, config)

    def test_legacy_results_are_preserved_instead_of_mixed(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            old = root / "baseline/metadata.json"
            old.parent.mkdir()
            old.write_text('{"legacy": true}')
            with self.assertRaisesRegex(ValueError, "legacy sampling"):
                prepare_shared_design(root, sensi.SensitivityConfig())
            self.assertEqual(old.read_text(), '{"legacy": true}')

    def test_shared_sampling_recovers_known_additive_sobol_indices(self):
        _, _, (a, b, design) = self.design(4096)
        problem = {"num_vars": 2, "names": ["beta", "temperature_factor"], "bounds": [[0., 5.], [0., 5.]]}
        samples = scenario_samples(problem, a, b, design)
        result = analyzer.analyze(problem, samples[:, 0] + 2 * samples[:, 1],
                                  calc_second_order=False, seed=42)
        np.testing.assert_allclose(result["S1"], [.2, .8], atol=.01)
        np.testing.assert_allclose(result["ST"], [.2, .8], atol=.01)

    def test_selected_no_norm_is_always_first_and_selection_is_preserved(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            order = []
            def fake_run(name, root, config, overwrite_existing):
                order.append(name)
                folder = root / name.replace(" ", "_")
                folder.mkdir()
                pd.DataFrame({"parameter": ["beta"], "overall_score": [1.]}).to_csv(
                    folder / "parameter_ranking.csv", sep=";", index=False)
                return folder
            with patch.object(sensi, "run_sensitivity_analysis", side_effect=fake_run), \
                 patch("analysis.sensitivity.sensitivity_plots.create_parameter_ranking_barplots", return_value=[]), \
                 patch("analysis.sensitivity.sensitivity_plots.create_goal_variable_violin_boxplots", return_value=[]):
                sensi._run_scenarios(["baseline", "No social norm", "Static injunctive"], root,
                                     sensi.SensitivityConfig())
            self.assertEqual(order, ["No social norm", "baseline", "Static injunctive"])


class ReferenceCacheTests(unittest.TestCase):
    def test_unused_norm_parameters_share_keys_but_physical_settings_do_not(self):
        with tempfile.TemporaryDirectory() as directory:
            config = sensi.SensitivityConfig(save_time_series=False)
            with ReferenceCache(directory, config) as cache:
                baseline = resolve_parameters("baseline")
                control = resolve_parameters("No social norm")
                dynamic = resolve_parameters("Descriptive, injunctive, dynamic2")
                self.assertEqual(cache.key(baseline), cache.key(control))
                self.assertEqual(cache.key(dynamic), cache.key(control))
                self.assertEqual(cache.key({**dynamic, "c_inj": 9, "rho": 8}), cache.key(control))
                for key in ("beta", "kappa", "temperature_factor", "x0", "C_at0", "f_max"):
                    self.assertNotEqual(cache.key({**control, key: control[key] + .1}), cache.key(control))
                original = cache.key(control)
            for changed in (replace(config, seed=43), replace(config, constant_temperature_costs=True),
                            replace(config, simulation_time=601), replace(config, coupling_interval=.2)):
                with ReferenceCache(directory, changed) as cache:
                    self.assertNotEqual(original, cache.key(control))

    def test_agents_are_separate_and_only_social_norm_factor_changes_are_reused(self):
        with tempfile.TemporaryDirectory() as directory, ReferenceCache(directory, sensi.SensitivityConfig()) as cache:
            agents = resolve_parameters("Observation-based / intention motivation (agents)")
            self.assertEqual(cache.key(agents), cache.key({**agents, "social_norm_factor": 0.}))
            self.assertNotEqual(cache.key(agents), cache.key(resolve_parameters("No social norm")))
            for key in ("network_size", "phi", "psi"):
                self.assertNotEqual(cache.key(agents), cache.key({**agents, key: agents[key] + 1}))

    def test_persistence_failures_and_source_archive_links(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source, target = root / "No_social_norm", root / "baseline"
            (source / "series").mkdir(parents=True)
            target.mkdir()
            (source / "series/sample_000007.npz").touch()
            config = sensi.SensitivityConfig()
            with ReferenceCache(root, config) as cache:
                key = cache.key(resolve_parameters("No social norm"))
                cache.put(key, {"status": "completed", P + "first_x1": None,
                                "time_series_file": "series/sample_000007.npz"}, source, 7)
                cache.put(key, {"status": "timed_out"}, target, 3)
            with ReferenceCache(root, config) as cache:
                row = cache.get(key, target)
                self.assertEqual(row["status"], "completed")
                self.assertEqual(row["reference_source_sample_index"], 7)
                self.assertEqual(row["reference_source_scenario"], "No_social_norm")
                self.assertTrue((target / row["time_series_file"]).is_file())
                (source / "series/sample_000007.npz").unlink()
                with self.assertRaises(FileNotFoundError):
                    cache.get(key, target)

    def test_repeated_parameter_rows_are_simulated_once(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            actual = pd.DataFrame({"sample_index": [0, 1], "status": "completed"})
            computed = pd.DataFrame({"status": ["completed"], P + "status": ["Available"]})
            with patch.object(sensi, "run_samples", return_value=computed) as run:
                paired, count = sensi.add_no_norm_comparisons(
                    actual, resolve_parameters("baseline"), {"names": ["social_norm_factor"]},
                    np.array([[1.], [4.]]), sensi.SensitivityConfig(save_time_series=False), root, None, None)
            self.assertEqual(count, 1)
            self.assertEqual(len(run.call_args.args[2]), 1)
            self.assertEqual(paired["norm_comparison_reference_key"].nunique(), 1)

    def test_metric_only_references_can_be_upgraded_to_archives(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "No_social_norm"
            source.mkdir()
            params = resolve_parameters("No social norm")
            metrics_only = sensi.SensitivityConfig(save_time_series=False)
            with ReferenceCache(root, metrics_only) as cache:
                key = cache.key(params)
                cache.put(key, {"status": "completed"}, source, 1)
                self.assertIsNotNone(cache.get(key, source))
            with ReferenceCache(root, replace(metrics_only, save_time_series=True)) as cache:
                self.assertEqual(key, cache.key(params))
                self.assertIsNone(cache.get(key, source))
                (source / "reference.npz").touch()
                cache.put(key, {"status": "completed", "time_series_file": "reference.npz"}, source, 2)
                self.assertEqual(cache.get(key, source)["reference_source_sample_index"], 2)

    def test_cached_failed_reference_does_not_trigger_repeated_runs(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config = sensi.SensitivityConfig(save_time_series=False)
            base = resolve_parameters("baseline")
            with ReferenceCache(root, config) as cache:
                key = cache.key(base)
                cache.put(key, {"status": "timed_out"}, root, 0)
            outputs = pd.DataFrame({"sample_index": [0], "status": ["completed"],
                                    **{name: [.5] for name in sensi.SENSITIVITY_OUTPUTS}})
            with patch.object(sensi, "run_samples", side_effect=AssertionError("must reuse failure")):
                paired, count = sensi.add_no_norm_comparisons(
                    outputs, base, {"names": []}, np.zeros((1, 0)), config, root, None, None)
            self.assertEqual(count, 0)
            self.assertEqual(paired.loc[0, "status"], "completed")
            self.assertEqual(paired.loc[0, "norm_comparison_x1_timing"], "Not comparable")
            pd.testing.assert_frame_equal(paired[sensi.SENSITIVITY_OUTPUTS], outputs[sensi.SENSITIVITY_OUTPUTS])

    def test_real_no_norm_results_are_reused_for_multiple_norms_and_append(self):
        config = sensi.SensitivityConfig(simulation_time=2, base_sample_size=2, workers=1,
                                         coupling_interval=1, output_points_per_year=2)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            control = sensi.run_sensitivity_analysis("No social norm", root, replace(config, compare_without_norm=False))
            original_control = (control / "simulation_outputs.csv").read_bytes()
            for name in ("baseline", "Static injunctive"):
                original = sensi.run_samples
                def forbid_references(*args, **kwargs):
                    if kwargs.get("phase") == "reference":
                        raise AssertionError("Cached no-norm results must be reused")
                    return original(*args, **kwargs)
                with patch.object(sensi, "run_samples", side_effect=forbid_references):
                    folder = sensi.run_sensitivity_analysis(name, root, config, overwrite_existing=False)
                outputs = pd.read_csv(folder / "simulation_outputs.csv", sep=";")
                metadata = json.loads((folder / "metadata.json").read_text())
                self.assertEqual(metadata["without_norm_comparison"]["number_of_additional_runs"], 0)
                self.assertTrue(outputs["norm_comparison_reference_reused"].all())
                self.assertTrue(outputs["norm_comparison_reference_source_scenario"].eq("No_social_norm").all())
                self.assertFalse(list(folder.glob("time_series_*/reference_*.npz")))
                for relative in outputs["norm_comparison_reference_time_series_file"]:
                    self.assertTrue((folder / relative).is_file())
            self.assertEqual(original_control, (control / "simulation_outputs.csv").read_bytes())


if __name__ == "__main__":
    unittest.main()
