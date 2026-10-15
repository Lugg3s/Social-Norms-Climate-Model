"""Model and coupling checks for annual, reversible intention-based decisions."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import numpy as np

import model.agent as agent
from simulation.batch_runner import (ExperimentGroup, create_run_name, run_single_combination,
                          sanitize_name, save_run_time_series_only, simulation_to_dataframe)
from model.model_equations import _make_agent_time_breaks, resolve_parameters, simulate
from analysis.sensitivity.sensitivity_analysis import build_problem
from analysis.simulation_metrics import compute_metrics_from_saved_time_series, compute_run_metrics


SCENARIO = "Observation-based / intention motivation (agents)"


class IntentionRuleTests(unittest.TestCase):
    def setUp(self):
        self.p = resolve_parameters(SCENARIO)
        # Rule checks set explicit thresholds independently of edited scenarios.
        self.p.update(phi=.5, psi=0)

    def test_threshold_equalities_and_simultaneous_actual_observation(self):
        people = [agent.Agent(0, 0, np.array([1, 2]), .5),
                  agent.Agent(1, 1, np.array([0, 2]), .3),
                  agent.Agent(2, 0, np.array([1]), .2)]
        self.p.update(eta=.8, phi=.5)
        agent.update_agents(people, temperature=.1, p=self.p, f_T=lambda t: t)
        # Agent 0 observes q=.5 exactly at tau and BI=0 exactly at the action
        # threshold. Agent 1 must still observe both peers' OLD zeros.
        np.testing.assert_allclose([a.peer_norm for a in people], [.5, 0, 1])
        np.testing.assert_allclose([a.behavioral_intention for a in people], [0, -.2, .7], atol=1e-15)
        np.testing.assert_array_equal(agent.actual_behaviors_array(people), [1, 0, 1])
        self.assertAlmostEqual(agent.mean_norm_contribution(people), .4)

    def test_low_observation_adds_no_norm_and_intention_is_not_behavior(self):
        people = [agent.Agent(0, 0, np.array([1]), .2),
                  agent.Agent(1, 0, np.array([], dtype=int), .2)]
        self.p.update(eta=10, psi=1)
        agent.update_agents(people, .7, self.p, lambda t: t)
        np.testing.assert_allclose([a.behavioral_intention for a in people], [.5, .5])
        np.testing.assert_array_equal(agent.actual_behaviors_array(people), [0, 0])

    def test_continuous_BI_survives_thresholding_into_actual_behavior(self):
        people = [agent.Agent(agent_id=0, actual_behavior=0,
                              peers=np.array([], dtype=int), beta=0)]
        self.p.update(eta=0, psi=.5)
        # Evaluating BI alone does not enact it, even above the threshold.
        agent.evaluate_intentions(people, .6, self.p, lambda t: t)
        self.assertEqual(people[0].behavioral_intention, .6)
        self.assertEqual(people[0].actual_behavior, 0)
        agent.update_agents(people, .6, self.p, lambda t: t)
        self.assertEqual(people[0].behavioral_intention, .6)
        self.assertEqual(people[0].actual_behavior, 1)
        agent.update_agents(people, .4, self.p, lambda t: t)
        self.assertEqual(people[0].behavioral_intention, .4)
        self.assertEqual(people[0].actual_behavior, 0)

    def test_temperature_drives_reversible_decisions_without_redrawing_costs(self):
        people = [agent.Agent(0, 0, np.array([], dtype=int), 1)]
        self.p["eta"] = 0
        agent.update_agents(people, 5, self.p, lambda t: t)
        self.assertEqual(people[0].actual_behavior, 1)
        self.assertEqual(people[0].behavioral_intention, 4)  # BI must not be clipped to 1.
        agent.update_agents(people, 0, self.p, lambda t: t)
        self.assertEqual(people[0].actual_behavior, 0)
        self.assertEqual(people[0].behavioral_intention, -1)
        self.assertEqual(people[0].beta, 1)

    def test_fixed_heterogeneity_and_network_are_seeded(self):
        options = dict(n_agents=40, initial_mitigation_share=.3, network_size=4, beta=2)
        first = agent.initialize_agents(rng=np.random.default_rng(7), **options)
        second = agent.initialize_agents(rng=np.random.default_rng(7), **options)
        costs = np.array([a.beta for a in first])
        np.testing.assert_array_equal(costs, [a.beta for a in second])
        self.assertTrue(np.all((costs >= 0) & (costs <= 4)))
        self.assertGreater(np.ptp(costs), 0)
        for a, b in zip(first, second):
            np.testing.assert_array_equal(a.peers, b.peers)
            self.assertNotIn(a.agent_id, a.peers)
        agent.update_agents(first, 10, self.p, lambda t: t)
        np.testing.assert_array_equal(costs, [a.beta for a in first])

    def test_empty_neighbourhood_does_not_observe_self(self):
        people = [agent.Agent(0, 1, np.array([], dtype=int), 1)]
        np.testing.assert_array_equal(agent.calculate_peer_norms(people), [0])

    def test_observations_use_behaviour_not_intention(self):
        people = [agent.Agent(0, 1, np.array([1]), 1, behavioral_intention=-9),
                  agent.Agent(1, 0, np.array([0]), 1, behavioral_intention=9)]
        np.testing.assert_array_equal(agent.calculate_peer_norms(people), [0, 1])

    def test_removed_inputs_and_invalid_parameters_are_rejected(self):
        for name in ("agent_susceptibility", "agent_update_rate"):
            with self.subTest(parameter=name), self.assertRaisesRegex(ValueError, "has been removed"):
                resolve_parameters({**self.p, name: 1})
        for old, new in (("agent_norm_weight", "eta"), ("agent_norm_threshold", "phi"),
                         ("agent_behavior_threshold", "psi")):
            with self.subTest(parameter=old), self.assertRaisesRegex(ValueError, f"renamed to {new}"):
                resolve_parameters({**self.p, old: 1})
        for name, value in (("eta", -1), ("phi", 1.1),
                            ("psi", float("nan"))):
            with self.subTest(parameter=name), self.assertRaises(ValueError):
                resolve_parameters({**self.p, name: value})
        for size in (-1, 4, 1.2):
            with self.subTest(size=size), self.assertRaises(ValueError):
                agent.initialize_agents(4, .5, np.random.default_rng(0), network_size=size, beta=1)

    def test_sensitivity_has_only_active_decision_parameters(self):
        names = build_problem(SCENARIO)["names"]
        self.assertIn("beta", names)
        self.assertIn("temperature_factor", names)
        self.assertIn("eta", names)
        self.assertNotIn("social_norm_factor", names)
        self.assertNotIn("kappa", names)
        self.assertNotIn("agent_susceptibility", names)

    def test_missing_decision_parameters_raise_native_key_errors(self):
        for name in ("eta", "phi", "psi", "network_size"):
            params = dict(self.p)
            del params[name]
            with self.subTest(parameter=name), self.assertRaises(KeyError) as error:
                simulate(params, simulation_time=1, n_agents=100, verbose=False)
            self.assertEqual(error.exception.args, (name,))


class AnnualCouplingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.params = {**resolve_parameters(SCENARIO), "temperature_factor": 0,
                      "beta": .25, "network_size": 3, "x0": .3, "phi": .5, "psi": 0}
        options = dict(extension=cls.params, simulation_time=220.3, n_agents=11,
                       seed=9, simulate_only_x=True, verbose=False)
        cls.coarse = simulate(**options, coupling_interval=1.7, output_points_per_year=1)
        cls.fine = simulate(**options, coupling_interval=.37, output_points_per_year=7)

    def test_exact_years_are_unique_even_with_unaligned_coupling(self):
        for interval in (.1, .37, 1.7, 300):
            times = _make_agent_time_breaks(220.3, interval)
            self.assertTrue(np.all(np.diff(times) > 0))
            for year in (217, 218, 219, 220):
                self.assertEqual(np.count_nonzero(times == year), 1)

    def test_yearly_schedule_is_independent_of_coupling_and_output_grid(self):
        a, b = self.coarse["agent_history"], self.fine["agent_history"]
        np.testing.assert_array_equal(a["t"], [0, 217, 218, 219, 220])
        for key in ("t", "behavioral_intention", "actual_behavior", "peer_norm", "beta", "is_decision"):
            np.testing.assert_array_equal(a[key], b[key])
        np.testing.assert_array_equal(a["is_decision"], [False, True, True, True, True])

    def test_x_is_actual_share_before_between_and_at_decisions(self):
        for result in (self.coarse, self.fine):
            h, sim = result["agent_history"], result["simulation"]
            np.testing.assert_array_equal(h["mitigation_share"], h["actual_behavior"].mean(axis=1))
            indices = np.searchsorted(h["t"], sim.t, side="right") - 1
            np.testing.assert_array_equal(sim.x, h["mitigation_share"][indices])
            self.assertEqual(sim.x[0], round(.3 * 11) / 11)
            self.assertEqual(sim.x[-1], agent.mitigation_share(result["agents"]))
            np.testing.assert_array_equal(result["social_norm_term"], h["social_norm_term"][indices])

    def test_metrics_do_not_smear_jumps_or_depend_on_output_density(self):
        a = compute_run_metrics(self.coarse, self.params)
        b = compute_run_metrics(self.fine, self.params)
        for key in ("x_area", "cumulative_emissions", "time_to_elimination",
                    "n_oscillations", "median_period", "oscillation_amplitude"):
            if np.isnan(a[key]):
                self.assertTrue(np.isnan(b[key]))
            else:
                self.assertAlmostEqual(a[key], b[key], places=10)

    def test_batch_export_retains_intentions_behaviours_and_metric_semantics(self):
        result = self.coarse
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            save_run_time_series_only(path, result["parameters"], result)
            with np.load(path / "agent_history.npz") as saved:
                np.testing.assert_array_equal(saved["behavioral_intention"], result["agent_history"]["behavioral_intention"])
                np.testing.assert_array_equal(saved["actual_behavior"], result["agent_history"]["actual_behavior"])
            params = json.loads((path / "parameters.json").read_text())
            self.assertEqual(params["agent_decision_model"], "annual_intention_threshold")
        frame = simulation_to_dataframe(result, result["parameters"])
        self.assertIn("mean_intention", frame)
        saved_metrics = compute_metrics_from_saved_time_series(frame, result["parameters"])
        live_metrics = compute_run_metrics(result, result["parameters"])
        self.assertEqual(saved_metrics.keys(), live_metrics.keys())
        np.testing.assert_allclose(list(saved_metrics.values()), list(live_metrics.values()),
                                   rtol=0, atol=0, equal_nan=True)

    def test_unused_replicator_parameters_cannot_influence_agents(self):
        params = {**self.params, "social_norm_factor": 123, "kappa": 123}
        other = simulate(params, simulation_time=220.3, n_agents=11, seed=9,
                         simulate_only_x=True, verbose=False, coupling_interval=1.7,
                         output_points_per_year=1)
        np.testing.assert_array_equal(np.asarray(other["simulation"]),
                                      np.asarray(self.coarse["simulation"]))

    def test_fixed_step_solver_also_decides_only_at_exact_years(self):
        result = simulate(self.params, simulation_time=220.3, n_agents=11, seed=9,
                          simulate_only_x=True, verbose=False, solver="RK4", dt=.3,
                          coupling_interval=1.7, output_points_per_year=1)
        for key in ("t", "actual_behavior", "behavioral_intention"):
            np.testing.assert_array_equal(result["agent_history"][key],
                                          self.coarse["agent_history"][key])

    def test_batch_cannot_reuse_legacy_agent_results(self):
        group = ExperimentGroup(name="agent_test", scenarios=[SCENARIO], sweep_parameters={})
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            run_dir = root / sanitize_name(group.name) / sanitize_name(SCENARIO) / create_run_name(SCENARIO, {})
            save_run_time_series_only(run_dir, self.params, self.coarse)
            params_path = run_dir / "parameters.json"
            saved_params = json.loads(params_path.read_text())
            saved_params.pop("agent_decision_model")
            params_path.write_text(json.dumps(saved_params), encoding="utf-8")
            with patch('simulation.batch_runner.simulate') as simulation:
                with self.assertRaisesRegex(ValueError, "replaced model"):
                    run_single_combination(self.params, {}, group, root, SCENARIO)
                simulation.assert_not_called()

    def test_batch_cannot_reuse_ambiguous_history_field_names(self):
        group = ExperimentGroup(name="agent_test", scenarios=[SCENARIO], sweep_parameters={})
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            run_dir = root / sanitize_name(group.name) / sanitize_name(SCENARIO) / create_run_name(SCENARIO, {})
            save_run_time_series_only(run_dir, self.params, self.coarse)
            np.savez_compressed(run_dir / "agent_history.npz",
                                intention=self.coarse["agent_history"]["behavioral_intention"],
                                behavior=self.coarse["agent_history"]["actual_behavior"])
            with patch('simulation.batch_runner.simulate') as simulation:
                with self.assertRaisesRegex(ValueError, "outdated field names"):
                    run_single_combination(self.params, {}, group, root, SCENARIO)
                simulation.assert_not_called()

    def test_climate_uses_actual_behavior_and_crossing_is_at_decision(self):
        options = dict(simulation_time=220, n_agents=11, seed=9, verbose=False,
                       coupling_interval=1, output_points_per_year=2)
        all_act = simulate({**self.params, "beta": 0, "eta": 0}, **options)
        none_act = simulate({**self.params, "beta": 100, "eta": 0}, **options)
        self.assertEqual(all_act["simulation"].x[-1], 1)
        self.assertEqual(none_act["simulation"].x[-1], 0)
        self.assertLess(all_act["simulation"].C_at[-1], none_act["simulation"].C_at[-1])
        self.assertLess(all_act["simulation"].T[-1], none_act["simulation"].T[-1])
        self.assertEqual(compute_run_metrics(all_act, self.params)["time_to_elimination"], 217)
        index = np.flatnonzero(all_act["simulation"].t == 217)[0]
        self.assertAlmostEqual(all_act["simulation"].T[index], none_act["simulation"].T[index], places=10)


if __name__ == "__main__":
    unittest.main()
