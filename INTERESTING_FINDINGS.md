# Interesting Findings

# Die Formel von Observation based / approval ist ein specialcase von static injunctive mit x_target = 1

# Analyse der Ergebnisse der  Sensitivitätsanalyse
- Das Agentenmodell wurde nicht betrachtet
- x_target ist besonders einflussreich bei den injunctive modellen
- "Seltene Oszillationen verursachen unzuverlässige Unsicherheitsschätzungen. Deshalb sollte das bisherige Mittel über alle sieben Zielgrößen nicht als zentrale Parameterrangfolge verwendet werden." ???
- Der Mitigationsanteil am letzten Zeitpunkt kann stark von der Schwingungsphase abhängen
- "„Elimination“ muss genauer definiert werden: Erstes Überschreiten von 95 %, Zustand am Ende und dauerhaftes Erreichen sind unterschiedliche Fragen"


This document collects potentially interesting findings from the social-norm climate model. It is intended as a living document and should be extended or revised as additional simulations and analyses are completed.

> **Status:** Preliminary. The findings below are primarily analytical consequences of the currently implemented model equations and parameterization. They should be verified and quantified with systematic simulation experiments before being reported as empirical simulation results.

## 1. Descriptive imitation creates a majority threshold at x = 0.5

For the observation-based imitation norm, the social-norm term is

```text
N_desc = 2x - 1.
```

The term changes sign at `x = 0.5`. Below 50% mitigation, the norm discourages mitigation; above 50%, it encourages mitigation. Thus, descriptive imitation introduces self-reinforcing majority dynamics and can potentially generate lock-in or tipping behaviour.

With the current baseline `x0 = 0.3` and `social_norm_factor = 1`, the initial norm term and its weighted contribution are both `-0.4`, i.e. initially anti-mitigation. The behavioural equation weights the norm term with `social_norm_factor`.

## 2. Approval and descriptive imitation can point in opposite directions

The implemented approval norm uses

```text
N_approval = x; weighted contribution = social_norm_factor * x.
```

This term is non-negative for all feasible `x`. At the current baseline (`x0 = 0.3`, `social_norm_factor = 1`) both the term and its weighted contribution equal `0.3`, whereas descriptive imitation equals `-0.4`.

Consequently, two observation-based norms can predict opposite social pressure from exactly the same behavioural state. This is a structurally important difference between the norm formulations rather than merely a difference in parameter magnitude.

## 3. Injunctive norms act as restoring feedback toward a target

The static injunctive norm is

```text
N_inj = c_inj * (x_target - x).
```

For the current `x_target = 0.7`, the norm promotes mitigation below 0.7 and opposes further increases above 0.7. This differs fundamentally from descriptive imitation: the injunctive norm provides restoring feedback toward a target, while descriptive imitation reinforces whichever behaviour is already in the majority.

## 4. The combined descriptive-injunctive model has a critical initial boundary at c_inj = 1

Ignoring the dynamic component at initialization, where `x = x_p = x_ref`, the combined norm is

```text
N = (2x - 1) + c_inj * (0.7 - x).
```

At the current `x0 = 0.3`,

```text
N(x0) = -0.4 + 0.4*c_inj
      = 0.4*(c_inj - 1).
```

Therefore:

- `c_inj < 1`: initial social pressure is anti-mitigation;
- `c_inj = 1`: descriptive and injunctive components exactly cancel initially;
- `c_inj > 1`: initial social pressure is pro-mitigation.

This suggests that the neighbourhood around `c_inj = 1` deserves targeted simulation analysis.

## 5. The combined descriptive-injunctive feedback changes character at c_inj = 2

Again excluding the dynamic component,

```text
N(x) = (2 - c_inj)*x + 0.7*c_inj - 1.
```

Hence

```text
dN/dx = 2 - c_inj.
```

This gives a structural boundary at `c_inj = 2`:

- `c_inj < 2`: the norm term increases with mitigation, giving reinforcing feedback;
- `c_inj = 2`: the static combined norm becomes independent of `x` (`N = 0.4` for `x_target = 0.7`);
- `c_inj > 2`: the norm term decreases with mitigation, giving restoring feedback.

The transition around `c_inj = 2` may therefore separate qualitatively different dynamical regimes.

## 6. Dynamic norms are primarily transient mechanisms

For the ODE-based dynamic norm, the trend component depends on the difference between perceived current behaviour (`x_p`) and the slower reference (`x_ref`). At a stationary state with `x = x_p = x_ref`, this component vanishes.

The delay-based dynamic formulation similarly measures recent behavioural change. Its contribution also vanishes when behaviour becomes constant.

Therefore, dynamic norms should not be evaluated primarily through `final_x`. Their distinctive effects are more likely to appear in transition timing, acceleration, overshoot, oscillations, damping, and whether a trajectory crosses a behavioural threshold.

## 7. Timing can matter even when final behavioural states are similar

Because mitigation behaviour feeds back into emissions and therefore temperature, two norm formulations can have similar final `x` while producing different climate outcomes if mitigation occurs at different times. This makes trajectory-level measures such as `x_area`, threshold-crossing times, and temperature area potentially more informative than final-state comparisons alone.

## Findings to verify next

The following points should be tested explicitly in simulation output:

- whether `c_inj = 1` corresponds to a visible transition in trajectories or long-run outcomes;
- whether the feedback change around `c_inj = 2` creates a regime boundary;
- whether dynamic norms generate overshoot or oscillatory behaviour absent from static formulations;
- whether different norms produce substantially different climate outcomes despite similar `final_x`;
- whether the descriptive `x = 0.5` threshold produces tipping or path dependence in the coupled model.










- Wenn der social norm term klein ist, entsteht (fast?) immer durch die Temperaturfunktion gedämpfte Oszillation. Umso kleiner also Faktoren im social_norm_term sind, umso stärker ist die Oszillation (außer bei dynamischen Normen. Dort entstehen Oszillationen auch durch die Norm)
