# Social Norms Climate Model

This repository contains the computational model developed as part of a Master's thesis. It investigates how social norms and peer influence can affect climate-mitigation behaviour and its interaction with a climate/emissions model.

## Contents

- `model/agent.py` — agent-based social-norm layer and peer interactions
- `model/model_equations.py` — climate and behavioural model equations and scenario handling
- `simulation/batch_runner.py` — batch simulations
- `main.ipynb` — main notebook for running and exploring the model
- `visualization/plotting.py` — visualisation utilities
- `visualization/make_plot_videos.py` — generation of plot videos
- `config/scenarios.json` — model parameter scenarios
- `data/global.1751_2017.csv` — emissions data used by the model

Model code lives in `model/`, run orchestration in `simulation/`, and numerical
and symbolic analyses in `analysis/`. Shared infrastructure is in `utils/` and
general plotting in `visualization/`. `config/` and `data/` contain model inputs.
`main.ipynb` and `INTERESTING_FINDINGS.md` stay at the repository root.

Tests, the qualitative workbook, profiling tools/results and supplementary
notes are grouped in `support/`. Simulation results stay in `plots/`; explicitly
selected external result folders are unchanged. Repository-owned input and
default output paths are resolved centrally in `utils/paths.py`.

Run these commands from the repository root:

```powershell
# Sensitivity analysis
python -m analysis.sensitivity.sensitivity_analysis --base-sample-size 64 --workers 11

# Sensitivity analysis followed by regression trees
python -m analysis.sensitivity.sensitivity_pipeline --base-sample-size 64 --workers 11

# Batch simulations and the qualitative workbook
python -m simulation.batch_runner --help
python support/qualitative_norms/serve.py

# Python tests (including nested test packages)
python -m unittest discover -s support/tests -t . -v
```

The pytest-style sensitivity-review tests can additionally be run with
`python -m pytest support/tests/sensitivity/test_sensitivity_review.py`.

## Status

The code is part of ongoing Master's thesis research and is therefore subject to change.

## Reproducibility

The model is implemented primarily in Python and uses NumPy, pandas, SciPy, and Jupyter notebooks. Parameter scenarios are defined in `config/scenarios.json`.

`load_scenarios()` loads named scenarios using the shared parameters explicitly
configured in the JSON `baseline` block and each scenario's own values.
`resolve_parameters(extension)` loads a named scenario or copies a complete
parameter dictionary, validates values, and calculates derived parameters such
as `theta = tau*rho`. It does not fill missing model inputs with Python defaults.
A dictionary is used as supplied; missing keys are not restored from `baseline`.
Missing inputs raise native `KeyError` exceptions when accessed by the model.

To vary a parameter, start from the explicitly selected configuration:

```python
from model.model_equations import resolve_parameters, simulate

params = resolve_parameters("dynamic social norm2")
params.update(tau=3, rho=2)
result = simulate(params)
```

## Social norm strength

`social_norm_factor` controls the overall strength of the social-norm contribution
in the replicator scenarios. The agent intention scenario uses its own
`eta`. The descriptive term is
`2*x - 1`; `c_inj` and `c_dyn` weight the injunctive and dynamic components
relative to it in combined norms.

In `dynamic social norm`, the unweighted term is `(x_p - x_ref) / x_ref`.
The combined ODE norm weights this dynamic component with `c_dyn`. Both use
the existing zero-reference guard; the adaptation times remain `tau_ref` and
`tau_xp`.

