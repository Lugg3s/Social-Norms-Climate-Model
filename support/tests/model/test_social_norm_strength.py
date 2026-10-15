"""Regression checks for norm strength after removing the redundant parameter."""
import unittest

import numpy as np

from simulation.interesting_parameter_loader import load_interesting_parameter_sets
from model.model_equations import load_scenarios, resolve_parameters, simulate
from analysis.symbolic_analysis import SUPPORTED_NORMS, symbolic_social_norm_term


class SocialNormStrengthTests(unittest.TestCase):
    def test_scenarios_and_symbolic_terms_have_no_removed_parameter(self):
        for name in load_scenarios():
            with self.subTest(scenario=name):
                for removed in ("delta", "tau_STref", "alpha"):
                    self.assertNotIn(removed, resolve_parameters(name))
        for name in SUPPORTED_NORMS:
            with self.subTest(norm=name):
                term = symbolic_social_norm_term(name)
                if term is not None:
                    for removed in ("delta", "tau_STref", "alpha"):
                        self.assertNotIn(removed, {str(s) for s in term.free_symbols})

    def test_saved_baseline_examples_preserve_their_strengths(self):
        entries = load_interesting_parameter_sets()
        for entry in entries:
            for removed in ("delta", "tau_STref", "alpha"):
                self.assertNotIn(removed, entry["parameters"])
        strengths = [entry["parameters"]["social_norm_factor"] for entry in entries
                     if entry["social_norm"] == "observation_based_imitation"]
        self.assertEqual(strengths, [10, 3, .1])
        trend_strengths = [entry["parameters"]["social_norm_factor"] for entry in entries
                           if entry["social_norm"] == "dynamic_social_norm"]
        self.assertEqual(trend_strengths, [4, 1, 4])

    def test_legacy_inputs_cannot_silently_change_dynamics(self):
        for removed in ("delta", "tau_STref", "alpha"):
            with self.subTest(parameter=removed):
                with self.assertRaisesRegex(ValueError, f"{removed} has been removed"):
                    resolve_parameters({removed: 3})
                with self.assertRaisesRegex(ValueError, f"{removed} has been removed"):
                    simulate({removed: 3}, simulation_time=1, verbose=False)

    def test_parameter_dict_does_not_restore_missing_baseline_values(self):
        params = resolve_parameters("baseline")
        del params["beta"]
        self.assertNotIn("beta", resolve_parameters(params))
        with self.assertRaises(KeyError) as error:
            simulate(params, simulation_time=218, coupling_interval=1,
                     output_points_per_year=1, simulate_only_x=True, verbose=False)
        self.assertEqual(error.exception.args, ("beta",))

    def test_missing_mode_flag_raises_native_key_error(self):
        params = resolve_parameters("baseline")
        del params["ABM"]
        with self.assertRaises(KeyError) as error:
            resolve_parameters(params)
        self.assertEqual(error.exception.args, ("ABM",))

    def test_imitation_matches_closed_form_for_multiple_strengths(self):
        # With no non-social utility, y=2*x-1 obeys a logistic equation in y**2.
        # Compare the complete active trajectory to its analytic solution.
        for strength in (0, .1, 3, 10):
            with self.subTest(strength=strength):
                result = simulate(
                    {**resolve_parameters("baseline"), "social_norm_factor": strength, "temperature_factor": 0,
                     "beta": 0, "kappa": .05, "x0": .3},
                    simulation_time=225, coupling_interval=1,
                    output_points_per_year=4, simulate_only_x=True, verbose=False,
                )
                sim = result["simulation"]
                elapsed = np.maximum(sim.t - 217, 0)
                initial_y = -.4
                y = initial_y / np.sqrt(
                    initial_y**2 + (1-initial_y**2) * np.exp(-.05*strength*elapsed)
                )
                np.testing.assert_allclose(sim.x, (y+1)/2, rtol=0, atol=2e-6)
                np.testing.assert_allclose(result["social_norm_term"], 2*sim.x-1)

if __name__ == "__main__":
    unittest.main()
