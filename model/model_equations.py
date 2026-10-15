import json
import multiprocessing
from pathlib import Path
from collections import namedtuple

import numpy as np
import pandas as pd
from model.solvers import ADAPTIVE_SOLVERS, get_solver
import model.agent as agent
from utils.paths import CONFIG_DIR, DATA_DIR

DELAY_NORMS = {"dynamic social norm2", "Descriptive, injunctive, dynamic2",
               "Injunctive, dynamic2"}
DYNAMIC_ODE_NORMS = {"dynamic social norm", "Descriptive, injunctive, dynamic"}

emissions_path = DATA_DIR / "global.1751_2017.csv"
df = pd.read_csv(emissions_path)
second_column = df.iloc[:, 1]
second_column_numeric = pd.to_numeric(second_column, errors="coerce").dropna()
second_column_array = second_column_numeric.to_numpy()
emission_rate = second_column_array[49:] / (10**3)
year_column_numeric = pd.to_numeric(df.iloc[:, 0], errors="coerce").dropna()
year_array = year_column_numeric.to_numpy(dtype=int)
simulation_years = year_array[49:]

def load_scenarios(include=None, exclude=None):
    """Load scenarios with their shared parameters explicitly set in JSON.

    Args:
        include: Iterable of scenario names to keep. If None, all scenarios are
            included. Pass a one-element list/tuple/set for a single scenario.
        exclude: Iterable of scenario names to remove after include filtering.
            Pass a one-element list/tuple/set for a single scenario.
    """
    scenarios_path = CONFIG_DIR / "scenarios.json"
    with scenarios_path.open("r", encoding="utf-8") as file:
        configured = json.load(file)
    common = configured["baseline"]
    loaded_scenarios = {name: {**common, **values}
                        for name, values in configured.items() if name != "ignore"}

    if include is not None:
        include = set(include)
        loaded_scenarios = {name: params for name, params in loaded_scenarios.items() if name in include}

    if exclude is not None:
        exclude = set(exclude)
        loaded_scenarios = {name: params for name, params in loaded_scenarios.items() if name not in exclude}

    return loaded_scenarios


def _resolve_extension(extension):
    """Resolve `extension` to a parameter dictionary.
    Named scenarios use their shared JSON configuration. Dictionaries are
    complete model inputs and receive no missing values from another scenario.
    """
    if isinstance(extension, str):
        scenarios = load_scenarios()
        return scenarios[extension]

    if isinstance(extension, dict):
        return dict(extension)

    raise TypeError(
        "extension must be a scenario name string or a complete parameter dict"
    )


