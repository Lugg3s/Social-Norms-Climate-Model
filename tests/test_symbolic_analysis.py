import sympy as sp

from symbolic_analysis import (
    T,
    analyze_all_social_norms,
    analyze_social_norm,
)


def test_imitation_equilibria_are_symbolic():
    result = analyze_social_norm("Observation-based / imitation")

    assert len(result.equilibria) == 3
    assert result.equilibria[0].value == 0
    assert result.equilibria[1].value == 1
    assert T in result.equilibria[2].value.free_symbols
    assert result.equilibria[2].value.has(sp.Symbol("beta", real=True))

    # No numeric scenario value is substituted into the expression.
    assert result.behavioural_bracket.has(sp.Symbol("delta", real=True))
    assert result.behavioural_bracket.has(sp.Symbol("f_max", real=True))


def test_imitation_boundary_bifurcations_are_symbolic():
    result = analyze_social_norm("Observation-based / imitation", bifurcation_parameter="beta")
    equations = {str(eq) for eq in result.bifurcation_conditions}

    assert any("beta" in eq and "temperature_factor" in eq for eq in equations)
    assert len(result.bifurcation_conditions) == 2


def test_dynamic_equilibrium_sets_xp_and_xref_equal_to_x():
    result = analyze_social_norm("dynamic baseline")

    assert result.variables
    assert result.social_norm_term == 2 * sp.Symbol("delta", real=True) * sp.Symbol("x", real=True) - sp.Symbol("delta", real=True)
    assert all(eq.value.has(T) or eq.value in {0, 1} for eq in result.equilibria)
    assert all(eq.eigenvalues or eq.value in {0, 1} for eq in result.equilibria)


def test_delay_norm_has_equilibria_but_does_not_fake_ode_stability():
    result = analyze_social_norm("dynamic social norm2")

    assert result.social_norm_term == 0
    assert result.equilibria
    assert all("delay-system" in eq.stability for eq in result.equilibria)


def test_agent_based_norm_is_explicitly_unsupported_symbolically():
    result = analyze_social_norm("Observation-based / intention motivation")

    assert result.status == "unsupported"
    assert result.equilibria == ()


def test_all_configured_norms_are_discovered():
    results = analyze_all_social_norms()

    assert "Observation-based / imitation" in results
    assert "Static injunctive" in results
    assert "dynamic social norm2" in results
