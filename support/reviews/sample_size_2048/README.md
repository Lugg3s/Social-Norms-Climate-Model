# Sample-size assessment: 2048 base samples

Date: 2026-11-19. Source: `E:/Masterarbeit/Sensitivity/job-3311884_samplsize2048/job-3311884/2026-11-19_04-50-55`.

Conclusion: N=2048 supports broad rankings for mitigation and climate outputs in this run, but is not a general guarantee of precise Sobol indices. It is not demonstrably excessive. Oscillation frequency for the combined dynamic norms remains poorly resolved.

## Method and precision goals

All 10 norms, all 7 saved targets, intact nested Saltelli prefixes N=256, 512, 1024 and 2048. No simulations were repeated and no failed rows were removed. Bootstrap: 500 resamples, seed 42, approximate 95% confidence half-widths. Strict exploratory goals: maximum change <=0.03 and maximum half-width <=0.05 for both S1 and ST, across every parameter. These are declared project precision goals, not a published universal sample-size requirement.

At N=2048, 58 norm-output pairs have nonconstant responses; 12 are constant oscillation outputs and cannot yield informative variance-based sensitivities. Of the 58, 47 have maximum ST change <=0.03 and 48 have maximum S1 change <=0.03 compared with N=1024. The top-three ST parameter set is unchanged in 56/58 pairs; this says nothing about the ordering within that set or separation of near ties. Only 5/58 pairs meet both strict all-parameter precision goals.

| Target | Largest ST change, 1024 to 2048 | Largest 95% ST half-width at 2048 |
| --- | ---: | ---: |
| `bool_x95` | 0.044 | 0.069 |
| `cumulative_emissions` | 0.023 | 0.062 |
| `final_temperature` | 0.026 | 0.061 |
| `first_time_x95` | 0.062 | 0.075 |
| `oscillation_occurrence` | 0.089 | 0.106 |
| `oscillations_per_500_years` | 0.279 | 0.964 |
| `x_mean` | 0.021 | 0.061 |

The maxima are over the norms and their parameters, so the maximum change and maximum half-width may refer to different parameters. Confidence half-width 0.05 means ST +/- 0.05, not a 5% relative error.

For Descriptive, injunctive, dynamic2, the oscillation-frequency ST estimate for tau is 1.261 +/- 0.955. The theoretical population index is bounded by 1; this noisy finite-sample estimate is not clipped. Treat precise parameter ordering for this target as unresolved.

## Recommendation

- Keep the completed N=2048 dataset. For qualitative ranking of x_mean, final_temperature and cumulative_emissions, increasing every norm uniformly has limited demonstrated benefit: maximum ST changes are below 0.03 here.
- Do not describe all outputs as converged. Threshold timing and oscillation metrics require more caution. Larger N and independent scrambling replicates are useful for these particular targets; no specific larger N is guaranteed to suffice.
- Independent scrambling replicates test sampling robustness. ABM seed replication separately tests stochastic population/network robustness. Solver, time resolution, horizon and classification-threshold sensitivity remain separate issues.
- Constant oscillation outputs mean no events were observed in this sampled region/window. They do not prove oscillations are impossible.

Nested prefixes are statistically dependent, not independent replications or independent validation. Bootstrap intervals are approximate diagnostics for this QMC design; they do not quantify model-structure, numerical or parameter-range uncertainty.

## Reproduce

```powershell
python -m analysis.sensitivity.sample_size_review --input-root "E:\Masterarbeit\Sensitivity\job-3311884_samplsize2048\job-3311884\2026-11-19_04-50-55" --output-root support/reviews/sample_size_2048
```

- [Summary table](sample_size_summary.csv)
- [All indices](indices_by_sample_size.csv)
- [Settings](review_settings.json)

