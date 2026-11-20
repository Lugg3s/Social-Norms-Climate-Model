# Behavioural classification

`analysis/trajectory_classification.py` supplies the shared batch/Sobol classifier.
All labels and plots are in English. Chaos and tipping points are excluded.
This is a descriptive finite-horizon classification, not proof of equilibrium,
asymptotic stability, irreversibility, or a bifurcation.

## Windows and precedence

- Exclude the prescribed historical period: evaluate only `t >= 217` (2017).
- Require a complete 100-year post-historical end window for a definitive class.
  Shorter observations are `Transitional / unresolved`, with diagnostics retained.
- Detect oscillations over the entire post-historical trajectory first. Two
  complete qualifying cycles are required. Each uses consecutive half-cycles. A qualifying half-cycle
  has peak-to-trough swing at least `max(0.02, 0.05 * range(x))` in the evaluated
  window. The shared metric implementation is called with reversal filtering:
  a turning point is confirmed only after a reversal of this size, so small
  counter-movements do not interrupt a large cycle. Window-boundary extrema and
  final unconfirmed reversals do not form complete cycles.
- Oscillatory trajectories cannot enter a class labelled "no oscillation
  detected", even when they have settled by the end. Their final state is
  recorded independently in `classification_end_state`.
- Without detected oscillations, stationary means `max(x)-min(x) <= 0.02` over
  the full 100-year end window. Use the time-weighted mean of that window for
  low (`<=0.05`), intermediate (`0.05 < mean < 0.95`), or high (`>=0.95`).

## Exclusive classes

| Class | Rule after sufficient observation |
| --- | --- |
| Average x ≤ 5% over the last 100 years | No qualifying oscillations; stationary low end window. A previous high state is not required. |
| Average x ≥ 95% over the last 100 years | No qualifying oscillations; stationary high end window. No S-shape is inferred. |
| Stable intermediate level (no oscillation detected) | No qualifying oscillations; stationary intermediate end window. "Stable" describes this observation window only. |
| Damped oscillations | After checking for persistent/growing end-window oscillations: at least two complete post-historical cycles; `log(A_initial/A_final) >= 0.15` and positive fitted `damping_rate`. Amplitudes are median half-cycle amplitudes in the first/second halves of detected swings. |
| Persistent oscillations (within observation window) | At least two cycles in the 100-year end window, with `abs(log(A_initial/A_final)) <= 0.15` there. Takes precedence over earlier damping, which remains in `classification_transient_damping`. Weak amplitude trends within this tolerance are allowed. |
| Transitional / unresolved | Insufficient observation, continued drift, growing oscillations, or oscillatory behaviour not meeting the above rules. |

One observed cycle does not meet the detector's two-cycle requirement. Thus "no
oscillation detected" means that this requirement was not met, not that the
trajectory is mathematically monotonic. Sub-threshold swings are also possible.
Oscillation detection is limited by the stored output resolution. Slowly varying
cycles may not fit into the observation window; irregularity does not imply chaos.

Thresholds and windows are project conventions, not empirical estimates. Compare
alternative thresholds/windows before drawing robust substantive conclusions.

## Separate collapse/recovery events

These are additional metadata, not exclusive classes or Sobol targets:

- A high episode is continuous `x >= 0.8` for at least 20 years.
- A collapse event requires a later continuous `x <= 0.2` episode for at least
  20 years. `collapse_time` is the start of that low episode;
  `collapse_confirmed_at` is 20 years later. `collapse_duration` is the interval
  from leaving the most recent qualifying high episode to entering the low one.
- `collapse_count` counts confirmed high-to-low transitions. A new qualifying
  high episode is required before another collapse can be counted. Repeated
  events can belong to oscillatory trajectories.
- Recovery requires a subsequent qualifying high episode; `recovery_time` is its
  start; `recovery_confirmed_at` is 20 years later. `low_until_end` describes only
  the observation horizon, not permanence.
- `collapse_pending_at_end` flags an ongoing, still-too-short low episode after
  a qualifying high. `recovery_pending_at_end` is the corresponding flag for
  an unconfirmed high episode after a collapse. Terminal entries with zero
  observed duration can also be pending. Undefined event times remain missing,
  never artificial zero.
- Continuous ODE output is interpolated linearly; annual agent behaviour is
  held constant until its next observed decision. Durations use actual years,
  not sample counts. Missing/nonfinite data are never silently bridged.

## Saving and plots

