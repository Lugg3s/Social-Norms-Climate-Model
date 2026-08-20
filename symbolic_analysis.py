"""Symbolic equilibrium, stability, and bifurcation analysis for social norms.

The analysis deliberately treats temperature and model parameters as symbols.
It works on the behavioural equation already used by ``model_equations.py``
and does not substitute values from ``scenarios.json`` into the returned
expressions.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import sympy as sp

from model_equations import load_scenarios


T = sp.Symbol("T", real=True)
x = sp.Symbol("x", real=True)
x_p = sp.Symbol("x_p", real=True)
x_ref = sp.Symbol("x_ref", real=True)

SUPPORTED_NORMS = (
    "Observation-based / imitation",
    "Observation-based / intention motivation",
    "Belief-based / intention motivation",
    "Observation based / approval (punish only one behaviour)",
    "dynamic social norm",
    "dynamic baseline",
    "Static injunctive",
    "Descriptive, injunctive, dynamic",
    "dynamic social norm2",
    "Descriptive, injunctive, dynamic2",
)

ABM_NORMS = {"Observation-based / intention motivation"}


@dataclass(frozen=True)
class Equilibrium:
    """One symbolic equilibrium and its local stability information."""

    value: sp.Expr
    stability: str
    eigenvalues: tuple[sp.Expr, ...] = ()


@dataclass(frozen=True)
class SocialNormAnalysis:
    """Symbolic analysis result for one social norm."""

    name: str
    variables: tuple[sp.Symbol, ...]
    social_norm_term: sp.Expr | None
    behavioural_bracket: sp.Expr | None
    equilibria: tuple[Equilibrium, ...]
    bifurcation_conditions: tuple[sp.Expr, ...]
    bifurcation_equations: tuple[sp.Expr, ...]
    status: str = "ok"
    note: str | None = None


def _symbols_for_parameters(parameter_names: set[str]) -> dict[str, sp.Symbol]:
    return {
        name: sp.Symbol(name, real=True)
        for name in sorted(parameter_names)
    }


def _parameter_names_for_norm(norm: str) -> set[str]:
    common = {"beta", "temperature_factor", "f_max", "omega", "T_c", "social_norm_factor"}
    by_norm = {
        "Observation-based / imitation": {"delta"},
        "Observation-based / intention motivation": set(),
        "Belief-based / intention motivation": {"N"},
        "Observation based / approval (punish only one behaviour)": {"alpha"},
        "dynamic social norm": {"tau_STref", "tau_ref", "tau_xp"},
        "dynamic baseline": {"delta", "tau_STref", "tau_ref", "tau_xp"},
        "Static injunctive": {"c_inj", "x_target"},
        "Descriptive, injunctive, dynamic": {
            "delta", "c_inj", "x_target", "c_dyn", "tau_STref", "tau_ref", "tau_xp"
        },
        "dynamic social norm2": {"c_dyn", "tau", "theta"},
        "Descriptive, injunctive, dynamic2": {
            "delta", "c_inj", "x_target", "c_dyn", "tau", "theta"
        },
    }
    return common | by_norm.get(norm, set())


def _temperature_term(s: dict[str, sp.Symbol]) -> sp.Expr:
    return s["temperature_factor"] * s["f_max"] / (
        1 + sp.exp(-s["omega"] * (T - s["T_c"]))
    )


def _social_norm_term(norm: str, s: dict[str, sp.Symbol]) -> sp.Expr:
    if norm == "Observation-based / imitation":
        return s["delta"] * (2 * x - 1)
    if norm == "Belief-based / intention motivation":
        return s["N"]
    if norm == "Observation based / approval (punish only one behaviour)":
        return s["alpha"] * x
    if norm == "Static injunctive":
        return s["c_inj"] * (s["x_target"] - x)
    if norm == "dynamic social norm":
        return (x_p - x_ref) / (x_ref * s["tau_STref"])
    if norm == "dynamic baseline":
        trend = (x_p - x_ref) / (x_ref * s["tau_STref"])
        return (1 + trend) * s["delta"] * (2 * x - 1)
    if norm == "Descriptive, injunctive, dynamic":
        dynamic = s["c_dyn"] * (x_p - x_ref) / (x_ref * s["tau_STref"])
        return (
            s["delta"] * (2 * x - 1)
            + s["c_inj"] * (s["x_target"] - x)
            + dynamic
        )
    if norm in {"dynamic social norm2", "Descriptive, injunctive, dynamic2"}:
        # At a stationary solution x(t-delay) == x(t), so the finite-difference
        # dynamic term is exactly zero. The delays therefore disappear from the
        # equilibrium equations, while they still matter for stability of the
        # delay differential equation.
        if norm == "dynamic social norm2":
            return sp.Integer(0)
        return s["delta"] * (2 * x - 1) + s["c_inj"] * (s["x_target"] - x)
    raise ValueError(f"Unsupported social norm: {norm}")


def _equilibrium_social_term(norm: str, s: dict[str, sp.Symbol]) -> sp.Expr:
    term = _social_norm_term(norm, s)
    if norm in {
        "dynamic social norm",
        "dynamic baseline",
        "Descriptive, injunctive, dynamic",
    }:
        term = sp.simplify(term.subs({x_p: x, x_ref: x}))
    return sp.simplify(term)


def _bracket(norm: str, s: dict[str, sp.Symbol]) -> sp.Expr:
    return sp.simplify(-s["beta"] + _temperature_term(s) + s["social_norm_factor"] * _equilibrium_social_term(norm, s))


def _classify_1d(value: sp.Expr, bracket: sp.Expr) -> str:
    derivative = sp.simplify(x * (1 - x) * sp.diff(bracket, x))
    # The derivative of x(1-x) * bracket at x=0/1 is determined by the
    # bracket evaluated at the boundary. We retain a symbolic sign test,
    # because no parameter values are substituted.
    local = sp.simplify(derivative.subs(x, value))
    if local == 0:
        return "nonhyperbolic"
    return "stable if expression < 0; unstable if expression > 0"


def _equilibria_1d(bracket: sp.Expr) -> tuple[Equilibrium, ...]:
    result: list[Equilibrium] = [
        Equilibrium(sp.Integer(0), _classify_1d(sp.Integer(0), bracket)),
        Equilibrium(sp.Integer(1), _classify_1d(sp.Integer(1), bracket)),
    ]
    internal = sp.solve(sp.Eq(bracket, 0), x)
    for value in internal:
        if value not in {0, 1}:
            result.append(Equilibrium(sp.factor(value), _classify_1d(value, bracket)))
    return tuple(result)


def _equilibria_dynamic(norm: str, s: dict[str, sp.Symbol], bracket: sp.Expr) -> tuple[Equilibrium, ...]:
    # At equilibrium x_p=x_ref=x. The full Jacobian is retained so stability
    # is not inferred from the reduced scalar equation alone.
    g = x * (1 - x) * bracket
    if norm in {"dynamic social norm2", "Descriptive, injunctive, dynamic2"}:
        # A delay equation requires a characteristic equation for stability;
        # the equilibrium itself is still exactly determined by the reduced g.
        return tuple(
            Equilibrium(v, "delay-system stability requires characteristic roots")
            for v in _equilibria_1d(bracket)
        )

    tau_xp = s.get("tau_xp", sp.Symbol("tau_xp", real=True))
    tau_ref = s.get("tau_ref", sp.Symbol("tau_ref", real=True))
    full = sp.Matrix([
        g,
        (x - x_p) / tau_xp,
        (x_p - x_ref) / tau_ref,
    ])
    J = full.jacobian([x, x_p, x_ref])
    result = []
    for eq in _equilibria_1d(bracket):
        point = {x: eq.value, x_p: eq.value, x_ref: eq.value}
        eigenvalues = tuple(sp.simplify(v) for v in J.subs(point).eigenvals().keys())
        result.append(Equilibrium(eq.value, "stable if all eigenvalue real parts < 0; unstable if any > 0", eigenvalues))
    return tuple(result)


def _bifurcation_conditions(bracket: sp.Expr, parameter: sp.Symbol) -> tuple[sp.Expr, ...]:
    """Return symbolic boundary and interior bifurcation conditions.

    The bounded state x in [0, 1] means equilibria can exchange stability at
    x=0 or x=1. Interior saddle-node candidates satisfy g=0 and dg/dx=0.
    """
    g = sp.simplify(x * (1 - x) * bracket)
    conditions: list[sp.Expr] = []
    for boundary in (sp.Integer(0), sp.Integer(1)):
        condition = sp.factor(bracket.subs(x, boundary))
        if condition != 0 and parameter in condition.free_symbols:
            conditions.append(sp.Eq(condition, 0))
    dg = sp.diff(g, x)
    # Keep the equations symbolic rather than forcing a potentially enormous
    # solve over the transcendental temperature term.
    if sp.simplify(bracket.diff(x)) != 0:
        conditions.append(sp.Eq(bracket, 0))
        conditions.append(sp.Eq(sp.diff(bracket, x), 0))
    return tuple(conditions)


def analyze_social_norm(norm: str, bifurcation_parameter: str = "beta") -> SocialNormAnalysis:
    """Analyze one implemented social norm symbolically.

    Parameters are never replaced by values from ``scenarios.json``.
    ``T`` is always the symbolic temperature parameter.
    """
    if norm not in SUPPORTED_NORMS:
        raise ValueError(f"Unsupported social norm: {norm}")
    if norm in ABM_NORMS:
        return SocialNormAnalysis(
            name=norm,
            variables=(x,),
            social_norm_term=None,
            behavioural_bracket=None,
            equilibria=(),
            bifurcation_conditions=(),
            bifurcation_equations=(),
            status="unsupported",
            note="The agent-based social-norm term is stochastic and is not a deterministic symbolic function of x.",
        )

    names = _parameter_names_for_norm(norm)
    names.add(bifurcation_parameter)
    s = _symbols_for_parameters(names)
    if bifurcation_parameter not in s:
        raise ValueError(f"Unknown bifurcation parameter: {bifurcation_parameter}")

    bracket = _bracket(norm, s)
    term = _equilibrium_social_term(norm, s)
    dynamic = norm in {
        "dynamic social norm", "dynamic baseline", "Descriptive, injunctive, dynamic",
        "dynamic social norm2", "Descriptive, injunctive, dynamic2",
    }
    variables = (x, x_p, x_ref) if dynamic else (x,)
    equilibria = _equilibria_dynamic(norm, s, bracket) if dynamic else _equilibria_1d(bracket)
    bifurcations = _bifurcation_conditions(bracket, s[bifurcation_parameter])
    return SocialNormAnalysis(
        name=norm,
        variables=variables,
        social_norm_term=term,
        behavioural_bracket=bracket,
        equilibria=equilibria,
        bifurcation_conditions=bifurcations,
        bifurcation_equations=bifurcations,
    )


def analyze_all_social_norms(bifurcation_parameter: str = "beta") -> dict[str, SocialNormAnalysis]:
    """Analyze every social norm currently represented in scenarios.json."""
    scenarios = load_scenarios()
    norms = []
    for params in scenarios.values():
        norm = params.get("social_norm")
        if norm and norm not in norms:
            norms.append(norm)
    return {norm: analyze_social_norm(norm, bifurcation_parameter) for norm in norms}
