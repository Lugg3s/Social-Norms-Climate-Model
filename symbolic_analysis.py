"""Symbolic equilibrium, stability, and bifurcation analysis for social norms.

The analysis deliberately treats temperature and model parameters as symbols.
It works on the behavioural equation already used by ``model_equations.py``
and does not substitute values from ``scenarios.json`` into the returned
expressions.
"""

from __future__ import annotations

from dataclasses import dataclass

import sympy as sp

from model_equations import load_scenarios


T = sp.Symbol("T", real=True)
x = sp.Symbol("x", real=True)
x_p = sp.Symbol("x_p", real=True)
x_ref = sp.Symbol("x_ref", real=True)
x_tau = sp.Symbol("x_tau", real=True)
x_tau_theta = sp.Symbol("x_tau_theta", real=True)

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
    "Injunctive, dynamic2",
)

ABM_NORMS = {"Observation-based / intention motivation"}
DYNAMIC_ODE_NORMS = {
    "dynamic social norm",
    "dynamic baseline",
    "Descriptive, injunctive, dynamic",
}
DELAY_NORMS = {
    "dynamic social norm2",
    "Descriptive, injunctive, dynamic2",
    "Injunctive, dynamic2",
}


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
    return {name: sp.Symbol(name, real=True) for name in sorted(parameter_names)}


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
        "Injunctive, dynamic2": {"c_inj", "x_target", "c_dyn", "tau", "theta"},
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
    if norm == "dynamic social norm2":
        return s["c_dyn"] * (x_tau - x_tau_theta) / s["theta"]
    if norm == "Descriptive, injunctive, dynamic2":
        return (
            s["delta"] * (2 * x - 1)
            + s["c_inj"] * (s["x_target"] - x)
            + s["c_dyn"] * (x_tau - x_tau_theta) / s["theta"]
        )
    if norm == "Injunctive, dynamic2":
        return (
            s["c_inj"] * (s["x_target"] - x)
            + s["c_dyn"] * (x_tau - x_tau_theta) / s["theta"]
        )
    raise ValueError(f"Unsupported social norm: {norm}")


def _equilibrium_social_term(norm: str, s: dict[str, sp.Symbol]) -> sp.Expr:
    term = _social_norm_term(norm, s)
    if norm in DYNAMIC_ODE_NORMS:
        term = sp.simplify(term.subs({x_p: x, x_ref: x}))
    if norm in DELAY_NORMS:
        term = sp.simplify(term.subs({x_tau: x, x_tau_theta: x}))
    return sp.simplify(term)


def symbolic_social_norm_term(norm: str) -> sp.Expr | None:
    """Return the social-norm term with symbolic variables and parameters."""
    if norm not in SUPPORTED_NORMS:
        raise ValueError(f"Unsupported social norm: {norm}")
    if norm in ABM_NORMS:
        return None
    symbols = _symbols_for_parameters(_parameter_names_for_norm(norm))
    return _social_norm_term(norm, symbols)


def _bracket(norm: str, s: dict[str, sp.Symbol], equilibrium: bool = True) -> sp.Expr:
    term = _equilibrium_social_term(norm, s) if equilibrium else _social_norm_term(norm, s)
    return sp.simplify(
        -s["beta"] + _temperature_term(s) + s["social_norm_factor"] * term
    )


def _classify_1d(value: sp.Expr, bracket: sp.Expr) -> str:
    g = x * (1 - x) * bracket
    local = sp.simplify(sp.diff(g, x).subs(x, value))
    if local == 0:
        return "nonhyperbolic"
    return f"stable if {local} < 0; unstable if {local} > 0"


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
    reduced_equilibria = _equilibria_1d(bracket)
    if norm in DELAY_NORMS:
        return tuple(
            Equilibrium(
                eq.value,
                "not classified symbolically: delay-system characteristic roots required",
            )
            for eq in reduced_equilibria
        )

    full_bracket = _bracket(norm, s, equilibrium=False)
    g = x * (1 - x) * full_bracket
    tau_xp = s["tau_xp"]
    tau_ref = s["tau_ref"]
    full = sp.Matrix([
        g,
        (x - x_p) / tau_xp,
        (x_p - x_ref) / tau_ref,
    ])
    jacobian = full.jacobian([x, x_p, x_ref])

    result = []
    for eq in reduced_equilibria:
        if eq.value == 0:
            # The implemented numerical model explicitly special-cases x_ref=0
            # in the dynamic norm term. Its local derivative is therefore not
            # represented by the ordinary symbolic expression containing 1/x_ref.
            result.append(Equilibrium(eq.value, "boundary stability depends on x_ref=0 special case"))
            continue
        point = {x: eq.value, x_p: eq.value, x_ref: eq.value}
        eigenvalues = tuple(sp.simplify(v) for v in jacobian.subs(point).eigenvals().keys())
        result.append(
            Equilibrium(
                eq.value,
                "stable if all eigenvalue real parts < 0; unstable if any > 0",
                eigenvalues,
            )
        )
    return tuple(result)


def _bifurcation_conditions(bracket: sp.Expr, parameter: sp.Symbol) -> tuple[sp.Expr, ...]:
    """Return symbolic boundary and interior bifurcation conditions.

    Because x is bounded to [0, 1], boundary equilibria can change stability
    when the interior equilibrium reaches x=0 or x=1. Interior saddle-node
    candidates satisfy g=0 and dg/dx=0 with 0 < x < 1.
    """
    conditions: list[sp.Expr] = []
    for boundary in (sp.Integer(0), sp.Integer(1)):
        condition = sp.factor(bracket.subs(x, boundary))
        if condition != 0 and parameter in condition.free_symbols:
            solutions = sp.solve(sp.Eq(condition, 0), parameter)
            conditions.extend(sp.Eq(parameter, value) for value in solutions)

    if sp.simplify(sp.diff(bracket, x)) != 0:
        conditions.extend((sp.Eq(bracket, 0), sp.Eq(sp.diff(bracket, x), 0)))
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
    bracket = _bracket(norm, s)
    term = _equilibrium_social_term(norm, s)
    dynamic = norm in DYNAMIC_ODE_NORMS or norm in DELAY_NORMS
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