def resolve_parameters(extension):
    """Load/copy parameters, validate their values and calculate derived values.

    No fallback parameter values are inserted. Missing inputs raise native
    KeyError exceptions when the model accesses them.
    """
    parameters = dict(_resolve_extension(extension))
    if "alpha" in parameters:
        raise ValueError(
            "alpha has been removed. For approval use "
            "social_norm_factor_new = social_norm_factor_old * alpha_old."
        )
    if "delta" in parameters:
        raise ValueError(
            "delta has been removed. Use social_norm_factor for norm strength; "
            "see README.md for converting legacy parameter sets."
        )
    if "tau_STref" in parameters:
        raise ValueError(
            "tau_STref has been removed. Use c_dyn for combined-norm "
            "trend strength, or social_norm_factor for the pure "
            "dynamic norm; see README.md for converting legacy parameter sets."
        )
    if parameters["social_norm"] == "Static injunctive" and "c_inj" in parameters:
        raise ValueError(
            "c_inj has been removed from Static injunctive. Use "
            "social_norm_factor_new = social_norm_factor_old * c_inj_old."
        )
    if parameters["social_norm"] in DELAY_NORMS:
        if "a" in parameters:
            raise ValueError("Dynamic2 parameter a has been renamed to rho; update the parameter key.")
        tau_delay = float(parameters["tau"])
        if not np.isfinite(tau_delay) or tau_delay <= 0:
            raise ValueError("Dynamic2 requires finite tau > 0 so that theta = tau*rho > tau.")
        factor = float(parameters["rho"])
        if not np.isfinite(factor) or factor <= 1:
            raise ValueError("Dynamic2 requires finite rho > 1.")
        theta_delay = tau_delay * factor
        if not np.isfinite(theta_delay) or theta_delay <= tau_delay:
            raise ValueError("Dynamic2 requires finite theta = tau*rho > tau.")
        parameters["tau"] = tau_delay
        parameters["rho"] = factor  # rho (ρ): Verhältnis theta/tau, strikt > 1.
        parameters["theta"] = theta_delay  # Abgeleitetes Zeitfenster; kein freier Parameter.
    is_agent_norm = parameters["social_norm"] == "Observation-based / intention motivation"
    if bool(parameters["ABM"]) != is_agent_norm:
        raise ValueError("The observation-based intention norm requires ABM=True; "
                         "ABM=True supports only this norm.")
    if is_agent_norm:
        parameters["agent_decision_model"] = "annual_intention_threshold"
        renamed = {"agent_norm_weight": "eta", "agent_norm_threshold": "phi",
                   "agent_behavior_threshold": "psi"}
        for old, new in renamed.items():
            if old in parameters:
                raise ValueError(f"{old} has been renamed to {new}; update the parameter key.")
        for removed in ("agent_susceptibility", "agent_update_rate"):
            if removed in parameters:
                raise ValueError(f"{removed} has been removed from the intention model; "
                                 "use eta and annual threshold decisions.")
        # eta: norm weight; phi: observed-share threshold; psi: BI action threshold.
        for name in ("eta", "phi", "psi"):
            value = float(parameters[name])
            if not np.isfinite(value):
                raise ValueError(f"{name} must be finite")
            parameters[name] = value
        if parameters["eta"] < 0:
            raise ValueError("eta must be nonnegative")
        if not 0 <= parameters["phi"] <= 1:
            raise ValueError("phi must be between 0 and 1")
    return parameters


def _make_time_breaks(simulation_time, coupling_interval):
    """
    Create outer-loop coupling times.
    """

    if simulation_time <= 0:
        raise ValueError("simulation_time must be positive")

    if coupling_interval <= 0:
        raise ValueError("coupling_interval must be positive")

    breaks = [0.0]
    current_time = 0.0

    while current_time + coupling_interval < simulation_time:
        current_time += coupling_interval
        breaks.append(current_time)

    if breaks[-1] < simulation_time:
        breaks.append(float(simulation_time))

    return np.asarray(breaks, dtype=float)


def _make_agent_time_breaks(simulation_time, coupling_interval):
    """Include exact years for decisions/forcing, independently of solver steps."""
    if not np.isfinite(simulation_time) or simulation_time <= 0:
        raise ValueError("simulation_time must be finite and positive")
    if not np.isfinite(coupling_interval) or coupling_interval <= 0:
        raise ValueError("coupling_interval must be finite and positive")
    coupling_times = np.arange(int(np.ceil(simulation_time / coupling_interval))) * coupling_interval
    # Multiplication avoids accumulated addition error; snap near-year points
    # so that e.g. 217 and 217.00000000000003 cannot trigger two decisions.
    nearest_year = np.rint(coupling_times)
    coupling_times = np.where(np.abs(coupling_times - nearest_year) < 1e-10,
                              nearest_year, coupling_times)
    years = np.arange(int(np.floor(simulation_time)) + 1, dtype=float)
    breaks = np.concatenate((coupling_times[coupling_times < simulation_time],
                             years, [float(simulation_time)]))
    return np.unique(breaks)


STATE_NAMES = ("C_at", "C_oc", "C_v", "C_so", "T", "x", "x_p", "x_ref")
SimulationResult = namedtuple("SimulationResult", ("t",) + STATE_NAMES)

def unpack_state(z):
    """Map the solver state vector to named state variables."""
    return dict(zip(STATE_NAMES, z))


