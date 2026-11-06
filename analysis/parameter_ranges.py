"""Shared analysis ranges from scenarios.json; never inserted into model inputs."""
import json

import numpy as np

from model.model_equations import load_scenario_defaults
from utils.paths import CONFIG_DIR


def _configuration():
    with (CONFIG_DIR / "scenarios.json").open(encoding="utf-8") as handle:
        return json.load(handle)["parameter_ranges"]


def validate_bounds(bounds):
    if len(bounds) != 2:
        raise ValueError("A parameter range needs exactly two limits")
    low, high = map(float, bounds)
    if not np.isfinite(low) or not np.isfinite(high) or low >= high:
        raise ValueError("Parameter ranges require finite MIN < MAX")
    return [low, high]


def parse_range_overrides(items):
    """Parse repeatable CLI triples: NAME MIN MAX."""
    result = {}
    for name, low, high in items or []:
        if name in result:
            raise ValueError(f"Duplicate range override: {name}")
        result[name] = validate_bounds([low, high])
    return result


def get_parameter_ranges(scenario_name, overrides=None):
    config = _configuration()
    parameters = load_scenario_defaults(scenario_name)
    overrides = {} if overrides is None else overrides
    for name in overrides:
        parameters[name]  # A CLI range must refer to an explicitly declared input.
    ranges = {name: overrides[name] if name in overrides else config["bounds"][name]
              for name in parameters if name in config["bounds"] or name in overrides}
    return {name: validate_bounds(bounds) for name, bounds in ranges.items()}


def get_parameter_range(parameter_name):
    """Look up one global range, independently of the norm's Sobol input list."""
    return validate_bounds(_configuration()["bounds"][parameter_name])


def default_sensitivity_scenarios():
    return list(_configuration()["sensitivity_scenarios"])
