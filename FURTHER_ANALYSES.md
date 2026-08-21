# Further Analyses and Research Questions

This document collects candidate analyses that may reveal scientifically interesting differences between the implemented social-norm formulations. It is intended as a living backlog rather than a fixed analysis plan.

A useful general principle is to search for **qualitative differences and regime changes**, not only large differences in final values.

## 1. Behavioural regime classification

**Research question:** Under which parameter combinations do alternative social-norm formulations produce qualitatively different behavioural regimes?

Classify each simulation into dynamical regimes, for example:

- collapse / convergence toward `x = 0`;
- low-mitigation equilibrium;
- high-mitigation equilibrium;
- successful transition across `x = 0.5`;
- overshoot;
- damped oscillations;
- persistent oscillations;
- delayed transition.

For two-dimensional parameter sweeps, visualize these classes as regime maps. Boundaries between regimes are likely to be more informative than differences within a homogeneous regime.

## 2. Threshold-crossing analysis

**Research question:** How do different social norms affect whether and when mitigation crosses behaviourally important thresholds?

Calculate, where applicable:

- `time_to_x_0.5`;
- `time_to_x_target` (currently `x_target = 0.7`);
- whether the threshold is ever crossed;
- whether it is crossed permanently or only temporarily.

The `x = 0.5` threshold is particularly relevant because the descriptive imitation term changes sign there.

## 3. Targeted analysis around c_inj = 1 and c_inj = 2

**Research question:** Do the analytically identified boundaries at `c_inj = 1` and `c_inj = 2` correspond to observable transitions in the coupled model dynamics?

Run higher-resolution sweeps around both values instead of treating the full `c_inj` range uniformly. Compare trajectory shape, threshold crossing, equilibria, oscillations, and climate outcomes on either side of the boundaries.

## 4. Sensitivity to initial mitigation share x0

**Research question:** Which norm formulations exhibit path dependence, tipping, or sensitivity to the initial prevalence of mitigation behaviour?

Sweep `x0`, especially around `x0 = 0.5`. Compare final states and trajectories for otherwise identical parameters. This should be particularly informative for descriptive imitation because its social pressure changes sign at 50% mitigation.

A finer sweep around any transition point could reveal bistability or a tipping threshold.

## 5. Pairwise trajectory distance between norm formulations

**Research question:** For which parameter combinations do competing norm formulations make the most divergent behavioural predictions?

For norms A and B, calculate a trajectory-distance metric such as

```text
D_x(A,B) = (1/T) * integral |x_A(t) - x_B(t)| dt.
```

Analogously calculate a temperature distance `D_T`. Rank parameter combinations by these distances to automatically identify cases where the choice of norm formulation matters most.

## 6. Behavioural speed and take-off analysis

**Research question:** Do some norm mechanisms generate abrupt behavioural transitions while others produce gradual adaptation?

Calculate metrics such as:

- maximum `|dx/dt|`;
- maximum positive `dx/dt`;
- time of maximum behavioural acceleration;
- duration required to move from e.g. `x = 0.4` to `x = 0.6`.

This can distinguish similar final outcomes that arise through very different transition dynamics.

## 7. Dynamic-norm overshoot and oscillation analysis

**Research question:** Under which combinations of norm strength and social-memory timescales do dynamic norms produce overshoot, damped oscillations, or persistent oscillations?

Use the existing oscillation metrics (`n_oscillations`, `median_period`, `amplitude_ratio`, `damping_rate`, `oscillation_score`) and extend them with an explicit overshoot measure.

For the ODE dynamic formulation, investigate `tau_ref`, `tau_xp`, and `tau_STref`. For the delay formulation, investigate `tau`, `theta`, and `c_dyn`.

## 8. Comparison of the two dynamic-norm implementations

**Research question:** When do the perception/reference formulation and the explicit delay formulation generate equivalent dynamics, and when do their predictions diverge?

