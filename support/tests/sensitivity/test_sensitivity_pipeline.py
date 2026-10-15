from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import Mock, patch

import analysis.sensitivity.sensitivity_pipeline as pipeline
from analysis.regression_trees.regression_tree_demo import write_demo


class SensitivityPipelineTests(unittest.TestCase):
    def test_regression_uses_completed_sobol_folder_without_new_simulations(self):
        root = Path("saved_run")
        config = SimpleNamespace(seed=17)
        events = []

        def sobol(names, path, config, overwrite_existing):
            events.append("sobol_done")
            return "completed"

        def trees(input_root, output_dir, config):
            self.assertEqual(events, ["sobol_done"])
            self.assertEqual(input_root, root)
            self.assertEqual(output_dir.parent, root / "regression_trees")
            self.assertEqual(config.seed, 17)
            events.append("trees_done")
            return [{"status": "fitted"}, {"status": "insufficient_data"}]

        with patch.object(pipeline, "run_analysis", side_effect=trees):
            result = pipeline.pipeline_runner(sobol)(["baseline"], root, config)
        self.assertEqual(result, "completed")
        self.assertEqual(events, ["sobol_done", "trees_done"])

    def test_failed_sobol_run_does_not_start_trees(self):
        with patch.object(pipeline, "run_analysis") as trees:
            runner = pipeline.pipeline_runner(Mock(side_effect=ValueError("simulation failed")))
            with self.assertRaisesRegex(ValueError, "simulation failed"):
                runner(["baseline"], Path("run"), SimpleNamespace(seed=42))
        trees.assert_not_called()

    def test_cli_restores_original_runner_after_success_and_failure(self):
        original = pipeline.sensitivity._run_scenarios
        with patch.object(pipeline.sensitivity, "main") as main:
            pipeline.main()
            main.assert_called_once()
        self.assertIs(pipeline.sensitivity._run_scenarios, original)
        with patch.object(pipeline.sensitivity, "main", side_effect=RuntimeError("stop")):
            with self.assertRaisesRegex(RuntimeError, "stop"):
                pipeline.main()
        self.assertIs(pipeline.sensitivity._run_scenarios, original)

    def test_pipeline_exports_trees_into_saved_run_subfolder(self):
        with tempfile.TemporaryDirectory() as root:
            run_root = Path(root) / "run"
            source = write_demo(run_root / "demo")
            originals = {p: p.read_bytes() for p in source.iterdir()}
            pipeline.pipeline_runner(Mock())(["demo"], run_root, SimpleNamespace(seed=42))
            result_dirs = list((run_root / "regression_trees").iterdir())
            self.assertEqual(len(result_dirs), 1)
            self.assertTrue((result_dirs[0] / "summary.csv").exists())
            self.assertTrue((result_dirs[0] / "demo" / "final_x" / "tree.svg").exists())
            for path, content in originals.items():
                self.assertEqual(path.read_bytes(), content)


if __name__ == "__main__":
    unittest.main()