Every new Sensi sample stores `behaviour_class`, `classification_version`, its
reason, window/cycle diagnostics and event fields in `simulation_outputs.csv`.
They are also in NPZ metadata if time-series saving is enabled. Classification
still works with `--no-save-time-series`.

Per scenario, the Sensi also writes:

- `behaviour_classes.csv`: sample IDs, status, classes and classification/event diagnostics.
- `behaviour_class_frequencies.csv`: counts and relative frequencies.
- `behaviour_class_frequencies.svg` and `.png`: one vertical bar per class.
- `metadata.json`: versioned settings and definitions.

After all scenarios finish, `klassifikationen_alle_normen.svg` in the run root
combines every norm's class-frequency chart and available without-norm comparison
charts. Each norm has one section; all charts retain their native vector size,
category labels, colours and denominator. Appending includes earlier scenario
charts as well. The standalone plotting command writes the same overview into
its output root for the selected norms, without simulations or source changes.

The denominator is **all requested Sobol sample rows**, including failed/time-out
rows, independently of which complete blocks enter Sobol estimation. Boundary
checks do not enter these frequencies. Failures/invalid/unavailable classifications
appear separately; they are never assigned a behavioural outcome. All six ordinary
classes remain visible even when empty. Shares reflect the chosen sampling ranges
and design; they are not real-world probabilities or independent Bernoulli trials.

The seven existing Sobol outputs and their definitions are unchanged. In particular,
the existing Sobol oscillation metrics retain their whole-simulation window and
original adjacent-extrema detector. The classification has a separate
post-historical window and the additional reversal filter; raw
`n_oscillations` and `classification_complete_cycles` can therefore differ.

## Paired comparison with norm influence removed

New sensitivity runs enable this comparison by default; use
`--no-compare-without-norm` to disable the additional reference simulations.
`analysis/no_norm_comparison.py` defines the audit profile, reference inputs,
comparison categories, and frequency plots. This is a separate descriptive
classification alongside `behaviour_class`, not a new exclusive behavioural
class or a Sobol output. Reference failures never affect original Sobol inclusion.

### Shared design and reference reuse

`analysis/sensitivity/shared_sampling.py` creates one Sobol design over all global
range coordinates plus explicitly added range overrides. Each norm projects the
same A and B rows onto its own parameter columns, then constructs the usual
A/AB/B blocks in that norm's parameter order. Bounds and N*(D+2) row counts remain
unchanged; no columns are replaced after independent sampling. In the default
configuration all continuous norms' temperature_factor/beta/kappa combinations
are covered exactly by the N*5 no-norm runs. Additional norm-only hybrids reuse
the same A reference. Shared coordinates also align other shared parameters.

When selected, `No social norm` is executed before other scenarios, regardless
of CLI order. Selection itself is preserved. Its ordinary sample outputs populate
the shared cache even when comparison plots are disabled; boundary checks do not. If no no-norm scenario is selected, or
a custom scenario changes physical/initial inputs, only missing unique controls
are simulated. Repeated controls within or across norms are deduplicated.

`reference_cache.sqlite3` is accessed by the parent process, never by workers.
Keys use effective reference inputs (ignoring only configured norm-only fields
for ODE controls), actual simulation settings, timeout budget, numerical package
versions and hashes of model/classification code and emissions data. ABM controls
use a separate model identity and are labelled `Agent model without social influence`.
Completed controls are preferred over failed duplicates. Failed/timed-out controls
can be reused as unavailable comparisons and never invalidate the original sample.
Metric-only results are reusable without archives; if archives are newly requested,
a metric-only cache entry is recomputed to provide the requested time series.

`sampling_design.json` and `sampling_AB.npz` preserve the exact design and checksum.
Append operations require identical N, seed and range configuration and reuse the
stored values. A legacy folder without this design is not silently extended using
new sampling. Existing artifacts are preserved. Sampled values differ from legacy
independent designs, so old and new estimates need not match exactly at finite N.
Pooled regression-tree validation already holds equal block indices across norms
together, preserving separation of these now-shared A/B blocks between train/test.

Copy the entire run, including A/B files, SQLite cache and source scenario folders.
Per-row `norm_comparison_reference_*` fields identify the source scenario, sample,
cache key, model and reuse flag. Archive paths can refer to another scenario within
the same run. Metadata distinguishes additional simulations from reused references.

### Per-pair rules

- Each successful sample gets its own reference with identical effective inputs,
  initial conditions, forcing and solver settings. ODE references switch only
  `social_norm` to `No social norm`; all other inputs, including kappa, remain.
  Agent references keep the annual decision model, costs, peers, agent count and
  seed, and set only `eta=0`. Comparing the ABM to the configured replicator-based
  `No social norm` scenario would also change the decision mechanism and require
  an arbitrary kappa, so it is deliberately avoided. Explicit `No social norm`
  samples reuse their own results instead of simulating again.
