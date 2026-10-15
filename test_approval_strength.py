"""Approval has one strength parameter; old saved results retain their meaning."""
import unittest

import numpy as np

from interesting_parameter_loader import load_interesting_parameter_sets
from model_equations import resolve_parameters, simulate
from sensitivity_analysis import build_problem
from sensitivity_plots import _ranking_formula_content
from symbolic_analysis import symbolic_social_norm_term, x


SCENARIO = 'Observation based / approval (punish only one behaviour)'


class ApprovalStrengthTests(unittest.TestCase):
    def test_current_inputs_and_symbolic_term_use_only_one_strength(self):
        self.assertNotIn('alpha', resolve_parameters(SCENARIO))
        self.assertNotIn('alpha', build_problem(SCENARIO)['names'])
        self.assertIn('social_norm_factor', build_problem(SCENARIO)['names'])
        self.assertEqual(symbolic_social_norm_term(SCENARIO), x)

    def test_migrated_examples_preserve_the_old_products(self):
        examples = [entry for entry in load_interesting_parameter_sets()
                    if entry['social_norm'] == 'observation_based_approval_punish_one']
        self.assertEqual([entry['parameters']['social_norm_factor'] for entry in examples], [.5, 1])
        self.assertTrue(all('alpha' not in entry['parameters'] for entry in examples))

    def test_approval_trajectory_matches_integrated_payoff(self):
        for strength in (0., .5, 2.):
            with self.subTest(strength=strength):
                result = simulate({**resolve_parameters(SCENARIO), 'social_norm_factor': strength,
                                   'beta': 0, 'temperature_factor': 0, 'kappa': .05, 'x0': .3},
                                  simulation_time=225, coupling_interval=1,
                                  output_points_per_year=4, simulate_only_x=True, verbose=False)
                trajectory = result['simulation']
                np.testing.assert_array_equal(result['social_norm_term'], trajectory.x)
                # For dx/dt=kappa*sf*x^2*(1-x), F(x)=log(x/(1-x))-1/x
                # satisfies F(x(t))-F(x0)=kappa*sf*(t-217) after the historical phase.
                integrated = lambda value: np.log(value / (1-value)) - 1/value
                expected = .05 * strength * np.maximum(trajectory.t - 217, 0)
                np.testing.assert_allclose(integrated(trajectory.x)-integrated(.3), expected,
                                           rtol=0, atol=3e-5)

    def test_formula_exports_distinguish_current_and_historical_approval(self):
        current, current_notes = _ranking_formula_content({'scenario': SCENARIO}, resolve_parameters(SCENARIO))
        self.assertEqual(current[1], 'S=x')
        self.assertNotIn(r'\alpha', '\n'.join(current))
        legacy, legacy_notes = _ranking_formula_content({'scenario': SCENARIO, 'problem': {'names': ['alpha']}}, {})
        self.assertIn(r'\alpha', legacy[1])
        self.assertTrue(any('historische Parameterdefinition' in note for note in legacy_notes))


if __name__ == '__main__':
    unittest.main()
