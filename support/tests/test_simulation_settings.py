"""Defaults must agree across entry points, and explicit inputs must reach the model."""
import inspect
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from dataclasses import replace
from unittest.mock import patch

import numpy as np
import pandas as pd

from analysis import bifurcation_diagram as diagram
from analysis.sensitivity import sensitivity_analysis as sensitivity
from model.model_equations import simulate, resolve_parameters
from simulation import batch_runner as batch, interesting_parameter_loader as csv_runner
from simulation.settings import (DEFAULTS, SETTING_NAMES, load_simulation_settings,
                                 simulation_kwargs, simulation_overrides)
from support.tools import profile_dynamic_norms as profiling
from utils.paths import CONFIG_DIR, PROJECT_ROOT
from visualization import plotting


PARSERS = (diagram.parse_args, sensitivity.parse_args, csv_runner.parse_args, profiling.parse_args)


class SimulationSettingsTests(unittest.TestCase):
    def test_cli_configs_and_direct_model_defaults_agree(self):
        expected = simulation_kwargs()
        for parse in PARSERS:
            self.assertEqual(simulation_kwargs(parse([])), expected)
        for config in (diagram.SweepConfig(), sensitivity.SensitivityConfig(),
                       batch.ExperimentGroup("example", ["baseline"], {})):
            self.assertEqual(simulation_kwargs(config), expected)
        signature = inspect.signature(simulate)
        self.assertEqual({name: signature.parameters[name].default for name in SETTING_NAMES}, expected)
        for function in (plotting.plot_x, plotting.plot_temperature, plotting.plot_x_sensitivity,
                         plotting.plot_temperature_sensitivity, plotting.plot_temperature_sensitivity_2d,
                         plotting.plot_social_norms):
            parameters = inspect.signature(function).parameters
            self.assertEqual(parameters["simulation_time"].default, DEFAULTS.simulation_time)
            self.assertEqual(parameters["simulate_only_x"].default, DEFAULTS.simulate_only_x)

    def test_missing_or_unknown_json_setting_fails_without_fallback(self):
        for settings in ({name: value for name, value in simulation_kwargs().items() if name != "seed"},
                         {**simulation_kwargs(), "typo": 1}):
            with tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / "settings.json"
                path.write_text(json.dumps(settings), encoding="utf-8")
                with self.assertRaises(TypeError):
                    load_simulation_settings(path)

    def test_cli_overrides_and_both_boolean_directions(self):
        flags = ["--simulation-time", "230", "--coupling-interval", "0.5", "--seed", "19",
                 "--n-agents", "1100", "--output-points-per-year", "12", "--solver", "RK4",
                 "--dt", "0.02", "--constant-temperature-costs", "--simulate-only-x"]
        expected = dict(simulation_time=230, coupling_interval=.5, seed=19, n_agents=1100,
                        output_points_per_year=12, solver="RK4", dt=.02,
                        constant_temperature_costs=True, simulate_only_x=True)
        for parse in PARSERS:
            self.assertEqual(simulation_kwargs(parse(flags)), expected)
            disabled = parse(["--no-constant-temperature-costs", "--no-simulate-only-x"])
            self.assertFalse(disabled.constant_temperature_costs)
            self.assertFalse(disabled.simulate_only_x)
        self.assertEqual(simulation_overrides(batch.parse_args([])), {})
        self.assertEqual(simulation_overrides(batch.parse_args(flags)), expected)

    def test_changes_to_json_propagate_to_all_entry_points_in_new_process(self):
        changed = dict(simulation_time=231, output_points_per_year=7, coupling_interval=.25,
                       seed=17, n_agents=1200, solver="LSODA", dt=.01,
                       constant_temperature_costs=True, simulate_only_x=True)
        with tempfile.TemporaryDirectory() as directory:
            for name in ("scenarios.json", "batch_dynamic2_top5_sensi128.json"):
                shutil.copy(CONFIG_DIR / name, Path(directory) / name)
            (Path(directory) / "simulation_settings.json").write_text(json.dumps(changed), encoding="utf-8")
            code = '''
import inspect, json, sys
from pathlib import Path
import utils.paths
utils.paths.CONFIG_DIR = Path(sys.argv[1])
from simulation.settings import simulation_kwargs
from analysis.bifurcation_diagram import parse_args as bifurcation, SweepConfig
from analysis.sensitivity.sensitivity_analysis import parse_args as sensi, SensitivityConfig
from simulation.interesting_parameter_loader import parse_args as csv
from support.tools.profile_dynamic_norms import parse_args as profile
from simulation.batch_runner import ExperimentGroup, load_default_groups
from model.model_equations import simulate
expected = json.loads(sys.argv[2])
for parser in (bifurcation, sensi, csv, profile):
    assert simulation_kwargs(parser([])) == expected
    assert not parser(["--no-constant-temperature-costs"]).constant_temperature_costs
for config in (SweepConfig(), SensitivityConfig(), ExperimentGroup("test", ["baseline"], {})):
    assert simulation_kwargs(config) == expected
assert {key: inspect.signature(simulate).parameters[key].default for key in expected} == expected
archived = load_default_groups()[0]
assert archived.simulation_time == 600 and archived.n_agents == 1000
assert archived.solver == "BDF" and archived.dt is None
assert not archived.constant_temperature_costs and not archived.simulate_only_x
'''
            result = subprocess.run([sys.executable, "-c", code, directory, json.dumps(changed)],
                                    cwd=PROJECT_ROOT, capture_output=True, text=True, timeout=60)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_sensitivity_forwards_all_effective_settings(self):
        config = sensitivity.SensitivityConfig(simulation_time=2, n_agents=1200, solver="LSODA",
                                               seed=19, coupling_interval=.5,
                                               output_points_per_year=4, simulate_only_x=True,
                                               constant_temperature_costs=True)
        with patch.object(sensitivity, "simulate", return_value={}) as model, \
             patch.object(sensitivity, "compute_run_metrics", return_value={}), \
             patch.object(sensitivity, "_prepare_sensitivity_outputs", return_value={}):
            sensitivity._run_sample((resolve_parameters("baseline"), [], np.array([]), config))
        self.assertEqual({key: model.call_args.kwargs[key] for key in SETTING_NAMES},
                         simulation_kwargs(config))

    def test_batch_cli_overrides_group_values_and_manifest_records_them(self):
        group = replace(batch.load_default_groups()[0], parameter_sets=None, sweep_parameters={})
        overrides = dict(simulation_time=233, seed=23, constant_temperature_costs=True)
        with tempfile.TemporaryDirectory() as directory, \
             patch.object(batch, "load_default_groups", return_value=[group]), \
             patch.object(batch, "run_single_combination", return_value={"status": "failed"}) as run, \
             patch.object(batch, "save_group_comparison_plots"), \
             patch.object(batch, "save_approach_comparison_plot"), \
             patch.object(batch, "build_scenario_comparison_table", return_value=pd.DataFrame()), \
             patch.object(batch, "save_overall_comparison_plots"):
            root = batch.run_groups(output_root=Path(directory), workers=1, simulation_settings=overrides)
            effective = replace(group, **overrides)
            self.assertEqual(run.call_args.kwargs["group"], effective)
            manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["groups"][0]["simulation_settings"], simulation_kwargs(effective))

    def test_real_model_records_all_settings_and_reproduces_explicit_defaults(self):
        explicit = {**simulation_kwargs(), "simulation_time": 2}
        implicit = simulate(simulation_time=2, verbose=False)
        repeated = simulate(**explicit, verbose=False)
        self.assertEqual(implicit["solver_settings"], explicit)
        np.testing.assert_array_equal(implicit["simulation"].x, repeated["simulation"].x)
        np.testing.assert_array_equal(implicit["simulation"].T, repeated["simulation"].T)

    def test_csv_overrides_reach_model_and_are_saved(self):
        entry = dict(social_norm="baseline", parameters={}, classification="test", comment="", reason="")
        settings = replace(DEFAULTS, simulation_time=2, coupling_interval=.5, seed=19, solver="LSODA")
        from contextlib import ExitStack
        with tempfile.TemporaryDirectory() as directory, ExitStack() as stack:
            stack.enter_context(patch.object(csv_runner, "load_interesting_parameter_sets", return_value=[entry]))
            for name in ("save_temperature_plot", "save_x_plot", "save_x_phase_space_plot",
                         "save_social_norm_plot", "save_f_T_plot", "save_auxiliary_plot"):
                stack.enter_context(patch.object(csv_runner, name))
            root = csv_runner.run_interesting_parameter_sets(output_root=Path(directory),
                                                             **simulation_kwargs(settings))
            metadata = json.loads(next(root.glob("*/metadata.json")).read_text(encoding="utf-8"))
            self.assertEqual(metadata["simulation_settings"], simulation_kwargs(settings))

    def test_notebook_simulations_save_actual_overrides(self):
        with tempfile.TemporaryDirectory() as directory, \
             patch.object(plotting, "_RUN_OUTPUT_DIR", Path(directory)):
            parameters = {**resolve_parameters("baseline"), "beta": np.int64(1)}
            result = plotting._simulate_for_plot(parameters, simulation_time=2, seed=np.int64(17), verbose=False)
            record = json.loads((Path(directory) / "simulation_manifest.jsonl").read_text(encoding="utf-8"))
            self.assertEqual(record["simulation_settings"], result["solver_settings"])
            self.assertEqual(record["simulation_settings"]["seed"], 17)
            self.assertEqual(record["simulation_settings"]["simulation_time"], 2)

    def test_append_rejects_different_recorded_settings(self):
        metadata = dict(outputs_for_ranking=sensitivity.SENSITIVITY_OUTPUTS,
                        elimination_time_definition={"method": "zero_if_not_reached"},
                        oscillations_per_500_years_definition={
                            "minimum_complete_cycles": 2,
                            "method": "zero_below_minimum_otherwise_scaled_complete_cycle_count"},
                        constant_temperature_costs=DEFAULTS.constant_temperature_costs,
                        simulation_settings=simulation_kwargs())
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "baseline").mkdir()
            (root / "baseline" / "metadata.json").write_text(json.dumps(metadata), encoding="utf-8")
            sensitivity._validate_append_scenarios(root, ["Dynamic social norm"],
                                                  simulation_settings=simulation_kwargs())
            with self.assertRaisesRegex(ValueError, "different simulation settings: seed"):
                sensitivity._validate_append_scenarios(root, ["Dynamic social norm"],
                    simulation_settings={**simulation_kwargs(), "seed": DEFAULTS.seed + 1})


if __name__ == "__main__":
    unittest.main()