- Both trajectories evolve their own climate. Thus the comparison includes
  indirect climate feedbacks, rather than holding the temperature path fixed.
- First reaches use the existing low/high thresholds: x <= 0.05 and x >= 0.95,
  after t=217. A threshold already satisfied at the observation start counts at
  that start. These are first reaches, not the stationary-end-state test or the
  separate 20-year collapse-event persistence test. ODE crossings are linearly
  interpolated; ABM decisions retain their exact step times.
- Timing labels are `Earlier`, `Later`, `Equal`, `Reached with norm; not reached in reference`,
  `Not reached with norm; reached in reference`, `Neither reached`, and `Not comparable`.
  The reference is the matched ODE without social norms, or the matched ABM with eta = 0.
  Old saved labels are translated for plots without changing their numerical definitions.
  "Not reached" always refers to the finite common observation horizon.
- The change metric is `max(abs(x(y+1)-x(y)))` over complete integer-year
  intervals after t=217. ODE values are linearly interpolated at year boundaries;
  agent behaviour is held until the next decision. This is an annual change,
  not an instantaneous derivative or a rolling one-year maximum. Intrayear
  peaks can therefore be missed. No 10%-90% passage is required, so monotonic
  increases from the standard x0=0.3 are eligible.
- Save its positive magnitude in the existing `comparison_profile_slope` field,
  its sign in `comparison_profile_signed_annual_change`, its direction and the
  interval in `comparison_profile_slope_start`/`comparison_profile_slope_end`.
  Units are fraction per year (multiply by 100 for percentage points per year).
  For exactly tied maxima, retain the earliest interval. Magnitudes <=1e-12
  are numerical zero with direction `Stationary`.
- Constant trajectories have zero change and can be compared with nonzero
  changes. Opposite nonzero directions remain a separate category. Detected
  oscillations, invalid trajectories and observations without a complete
  calendar-year interval have no comparable change; timing remains independent.
- Comparison protocol version 3 replaces the former full-passage metric.
  New comparisons cannot be appended to a run with enabled older comparison
  definitions. Reference-cache source hashes also prevent stale reuse. Plotting
  saved older results retains their original metric label and does not recompute
  their comparison values.
- Slope labels are `Steeper`, `Flatter`, `Equal`, `Opposite directions`, and
  `Not comparable`, with the per-run reason retained.
- Timing equality uses an absolute tolerance of 0.0001 years. Slope equality
  uses `rtol=0.0001`, `atol=1e-8` fraction/year. These numerical tolerances are
  explicit project conventions, not claims of empirical equivalence.
- Nullable binary fields encode True for earlier/steeper and False for
  later/flatter. All other categories have missing binary values and must be
  interpreted through their categorical labels, never coerced to False.

The original outputs, Sobol estimates and metadata are saved before additional
references start. Missing unique references have `reference_<sample_index>.jsonl`
diagnostics, separate per-simulation timeouts, and (if enabled)
`reference_<sample_index>.npz` archives. Reused references point to their original
sample/archive, including files from the no-norm scenario. Boundary checks are not compared. Final paired columns use the prefix
`norm_comparison_` in `simulation_outputs.csv` and `behaviour_classes.csv`.
`without_norm_outputs.csv` contains reference metrics/statuses and sample IDs;
`without_norm_comparisons.csv` contains pairwise diagnostics. NPZ archives contain
the individual transition profiles (`comparison_profile_`), while final paired
comparisons live in the CSVs. Metadata records the protocol and reference count.

`without_norm_comparison_frequencies.csv/.svg/.png` reports three panels per norm:
low-threshold timing, high-threshold timing and transition speed. All requested
sample rows form the denominator, including unavailable comparisons. These shares
describe the sampling design, not real-world probabilities. The existing
classification plotting command also recreates these panels from saved comparison
columns without rerunning any model. Older runs without matched references cannot
acquire these comparisons merely by reclassifying a single archived trajectory.

Recreate plots without simulation:

```powershell
python -m analysis.behaviour_classification_plots --input-root "E:\Masterarbeit\Sensitivity\<run>"
```

For older runs with saved NPZ trajectories, add `--reclassify`. This saves derived
results separately and preserves original data and historical definitions.
The saved-Sensi batch renderer also records its current classification definition
and recomputes derived classes consistently, while leaving source archives intact.
