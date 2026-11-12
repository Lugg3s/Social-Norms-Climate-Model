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
| Collapse to 0 (no oscillation detected) | No qualifying oscillations; stationary low end window. This retains the user's preferred descriptive name; a previous high state is not required. |
| Approach to 1 (no oscillation detected) | No qualifying oscillations; stationary high end window. No S-shape is inferred. |
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

Recreate plots without simulation:

```powershell
python -m analysis.behaviour_classification_plots --input-root "E:\Masterarbeit\Sensitivity\<run>"
```

For older runs with saved NPZ trajectories, add `--reclassify`. This saves derived
results separately and preserves original data and historical definitions.
The saved-Sensi batch renderer also records its current classification definition
and recomputes derived classes consistently, while leaving source archives intact.
