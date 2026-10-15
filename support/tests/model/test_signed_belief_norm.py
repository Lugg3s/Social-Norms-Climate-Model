"""Signed belief influence reaches sampling, simulation and symbolic analysis."""
import unittest

import numpy as np
from SALib.sample import sobol

from simulation.batch_runner import BELIEF_VALUES
from model.model_equations import resolve_parameters, simulate
from analysis.sensitivity.sensitivity_analysis import build_problem
from analysis.symbolic_analysis import symbolic_social_norm_term


SCENARIO = "Belief-based / intention motivation"


class SignedBeliefNormTests(unittest.TestCase):
    def test_sobol_and_batch_cover_both_signs_and_neutrality(self):
        problem = build_problem(SCENARIO)
        index = problem['names'].index('N')
        self.assertEqual(list(problem['bounds'][index]), [-1., 1.])
        samples = sobol.sample(problem, 8, calc_second_order=False, seed=42)
        self.assertLess(samples[:, index].min(), 0)
        self.assertGreater(samples[:, index].max(), 0)
        self.assertEqual(min(BELIEF_VALUES), -1)
        self.assertEqual(max(BELIEF_VALUES), 1)
        self.assertIn(0, BELIEF_VALUES)

    def test_negative_neutral_and_positive_N_match_analytic_trajectories(self):
        finals = []
        term = symbolic_social_norm_term(SCENARIO)
        symbol, = term.free_symbols
        for value in (-1., 0., 1.):
            with self.subTest(N=value):
                params = {**resolve_parameters(SCENARIO), 'N': value, 'beta': 0,
                          'temperature_factor': 0, 'social_norm_factor': .7,
                          'kappa': .2, 'x0': .3}
                self.assertEqual(resolve_parameters(params)['N'], value)
                self.assertEqual(float(term.subs(symbol, value)), value)
                result = simulate(params, simulation_time=221, coupling_interval=1,
                                  output_points_per_year=4, simulate_only_x=True,
                                  verbose=False)
                trajectory = result['simulation']
                elapsed = np.maximum(trajectory.t - 217, 0)
                expected = 1 / (1 + .7 / .3 * np.exp(-.2 * .7 * value * elapsed))
                np.testing.assert_allclose(trajectory.x, expected, rtol=0, atol=2e-6)
                np.testing.assert_array_equal(result['social_norm_term'], value)
                finals.append(trajectory.x[-1])
        self.assertLess(finals[0], .3)
        self.assertAlmostEqual(finals[1], .3)
        self.assertGreater(finals[2], .3)


if __name__ == '__main__':
    unittest.main()
