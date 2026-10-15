"""Remove only the redundant strength of the standalone injunctive norm."""
import unittest

import numpy as np
from scipy.optimize import brentq

from interesting_parameter_loader import load_interesting_parameter_sets
from model_equations import resolve_parameters, simulate
from sensitivity_analysis import build_problem
from sensitivity_plots import _ranking_formula_content
from symbolic_analysis import symbolic_social_norm_term, x


STATIC = 'Static injunctive'
COMBINED = ('Descriptive, injunctive, dynamic', 'Descriptive, injunctive, dynamic2', 'Injunctive, dynamic2')


class StaticInjunctiveStrengthTests(unittest.TestCase):
    def test_parameter_is_removed_only_from_the_standalone_norm(self):
        self.assertNotIn('c_inj', resolve_parameters(STATIC))
        self.assertNotIn('c_inj', build_problem(STATIC)['names'])
        term = symbolic_social_norm_term(STATIC)
        self.assertEqual({s.name for s in term.free_symbols}, {'x', 'x_target'})
        for name in COMBINED:
            self.assertIn('c_inj', resolve_parameters(name))
            self.assertIn('c_inj', build_problem(name)['names'])
            self.assertIn('c_inj', {s.name for s in symbolic_social_norm_term(name).free_symbols})
        with self.assertRaisesRegex(ValueError, 'c_inj has been removed from Static injunctive'):
            resolve_parameters({**resolve_parameters(STATIC), 'c_inj': 2})

    def test_static_trajectories_match_the_integrated_payoff_on_both_sides_of_target(self):
        target = .7
        for initial in (.3, .8):
            for strength in (0., .5, 2.):
                with self.subTest(x0=initial, sf=strength):
                    result = simulate({**resolve_parameters(STATIC), 'social_norm_factor': strength,
                                       'x_target': target, 'beta': 0, 'temperature_factor': 0,
                                       'kappa': .05, 'x0': initial},
                                      simulation_time=225, coupling_interval=1, output_points_per_year=4,
                                      simulate_only_x=True, verbose=False)
                    trajectory = result['simulation']
                    np.testing.assert_allclose(result['social_norm_term'], target - trajectory.x, rtol=0, atol=1e-15)
                    # F'(x)=1/[x*(1-x)*(target-x)]; hence F(x)-F(x0)=kappa*sf*time.
                    def integrated(value):
                        return (np.log(value)/target - np.log(1-value)/(target-1)
                                + np.log(np.abs(target-value))/(target*(target-1)))
                    expected = .05 * strength * np.maximum(trajectory.t-217, 0)
                    bounds = (initial, target-1e-10) if initial < target else (target+1e-10, initial)
                    # Compare in x units: the integral magnifies tiny solver
                    # errors near the target, especially when x starts above it.
                    reference = [initial if elapsed == 0 else brentq(
                        lambda value: integrated(value)-integrated(initial)-elapsed, *bounds,
                        xtol=1e-12) for elapsed in expected]
                    np.testing.assert_allclose(trajectory.x, reference, rtol=0, atol=3e-6)

    def test_combined_trajectories_still_respond_to_c_inj(self):
        endings = []
        for weight in (0., 3.):
            result = simulate({**resolve_parameters(COMBINED[0]), 'c_inj': weight, 'c_dyn': 0,
                               'x_target': .7, 'beta': 0, 'temperature_factor': 0,
                               'social_norm_factor': 1, 'kappa': .05, 'x0': .3},
                              simulation_time=220, coupling_interval=1, output_points_per_year=2,
                              simulate_only_x=True, verbose=False)
            endings.append(result['simulation'].x[-1])
        self.assertLess(endings[0], .3)
        self.assertGreater(endings[1], .3)

    def test_examples_and_saved_formula_exports_keep_their_meaning(self):
        examples = [e for e in load_interesting_parameter_sets() if e['social_norm'] == 'static_injunctive']
        self.assertEqual([e['parameters']['social_norm_factor'] for e in examples], [1, 10])
        self.assertTrue(all('c_inj' not in e['parameters'] for e in examples))
        current, notes = _ranking_formula_content({'scenario': STATIC}, resolve_parameters(STATIC))
        self.assertNotIn(r'c_{\mathrm{inj}}', '\n'.join(current))
        self.assertFalse(any('c_inj' in note for note in notes))
        legacy, notes = _ranking_formula_content({'scenario': STATIC, 'problem': {'names': ['c_inj']}}, {})
        self.assertIn(r'c_{\mathrm{inj}}', legacy[1])
        self.assertTrue(any('historische Parameterdefinition' in note for note in notes))


if __name__ == '__main__':
    unittest.main()
