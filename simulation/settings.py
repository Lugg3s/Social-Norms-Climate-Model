"""Shared simulation defaults and CLI options, separate from model parameters.

The JSON file is read once per process. Missing/unknown settings raise native
TypeError exceptions; there are no fallback values in Python. Explicit settings
in saved historical experiments remain independent of these current defaults.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass, fields
import json
from pathlib import Path

from utils.paths import CONFIG_DIR


SETTINGS_PATH = CONFIG_DIR / "simulation_settings.json"


@dataclass(frozen=True)
class SimulationSettings:
    simulation_time: float
    output_points_per_year: int
    coupling_interval: float
    seed: int
    n_agents: int
    solver: str
    dt: float | None
    constant_temperature_costs: bool
    simulate_only_x: bool


def load_simulation_settings(path: Path = SETTINGS_PATH) -> SimulationSettings:
    return SimulationSettings(**json.loads(Path(path).read_text(encoding="utf-8")))


DEFAULTS = load_simulation_settings()
SETTING_NAMES = tuple(field.name for field in fields(SimulationSettings))


def simulation_kwargs(source=DEFAULTS) -> dict:
    """Extract all shared settings from a config, namespace or dictionary."""
    if isinstance(source, dict):
        return {name: source[name] for name in SETTING_NAMES}
    return {name: getattr(source, name) for name in SETTING_NAMES}


def simulation_overrides(namespace) -> dict:
    """For batch CLI: only explicitly supplied options override group values."""
    return {name: getattr(namespace, name) for name in SETTING_NAMES
            if getattr(namespace, name) is not None}


def add_simulation_arguments(parser, *, use_defaults=True):
    """Use the same options everywhere; batch groups resolve defaults themselves."""
    defaults = asdict(DEFAULTS) if use_defaults else dict.fromkeys(SETTING_NAMES)
    options = (
        ("simulation_time", float, "Simulation horizon in years since model start."),
        ("output_points_per_year", int, "Stored evaluation points per simulated year."),
        ("coupling_interval", float, "Coupling interval in years."),
        ("seed", int, "Random initialization seed."),
        ("n_agents", int, "Number of agents in ABM scenarios."),
        ("solver", str, "Integration method."),
        ("dt", float, "Required integration step in years for RK4."),
    )
    for name, kind, help_text in options:
        extra = {"choices": ("BDF", "LSODA", "RK4")} if name == "solver" else {}
        parser.add_argument("--" + name.replace("_", "-"), type=kind,
                            default=defaults[name], help=help_text, **extra)
    parser.add_argument("--constant-temperature-costs", action=argparse.BooleanOptionalAction,
                        default=defaults["constant_temperature_costs"],
                        help="Use f_T(T)=1 for decisions, scaled by temperature_factor.")
    parser.add_argument("--simulate-only-x", action=argparse.BooleanOptionalAction,
                        default=defaults["simulate_only_x"],
                        help="Freeze carbon stocks; the temperature equation still evolves.")
