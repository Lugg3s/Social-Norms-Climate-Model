"""The zero-norm reference must keep climate coupling and work throughout analysis."""
from dataclasses import replace
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import matplotlib.pyplot as plt
import numpy as np
from scipy.special import expit, logit
import sympy as sp

from analysis import bifurcation_diagram as diagram
from analysis.parameter_ranges import default_sensitivity_scenarios
from analysis.regression_trees.regression_tree_analysis import (
    TreeConfig, common_parameter_scenarios, load_scenario, run_analysis,
)
from analysis.sensitivity import sensitivity_analysis as sensitivity
from analysis.sensitivity.sensitivity_plots import _ranking_formula_content
from analysis.symbolic_analysis import analyze_social_norm, symbolic_social_norm_term
from model.model_equations import resolve_parameters, simulate
from simulation import batch_runner as batch
from support.tools.profile_dynamic_norms import parse_args as profiling_args
from visualization import plotting


SCENARIO = "No social norm"


class NoSocialNormTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.parameters = {**resolve_parameters(SCENARIO), "temperature_factor": .7, "beta": .1, "kappa": .3}
        cls.options = dict(simulation_time=220, coupling_interval=1, output_points_per_year=4,
                           constant_temperature_costs=True, verbose=False)
        cls.result = simulate(cls.parameters, **cls.options)

    def test_zero_term_and_analytic_behaviour_with_climate_coupling(self):
        result, params = self.result, self.parameters
        np.testing.assert_array_equal(result["social_norm_term"], 0)
        self.assertNotIn("social_norm_factor", result["parameters"])
        trajectory = result["simulation"]
        elapsed = np.maximum(trajectory.t - 217, 0)
        expected = expit(logit(params["x0"]) + params["kappa"] *
                         (params["temperature_factor"] - params["beta"]) * elapsed)
        np.testing.assert_allclose(trajectory.x, expected, rtol=0, atol=2e-6)
        self.assertGreater(float(np.ptp(trajectory.T)), 0)
        self.assertGreater(float(np.ptp(trajectory.C_at)), 0)
        self.assertGreater(trajectory.x[-1], params["x0"])

    def test_matches_imitation_with_disabled_norm_weight(self):
        comparison = simulate({**self.parameters, "social_norm": "Observation-based / imitation",
                               "social_norm_factor": 0}, **self.options)
        np.testing.assert_allclose(np.asarray(self.result["simulation"]),
                                   np.asarray(comparison["simulation"]), rtol=0, atol=1e-10)
        # The zero-norm mechanism must stay zero even if an extraneous weight is supplied.
        ignored = simulate({**self.parameters, "social_norm_factor": 1000}, **self.options)
        np.testing.assert_array_equal(ignored["social_norm_term"], 0)
        np.testing.assert_array_equal(ignored["simulation"].x, self.result["simulation"].x)

    def test_symbolic_equation_and_ranking_formula_exclude_unused_weight(self):
        self.assertEqual(symbolic_social_norm_term(SCENARIO), sp.Integer(0))
        analysis = analyze_social_norm(SCENARIO)
        self.assertEqual(analysis.status, "ok")
        self.assertNotIn("social_norm_factor", {s.name for s in analysis.behavioural_bracket.free_symbols})
        self.assertEqual({eq.value for eq in analysis.equilibria}, {0, 1})
        rows, _ = _ranking_formula_content({"scenario": SCENARIO}, self.parameters)
        self.assertIn("S=0", rows)
        self.assertNotIn(r"social\_norm\_factor", rows[0])

    def test_default_selections_and_three_input_sobol_problem(self):
        self.assertIn(SCENARIO, default_sensitivity_scenarios())
        self.assertIn(SCENARIO, profiling_args([]).scenarios)
        self.assertIn(SCENARIO, [name for group in batch.load_default_groups() for name in group.scenarios])
        problem = sensitivity.build_problem(SCENARIO)
        self.assertEqual(problem["names"], ["temperature_factor", "beta", "kappa"])
        self.assertEqual(problem["bounds"], [[0, 5], [0, 5], [0, .5]])
        grids = diagram.scenario_grids(default_sensitivity_scenarios(), "beta", num_points=2)
        tasks, _ = diagram.build_tasks(default_sensitivity_scenarios(), "beta", grids, diagram.SweepConfig())
        self.assertEqual(len([t for t in tasks if t["scenario"] == SCENARIO]), 2)

    def test_batch_and_notebook_incentive_plots_draw_zero_without_norm_weight(self):
        frame = batch.simulation_to_dataframe(self.result, self.parameters)
        figure, axis = plt.subplots()
        try:
            batch._plot_mitigation_incentives(axis, frame, self.parameters)
            np.testing.assert_array_equal(axis.lines[0].get_ydata(), 0)
        finally:
            plt.close(figure)
        with tempfile.TemporaryDirectory() as directory, \
             patch.object(plotting, "_RUN_OUTPUT_DIR", Path(directory)), \
             patch.object(plotting.plt, "show"):
            try:
                plotting.plot_social_norms(scenarios=[SCENARIO], results={SCENARIO: self.result},
                                           simulation_time=220)
            finally:
                plt.close("all")

    def test_small_real_sobol_run_saved_trajectories_and_regression_tree(self):
        config = sensitivity.SensitivityConfig(simulation_time=218, coupling_interval=1,
                                               output_points_per_year=2, base_sample_size=8,
                                               workers=2, constant_temperature_costs=True)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            saved = sensitivity.run_sensitivity_analysis(SCENARIO, root / "sensi", config)
            metadata = json.loads((saved / "metadata.json").read_text(encoding="utf-8"))
            self.assertEqual(metadata["number_of_model_runs"], 40)
            self.assertEqual(metadata["number_of_completed_samples"], 40)
            scenario = load_scenario(saved)
            self.assertEqual(scenario.feature_names, ["temperature_factor", "beta", "kappa"])
            extended = replace(scenario, feature_names=["social_norm_factor", *scenario.feature_names],
                               data=scenario.data.assign(social_norm_factor=1),
                               metadata={**scenario.metadata, "scenario": "Synthetic extended inputs"})
            common, _, _ = common_parameter_scenarios([extended, scenario])
            self.assertEqual(common, ["temperature_factor", "beta", "kappa"])
            reports = run_analysis(saved, root / "trees", targets=["final_x"],
                                   config=TreeConfig(depths=(2,), cv_folds=3, stability_repeats=1))
            self.assertEqual(reports[0]["status"], "fitted")
            self.assertEqual(reports[0]["scenario"], SCENARIO)
            from simulation.time_series import load_time_series
            archives = list(saved.glob("time_series_*/sample_*.npz"))
            self.assertEqual(len(archives), 40)
            for archive in archives:
                frame, _ = load_time_series(archive)
                np.testing.assert_array_equal(frame.social_norm_term.to_numpy(), 0)


if __name__ == "__main__":
    unittest.main()