def simulate(extension="baseline", simulation_time=400, n_agents=1000, seed=42, coupling_interval=0.1, output_points_per_year=100, simulate_only_x=False, verbose=None, solver="BDF", dt=None, constant_temperature_costs=False):
    """Run the coupled climate-social model and return state time series.

    solver: "BDF" (default), "LSODA" (both adaptive), or fixed-step "RK4".
    dt: Required positive step in years for RK4; ignored by adaptive solvers.
        RK4 shortens steps at coupling/end boundaries and records delay
        history at accepted steps independently of output sampling.
    constant_temperature_costs: Use f_T(T)=1 for behavioural decisions; the
        contribution is then temperature_factor, while climate still evolves.
    In the agent scenario, x is actual agent behaviour held between annual
    decisions at t=217,218,... (2017 onward); event outputs are right-continuous.
    """
    solver_name, integrate_interval = get_solver(solver, dt)
    p = resolve_parameters(extension)
    if verbose is None:
        verbose = multiprocessing.current_process().name == "MainProcess"
    if verbose:
        print(f"Running {extension} with parameters: {p}")
    use_agent_model = p["ABM"]
    social_norm_mode = str(p["social_norm"])
    is_delay_dynamic_mode = social_norm_mode in DELAY_NORMS
    tau_delay = float(p["tau"]) if is_delay_dynamic_mode else 0.0
    theta_delay = float(p["theta"]) if is_delay_dynamic_mode else 0.0
    delay_window = max(0.0, tau_delay) + max(0.0, theta_delay)
    rng = np.random.default_rng(seed)
    agents = None
    if use_agent_model:
        agents = agent.initialize_agents(
            n_agents=n_agents,
            initial_mitigation_share=p["x0"],
            rng=rng,
            network_size=p["network_size"],
            beta=p["beta"],
        )
    def epsilon(t):
        """Return the prescribed (or saturating) emission rate at timestep t."""
        t = int(t)
        if t < 217:
            return emission_rate[t]
        return (((t - 217) * p["epsilon_max"]) / (t - 217 + p["s"])) + emission_rate[217]

    def P_co2(C_a):
        """Compute partial pressure of CO2 from atmospheric carbon `C_a`."""
        return max(0.0, p["f_gtm"] * (C_a + p["C_at0"]) / p["K_a"])

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

    def diff_carbon(t, state):
        """Evaluate each shared flux once for this RHS state only.

        Preserve the arithmetic order in each original carbon equation.
        Never reuse fluxes across solver evaluations (including RK stages
        and finite-difference Jacobian evaluations).
        """
        emissions = epsilon(t) * (1 - state["x"])
        productivity = P(state["C_at"], state["T"])
        vegetation_respiration = R_veg(state["C_v"], state["T"])
        soil_respiration = R_so(state["T"], state["C_so"])
        ocean_flux = F_oc(state["C_at"], state["C_oc"])
        litterfall = L(state["C_v"])
        return (
            emissions - productivity + vegetation_respiration + soil_respiration - ocean_flux,
            ocean_flux,
            productivity - vegetation_respiration - litterfall,
            litterfall - soil_respiration,
        )

    def diff_T(t, state):
        """Time derivative of temperature anomaly T from radiative imbalance."""
        return (p["a_E"] / p["c"]) * (F_d(state["C_at"], state["T"]) - p["sigma"] * (state["T"] + p["T_0"]) ** 4) * 3.14 * 10**7 

    # important note: in the bury paper they use this function with T_f like this: f(T_F). However, here we've simplified the model to use T instead of T_F. T_F was defined like this: T_f(t) = T(t) + t_f/t_p (T(t) - T(t-t_p)))
    def f_T(T):
        """Temperature-dependent benefit function for social dynamics."""
        if constant_temperature_costs:
            return np.ones_like(T, dtype=float)
        return p["f_max"] / (1 + np.exp(-p["omega"] * (T - p["T_c"])))

    delay_history_times: list[float] = [0.0]
    delay_history_x: list[float] = [float(p["x0"])]
    # np.interp would otherwise convert both Python lists on every query.
    # Rebuild lazily after history changes; the sample values stay identical.
    delay_history_arrays = None

    def evaluate_delayed_x(query_time: float, current_time: float, current_x: float) -> float:
        """Get x(query_time) from stored history, with linear interpolation fallback."""
        nonlocal delay_history_arrays
        if query_time <= delay_history_times[0]:
            return delay_history_x[0]

        last_known_time = delay_history_times[-1]
        if query_time > last_known_time:
            # During an active interval, interpolate between last stored state and current RHS state.
            if current_time <= last_known_time:
                return current_x
            alpha = (query_time - last_known_time) / (current_time - last_known_time)
            alpha = float(np.clip(alpha, 0.0, 1.0))
            return delay_history_x[-1] + alpha * (current_x - delay_history_x[-1])

        if delay_history_arrays is None:
            delay_history_arrays = (
                np.asarray(delay_history_times, dtype=float),
                np.asarray(delay_history_x, dtype=float),
            )
        return float(np.interp(query_time, *delay_history_arrays))

    def get_social_norm_term(state, t):
        match p["social_norm"]:
            case "Observation-based / imitation":
                # Baseline from Bury
                return 2 * state["x"] - 1
            case "Belief-based / intention motivation":
                # Constant signed N, including N < 0; project adaptation inspired by Beckage.
                return p["N"]
            # case "Belief-based / approval":
            #     return 2 * p["sanction_term"]  # sanction term
            case "Observation based / approval (punish only one behaviour)":
                # Observation based / approval (in general) follows dynamics similar to Observation-based / imitation. however, here the agents pay-off is not determined by the observed majority, but by a distinct sanction term
                # approach 1: replicator equation with cost/reward is only applied to one behaviour (an agent not following the norm expects to be punished, while agents following the norm are not affected)
                #               equation was built by combining the model of sigdel et al. and bury et al. 
                # approach 2: replicator equation with punisher agents, who punish non-mitigators and the sanction depends on how many punishers exist (parameter z in the review). 
                # Fixed punisher proportion and punishment strength are combined
                # in social_norm_factor, applied once in diff_x.
                return state["x"]
            case "Observation based / approval (relative to mean)":
                #  approach 3: agent based: Here, agents are rewarded if they, for example, fish less than the mean population and punished if they fish more
                # TODO: in ODE konvertieren & implementieren
                # social_norm_term = 
                return None
            case "dynamic social norm":
                # based on the paper by Rajah et al.
                # x_p = current perceiption of x (aktuelle Wahrnehmung von x im Alltag)
                # x_ref = reference value for x (Referenzwert für x, der als normal angesehen wird) (deutlich träger als x_p) (gesellschaftliche Norm) (etablierter Maßstab)
                if abs(state["x_ref"]) < 1e-12:
                    return 0.0
                return (state["x_p"] - state["x_ref"]) / state["x_ref"]  # relative change in the social norm
            # Nicht mehr genutzte Norm; Gleichung nur als Referenz behalten.
            # case "dynamic baseline":
            #     if abs(state["x_ref"]) < 1e-12:
            #         trend = 0.0
            #     else:
            #         trend = p["c_dyn"] * (state["x_p"] - state["x_ref"]) / state["x_ref"]
            #     return (1 + trend) * (2 * state["x"] - 1)
            case "Static injunctive":
                return p["x_target"] - state["x"]
            case "Descriptive, injunctive, dynamic":
                if abs(state["x_ref"]) < 1e-12:
                    dynamic_term = 0.0
                else:
                    dynamic_term = p["c_dyn"] * (state["x_p"] - state["x_ref"]) / state["x_ref"]
                descriptive_term = 2 * state["x"] - 1
                injunctive_term = p["c_inj"] * (p["x_target"] - state["x"])
                return descriptive_term + injunctive_term + dynamic_term              
            case "dynamic social norm2":
                x_tau = evaluate_delayed_x(t - p["tau"], t, float(state["x"]))
                x_tau_theta = evaluate_delayed_x(t - p["tau"] - p["theta"], t, float(state["x"]))
                dynamic_term = (x_tau - x_tau_theta) / p["theta"]
                return p["c_dyn"] * dynamic_term
            case "Descriptive, injunctive, dynamic2":
                x_tau = evaluate_delayed_x(t - p["tau"], t, float(state["x"]))
                x_tau_theta = evaluate_delayed_x(t - p["tau"] - p["theta"], t, float(state["x"]))
                dynamic_term = (x_tau - x_tau_theta) / p["theta"]
                descriptive_term = 2 * state["x"] - 1
                injunctive_term = p["c_inj"] * (p["x_target"] - state["x"])
                return descriptive_term + injunctive_term + p["c_dyn"] * dynamic_term
            case "Injunctive, dynamic2":
                x_tau = evaluate_delayed_x(t - p["tau"], t, float(state["x"]))
                x_tau_theta = evaluate_delayed_x(t - p["tau"] - p["theta"], t, float(state["x"]))
                dynamic_term = (x_tau - x_tau_theta) / p["theta"]
                injunctive_term = p["c_inj"] * (p["x_target"] - state["x"])
                return injunctive_term + p["c_dyn"] * dynamic_term
            case _:
                raise ValueError(f"Unknown social norm type: {p['social_norm']}")
               

    def diff_x(t, state):
        if use_agent_model:
            # Actual behaviour is assigned at annual events, not by a replicator.
            return 0.0
        # Mitigation is fixed before 2017; no social-norm evaluation is needed.
        if t < 217:
            return 0
        social_norm_term = get_social_norm_term(state, t)
        if social_norm_term is None:
            return 0
        return p["kappa"] * state["x"] * (1 - state["x"]) * (-p["beta"] + p["temperature_factor"] * f_T(state["T"]) + p["social_norm_factor"] * social_norm_term)

    # Literaturanalogie: Rajah et al. (2025), Abs. 3.1.3 und Tab. A1, S. 6017.
    # https://doi.org/10.5194/gmd-18-5997-2025
    # tau_xp entspricht AT_adc; tau_ref dem Kurzzeitreferenz-Horizont AT_STref.
    # Tierprodukte: 2.86 (1.87-3.84) bzw. 5.53 (1-10.1) Jahre.
    # Gesamtnahrung: 1.11 (1-1.23) bzw. 2.37 (1-3.74) Jahre.
    # Kalibrierte Werte/Unsicherheitsbereiche; Übertragung auf Mitigation ist eine Annahme.
    def diff_x_ref(t, state):
        if social_norm_mode not in DYNAMIC_ODE_NORMS:
            return 0
        return (state["x_p"] - state["x_ref"]) / p["tau_ref"]
    
    def diff_x_p(t, state):
        if social_norm_mode not in DYNAMIC_ODE_NORMS:
            return 0
        return (state["x"] - state["x_p"]) / p["tau_xp"]

    def model(t, z):
        """Pure climate/ODE RHS; annual agent decisions occur outside the solver."""
        state = unpack_state(z)
        carbon_derivatives = (0, 0, 0, 0) if simulate_only_x else diff_carbon(t, state)
        return np.array([
            *carbon_derivatives,
            diff_T(t, state),
            diff_x(t, state),
            diff_x_p(t, state),
            diff_x_ref(t, state),
        ])

    initial_state = {"C_at": 0, "C_oc": 0, "C_v": 0, "C_so": 0, "T": 0, "x": p["x0"], "x_ref": p["x0"], "x_p": p["x0"]}
    if use_agent_model:
        # Rounding to whole agents also applies before the first decision.
        actual_initial_share = agent.mitigation_share(agents)
        initial_state.update(x=actual_initial_share, x_p=actual_initial_share,
                             x_ref=actual_initial_share)
    z_current = np.array([initial_state[name] for name in STATE_NAMES])     # initialize the current state vector for the ODE solver
    make_time_breaks = _make_agent_time_breaks if use_agent_model else _make_time_breaks
    time_breaks = make_time_breaks(simulation_time=simulation_time, coupling_interval=coupling_interval)

    all_times = []
    all_states = []
    all_social_terms = []

    agent_times = []
    agent_shares = []
    agent_social_terms = []
    agent_temperatures = []
    agent_behavioral_intentions = []
    agent_actual_behaviors = []
    agent_peer_norms = []

    def record_agents(time, temperature):
        agent_times.append(float(time))
        agent_temperatures.append(float(temperature))
        agent_shares.append(agent.mitigation_share(agents))
        agent_social_terms.append(agent.mean_norm_contribution(agents))
        agent_behavioral_intentions.append(np.asarray([a.behavioral_intention for a in agents], dtype=float))
        agent_actual_behaviors.append(agent.actual_behaviors_array(agents).astype(np.uint8))
        agent_peer_norms.append(np.asarray([a.peer_norm for a in agents], dtype=float))

    if use_agent_model:
        # The historical initial behaviour is prescribed, not decided at t=0.
        agent.evaluate_intentions(agents, initial_state["T"], p, f_T)
        record_agents(0.0, initial_state["T"])

    def record_solver_step(t, state):
        nonlocal delay_history_arrays
        # RK4 checks every accepted node, including nodes absent from t_eval.
        if np.any(state[5:8] < -1e-7) or np.any(state[5:8] > 1 + 1e-7):
            raise RuntimeError(f"RK4 fractions left [0, 1] at t={t}; reduce dt")
        if is_delay_dynamic_mode:
            delay_history_times.append(float(t))
            delay_history_x.append(float(state[5]))
            delay_history_arrays = None

    # -------------------------------------------------------------
    # Coupled simulation loop
    # -------------------------------------------------------------

    for interval_index, (t0, t1) in enumerate(zip(time_breaks[:-1], time_breaks[1:])):
        interval_agent_social_term = agent_social_terms[-1] if use_agent_model else None
        interval_length = t1 - t0
        n_output_points = max(2, int(round(interval_length * output_points_per_year)) + 1,)

        local_t_eval = np.linspace(t0, t1, n_output_points)

        interval_solution = integrate_interval(
            model,
            (t0, t1),
            z_current,
            t_eval=local_t_eval,
            dt=dt,
            on_step=record_solver_step,
        )

        if not interval_solution.success:
            raise RuntimeError("ODE integration failed: " + interval_solution.message)

        # x, x_p and x_ref are fractions/reference fractions whose analytical
        # dynamics preserve the interval [0, 1]. BDF does not enforce state
        # constraints, so retry a numerically invalid interval with stricter
        # tolerances and a smaller maximum step.
        fraction_state_indices = {
            "x": 5,
            "x_p": 6,
            "x_ref": 7,
        }
        fraction_tolerance = 1e-7

        def invalid_fraction_states(solution):
            invalid = {}
            for state_name, state_index in fraction_state_indices.items():
                values = solution.y[state_index, :]
                if not np.all(np.isfinite(values)):
                    invalid[state_name] = (float("nan"), float("nan"))
                    continue
                min_value = float(np.min(values))
                max_value = float(np.max(values))
                if (
                    min_value < -fraction_tolerance
                    or max_value > 1.0 + fraction_tolerance
                ):
                    invalid[state_name] = (min_value, max_value)
            return invalid

        invalid_states = invalid_fraction_states(interval_solution)
        if invalid_states and solver_name in ADAPTIVE_SOLVERS:
            interval_solution = integrate_interval(
                model,
                (t0, t1),
                z_current,
                t_eval=local_t_eval,
                retry=True,
            )
            if not interval_solution.success:
                raise RuntimeError("ODE integration failed: " + interval_solution.message)
            invalid_states = invalid_fraction_states(interval_solution)

        if invalid_states:
            state_summary = ", ".join(
                f"{state_name}: min={bounds[0]:.6g}, max={bounds[1]:.6g}"
                for state_name, bounds in invalid_states.items()
            )
            raise RuntimeError(
                "Numerical integration left the valid fraction interval [0, 1] "
                f"in interval ({t0}, {t1}): {state_summary}"
            )

        # Project only residual floating-point boundary errors after validation.
        for state_index in fraction_state_indices.values():
            interval_solution.y[state_index, :] = np.clip(
                interval_solution.y[state_index, :],
                0.0,
                1.0,
            )

        z_current = interval_solution.y[:, -1].copy()
        if use_agent_model and t1 >= 217.0 and float(t1).is_integer():
            agent.update_agents(agents, temperature=z_current[4], p=p, f_T=f_T)
            z_current[5] = agent.mitigation_share(agents)
            # Record the post-decision value exactly at the event. Climate
            # states stay continuous; the next interval emits using this x.
            interval_solution.y[5, -1] = z_current[5]
            record_agents(t1, z_current[4])

        interval_times = interval_solution.t
        interval_states = interval_solution.y

        # TODO: is this required? If so, why?
        # Remove duplicated boundary points between intervals.
        if interval_index > 0:
            interval_times = interval_times[1:]
            interval_states = interval_states[:, 1:]

        all_times.append(interval_times)
        all_states.append(interval_states)

        if is_delay_dynamic_mode:
            # Extend and retain only the history needed for delayed interpolation.
            if solver_name in ADAPTIVE_SOLVERS:
                delay_history_times.extend(interval_times.tolist())
                delay_history_x.extend(interval_states[5, :].tolist())
            cutoff_time = float(interval_times[-1]) - delay_window - max(float(coupling_interval), 1.0)
            if cutoff_time > delay_history_times[0]:
                keep_from = int(np.searchsorted(delay_history_times, cutoff_time, side="left"))
                keep_from = max(0, keep_from - 1)
                if keep_from > 0:
                    delay_history_times = delay_history_times[keep_from:]
                    delay_history_x = delay_history_x[keep_from:]
            delay_history_arrays = None

        if use_agent_model:
            interval_terms = np.full(interval_times.shape, interval_agent_social_term, dtype=float)
            interval_terms[-1] = agent_social_terms[-1]
            all_social_terms.append(interval_terms)

    # t_span = (0, simulation_time)

    # sol = solve_ivp(
    #     model,
    #     t_span,
    #     z0,
    #     method="BDF",
    #     t_eval=np.linspace(0, simulation_time, simulation_time * 100),
    # )


    # -------------------------------------------------------------
    # Assemble simulation output
    # -------------------------------------------------------------

    simulation_times = np.concatenate(all_times)
    simulation_states = np.concatenate(all_states, axis=1)
    simulation = SimulationResult(simulation_times, *simulation_states)
    if use_agent_model:
        social_norm_history = np.concatenate(all_social_terms)
    elif social_norm_mode in DELAY_NORMS:
        x_series = simulation_states[5, :].astype(float)
        x_tau = np.interp(simulation_times - tau_delay, simulation_times, x_series, left=x_series[0], right=x_series[-1])
        x_tau_theta = np.interp(simulation_times - tau_delay - theta_delay, simulation_times, x_series, left=x_series[0], right=x_series[-1])
        trend_series = (x_tau - x_tau_theta) / theta_delay

        dynamic_term = float(p["c_dyn"]) * trend_series
        if social_norm_mode == "dynamic social norm2":
            social_norm_history = dynamic_term
        elif social_norm_mode == "Injunctive, dynamic2":
            injunctive_term = float(p["c_inj"]) * (float(p["x_target"]) - x_series)
            social_norm_history = injunctive_term + dynamic_term
        else:
            descriptive_term = 2.0 * x_series - 1.0
            injunctive_term = float(p["c_inj"]) * (float(p["x_target"]) - x_series)
            social_norm_history = descriptive_term + injunctive_term + dynamic_term
    else:
        social_norm_history = np.asarray(
            [
                get_social_norm_term(
                    unpack_state(simulation_states[:, i]),
                    float(simulation_times[i]),
                )
                for i in range(simulation_states.shape[1])
            ],
            dtype=float,
        )

    result = {
        "simulation": simulation,
        "social_norm_term": social_norm_history,
        "f_T": np.asarray(f_T(simulation.T), dtype=float),
        "parameters": dict(p),
        "solver_settings": {"solver": solver_name, "dt": dt,
                            "coupling_interval": coupling_interval,
                            "output_points_per_year": output_points_per_year,
                            "constant_temperature_costs": constant_temperature_costs},
    }

    if use_agent_model:
        result["agents"] = agents
        result["agent_history"] = {
            "t": np.asarray(agent_times, dtype=float),
            "temperature": np.asarray(agent_temperatures, dtype=float),
            "mitigation_share": np.asarray(agent_shares, dtype=float),
            "social_norm_term": np.asarray(agent_social_terms, dtype=float),
            "behavioral_intention": np.asarray(agent_behavioral_intentions, dtype=float),
            "actual_behavior": np.asarray(agent_actual_behaviors, dtype=np.uint8),
            "peer_norm": np.asarray(agent_peer_norms, dtype=float),
            "beta": np.asarray([a.beta for a in agents], dtype=float),
            "is_decision": np.asarray([False] + [True] * (len(agent_times) - 1)),
        }
    return result
    
    # # create a list of all states at each time step by unpacking the solver state vector
    # states = [
    #     unpack_state(sol.y[:, i])
    #     for i in range(sol.y.shape[1])
    # ]
    # social_norm_term = np.array([
    #     get_social_norm_term(state)
    #     for state in states
    # ])

    # return {
    #     "simulation": SimulationResult(sol.t, *sol.y),
    #     "social_norm_term": social_norm_term
    # }
