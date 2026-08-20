import json
from pathlib import Path
from collections import namedtuple

import numpy as np
import pandas as pd
from scipy.integrate import solve_ivp
import agent

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

    if "baseline" not in scenarios:
        raise KeyError('Missing "baseline" scenario in scenarios.json')

    if "ignore" in scenarios:
        del scenarios["ignore"]

    return scenarios["baseline"]


def load_scenarios(include=None, exclude=None):
    """Load parameter scenarios from `scenarios.json`.

    Args:
        include: Scenario name or iterable of names to keep. If None, all
            scenarios are included.
        exclude: Scenario name or iterable of names to remove after include
            filtering.
    """
    scenarios_path = Path(__file__).with_name("scenarios.json")
    with scenarios_path.open("r", encoding="utf-8") as file:
        loaded_scenarios = {k: v for k, v in json.load(file).items() if k != "ignore"}

    if include is not None:
        include = set(include)
        loaded_scenarios = {name: params for name, params in loaded_scenarios.items() if name in include}

    if exclude is not None:
        exclude = set(exclude)
        loaded_scenarios = {name: params for name, params in loaded_scenarios.items() if name not in exclude}

    return loaded_scenarios


def _resolve_extension(extension):
    """Resolve `extension` to a parameter dictionary.
    Accepts `None`/`"baseline"`, a scenario name, or a dictionary of
    parameter values loaded from JSON.
    """
    if extension is None or extension == "baseline":
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


_baseline = _load_baseline_parameters()
STATE_NAMES = ("C_at", "C_oc", "C_v", "C_so", "T", "x", "x_p", "x_ref")
SimulationResult = namedtuple("SimulationResult", ("t",) + STATE_NAMES)

def unpack_state(z):
    """Map the solver state vector to named state variables."""
    return dict(zip(STATE_NAMES, z))


