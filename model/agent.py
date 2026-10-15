"""Annual, reversible decisions from behavioural intentions and observed behaviour."""
from dataclasses import dataclass

import numpy as np


# Schwarz et al. (2025), InSEEDS, Eq. (2) and Table 1 (preprint):
# https://doi.org/10.5194/egusphere-2025-4079
# Norm/attitude weight ratios are 0.2/0.8 = 0.25 and 0.4/0.6 = 2/3.
# With an attitude coefficient of one, 0.5 is an illustrative intermediate
# relative norm weight, not an empirical calibration of this climate model.
# eta, phi and psi are set explicitly in scenarios.json.


@dataclass
class Agent:
    """An agent with fixed costs/peers, continuous intention and binary behaviour.

    behavioral_intention stores the continuous BI_i score unchanged.
    actual_behavior stores only the binary outcome of the threshold decision.
    Intention fields describe the last evaluation, before simultaneous switching.
    """

    agent_id: int
    actual_behavior: int
    peers: np.ndarray
    beta: float
    behavioral_intention: float = float("nan")
    non_social_intention: float = float("nan")
    peer_norm: float = float("nan")
    norm_contribution: float = 0.0


def initialize_agents(n_agents, initial_mitigation_share, rng,
                      network_size, beta):
    """Draw costs and peer networks once; prescribe the initial actual share."""
    if not isinstance(n_agents, (int, np.integer)) or n_agents < 1:
        raise ValueError("n_agents must be a positive integer")
    if not 0.0 <= initial_mitigation_share <= 1.0:
        raise ValueError("initial_mitigation_share must be between 0 and 1")
    if not np.isfinite(beta) or beta < 0:
        raise ValueError("beta must be finite and nonnegative")
    if network_size is not None:
        if (not np.isfinite(network_size) or int(network_size) != network_size
                or not 0 <= network_size < n_agents):
            raise ValueError("network_size must be an integer between 0 and n_agents - 1")
        network_size = int(network_size)

    actual_behaviors = np.zeros(n_agents, dtype=int)
    actual_behaviors[:round(initial_mitigation_share * n_agents)] = 1
    rng.shuffle(actual_behaviors)

    # beta_i ist gleichverteilt zwischen 0 und 2*beta, mit erwartetem Mittelwert beta.
    costs = 2.0 * beta * rng.uniform(0.0, 1.0, n_agents)
    all_agent_ids = np.arange(n_agents)
    agents = []
    for agent_id in range(n_agents):
        possible_peers = all_agent_ids[all_agent_ids != agent_id]
        peer_ids = (possible_peers.copy() if network_size is None else
                    rng.choice(possible_peers, size=network_size, replace=False))
        agents.append(Agent(agent_id=agent_id,
                            actual_behavior=int(actual_behaviors[agent_id]),
                            peers=np.asarray(peer_ids, dtype=int), beta=float(costs[agent_id])))
    return agents


def actual_behaviors_array(agents):
    """Return binary actual behaviour in agent-ID order."""
    return np.asarray([individual.actual_behavior for individual in agents], dtype=int)


def mitigation_share(agents):
    if not agents:
        raise ValueError("The agent list cannot be empty")
    return float(actual_behaviors_array(agents).mean())


def calculate_peer_norms(agents):
    """Observed actual behaviour NB/N; an empty neighbourhood contributes zero."""
    actual_behaviors = actual_behaviors_array(agents)
    return np.asarray([actual_behaviors[individual.peers].mean()
                       if len(individual.peers) else 0.0
                       for individual in agents], dtype=float)


def evaluate_intentions(agents, temperature, p, f_T):
    """Evaluate BI_i from the old behaviour without changing actual behaviour.

    Prawitz et al. (2026), section 4.3, thresholded observation-based intention:
    https://doi.org/10.1088/1748-9326/ae3b55
    Our climate extension is A_i(t) = -beta_i + temperature_factor*f_T(T).
    In the review's notation the weight/activation threshold are omega/tau;
    here they are eta/phi, to avoid the existing temperature/delay parameters.
    BI_i = A_i + eta*q_i if q_i >= phi, otherwise BI_i = A_i.
    BI is a net score; it is not a probability and is not clipped to [0,1].
    """
    peer_norms = calculate_peer_norms(agents)  # q_i = NB/N: tatsächliches Verhalten der Nachbarn.
    climate_benefit = float(p["temperature_factor"] * f_T(temperature))  # Temperaturanteil von A_i.
    # Normbeitrag: eta*q_i ab q_i >= phi, sonst 0.
    norm_terms = np.where(peer_norms >= p["phi"], p["eta"] * peer_norms, 0.0)
    intentions = np.empty(len(agents), dtype=float)
    for i, individual in enumerate(agents):
        individual.peer_norm = float(peer_norms[i])
        individual.non_social_intention = climate_benefit - individual.beta  # A_i = Temperaturanteil - beta_i.
        individual.norm_contribution = float(norm_terms[i])
        # BI_i = A_i + Normbeitrag; bleibt kontinuierlich.
        individual.behavioral_intention = individual.non_social_intention + individual.norm_contribution
        intentions[i] = individual.behavioral_intention
    return intentions


def mean_norm_contribution(agents):
    """Mean of the already weighted norm contributions at the last evaluation."""
    return float(np.mean([individual.norm_contribution for individual in agents]))


def update_agents(agents, temperature, p, f_T):
    """Threshold BI into actual behaviour, preserving the continuous BI score.

    E.g. BI=0.6 and threshold=0.5 gives actual_behavior=1 and keeps BI=0.6.
    Decisions are simultaneous and reversible.
    """
    intentions = evaluate_intentions(agents, temperature, p, f_T)
    new_actual_behaviors = (intentions >= p["psi"]).astype(int)  # Verhalten = 1 ab BI_i >= psi; BI_i bleibt erhalten.
    for individual, new_actual_behavior in zip(agents, new_actual_behaviors):
        individual.actual_behavior = int(new_actual_behavior)
    return agents
