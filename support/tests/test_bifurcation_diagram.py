import contextlib
from io import StringIO
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from analysis import bifurcation_diagram as diagram
from model.model_equations import resolve_parameters


class EndpointSweepTests(unittest.TestCase):
    def test_each_independent_run_changes_only_one_parameter(self):
        scenario = "Descriptive, injunctive, dynamic2 (custom)"
        original = resolve_parameters(scenario)
        config = diagram.SweepConfig(simulation_time=1000, seed=73)
        for parameter in ("beta", "c_inj"):
            tasks, bases = diagram.build_tasks([scenario], parameter, [0., 2.], config)
            self.assertEqual(bases[scenario], original)
            for task in tasks:
                expected = {**original, parameter: task["parameter_value"]}
                self.assertEqual(task["parameters"], expected)
                self.assertEqual(task["config"]["seed"], 73)
            tasks[0]["parameters"]["x0"] = 0.9
            self.assertEqual(tasks[1]["parameters"]["x0"], original["x0"])
        self.assertEqual(resolve_parameters(scenario), original)

    def test_unknown_parameter_or_noninteger_network_is_rejected(self):
        with self.assertRaises(KeyError):
            diagram.build_tasks(["baseline"], "betaa", [1.], diagram.SweepConfig())
        with self.assertRaises(ValueError):
            diagram.build_tasks(["Observation-based / intention motivation (agents)"],
                                "network_size", [1.5], diagram.SweepConfig())

    def test_grid_and_cli_allow_only_one_sweep_parameter(self):
        np.testing.assert_allclose(diagram.parameter_grid(interval=[0, 1, 3]), [0, .5, 1])
        for kwargs in ({"interval": [0, 1, 2.5]}, {"values": [np.nan]},
                       {"values": [1], "interval": [0, 1, 3]}):
            with self.assertRaises(ValueError):
                diagram.parameter_grid(**kwargs)
        with contextlib.redirect_stderr(StringIO()), self.assertRaises(SystemExit):
            diagram.parse_args(["--parameter-name", "beta", "c_inj", "--parameter-values", "0", "1"])

    def test_endpoint_must_reach_requested_horizon(self):
        task = diagram.build_tasks(["baseline"], "beta", [1.],
                                   diagram.SweepConfig(simulation_time=230))[0][0]
        trajectory = SimpleNamespace(t=[0, 230], x=[.3, .72])
        with patch.object(diagram, "simulate", return_value={"simulation": trajectory}):
            result = diagram.run_endpoint(task)
        self.assertEqual(result["final_x"], .72)
        self.assertEqual(result["end_year"], diagram.TIME_ZERO_YEAR + 230)
        trajectory.t[-1] = 229
        with patch.object(diagram, "simulate", return_value={"simulation": trajectory}):
            with self.assertRaisesRegex(RuntimeError, "end time"):
                diagram.run_endpoint(task)

    def test_failed_points_remain_missing_and_are_not_plotted(self):
        outcomes = [(1, {"status": "failed", "error_message": "integration failure"}),
                    (0, {"status": "completed", "result": {"final_x": .72,
                         "end_time": 230., "end_year": diagram.TIME_ZERO_YEAR + 230}})]
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(diagram, "bounded_map", return_value=iter(outcomes)):
                root = diagram.run_analysis("beta", [0., 1.], scenarios=["baseline"], output_root=Path(directory),
                                            config=diagram.SweepConfig(simulation_time=230))
            frame = pd.read_csv(root / "results.csv", sep=";")
            self.assertTrue(np.isnan(frame.loc[1, "final_x"]))
            self.assertEqual(frame.loc[0, "final_x"], .72)
            meta = json.loads((root / "metadata.json").read_text(encoding="utf-8"))
            self.assertEqual(meta["parameters_varied_per_plot"], 1)
            self.assertTrue((root / "scenario_01/final_x_vs_beta.svg").exists())
            figure = diagram.endpoint_plot(frame, "baseline", "beta", 230)
            try:
                self.assertEqual(len(figure.axes[0].collections[0].get_offsets()), 1)
                self.assertIn("t = 230 years", figure.axes[0].get_ylabel())
                self.assertIn(str(diagram.TIME_ZERO_YEAR + 230), figure.axes[0].get_ylabel())
            finally:
                plt.close(figure)


if __name__ == "__main__":
    unittest.main()