Sources checked on 2026-11-19: [SALib estimator and bootstrap implementation](https://salib.readthedocs.io/en/latest/_modules/SALib/analyze/sobol.html); [SciPy on independent randomized-QMC replications](https://docs.scipy.org/doc/scipy/reference/stats.qmc.html).

## Plot-language audit

Sensitivity ranking charts, formula annotations and combined overview now use English. Existing active regression-tree renderers still contain German labels in `analysis/regression_trees/regression_tree_analysis.py` and `analysis/regression_trees/regression_tree_plots.py`. The historical specialised `analysis/sensitivity/sensitivity_review.py` also contains German report/plot text. Those renderers were inspected but not edited in this task. Previously generated images are not automatically translated; the N=2048 sensitivity charts were regenerated explicitly.


## Cause investigation (20 November 2026)

The main identified source of the large oscillation-frequency uncertainty is concentration of the Sobol estimator on a small tail of high-cycle responses, especially for Descriptive, injunctive, dynamic2. The targeted checks do not support the terminal oscillation phase as the main explanation for the large frequency-index uncertainty. They do show that phase matters greatly for the single endpoint x and that small boundary/numerical cycle-count effects exist.

### Direct decomposition of the saved estimator

The total-order estimator uses `mean((A - AB_j)^2) / (2 * var(A,B))`. Both the squared-difference numerator and the A/B variance denominator can therefore be dominated by a few large responses.

- Dynamic2 combined norm: only 69 of 24,576 sampled rows have at least 20 cycles. The maximum is 110 cycles, while the median positive response is just 2 cycles (1.667 per 500 years). These are descriptive counts within the dependent Saltelli design, not independent population frequencies.
- For tau, the largest one of 2048 blocks supplies 31.13% of the squared-difference numerator; the largest five supply 70.38%.
- One of the 4096 A/B responses supplies 38.91% of the estimated A/B variance; the largest five supply 69.85% and the largest ten 85.25%.
- Between N=1024 and N=2048, the tau numerator mean falls from 6.1913 to 5.6663, while the A/B variance falls more strongly, from 6.3072 to 4.4944. Their ratio ST therefore rises from 0.9816 to 1.2607. This is a sampling/composition effect in a tail-sensitive ratio estimator.
- In the 500 block-bootstrap resamples, the most influential c_dyn numerator block is omitted 181 times, included once 193 times and included at least twice 126 times. The corresponding mean ST values are 0.406, 0.703 and 1.161. This directly shows how varying the weight of one rare high-response block changes the estimate.
- For the other combined norm, Descriptive, injunctive, dynamic, one block supplies 38.50% of the kappa numerator. Thus the same concentration mechanism also affects its frequency estimate, though its A/B denominator is less concentrated.

[Distribution and influence figure](oscillation_diagnosis/tail_and_influence.png).

### A paired physical example rather than an endpoint-phase difference

In the dynamic2 combined norm, rows 9480 and 9489 differ only in tau:

| Sample | tau (years) | Saved complete cycles | Median period (years) |
| --- | ---: | ---: | ---: |
| 9480 | 0.127641 | 102 | 3.75 |
| 9489 | 6.976529 | 0 | Not defined |

All other parameters are identical. The first trajectory is persistently oscillatory; the second has a slowly varying intermediate end level. Moving the observation endpoint within a cycle cannot turn the first trajectory's 102 cycles into the second trajectory's zero cycles. This is a change in the model's response to the delay parameter within the finite observation horizon.

The cases with at least 20 cycles have median tau approximately 0.244 years, compared with 5.050 across all sampled rows. Short-delay, rapidly oscillating responses occupy a small part of the sampled range. This association is descriptive; the paired tau example provides the controlled comparison.

### Targeted numerical and phase checks

Because the original run saved no full trajectories, four influential parameter sets were resimulated to 620 years. Metrics below use only years 0-600, matching the original analysis. The extra 20 years support translated observation windows. Twelve runs were performed: saved settings, denser output/history, and refined coupling. Source parameters and settings came from the saved run, not current defaults.

| Norm / sample | Saved settings: coupling 0.1, requested output 24/year | Dense history: coupling 0.1, output 200/year | Refined coupling: 0.025, output 200/year |
| --- | ---: | ---: | ---: |
| Dynamic2 combined / 9480 | 102 | 102 | 102 |
| Dynamic2 combined / 9489 | 0 | 0 | 0 |
| Dynamic2 combined / 3524 | 78 | 78 | 78 |
| Dynamic combined / 7583 | 24 | 24 | 23 |

The four baseline cycle counts reproduce the saved counts exactly. Maximum baseline final-x discrepancy is 1.40e-6. The prominent-reversal/post-2017 classifier gives 101, 0, 77 and 23 cycles respectively, unchanged across all three numerical variants. It uses a different window and detector, so these numbers are a robustness check, not identical definitions.

For delayed models, changing output density also changes the stored interpolation history, so the dense-history run is not a pure observation-only test. A separate test resampled each already-computed trajectory on fixed 0.05/0.1/0.25/0.5-year observation grids: counts were stable at the first three spacings in these cases; the coarse 0.5-year grid lost one cycle in two variants of sample 9480.

Shifting a 100-year end window through up to one median period (capped at 10 years) gives:

- Sample 9480: 26 cycles for every tested shift and numerical variant, while endpoint x under saved settings ranges from approximately 0.622 to 0.958.
- Sample 3524: 20 cycles for every tested shift and numerical variant; endpoint x ranges from approximately 0.003 to 1.000.
- Sample 7583: 6-7 cycles, demonstrating a real one-cycle boundary effect.
- When the entire history is evaluated up to shifted endpoints near 600, the two fast dynamic2 cases vary by one cycle (102-103 and 78-79), not by tens of cycles. These are slightly different horizons, not independent phase-shifted replications.

[Phase check figure](oscillation_diagnosis/phase_check.png).

### Role of the minimum-cycle rule and extreme responses

Removing the two-cycle gate changes the maximum 1024-to-2048 ST difference for the dynamic2 combined norm only from 0.279 to 0.274. Thus this gate is not the main source of that norm's large sample-size instability. Boundary effects can still matter for cases close to two cycles and for binary oscillation occurrence; this investigation does not establish the cause of every binary-index uncertainty.

As diagnostic changes to the response, log(1+rate) and capping at the 99th percentile reduce the maximum ST change to approximately 0.071. They answer different questions and are not replacements or corrections to the original target. Their behaviour supports the diagnosis of tail leverage. No original target, classifier, parameter range or model equation was changed, and no extreme cases were removed from the actual sensitivity analysis.

### Scope and audit trail

The numerical checks concern four deliberately influential cases, not all 2048 base blocks or every solver/seed. They support the absence of a gross numerical counting artefact in those cases; they do not prove numerical convergence of the full design. Other individual cases may still be numerically or threshold sensitive. The stored [audit checks](oscillation_diagnosis/audit_checks.json) confirm source-file hashes, reproduction of the saved indices and baseline counts, and the single-parameter difference of the tau pair.

Tables: [distribution](oscillation_diagnosis/distribution.csv), [numerator contributions](oscillation_diagnosis/contributions.csv), [denominator concentration](oscillation_diagnosis/denominator_concentration.csv), [influential rows and parameters](oscillation_diagnosis/influential_rows.csv), [bootstrap groups](oscillation_diagnosis/bootstrap_groups.csv), [response-definition stress tests](oscillation_diagnosis/response_stress.csv), [numerical probes](oscillation_diagnosis/numerical_probes.csv), [phase windows](oscillation_diagnosis/phase_windows.csv), [observation-grid checks](oscillation_diagnosis/observation_grid.csv).

The `phase_bounds.csv` table additionally gives deliberately conservative analytic bounds for arbitrary row perturbations of one cycle, or two cycles when the detection gate is crossed. Those bounds are stress bounds, not estimated confidence intervals or proof of how real phases behave.

The two historical reproduction scripts are documented in SCRIPTS.md. Probe archives are compact diagnostic t/x/T arrays and metadata, not the batch-run archive schema. Existing archives are reused after checking their parameters/settings; they remain historical numerical results, not a fresh validation after future model-code changes.
