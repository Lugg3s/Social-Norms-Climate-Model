# Social Norms Climate Model

This repository contains the computational model developed as part of a Master's thesis. It investigates how social norms and peer influence can affect climate-mitigation behaviour and its interaction with a climate/emissions model.

## Contents

- `agent.py` — agent-based social-norm layer and peer interactions
- `model_equations.py` — climate and behavioural model equations and scenario handling
- `batch_runner.py` — batch simulations
- `main.ipynb` — main notebook for running and exploring the model
- `plotting.py` — visualisation utilities
- `make_plot_videos.py` — generation of plot videos
- `scenarios.json` — model parameter scenarios
- `global.1751_2017.csv` — emissions data used by the model

## Status

The code is part of ongoing Master's thesis research and is therefore subject to change.

## Reproducibility

The model is implemented primarily in Python and uses NumPy, pandas, SciPy, and Jupyter notebooks. Parameter scenarios are defined in `scenarios.json`.

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
params["theta"] = h
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
Output between integration nodes uses linear interpolation. Agent updates
still occur at coupling boundaries. RK4 stores delayed `x` history at every
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

Integrator implementations and the `SOLVERS` registry live in `solvers.py`,
separate from model equations and coupling logic, for future solver additions.
Run checks with `python -m unittest test_solvers -v`.

## Model performance

Shared carbon fluxes are computed once per right-hand-side evaluation and reused
in the four carbon equations, preserving each equation's arithmetic order.
Fluxes are never reused between solver evaluations or RK stages.

Delayed-state interpolation reuses NumPy arrays of the existing history. These
arrays are invalidated whenever history is extended or pruned, including after
every accepted RK4 step. The interpolation formula, samples, boundary behavior,
solver tolerances, and coupling/output intervals are unchanged.

Run solver and history-update checks with
`python -m unittest test_solvers test_model_optimizations -v`.

## Runtime profiling

`python profile_dynamic_norms.py` profiles representative baseline and dynamic
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

Results are saved under `profiling_results/<timestamp>/`: each case contains
`profile.prof`, a readable `profile.txt`, function timings in `functions.csv`,
interval timings and solver counters in `intervals.csv`, and `summary.json`.
`--max-seconds` bounds each case (default 60); time-limited cases retain partial
profiles. Cumulative function timings include child calls and overlap.

## Sensitivity sample diagnostics

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
python sensitivity_analysis.py --scenarios baseline --output-root plots/sensitivity_results
python sensitivity_analysis.py --scenarios "Dynamic social norm" --output-root plots/sensitivity_results --append-existing-folder 2026-09-24_10-00-00
```

The folder is resolved below `--output-root`. Supplying
`--append-existing-folder` enables
append mode and requires that the selected folder already exists.
Existing scenario results are never overwritten in append mode; trying to add a
scenario that is already present stops with an error. The overall top-parameter
file is rebuilt from all scenario result folders.

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

Run checks with `python -m unittest test_sensitivity_diagnostics test_sensitivity_timeouts -v`.