Compare `dynamic social norm` with `dynamic social norm2`, and the corresponding combined descriptive-injunctive-dynamic formulations. Search for parameter mappings that produce similar trajectories, then identify parameter regions where the formulations differ qualitatively.

This analysis could clarify whether the implementation choice itself has substantive consequences.

## 9. Norm-component ablation analysis

**Research question:** Which component of the combined descriptive-injunctive-dynamic norm is responsible for each observed dynamical feature?

For matched parameter sets compare:

- descriptive only;
- injunctive only;
- dynamic only;
- descriptive + injunctive;
- descriptive + dynamic;
- injunctive + dynamic;
- all three components.

This isolates interaction effects that cannot be inferred from comparing the full combined model with the baseline alone.

## 10. Interaction / synergy between injunctive and dynamic strength

**Research question:** Does combining injunctive and dynamic normative influence produce effects that are larger or qualitatively different than the sum of their separate effects?

Use the existing `c_inj x c_dyn` sweep to compare the combined result against appropriate single-component counterfactuals. A non-additive interaction could indicate synergy or interference between normative mechanisms.

## 11. Climate consequences conditional on behavioural similarity

**Research question:** Can different norm formulations produce materially different climate outcomes even when they converge to similar final mitigation levels?

Select simulations with similar `final_x` and compare:

- `max_temperature`;
- `final_temperature`;
- `temperature_area`;
- `time_to_peak_temperature`;
- `x_area`.

This directly tests whether the timing and shape of behavioural transitions matter for climate outcomes independently of the final behavioural state.

## 12. Climate amplification of small behavioural differences

**Research question:** Can small differences in behavioural trajectories generated by alternative norm formulations become amplified into larger differences in climate outcomes?

Relate pairwise behavioural distance `D_x` to climate distance `D_T`, peak-temperature differences, and temperature-area differences. Cases with small `D_x` but large climate differences would be particularly noteworthy.

## 13. Social-norm dominance versus temperature feedback

**Research question:** Under which conditions is behavioural change primarily driven by social norms rather than temperature-dependent incentives?

Sweep `social_norm_factor` and `temperature_factor` jointly and identify regions where changing the norm formulation substantially alters outcomes versus regions where temperature feedback dominates and norm choice becomes relatively unimportant.

## 14. Equilibrium and bifurcation analysis linked to simulations

**Research question:** Do analytically predicted equilibrium or stability changes correspond to transitions observed in numerical simulations?

Use `symbolic_analysis.py` to derive candidate stability/bifurcation boundaries, then overlay or compare these with regime boundaries from parameter sweeps. Agreement would provide a mechanistic explanation for numerical transitions rather than treating them as purely empirical simulation patterns.

## 15. Robustness across parameter uncertainty

**Research question:** Are differences between norm formulations robust across plausible uncertainty in shared model parameters, or do they depend on narrow parameter choices?

After identifying candidate interesting differences, vary shared behavioural and climate parameters around the baseline. Report whether the qualitative finding persists rather than relying only on a single calibration.

## 16. Agent-based versus aggregate norm dynamics

**Research question:** Does representing social influence explicitly at the agent/network level generate aggregate behaviour that cannot be reproduced by the deterministic norm formulations?

For the agent-based intention model, vary network size, susceptibility, threshold, and random seed. Compare distributions across repeated stochastic runs with deterministic trajectories, focusing on transition probability, timing variability, and threshold crossing.

## Suggested prioritization

A practical first sequence is:

1. implement threshold-crossing and `max_dxdt` metrics;
2. classify behavioural regimes;
3. generate regime maps for the existing `c_inj x c_dyn` sweeps;
4. investigate the neighbourhoods of `c_inj = 1` and `c_inj = 2` at higher resolution;
5. compare the two dynamic formulations using oscillation and trajectory-distance metrics;
6. connect behavioural differences to temperature outcomes;
7. use symbolic stability/bifurcation results to explain the numerical regime boundaries.

This sequence reuses the existing batch infrastructure and should help identify a smaller number of parameter combinations that warrant detailed interpretation and plotting.