def simulate(extension="baseline", simulation_time=400, n_agents=1000, seed=42, coupling_interval=1, output_points_per_year=100, simulate_only_x=False):     # network_size
    """Run the coupled climate-social model for given parameters and return
    time series for each state variable."""
    p = _resolve_extension(extension)
    print(f"Running {extension} with parameters: {p}")
    use_agentic_norm = p.get("ABM", False)
    social_norm_mode = str(p.get("social_norm", ""))
    is_delay_dynamic_mode = social_norm_mode in {"dynamic social norm2", "Descriptive, injunctive, dynamic2"}
    tau_delay = float(p.get("tau", 0.0)) if is_delay_dynamic_mode else 0.0
    theta_delay = float(p.get("theta", 0.0)) if is_delay_dynamic_mode else 0.0
    delay_window = max(0.0, tau_delay) + max(0.0, theta_delay)
    rng = np.random.default_rng(seed)
    agents = None
    if use_agentic_norm:
        agents = agent.initialize_agents(
            n_agents=n_agents,
            initial_mitigation_share=p["x0"],
            rng=rng,
            network_size = p["network_size"] if "network_size" in p and p["network_size"] != 0 else None,
            susceptibility=p.get("agent_susceptibility", 1.0),
        )
    def epsilon(t):
        """Return the prescribed (or saturating) emission rate at timestep t."""
        t = int(t)
        if t < 216:
            return emission_rate[t]
        return (((t - 216) * p["epsilon_max"]) / (t - 216 + p["s"])) + emission_rate[216]

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

    def diff_C_at(t, state):
        """Time derivative of atmospheric carbon pool C_a."""
        return (
            epsilon(t) * (1 - state["x"])
            - P(state["C_at"], state["T"])
            + R_veg(state["C_v"], state["T"])
            + R_so(state["T"], state["C_so"])
            - F_oc(state["C_at"], state["C_oc"])
        )

    def diff_C_o(t, state):
        """Time derivative of ocean carbon pool C_oc (flux to/from atmosphere)."""
        return F_oc(state["C_at"], state["C_oc"])

    def diff_C_v(t, state):
        """Time derivative of vegetation carbon pool C_v."""
        return P(state["C_at"], state["T"]) - R_veg(state["C_v"], state["T"]) - L(state["C_v"])

    def diff_C_so(t, state):
        """Time derivative of soil organic carbon pool C_so."""
        return L(state["C_v"]) - R_so(state["T"], state["C_so"])

    def diff_T(t, state):
        """Time derivative of temperature anomaly T from radiative imbalance."""
        return (p["a_E"] / p["c"]) * (F_d(state["C_at"], state["T"]) - p["sigma"] * (state["T"] + p["T_0"]) ** 4) * 3.14 * 10**7

    def f_T(T):
        """Temperature-dependent benefit function for social dynamics."""
        return p["f_max"] / (1 + np.exp(-p["omega"] * (T - p["T_c"])))

    delay_history_times: list[float] = [0.0]
    delay_history_x: list[float] = [float(p["x0"])]

    def evaluate_delayed_x(query_time: float, current_time: float, current_x: float) -> float:
        """Get x(query_time) from stored history, with linear interpolation fallback."""
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

        return float(np.interp(query_time, delay_history_times, delay_history_x))

    def get_social_norm_term(state, t, frozen_agentic_term_observation_intention=None):
        match p["social_norm"]:
            case "Observation-based / imitation":
                # Baseline from Bury
                return p["delta"] * (2 * state["x"] - 1)
            case "Observation-based / intention motivation":
                # BI = agent based Behavioural Intention (Verhaltensabsicht) (from theory of planned behvaoiur)
                return frozen_agentic_term_observation_intention
            case "Belief-based / intention motivation":
                # here the norm is not based on behaviour, but eg as a static value (beckage)
                return p["N"]
            # case "Belief-based / approval":
            #     return 2 * p["sanction_term"]  # sanction term
            case "Observation based / approval (punish only one behaviour)":
                # Observation based / approval (in general) follows dynamics similar to Observation-based / imitation. however, here the agents pay-off is not determined by the observed majority, but by a distinct sanction term
                # approach 1: replicator equation with cost/reward is only applied to one behaviour (an agent not following the norm expects to be punished, while agents following the norm are not affected)
                #               equation was built by combining the model of sigdel et al. and bury et al. 
                # approach 2: replicator equation with punisher agents, who punish non-mitigators and the sanction depends on how many punishers exist (parameter z in the review). 
                #               In this case, the punishment is implemented by using a fixed proportion of cooperators as punishers and a fixed strength of the punishment. Combined they result in alpha * x.
                # This should have some different dynamics shouldnt it?
                return p["alpha"] * state["x"]     # one could add a factor for x at the end for sensitivity analysis, but it is not necessary for the dynamics to work
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
                return (state["x_p"] - state["x_ref"]) / (state["x_ref"] * p["tau_STref"])  # relative change in the social norm
            case "dynamic baseline":
                # dynamic social norm factors the baseline norm
                if abs(state["x_ref"]) < 1e-12:
                    trend = 0.0
                else:
                    trend = (state["x_p"] - state["x_ref"]) / (state["x_ref"] * p["tau_STref"])
                return (1 + trend) * p["delta"] * (2 * state["x"] - 1)
            case "Static injunctive":
                return p["c_inj"] * (p["x_target"] - state["x"])
            case "Descriptive, injunctive, dynamic":
                if abs(state["x_ref"]) < 1e-12:
                    dynamic_term = 0.0
                else:
                    dynamic_term = p["c_dyn"] * (state["x_p"] - state["x_ref"]) / (state["x_ref"] * p["tau_STref"])
                descriptive_term = p["delta"] * (2 * state["x"] - 1)
                injunctive_term = p["c_inj"] * (p["x_target"] - state["x"])
                return descriptive_term + injunctive_term + dynamic_term              
            case "dynamic social norm2":
                if p["theta"] <= 0:
                    return 0.0
                x_tau = evaluate_delayed_x(t - p["tau"], t, float(state["x"]))
                x_tau_theta = evaluate_delayed_x(t - p["tau"] - p["theta"], t, float(state["x"]))
                dynamic_term = (x_tau - x_tau_theta) / p["theta"]
                return p["c_dyn"] * dynamic_term
            case "Descriptive, injunctive, dynamic2":
                if p["theta"] <= 0:
                    dynamic_term = 0.0
                else:
                    x_tau = evaluate_delayed_x(t - p["tau"], t, float(state["x"]))
                    x_tau_theta = evaluate_delayed_x(t - p["tau"] - p["theta"], t, float(state["x"]))
                    dynamic_term = (x_tau - x_tau_theta) / p["theta"]
                descriptive_term = p["delta"] * (2 * state["x"] - 1)
                injunctive_term = p["c_inj"] * (p["x_target"] - state["x"])
                return descriptive_term + injunctive_term + p["c_dyn"] * dynamic_term
            case _:
                raise ValueError(f"Unknown social norm type: {p['social_norm']}")
               

    def diff_x(t, state, frozen_agentic_term_observation_intention=None):
        social_norm_term = get_social_norm_term(state, t, frozen_agentic_term_observation_intention)
        if t < 216:
            return 0
        if social_norm_term is None:
            return 0
        return p["kappa"] * state["x"] * (1 - state["x"]) * (-p["beta"] + p["temperature_factor"] * f_T(state["T"]) + p["social_norm_factor"] * social_norm_term)

    def diff_x_ref(t, state):
        if "tau_ref" not in p:
            return 0
        return (state["x_p"] - state["x_ref"]) / p["tau_ref"]
    
    def diff_x_p(t, state):
        if "tau_xp" not in p:
            return 0
        return (state["x"] - state["x_p"]) / p["tau_xp"]

    def make_model(frozen_agentic_term_observation_intention):
        """
        Create a pure solve_ivp right-hand-side function.

        The agent-derived social-norm term remains fixed
        during the current coupling interval.
        """

        def model(t, z):
            state = unpack_state(z)

            return np.array([
                0 if simulate_only_x else diff_C_at(t, state),
                0 if simulate_only_x else diff_C_o(t, state),
                0 if simulate_only_x else diff_C_v(t, state),
                0 if simulate_only_x else diff_C_so(t, state),
                0 if simulate_only_x else diff_T(t, state),
                diff_x(t, state, frozen_agentic_term_observation_intention),
                diff_x_p(t, state),
                diff_x_ref(t, state),
            ])

        return model

    initial_state = {"C_at": 0, "C_oc": 0, "C_v": 0, "C_so": 0, "T": 0, "x": p["x0"], "x_ref": p["x0"], "x_p": p["x0"]}
    z_current = np.array([initial_state[name] for name in STATE_NAMES])     # initialize the current state vector for the ODE solver
    time_breaks = _make_time_breaks(simulation_time=simulation_time, coupling_interval=coupling_interval)

    all_times = []
    all_states = []
    all_social_terms = []

    agent_times = []
    agent_shares = []
    agent_social_terms = []

    if use_agentic_norm:
        initial_agent_share = agent.mitigation_share(agents)

        initial_agent_social_term = agent.calculate_agent_social_norm_term(agents,p)

        agent_times.append(0.0)
        agent_shares.append(initial_agent_share)
        agent_social_terms.append(initial_agent_social_term)

    # -------------------------------------------------------------
    # Coupled simulation loop
    # -------------------------------------------------------------

    for interval_index, (t0, t1) in enumerate(zip(time_breaks[:-1], time_breaks[1:])):
        if use_agentic_norm:
                    frozen_agentic_term = agent.calculate_agent_social_norm_term(agents,p)
        else:
            frozen_agentic_term = None
        interval_length = t1 - t0
        n_output_points = max(2, int(round(interval_length * output_points_per_year)) + 1,)

        local_t_eval = np.linspace(t0, t1, n_output_points)

        interval_solution = solve_ivp(
            make_model(frozen_agentic_term),
            (t0, t1),
            z_current,
            method="BDF",
            t_eval=local_t_eval,
        )

        if not interval_solution.success:
            raise RuntimeError("ODE integration failed: " + interval_solution.message)

        interval_times = interval_solution.t
        interval_states = interval_solution.y

        # TODO: is this required? If so, why?
        # Remove duplicated boundary points between intervals.
        if interval_index > 0:
            interval_times = interval_times[1:]
            interval_states = interval_states[:, 1:]

        all_times.append(interval_times)
        all_states.append(interval_states)

        # Extend delay history after each solved interval.
        delay_history_times.extend(interval_times.tolist())
        delay_history_x.extend(interval_states[5, :].tolist())

        # Keep only the time window needed for delayed interpolation.
        if is_delay_dynamic_mode:
            cutoff_time = float(interval_times[-1]) - delay_window - max(float(coupling_interval), 1.0)
            if cutoff_time > delay_history_times[0]:
                keep_from = int(np.searchsorted(delay_history_times, cutoff_time, side="left"))
                keep_from = max(0, keep_from - 1)
                if keep_from > 0:
                    delay_history_times = delay_history_times[keep_from:]
                    delay_history_x = delay_history_x[keep_from:]

        if use_agentic_norm:
            all_social_terms.append(np.full(interval_times.shape, frozen_agentic_term, dtype=float))

        z_current = interval_solution.y[:, -1]
        final_state = unpack_state(z_current)

        # Agents update only after solve_ivp finishes.
        if use_agentic_norm:
            if t1 >= 216.0:
                agents = agent.update_agents(
                    agents=agents,
                    temperature=final_state["T"],
                    p=p,
                    f_T=f_T,
                    dt=interval_length,
                    rng=rng,
                )

            agent_times.append(float(t1))
            agent_shares.append(agent.mitigation_share(agents))
            agent_social_terms.append(agent.calculate_agent_social_norm_term(agents, p))

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
    if use_agentic_norm:
        social_norm_history = np.concatenate(all_social_terms)
    elif social_norm_mode in {"dynamic social norm2", "Descriptive, injunctive, dynamic2"}:
        x_series = simulation_states[5, :].astype(float)
        if theta_delay <= 0:
            trend_series = np.zeros_like(x_series)
        else:
            x_tau = np.interp(simulation_times - tau_delay, simulation_times, x_series, left=x_series[0], right=x_series[-1])
            x_tau_theta = np.interp(simulation_times - tau_delay - theta_delay, simulation_times, x_series, left=x_series[0], right=x_series[-1])
            trend_series = (x_tau - x_tau_theta) / theta_delay

        if social_norm_mode == "dynamic social norm2":
            social_norm_history = float(p["c_dyn"]) * trend_series
        else:
            descriptive_term = float(p["delta"]) * (2.0 * x_series - 1.0)
            injunctive_term = float(p["c_inj"]) * (float(p["x_target"]) - x_series)
            social_norm_history = descriptive_term + injunctive_term + float(p["c_dyn"]) * trend_series
    else:
        social_norm_history = np.asarray(
            [
                get_social_norm_term(
                    unpack_state(simulation_states[:, i]),
                    float(simulation_times[i]),
                    None,
                )
                for i in range(simulation_states.shape[1])
            ],
            dtype=float,
        )

    result = {
        "simulation": simulation,
        "social_norm_term": social_norm_history,
    }

    if use_agentic_norm:
        result["agents"] = agents
        result["agent_history"] = {
            "t": np.asarray(agent_times, dtype=float),
            "mitigation_share": np.asarray(agent_shares, dtype=float),
            "social_norm_term": np.asarray(agent_social_terms, dtype=float)
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