A structural literature analogue for these two timescales is
[Rajah et al. (2025), FRIDA v2.1, section 3.1.3 and Table A1, p. 6017](https://doi.org/10.5194/gmd-18-5997-2025).
Their `AT_adc` smooths actual consumption into perceived consumption, like
`tau_xp`; `AT_STref` smooths perceived consumption into the recent reference,
like `tau_ref`. The reported calibrated values and uncertainty ranges, in years,
are:

| Dietary domain | Our analogous parameter | FRIDA parameter | Value | Min–max |
| --- | --- | --- | ---: | ---: |
| Animal products | `tau_xp` | `AT_adc` | 2.86 | 1.87–3.84 |
| Animal products | `tau_ref` | `AT_STref` | 5.53 | 1–10.1 |
| Total food | `tau_xp` | `AT_adc` | 1.11 | 1–1.23 |
| Total food | `tau_ref` | `AT_STref` | 2.37 | 1–3.74 |

These parameters were estimated through model calibration to food-system data
for 1980–2020. The ranges are model-specific likelihood-based uncertainty ranges,
not direct measurements of general social adaptation times or 95% parameter
confidence intervals. Using them for a general mitigation fraction is a transfer
assumption. The roughly 55.5-year `AT_LTref` in the same table concerns a distinct
long-term social-value process and is not the reference used for their dynamic
descriptive norm. Source annotations accompany the adaptation equations; this
literature lookup does not change configured parameter values.

The former `tau_STref` parameter has also been removed. To preserve legacy
trend strength, convert it before removing the key:

- `Descriptive, injunctive, dynamic`: set `c_dyn = c_dyn / tau_STref`.
- `dynamic social norm`: set `social_norm_factor = social_norm_factor / tau_STref`.

Other norms did not use this parameter. Stored scenarios and CSV examples have
been converted. Simulations reject legacy dictionaries containing `tau_STref`
so that outdated inputs cannot silently change dynamics.

The former `delta` parameter has been removed. Default scenarios previously used
`delta = 1`, so their dynamics are unchanged. The baseline examples in
`data/interesting_parameter_sets.csv` have been converted to `social_norm_factor`.
Simulations reject parameter dictionaries containing `delta` to avoid silently
changing the meaning of older inputs.

For legacy imitation parameter sets, replace
`social_norm_factor` with `social_norm_factor * delta`, then remove `delta`.
For combined descriptive/injunctive/dynamic norms with positive `delta`, also
divide `c_inj` and `c_dyn` by the old `delta` to preserve all weighted components.
A legacy combined norm with `delta = 0` and nonzero other components cannot be
represented exactly by this normalization. In norms without a descriptive
component, simply remove the previously unused `delta`.
Legacy agent equations have been replaced by the intention model below;
their trajectories cannot be preserved through parameter conversion.

Existing sensitivity results describe their saved equations and parameter
distributions. Rankings from runs that varied `delta` or `tau_STref` must be recomputed using
the current model; their indices cannot simply be renamed or added together.

## Approval norm

`Observation based / approval (punish only one behaviour)` uses the norm term
`x`, weighted once by `social_norm_factor`. The redundant parameter `alpha` has
been removed from scenarios, batch sweeps, Sobol inputs and the current formulas:

```text
dx/dt = kappa*x*(1-x)*(-beta + temperature_factor*f_T(T) + social_norm_factor*x)
```

To reproduce an old approval parameter set, use
`social_norm_factor_new = social_norm_factor_old * alpha_old` and remove
`alpha`. Current simulations reject obsolete `alpha` inputs rather than silently
ignoring their effect. The approval examples in `data/interesting_parameter_sets.csv`
have been converted this way. The configured scenario had `alpha = 1`, so its
trajectory is unchanged. Sobol now varies only `social_norm_factor` on `[0,5]`;
this is a different sampling distribution from the former product of two
independently sampled factors, so old indices cannot simply be renamed.
Saved sensitivity results remain historical: their formula plots retain the
old factor when their saved parameter names include it. Regression trees built
from those old results continue to describe the saved model.

## Static injunctive norm

`Static injunctive` now uses only `x_target - x`, weighted by
`social_norm_factor`. Its redundant `c_inj` parameter has been removed:

```text
dx/dt = kappa*x*(1-x)*(-beta + temperature_factor*f_T(T) + social_norm_factor*(x_target-x))
```

For old standalone static-injunctive parameter sets, use
`social_norm_factor_new = social_norm_factor_old * c_inj_old`, then remove
`c_inj`. The two static examples in `data/interesting_parameter_sets.csv` have been
converted; combined-norm examples retain `c_inj` and their original strengths.
The simulator rejects `c_inj` only for `Static injunctive`, where it would
otherwise be silently ignored. Combined norms still use it to weight their
injunctive component relative to the other components.

New static-injunctive Sobol runs retain the shared `social_norm_factor` range
`[0,5]`; the former product could reach 50. Thus this change also narrows the
sampled effective strength and changes its distribution. Historical results
keep their original inputs and formula plots; new indices require new runs.

## Belief-based intention motivation

`Belief-based / intention motivation` uses the constant signed norm term `N`:

```text
dx/dt = kappa*x*(1-x)*(-beta + temperature_factor*f_T(T) + social_norm_factor*N)
```

Negative `N` favours non-mitigation, zero contributes no norm influence, and
positive `N` favours mitigation (for positive `social_norm_factor`). `N` is not
a probability. Sobol samples it on `[-1,1]`; the batch belief-value sweep covers
both signs and zero within the same interval. This interval and interpretation
are project assumptions, not a calibrated literature range. The simulator and
symbolic analysis preserve the sign; no clipping or nonnegativity constraint is
applied to `N`. The configured example `N = 0.1` remains a valid positive case.
Previously saved results retain their original sampling ranges.

## Observation-based intention agents

`Observation-based / intention motivation (agents)` uses annual simultaneous,
reversible decisions, starting in 2017 (`t = 217`):

```text
q_i = actual mitigators among agent i's peers / number of peers
A_i(t) = -beta_i + temperature_factor * f_T(T(t))
BI_i(t) = A_i(t) + eta * q_i   if q_i >= phi
BI_i(t) = A_i(t)                           otherwise
actual_behavior_i(t) = 1 if BI_i(t) >= psi, otherwise 0
x(t) = mean(actual_behavior_i(t))
```

All agents observe the old actual behaviours before switching together. The
climate ODE uses `epsilon(t) * (1 - x)` with this actual share. There is no
replicator equation, `kappa`, or `social_norm_factor` in this scenario's decisions.
Temperature still affects behaviour through `f_T`, whose existing steepness
parameter `omega` is separate from the new `eta`.
The agent parameters use free Greek letters: `eta` (η, norm weight),
`phi` (φ, norm-activation threshold), and `psi` (ψ, action threshold).
The previous keys `agent_norm_weight`, `agent_norm_threshold`, and
`agent_behavior_threshold` must be renamed; outdated keys are rejected.
BI is a continuous net score, may be negative or greater than one, and is not
clipped or interpreted as a probability.
For example, `BI_i = 0.6` and an action threshold of `0.5` give
`actual_behavior_i = 1` while `BI_i` remains `0.6`. In code these are separate
fields: `Agent.behavioral_intention` and `Agent.actual_behavior`.

Costs `beta_i` are drawn once from `Uniform(0, 2*beta)` and remain fixed, as do
the random peer networks. Thus `beta` is the expected mean cost, not each
agent's identical cost. [Torren-Peraire et al. (2024), Eq. (1)](https://doi.org/10.18564/jasss.5291)
uses individual static barriers on `[0,1]` and Beta-distributed initialization.
Our uniform choice (Beta(1,1)) and rescaling to preserve expected cost `beta`
are modelling assumptions, not empirical cost bounds.

The configured independent norm weight is `0.5`. [InSEEDS, Schwarz et al. (2025),
Eq. (2) and Table 1, preprint](https://doi.org/10.5194/egusphere-2025-4079)
uses norm/attitude weight ratios of `0.25` and `2/3`; our configured value is an
illustrative intermediate value, not a calibration. `eta`, `phi`, `psi`, and
`network_size` must be explicitly configured. The agent module supplies no
fallback parameter values. The base thresholded BI rule follows
[Prawitz et al. (2026), section 4.3](https://doi.org/10.1088/1748-9326/ae3b55);
the temperature-dependent `A_i(t)` is this project's extension. Sources and
these qualifications also appear in code comments in `model/agent.py`.

The initial actual share is `round(x0*n_agents)/n_agents` and remains prescribed
until the first decision. Decision times are exact years even when
`coupling_interval`, RK4 `dt`, or the output grid do not align with them. Between
decisions, actual behaviour is held constant. Values recorded at a decision
are the new, post-decision values. Climate states remain continuous.
`network_size` counts observed peers, excludes the agent itself, and must be
between zero and `n_agents-1`; `None` observes everyone else. Zero or an empty
neighbourhood observes nobody and contributes no norm influence.

`result['agent_history']` stores the initial evaluation and annual decisions:
`t`, `temperature`, `behavioral_intention`, `actual_behavior`, `peer_norm`, `mitigation_share`,
`social_norm_term`, fixed `beta`, and `is_decision`. The first row prescribes
behaviour rather than deciding it; `peer_norm` records the observations used
before simultaneous switching. BI/behaviour/peer arrays have one column per
agent. `social_norm_term` is the mean already weighted, thresholded norm
contribution used at the last evaluation. Batch runs also save this history
as `agent_history.npz` and include `mean_intention` in `time_series.csv`.

Plots show actual behaviour as steps. Cumulative emissions, mitigation area,
and threshold-crossing times respect these steps; annual oscillation metrics
do not depend on output density. Old results retain their old interpretation;
new parameter files identify `agent_decision_model = annual_intention_threshold`.
Batch runs reject reuse of legacy agent results or histories with outdated
field names unless explicitly overwritten.
`agent_susceptibility` and `agent_update_rate` are rejected as removed inputs.
The automated Sobol runner includes this scenario, both in the default scenario
selection and when selected explicitly. It varies `temperature_factor` and
`beta` on `[0,5]`, `eta`, `phi`, and `psi` on `[0,1]`, and `network_size` on
`[1,999]`, rounded to the nearest integer. `kappa` and `social_norm_factor` are
excluded because they do not enter agent decisions. All seven active targets use the
same definitions as the ODE scenarios, respecting annual behaviour steps.

Sensitivity runs use 1,000 agents and the same configured `seed` for every sample.
This makes each parameter-to-output mapping reproducible; the indices are
conditional on that initialization seed, rather than averages over random
initializations. Repeat the analysis with different `--seed` values to assess
robustness. The seed also controls Sobol sampling. `metadata.json` records this
interpretation and the agent count; diagnostics record the effective integer
peer count, while `samples.csv` preserves the original Sobol draw.

## Solver selection

Existing calls keep the adaptive BDF solver, including its stricter retry when
fraction states leave their valid range:

```python
result = simulate("baseline", solver="BDF")
```

LSODA is available through SciPy's `solve_ivp`, using the same tolerances,
fraction-validation retry, and delayed-history handling as BDF:

```python
result = simulate("baseline", solver="LSODA")
```

Both BDF and LSODA choose adaptive internal steps and ignore `dt`.
In `main.ipynb`, the main scenario simulation cell has `solver` and `dt`
settings immediately below `simulation_time`. Set `solver="LSODA"` there
and rerun that cell (restart the kernel first if old modules are loaded).
These settings control that cell's scenario simulations, not the separate
interesting-parameter-set loader cell.

Classical fixed-step RK4 is also available. `dt` is required, in years:

```python
h = 0.01
params = resolve_parameters("dynamic social norm2")
params.update(tau=h / 2, rho=2)  # Derived theta = tau*rho = h.
result = simulate(params, solver="RK4", dt=h, simulate_only_x=True)
```

Import `simulate` and `resolve_parameters` from `model_equations`. The example
uses the reduced model: `simulate_only_x=True` freezes carbon reservoirs but
retains temperature and social dynamics. The full carbon equations are very
stiff: RK4 was unstable even at `dt=1e-8` years in baseline testing. Use BDF for
practical full-model runs; a useful RK4 step must be established by convergence
and stability checks for the selected scenario.

RK4 uses `dt` independently of `output_points_per_year`. A step is shortened at
a coupling or simulation-end boundary if necessary; choose coupling interval
and simulation duration as multiples of `dt` for uniform steps throughout.
Output between integration nodes uses linear interpolation. Agent decisions
occur at exact annual boundaries; actual `x` stays constant between them.
RK4 stores delayed `x` history at every
accepted integration node; intermediate RK stages use interpolation between
the last committed history value and the current stage for within-step queries.
This delay approximation does not in general retain RK4's fourth-order ODE
accuracy. BDF retains its existing output-based history behavior.

RK4 never retries with a different timestep. Non-finite states or fraction
violations beyond the existing tolerance raise an error asking for a smaller
`dt`. Adaptive solvers ignore a supplied `dt`.

For batch comparisons, set `solver="RK4", dt=h` on an `ExperimentGroup`;
defaults are `solver="BDF", dt=None`. Batch metadata records both settings,
and direct simulation results include `solver_settings`. Keep `theta` fixed
while refining `dt` to test numerical convergence separately from changing the
model's observation window.

Integrator implementations and the `SOLVERS` registry live in `model/solvers.py`,
separate from model equations and coupling logic, for future solver additions.
Run checks with `python -m unittest support.tests.model.test_solvers -v`.

## Model performance

Shared carbon fluxes are computed once per right-hand-side evaluation and reused
in the four carbon equations, preserving each equation's arithmetic order.
Fluxes are never reused between solver evaluations or RK stages.

Delayed-state interpolation reuses NumPy arrays of the existing history. These
arrays are invalidated whenever history is extended or pruned, including after
every accepted RK4 step. The interpolation formula, samples, boundary behavior,
solver tolerances, and coupling/output intervals are unchanged.

Run solver and history-update checks with
`python -m unittest support.tests.model.test_solvers support.tests.model.test_model_optimizations -v`.

## Runtime profiling

`python -m support.tools.profile_dynamic_norms` profiles representative baseline and dynamic
norm cases, serially, using a 400-year horizon, with the sensitivity defaults
of one-year coupling and 24 output intervals per year. It does
not change model equations or solver tolerances. Profiling adds overhead, so
the reported times are diagnostic rather than production runtime predictions.

Use `--scenarios "Descriptive, injunctive, dynamic2" --zero-boundaries` to
include the serial zero-boundary checks. To inspect existing sensitivity
samples, use `--scenarios "Descriptive, injunctive, dynamic2" --samples-file
"path/to/samples.csv" --sample-indices 0 1 10`. The adjacent `parameters.json`
is used when available. `--simulation-time`, `--coupling-interval`, and
`--output-points-per-year` control the reproduced simulation settings.

Results are saved under `support/profiling_results/<timestamp>/`: each case contains
`profile.prof`, a readable `profile.txt`, function timings in `functions.csv`,
interval timings and solver counters in `intervals.csv`, and `summary.json`.
`--max-seconds` bounds each case (default 60); time-limited cases retain partial
profiles. Cumulative function timings include child calls and overlap.

## Sensitivity sample diagnostics

Use `--constant-temperature-costs` to replace the temperature response by
`f_T(T) = 1` in every ODE and agent decision. The behavioural contribution becomes
`temperature_factor`; its Sobol sampling range is unchanged. Climate dynamics
continue to run. Omitting the flag keeps the usual sigmoid.

```powershell
python -m analysis.sensitivity.sensitivity_analysis --constant-temperature-costs --base-sample-size 64 --workers 11 --output-root "E:\Masterarbeit\Sensitivity"
```

The flag also works with `analysis/sensitivity/sensitivity_pipeline.py`. It is recorded in
`metadata.json` and per-simulation diagnostic configuration and shown in the
ranking formula graphics. When reconstructing a run from saved parameters, pass
the recorded `constant_temperature_costs` value to `simulate()`. Append mode
rejects mixing constant-response and sigmoid scenarios in one result folder.

### Regression trees from saved simulations

`analysis/regression_trees/regression_tree_analysis.py` evaluates saved simulations without running the
socio-climate model again. It fits a separate `DecisionTreeRegressor` per norm
and target. The seven active sensitivity targets are included: `x_mean`,
`final_temperature`, `cumulative_emissions`, `first_time_x95`, `bool_x95`,
`oscillation_occurrence` and `oscillations_per_500_years`. The five additional
targets `final_x`, `median_period`, `oscillation_amplitude`, `damping_index`
and `damping_rate` remain available. Inputs come only from sampled model parameters;
`sample_index` joins the two CSVs and never enters the model as a feature.

```powershell
python -m analysis.regression_trees.regression_tree_analysis --input-root "E:\Masterarbeit\Sensitivity\2026-10-08_12-24-45\baseline" --targets final_x --output-root plots/regression_tree_results
```

`--input-root` accepts a saved run root or a single scenario folder. Optional
`--scenarios` selects norm names or folder names. Omitting `--targets` analyzes
all twelve targets. The script requires `metadata.json`, `samples.csv` and
`simulation_outputs.csv`; metadata/output mismatches are rejected. Different
the original per-norm analysis is kept separate, and source files are never rewritten. A saved metadata
record is not a complete model-code archive: use a homogeneous source run and
interpret each result within its saved horizon and parameter bounds.

25% of whole Sobol A/AB/B blocks (including second-order layouts if saved) are
held out before target filtering. Hyperparameter selection uses grouped
cross-validation on training blocks only. Depths 2–4 and minimum leaf fractions
5%/10% are compared using MAE; numerically negligible splits are suppressed
relative to training-target variance. These limits and the seed are saved.

Only completed, finite target values enter a tree. The seven sensitivity targets
include nonoscillating simulations and genuine zeros. Boolean targets remain
regression targets: their leaf means are the proportions of training runs with
value 1, shown as percentages; deviations and MAE use percentage points.
`first_time_x95` keeps 0 (= never reached), so its means include these zeros and
are not conditional waiting times among successful runs.
The four conditional targets `median_period`, `oscillation_amplitude`,
`damping_index` and `damping_rate` additionally require at least two complete
prominent cycles, matching `oscillation_occurrence`.
The amplitude tree uses the **saved amplitude definition**, not a newly defined
full-cycle swing. Damping targets require finite positive initial/final amplitudes;
this removes undefined placeholder zeros while preserving real zero damping.
Filtering is separate for each target. Conditional trees describe eligible
oscillating trajectories, not the entire parameter space. Too few rows/blocks,
missing target columns and constant training targets receive explicit statuses
instead of misleading trees. Small samples remain exploratory.

Saved target values are not recomputed. In particular, older saved
`oscillations_per_500_years` may include individual cycles below the current
two-cycle minimum; this legacy definition is labelled in reports and plots.
New sensitivity runs use the corrected definition.

Every timestamped result folder contains `summary.csv`, reports and a source-hash
manifest. `regressiontrees_alle_normen.svg` embeds all saved trees in one vector
overview: one section per norm and one column per target. Unfitted targets show
their status and available row/block counts. Parameter and target names are
preserved; no trees are refitted for the overview. This SVG is created automatically
by the standalone tree analysis and by `analysis/sensitivity/sensitivity_pipeline.py`.
Fitted targets additionally export `tree.svg`/`.png`, `rules.txt`,
`predictions.csv`, prediction-check plots, training-CV results and test-set
permutation importance. Reports compare test MAE/RMSE/R² against a training-mean
baseline and count root splits across training-block subset refits. These
diagnostics are not Sobol indices, causal effects or confidence intervals.

Each tree leaf shows the target mean and the standard deviation of its training
target values (`ddof=0`), plus its training count. The deviation describes spread
within the leaf, not uncertainty of the mean or a confidence interval. For
`final_x` and `oscillation_amplitude` it is expressed in percentage points;
other targets retain their corresponding units. The combined SVG includes the
same leaf labels.

For inputs containing multiple norms, the default analysis additionally creates
`_common_parametes/pooled` (one tree per target over all selected norms) and
`_common_parametes/per_norm` (one tree per norm/target with the same common
inputs). Both groups include their own reports, summary and
`regressiontrees_alle_normen.svg`. Decision features are the intersection of
sampled input names across the selected norms, never the norm label. In the
current ten-norm sensitivity run, these are `temperature_factor` and `beta`;
the agent model does not sample `kappa` or `social_norm_factor`.

When the selected sources contain the agent norm and at least two other norms,
both common-input groups are also created without the agent norm under
`_common_parametes/without_agents/pooled` and
`_common_parametes/without_agents/per_norm`. The nine current ODE norms share
`social_norm_factor`, `temperature_factor`, `beta` and `kappa`. Each variant
recomputes its input intersection and has separate reports, source manifests and
SVG overviews labelled "mit Agentennorm" or "ohne Agentennorm". The agent rows
are excluded completely from the latter variant. This also runs automatically
in `analysis/sensitivity/sensitivity_pipeline.py`.

Pooled trees retain the source norm and original sample index for auditing.
Matching original Sobol block indices across norms are kept together during
holdout, cross-validation and stability checks. Each eligible simulation has
equal weight; norms with more eligible samples contribute more, and their
counts are saved per target. This tests held-out samples from the included
norms, not generalization to a previously unseen norm. Oscillation eligibility
remains target-specific, so pooled oscillation trees may use only a subset of
the norms. The simulation horizon must agree across sources.

To create only the common-input groups (both variants when agents are present)
from saved sensitivity data:

```powershell
python -m analysis.regression_trees.regression_tree_analysis --input-root "E:\Masterarbeit\Sensitivity\samplesize_64_2026-10-09_00-42-25" --analysis-modes pooled_common per_norm_common --output-root "E:\Masterarbeit\Sensitivity\samplesize_64_2026-10-09_00-42-25\regression_trees"
```

`--analysis-modes per_norm` selects only the original full-input trees. Single
scenario input defaults to that original mode. `analysis/sensitivity/sensitivity_pipeline.py` uses
all three modes automatically when several saved norms are present.

To add the overview to an existing tree result folder without repeating analysis:

```powershell
python -m analysis.regression_trees.regression_tree_plots --input-root "E:\Masterarbeit\Sensitivity\<run-folder>\regression_trees\<timestamp>"
```

For a small reproducible **synthetic known-rule example** (128 rows, no climate
simulation), run:

```powershell
python -m analysis.regression_trees.regression_tree_demo
python -m unittest support.tests.regression_trees.test_regression_tree_analysis -v
```

The demonstration writes separate input and result folders under
`plots/regression_tree_example/<timestamp>/`.

To run regression trees automatically after every successfully completed Sobol
invocation, use `analysis/sensitivity/sensitivity_pipeline.py` with the same sensitivity arguments:

```powershell
python -m analysis.sensitivity.sensitivity_pipeline --base-sample-size 32 --workers 11 --output-root "E:\Masterarbeit\Sensitivity"
```

This separate entry point leaves `analysis/sensitivity/sensitivity_analysis.py` unchanged. After the
simulations and Sobol plots complete, it reads that run's saved data and writes
trees to `<run-folder>/regression_trees/<timestamp>/`. No additional simulations
are run. The regression stage is also recorded in `sensitivity_analysis.log`.
Appending scenarios refreshes the tree analysis for all completed scenario
folders in the run. Insufficient eligible data are reported per target; unexpected
postprocessing errors remain visible and do not remove saved Sobol results.
The original `analysis/sensitivity/sensitivity_analysis.py` command continues to run Sobol only.

### Current Sobol targets

The Sobol analysis uses seven active targets. `x_mean` is the time-weighted mean over
the entire simulated interval, `integral(x dt)/(t_end - t_start)`, including
the prescribed historical period. ODE output uses trapezoidal integration;
annual agent decisions use the actual share held between decisions.

`time_to_elimination` is the first time `x >= 0.95`, even if x later decreases.
It remains `NaN` if this never happens. For Sobol, the target
`first_time_x95` stores **0 if the threshold is never reached**
and the actual first-passage time otherwise. Zero denotes non-occurrence, not
elimination at time zero. This is a zero-coded first-passage target, not a
horizon-censored time or an estimate of future elimination. Its Sobol indices
reflect both occurrence and timing; a smaller output is not always faster
elimination. The separate binary target `bool_x95` remains available.
Non-eliminating successful simulations stay in the complete Sobol design.

`oscillation_occurrence` is a binary target: 1 if at least two complete
prominent cycles are detected over the entire simulated interval, otherwise 0.
Each cycle consists of two consecutive qualifying half-cycles; the minimum
peak-to-trough swing is `max(0.02, 0.05 * (max(x) - min(x)))`. The definition
is saved in metadata. This detects occurrence, not persistence or frequency.
Rare events can still make Sobol estimates unstable.

`oscillations_per_500_years` uses the same minimum of two complete prominent
cycles. It is 0 when `oscillation_occurrence` is 0; otherwise it equals
`n_oscillations * 500 / simulation_time`, using the entire simulated interval.

The mitigation group contains `x_mean`, `first_time_x95` and `bool_x95`;
climate contains `final_temperature` and `cumulative_emissions`; dynamics
contains `oscillation_occurrence` and `oscillations_per_500_years`.
`final_x`, `oscillation_amplitude` and `damping_index` are commented out of
the Sobol selection and ranking groups but remain saved as raw metrics.
Together with `median_period` and `damping_rate`, they are candidates for
future regression-tree analyses (see support/docs/ToDos.md).
`simple_mean` averages all seven active ST indices; `grouped_mean` gives equal
weight to the three groups. Scores differ from runs with earlier target selections. Start a new result folder for this analysis: append mode rejects older
output definitions. Existing saved rankings remain readable with their original
targets and replacement-value labels; their scores are not recalculated by plotting.

Each new run also writes `sensitivity_analysis.log` in its timestamped output
directory (`--output-root/<timestamp>/`). Console messages remain visible and
are flushed to the log throughout the run, including worker start/completion
messages, progress/ETA, timeouts, Python warnings and uncaught errors.
Routine sample and boundary start/completion messages appear only in the `.log`
file; overall progress, timeouts and errors remain visible in the terminal.

New sensitivity runs automatically create a `sample_diagnostics_<timestamp>`
directory inside each scenario folder. `diagnostics.json` points to the current
attempt's directory, including if the analysis has not completed yet. Attempts
are kept separate when a scenario directory is reused.

To process norms one at a time in the same result set, pass the existing run
folder name with `--append-existing-folder` on subsequent runs:

```powershell
python -m analysis.sensitivity.sensitivity_analysis --scenarios baseline --output-root plots/sensitivity_results
python -m analysis.sensitivity.sensitivity_analysis --scenarios "Dynamic social norm" --output-root plots/sensitivity_results --append-existing-folder 2026-09-24_10-00-00
```

The folder is resolved below `--output-root`. Supplying
`--append-existing-folder` enables
append mode and requires that the selected folder already exists.
Existing scenario results are never overwritten in append mode; trying to add a
scenario that is already present stops with an error. The overall top-parameter
file is rebuilt from all scenario result folders.

After each sensitivity run, the runner also scans all scenario folders in the
run directory and overwrites one violin plot with an overlaid boxplot per
sensitivity output:

```text
violin_boxplot_final_x.png
violin_boxplot_x_mean.png
violin_boxplot_final_temperature.png
violin_boxplot_cumulative_emissions.png
violin_boxplot_first_time_x95.png
violin_boxplot_bool_x95.png
violin_boxplot_oscillation_occurrence.png
violin_boxplot_oscillation_amplitude.png
violin_boxplot_oscillations_per_500_years.png
violin_boxplot_damping_index.png
```

Only rows with `status=completed` are plotted. Adding another norm and using
`--append-existing-folder` regenerates all plots from the available norm
folders.

The runner also refreshes two bar-chart figures inside **every** norm folder
with a saved parameter ranking, including older norms in append mode:

```text
ranking_balken_gruppen_gesamt.png / .svg
ranking_balken_zielvariablen.png / .svg
```

The first shows `mitigation`, `climate`, `dynamics`, and `overall_score`; the
second shows all saved output-specific ST indices (seven for new runs). Both use the values and
parameter order in `parameter_ranking.csv`. Each metric has the same axis range
across all available norms, so existing figures are regenerated when a new norm
is appended. Metadata supplies each norm's sample size, simulation horizon,
non-occurrence convention, and score mode (`simple_mean` or `grouped_mean`).
Provisional analyses are labelled; unavailable analyses are skipped and undefined
values are marked `n. v.`. These are point estimates without error bars; the
confidence half-widths remain available in `sobol_indices.csv`.

The run's parent folder also receives `ranking_balken_alle_normen.svg`: one
section per available norm, with its equations above the complete groups/overall
figure on the left and the complete target-variable figure on the right. The
equation block includes the behavioural equation, norm-specific term, temperature
response and auxiliary perception/delay equations. Agent sections show continuous
BI, the binary action threshold, fixed cost distribution and peer proportion.
Code-name legends connect Greek symbols to the ranking parameters. Saved legacy
parameters (`delta`, `tau_STref`, or an independent `theta`) retain their original
formula and are labelled as historical; current delay norms show `theta=tau*rho`.
The individual SVGs are
embedded as vectors with unique element IDs; all bars, labels, and annotations
are preserved. This self-contained overview is rebuilt from all analysed norm
folders on every run, including append runs. It replaces the proposed comparison
of common parameters between norms.

To regenerate only these bar charts without running simulations:

```python
from pathlib import Path
from sensitivity_plots import create_parameter_ranking_barplots

create_parameter_ranking_barplots(Path("plots/sensitivity_results/<run-folder>"))
```

`rho` denotes the previously unused Greek letter rho (ρ).
All three `dynamic2` norms require `tau > 0` and `rho > 1` and derive
`theta = tau*rho`, so `theta > tau` in every simulation. `theta` remains in
resolved/saved parameters as a derived value; change `tau` and `rho` to set the
observation window. Changing either recalculates `theta` on the next resolution.
Legacy inputs containing only `theta` must use `rho = theta/tau`; combinations
with `theta <= tau` cannot be reproduced under the new constraint.

Configured `dynamic2` scenarios now use `rho = 2`; their previous `theta <= tau`
values were outside the new constraint, so previous testing/custom/chaos labels
do not establish the behaviour of the changed scenarios. Historical CSV entries
and saved results are retained. The interesting-set runner rejects historical
`theta` overrides rather than silently changing their dynamics; use valid `rho`
entries for new runs. Batch reuse rejects results with missing/different `rho`,
`tau`, or derived `theta`.

The `dynamic2` sensitivity definitions sample `tau` from `[0.1, 10]`, `rho` from
`[1.1, 10]`, and `c_dyn` from `[0, 10]`. These are exploratory project ranges.
Sobol indices for `rho` describe the window ratio; previous indices for an
independently sampled `theta` need to be recomputed for this parameterization.

Each `sample_000000.jsonl` file records the actual worker start, zero-based
`sample_index` (matching `samples.csv`), full input parameters, sampled overrides,
worker PID and configuration. A second event records completion time and elapsed
seconds, or failure/interruption details. Full timestamps with timezone offsets
are stored in files; console messages display only `HH:MM:SS`.
`boundary_000000.jsonl` files provide the same information for the serial
zero-boundary checks, identifying the parameter set to zero.

An absent sample file means its start has not been recorded. A `started` event
without a terminal event indicates unfinished work: the process may still be
computing, or may have been killed/crashed. It does not prove an infinite loop.
Each simulation now has a **20-minute wall-clock limit**, including zero-boundary
checks. Override it with `--sample-timeout-minutes 20` (positive, finite minutes).
The timer starts when the worker begins the task, excluding queue and worker
startup time. The parent terminates an overdue process and replaces it as needed;
other workers continue. This also stops a solver stuck in native code. Existing
running analyses must be restarted to use the new mechanism.

Timeouts are recorded immediately in the individual log and in
`sample_diagnostics_<timestamp>/timeouts.jsonl`, with the sample index, full
parameters, start/end times and elapsed time. Raw `simulation_outputs.csv` keeps
every original row, with `status=timed_out` and missing metrics for timeouts.
Explicit ODE integration failures are also recorded and skipped, with
`status=failed` and missing metrics. `failed_sample.csv` accumulates their indices,
full parameters and error details; individual diagnostic files retain timestamps
and tracebacks. Unexpected errors still stop the main sample analysis.
`simulation_outputs.csv` also contains `simulation_success` (`1` for completed,
`0` for failed or timed-out samples), and `simulation_status.csv` combines this
status with the sampled parameter values for failure analysis. This status output
is separate from the seven active Sobol target variables; failed metrics are not imputed.

Indices use only complete Sobol blocks of `D+2` rows; one missing simulation
excludes its entire block. `sample_inclusion.csv` records block membership and
exclusions. When blocks are excluded, indices and rankings are labelled
**provisional** and carry a warning: parameter-dependent timeouts or numerical failures can bias them,
and their confidence intervals do not account for that selection bias. There is
no imputation. `analysis_status.json` and `metadata.json` record the retained
base sample size and excluded indices. With fewer than two complete blocks,
headed empty index/ranking files are written and the next scenario continues.
Two blocks are only a computational minimum, not evidence of convergence.
Boundary checks do not form part of the Sobol design.

Run checks with `python -m unittest support.tests.sensitivity.test_sensitivity_diagnostics support.tests.sensitivity.test_sensitivity_timeouts -v`.
