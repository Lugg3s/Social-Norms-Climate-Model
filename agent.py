from dataclasses import dataclass

import numpy as np


@dataclass
class Agent:
    """
    One agent in the social-norm layer.
    strategy:
        0 = non-mitigator
        1 = mitigator
    peers:
        NumPy array containing peer agent IDs.
    susceptibility:
        Responsiveness to peer influence.
    """

    agent_id: int
    strategy: int
    peers: np.ndarray
    susceptibility: float = 1.0


def initialize_agents(
    n_agents,
    initial_mitigation_share,
    rng,
    network_size=None,
    susceptibility=1.0, # Maß dafür, wie stark ein Agent auf den sozialen Einfluss seiner Peers reagiert
):
    """
    Create agents and their peer networks.
    network_size=None:
        Every agent observes every other agent.
    network_size=10:
        Every agent receives ten randomly selected peers.
    """
    if not 0.0 <= initial_mitigation_share <= 1.0:
        raise ValueError("initial_mitigation_share must be between 0 and 1")

    strategies = np.zeros(n_agents, dtype=int)
    n_mitigators = round(initial_mitigation_share * n_agents)
    strategies[:n_mitigators] = 1
    rng.shuffle(strategies)
    all_agent_ids = np.arange(n_agents)
    agents = []

    for agent_id in range(n_agents):
        possible_peers = all_agent_ids[all_agent_ids != agent_id]
        if network_size is None:
            peer_ids = possible_peers.copy()
        else:
            peer_ids = rng.choice(possible_peers, size=network_size, replace=False)
        agents.append(
            Agent(
                agent_id=agent_id,
                strategy=int(strategies[agent_id]),
                peers=np.asarray(peer_ids, dtype=int),
                susceptibility=float(susceptibility),
            )
        )
    return agents


def strategies_array(agents):
    """
    Return agent strategies as a NumPy array.
    """

    return np.asarray([agent.strategy for agent in agents], dtype=float)


def mitigation_share(agents):
    """
    Calculate the fraction of agents that are mitigators.
    """

    if not agents:
        raise ValueError("The agent list cannot be empty")
    return float(strategies_array(agents).mean())


def calculate_peer_norms(agents):
    """
    Calculate each agent's perceived peer norm.
    The peer norm is the average mitigation strategy
    among that agent's peers.
    """

    strategies = strategies_array(agents)
    peer_norms = np.empty(len(agents), dtype=float)

    for i, agent in enumerate(agents):
        if len(agent.peers) == 0:
            peer_norms[i] = strategies[i]
        else:
            peer_norms[i] = strategies[agent.peers].mean()
    return peer_norms


def calculate_agent_social_norm_term(agents, p):
    """
    Calculate the aggregate social-norm term.
    Each agent contributes:
        delta * susceptibility * (2 * peer_norm - 1)
    The aggregate is the mean across all agents.
    """

    peer_norms = calculate_peer_norms(agents)
    susceptibilities = np.asarray([agent.susceptibility for agent in agents], dtype=float)
    individual_terms = (p["delta"] * susceptibilities * (2.0 * peer_norms - 1.0))           # TODO Warum Delta * 2 * norm - 1 ??? DAs ist doch die Bury Norm mit peer_norms statt x???
    return float(individual_terms.mean())


def update_agents(agents, temperature, p, f_T, dt, rng):
    """
    Update all agent strategies simultaneously.
    Agent decisions use:
        Bury's non-social utility difference
        plus the agent-specific social-norm term.
    All agents update from the old state at the same time.
    """

    if dt <= 0:
        raise ValueError("dt must be positive")

    peer_norms = calculate_peer_norms(agents)
    susceptibilities = np.asarray([agent.susceptibility for agent in agents], dtype=float)
    baseline_difference = -p["beta"] + (f_T(temperature) * p["temperature_factor"])
    social_terms = p["delta"] * susceptibilities * (2.0 * peer_norms - 1.0) * p["social_norm_factor"]           # TODO Warum Delta * 2 * norm - 1 ??? DAs ist doch die Bury Norm mit peer_norms statt x???
    utility_difference = (baseline_difference + social_terms)
    update_rate = p.get("agent_update_rate", p["kappa"])
    probability_to_mitigate = (1.0 - np.exp(-update_rate * np.maximum(utility_difference, 0.0) * dt))
    probability_to_stop_mitigating = (1.0 - np.exp(-update_rate * np.maximum(-utility_difference, 0.0) * dt))
    old_strategies = strategies_array(agents).astype(int)
    new_strategies = old_strategies.copy()
    random_draws = rng.random(len(agents))
    non_mitigators = old_strategies == 0
    mitigators = old_strategies == 1
    become_mitigators = (non_mitigators & (random_draws < probability_to_mitigate))
    stop_mitigating = (mitigators & (random_draws < probability_to_stop_mitigating))
    new_strategies[become_mitigators] = 1
    new_strategies[stop_mitigating] = 0

    for agent, new_strategy in zip(agents, new_strategies):
        agent.strategy = int(new_strategy)

    return agents
