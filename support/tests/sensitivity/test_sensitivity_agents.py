import json
import tempfile
import unittest
from argparse import Namespace
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pandas as pd

import analysis.sensitivity.sensitivity_analysis as sensitivity
from model.model_equations import resolve_parameters


SCENARIO = "Observation-based / intention motivation (agents)"


class AgentSensitivityTests(unittest.TestCase):
    def test_default_scenario_selection_includes_agent_norm(self):
        with tempfile.TemporaryDirectory() as folder:
            args = Namespace(scenarios=None, workers=1, output_points_per_year=2,
                             simulation_time=218, base_sample_size=4, seed=42,
                             score_mode="simple_mean", sample_timeout_minutes=1,
                             constant_temperature_costs=False,
                             append_existing_folder=None, output_root=Path(folder))
            with patch.object(sensitivity, "parse_args", return_value=args), \
                 patch.object(sensitivity, "_run_scenarios") as run:
                sensitivity.main()
            self.assertIn(SCENARIO, run.call_args.args[0])
        problem = sensitivity.build_problem(SCENARIO)
        self.assertEqual(set(problem["names"]),
                         {"temperature_factor", "beta", "network_size", "eta", "phi", "psi"})
        self.assertEqual(problem["bounds"][problem["names"].index("network_size")],
                         [1, sensitivity.ABM_AGENT_COUNT - 1])

    def test_peer_count_is_rounded_in_simulation_and_all_diagnostic_records(self):
        params = resolve_parameters(SCENARIO)
        config = sensitivity.SensitivityConfig(simulation_time=220)
        job = (params, ["network_size"], np.array([127.7]), config)
        metrics = {name: 0.3 for name in sensitivity.SENSITIVITY_OUTPUTS}
        metrics.update(time_to_elimination=float("nan"), bool_x95=False,
                       n_oscillations=0)
        with tempfile.TemporaryDirectory() as folder:
            directory = Path(folder)
            with patch.object(sensitivity, "simulate", return_value={}) as simulate, \
                 patch.object(sensitivity, "compute_run_metrics", return_value=metrics):
                actual = sensitivity._run_tracked_sample(job, 0, directory)
            inputs = simulate.call_args.kwargs
            self.assertEqual(inputs["extension"]["network_size"], 128)
            self.assertEqual(inputs["n_agents"], sensitivity.ABM_AGENT_COUNT)
            self.assertEqual(inputs["seed"], config.seed)
            self.assertEqual(actual["first_time_x95"], 0)
            events = [json.loads(line) for line in
                      (directory / "sample_000000.jsonl").read_text(encoding="utf-8").splitlines()]
            self.assertEqual(events[0]["parameters"]["network_size"], 128)
            self.assertEqual(events[0]["sampled_parameters"]["network_size"], 127.7)
            outcome = {"elapsed_seconds": 60, "worker_pid": 123}
            timeout = sensitivity._record_timeout((job, 0, directory, "sample", None), outcome)
            self.assertEqual(timeout["parameters"]["network_size"], 128)

    def test_agent_run_produces_rankings_and_initialization_metadata(self):
        def outputs(base, problem, samples, config, **kwargs):
            frame = pd.DataFrame({name: np.linspace(0, 1, len(samples))
                                  for name in sensitivity.SENSITIVITY_OUTPUTS})
            frame["status"] = "completed"
            return frame

        with tempfile.TemporaryDirectory() as folder:
            with patch.object(sensitivity, "run_samples", side_effect=outputs), \
                 patch.object(sensitivity, "run_zero_boundary_cases", return_value=pd.DataFrame()):
                directory = sensitivity.run_sensitivity_analysis(
                    SCENARIO, Path(folder), sensitivity.SensitivityConfig(base_sample_size=4, seed=9,
                                                                         constant_temperature_costs=True))
            metadata = json.loads((directory / "metadata.json").read_text(encoding="utf-8"))
            self.assertEqual(metadata["number_of_model_runs"], 32)
            self.assertEqual(metadata["agent_initialization"]["seed"], 9)
            self.assertEqual(metadata["agent_initialization"]["n_agents"], 1000)
            self.assertEqual(metadata["outputs_for_ranking"], sensitivity.SENSITIVITY_OUTPUTS)
            self.assertTrue(metadata["constant_temperature_costs"])
            self.assertIn("f_T(T) = 1", metadata["temperature_response_definition"])
            ranking = pd.read_csv(directory / "parameter_ranking.csv", sep=";")
            self.assertEqual(set(ranking["parameter"]), set(sensitivity.build_problem(SCENARIO)["names"]))
            self.assertTrue(set(sensitivity.SENSITIVITY_OUTPUTS).issubset(ranking))

    def test_real_agent_outputs_are_identical_with_one_or_two_workers(self):
        params = resolve_parameters(SCENARIO)
        # Decisions after t=217, using both extremes of the allowed peer count.
        samples = np.array([[1., 0., 1., 0., 0.6, 0.],
                            [0., 2., 999., 1., 0.4, 0.8]])
        problem = sensitivity.build_problem(SCENARIO)
        config = sensitivity.SensitivityConfig(simulation_time=218, workers=1,
                                               coupling_interval=1, output_points_per_year=2,
                                               constant_temperature_costs=True)
        serial = sensitivity.run_samples(params, problem, samples, config)
        parallel = sensitivity.run_samples(params, problem, samples, replace(config, workers=2))
        pd.testing.assert_frame_equal(serial, parallel, check_exact=True)
        self.assertTrue(serial["status"].eq("completed").all())
        self.assertTrue(np.isfinite(serial[sensitivity.SENSITIVITY_OUTPUTS].to_numpy(dtype=float)).all())


if __name__ == "__main__":
    unittest.main()
