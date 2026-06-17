import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.integrate import solve_ivp


df = pd.read_csv("global.1751_2017.csv")
second_column = df.iloc[:, 1]
second_column_numeric = pd.to_numeric(second_column, errors="coerce").dropna()
second_column_array = second_column_numeric.to_numpy()
emission_rate = second_column_array[50:] / (10**3)


def _load_baseline_parameters():
    """Load the baseline parameter set from `scenarios.json`."""
    scenarios_path = Path(__file__).with_name("scenarios.json")
    with scenarios_path.open("r", encoding="utf-8") as file:
        scenarios = json.load(file)

    if "Baseline" not in scenarios:
        raise KeyError('Missing "Baseline" scenario in scenarios.json')

    return scenarios["Baseline"]


def load_scenarios():
    """Load all parameter scenarios from `scenarios.json`."""
    scenarios_path = Path(__file__).with_name("scenarios.json")
    with scenarios_path.open("r", encoding="utf-8") as file:
        return json.load(file)


def _resolve_extension(extension):
    """Resolve `extension` to a parameter dictionary.
    Accepts `None`/`"Baseline"`, a scenario name, or a dictionary of
    parameter values loaded from JSON.
    """
    if extension is None or extension == "Baseline":
        return _baseline

    if isinstance(extension, str):
        scenarios = load_scenarios()
        if extension not in scenarios:
            raise KeyError(f'Missing "{extension}" scenario in scenarios.json')
        # Merge: start with baseline, overwrite with scenario-specific values
        return {**_baseline, **scenarios[extension]}

    if isinstance(extension, dict):
        # Also merge if a raw dict is passed in
        return {**_baseline, **extension}       # {**a, **b} is dictionary unpacking. The ** operator spreads a dict's key-value pairs inline, and when two dicts share a key, the last one wins.

    raise TypeError(
        "extension must be None, a scenario name string, or a parameter dict"
    )

_baseline = _load_baseline_parameters()


def simulate(extension="Baseline"):
    """Run the coupled climate-social model for given parameters and return
    time series for each state variable."""
    p = _resolve_extension(extension)
    print(f"Running {extension} with parameters: {p}")

    def epsilon(t):
        """Return the prescribed (or saturating) emission rate at timestep t."""
        t = int(t)
        if t < 216:
            return emission_rate[t]
        return (((t - 216) * p["epsilon_max"]) / (t - 216 + p["s"])) + emission_rate[216]

    def P_co2(C_a):
        """Compute partial pressure of CO2 from atmospheric carbon `C_a`."""
        return p["f_gtm"] * (C_a + p["C_at0"]) / p["K_a"]

    def P(C_a, T):
        """Gross primary productivity as a function of atmospheric CO2 and T."""
        if P_co2(C_a) - p["K_c"] > 0 and T > -15 and T < 25:
            return (
                p["K_p"]
                * p["C_veg0"]
                * p["K_mm"]
                * (P_co2(C_a) - p["K_c"])
                / (p["K_m"] + P_co2(C_a) - p["K_c"])
                * ((15 + T) ** 2)
                * (25 - T)
                / 5625
            )
        return 0

    def R_veg(C_v, T):
        """Vegetation respiration rate dependent on vegetation carbon and T."""
        return p["K_r"] * C_v * p["K_A"] * np.exp(-p["E_a"] / (p["R"] * (T + p["T_0"])))

    def R_so(T, C_so):
        """Soil respiration as function of temperature and soil carbon."""
        return p["K_sr"] * C_so * p["K_b"] * np.exp(-308.56 / (T + p["T_0"] - 227.13))

    def L(C_v):
        """Litterfall from vegetation carbon pool `C_v`."""
        return p["K_t"] * C_v

    def F_oc(C_a, C_oc):
        """Flux between atmosphere and ocean carbon reservoirs."""
        return p["F_0"] * p["xi"] * (C_a - p["zeta"] * p["C_at0"] * C_oc / p["C_ao0"])

    def tau(C_a, T):
        """Atmospheric optical thickness/tau as function of CO2 and temperature."""
        return (
            1.73 * (P_co2(C_a)) ** (0.263)
            + 0.0126 * (p["H"] * p["P_0"] * np.exp(-p["L"] / (p["R"] * (T + p["T_0"])))) ** (0.503)
            + 0.0231
        )

    def F_d(C_a, T):
        """Downward radiative flux at the surface given CO2 and temperature."""
        return (1 - p["A"]) * p["S"] / 4 * (1 + 0.75 * tau(C_a, T))

    def diff_C_at(t, z):
        """Time derivative of atmospheric carbon pool C_a."""
        return (
            epsilon(t) * (1 - z[5])
            - P(z[0], z[4])
            + R_veg(z[2], z[4])
            + R_so(z[4], z[3])
            - F_oc(z[0], z[1])
        )

    def diff_C_o(t, z):
        """Time derivative of ocean carbon pool C_oc (flux to/from atmosphere)."""
        return F_oc(z[0], z[1])

    def diff_C_v(t, z):
        """Time derivative of vegetation carbon pool C_v."""
        return P(z[0], z[4]) - R_veg(z[2], z[4]) - L(z[2])

    def diff_C_so(t, z):
        """Time derivative of soil organic carbon pool C_so."""
        return L(z[2]) - R_so(z[4], z[3])

    def diff_T(t, z):
        """Time derivative of temperature anomaly T from radiative imbalance."""
        return (p["a_E"] / p["c"]) * (F_d(z[0], z[4]) - p["sigma"] * (z[4] + p["T_0"]) ** 4) * 3.14 * 10**7

    def f_T(T):
        """Temperature-dependent benefit function for social dynamics."""
        return p["f_max"] / (1 + np.exp(-p["omega"] * (T - p["T_c"])))

    def diff_x(t, z):
        """Time derivative of social state variable x (adoption level)."""
        if t < 216:
            return 0
        return p["kappa"] * z[5] * (1 - z[5]) * (-p["beta"] + f_T(z[4]) + p["delta"] * (2 * z[5] - 1))

    def model(t, z):
        """Pack state derivatives into array for ODE solver."""
        return np.array([
            diff_C_at(t, z),
            diff_C_o(t, z),
            diff_C_v(t, z),
            diff_C_so(t, z),
            diff_T(t, z),
            diff_x(t, z),
        ])

    z0 = np.array([0, 0, 0, 0, 0, p["x0"]])
    simulation_time = 400
    t_span = (0, simulation_time)

    sol = solve_ivp(
        model,
        t_span,
        z0,
        method="BDF",
        t_eval=np.linspace(0, simulation_time, simulation_time * 100),
    )

    return (
        sol.t,
        sol.y.T[:, 0],
        sol.y.T[:, 1],
        sol.y.T[:, 2],
        sol.y.T[:, 3],
        sol.y.T[:, 4],
        sol.y.T[:, 5],
    )
