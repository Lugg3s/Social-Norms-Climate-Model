# Independent classification review

Date: 12 November 2026. Five separately tasked sub-agents reviewed the implementation
independently and read-only. They did not consult one another. This report records
their findings and the subsequent corrections; it is not empirical model output.

| Reviewer / focus | Finding | Resolution |
| --- | --- | --- |
| 1 — mathematical semantics | Early damping could override a constant-amplitude final regime. | Check persistent final-window oscillations first; keep earlier damping in `classification_transient_damping`. A growing final regime is not called persistent or damped from history alone. |
| 1 — mathematical semantics | Multiple low episodes could reuse the same old high episode as multiple collapses. | Another confirmed high episode is required to rearm collapse counting. |
| 2 — Sobol/storage integration | The live/archive metric-parity test assumed every metric was numeric. | Retain exact numeric parity checks and separately compare strings/undefined classification fields. |
| 2 — Sobol/storage integration | Chart rendering preceded Sobol reports and final metadata. | Numerical reports and metadata are persisted before rendering descriptive class charts. |
| 3 — time/events | A threshold entry exactly at the last timestamp was not marked pending. | Preserve terminal zero-duration episodes for censoring flags. |
| 3 — time/events | An unconfirmed recovery at the horizon was indistinguishable from no recovery attempt. | Add `recovery_pending_at_end` and `recovery_confirmed_at`. |
| 4 — oscillation robustness | Small rapid reversals could erase large slow cycles in the existing adjacent-extrema detector. | Add an optional minimum-reversal filter to the shared implementation, used by the classifier. Keep original Sobol targets on their existing algorithm and document the difference. |
| 4 — numerical thresholds | Floating-point time-weighted means could move constant x=0.05/0.95 into the intermediate class. | Apply a 1e-12 comparison tolerance; add irregular-grid counterexamples. |
| 3 — follow-up verification | A short final high could be called pending recovery despite an earlier confirmed recovery and no new collapse. | Check recovery status since the most recent collapse before marking pending recovery. |
| 4 — follow-up verification | Exact two-percentage-point agent swings could be lost through subtraction round-off. | Apply 1e-12 tolerance to the filtered detector's reversal and prominence comparisons; preserve legacy Sobol comparisons. |
| 4 — oscillation robustness | Long-period oscillations may not provide two complete cycles in a 100-year end window. | Keep unresolved rather than infer persistence; save end-window cycle count/period and an explicit reason. This remains a finite-observation limitation. |
| 5 — pipeline/provenance | Saved-Sensi batch plots could mix archived class values with phase maps recomputed under current rules. | Derived batch records consistently recompute current classes and record their definition in the manifest; source NPZ metadata stays intact. |
| 5 — documentation | Documentation required consecutive full cycles, exceeding the stated rule. | Require two complete cycles; consecutive half-cycles form each cycle. |
| 5 — CLI/tests | Missing CLI/default table and archived ODE/agent reclassification checks. | Add the SCRIPTS.md entry and real-model NPZ tests, with source-byte preservation and phase-map parity. |

All five reviews confirmed or supported keeping classification outside Sobol
targets and using explicit finite-horizon semantics. Integration/plot reviewers
confirmed that frequency denominators include all requested sampled runs, failure
categories remain separate, and boundary checks are excluded.

## Remaining methodological limitations

- Thresholds and the 100-year end window are project conventions. Test their
  sensitivity before substantive interpretation.
- Stored sampling resolution limits detectable cycles. Filtering small reversals
  does not recover dynamics that were never sampled.
- Two complete extrema-to-extrema cycles may require more than two physical
  periods within the observation window, depending on its boundaries.
- Low/high classes describe the stationary end window without detected
  oscillations. The separate collapse event requires a preceding high episode.
- Finite-window stationarity and persistence do not prove asymptotic stability,
  absence of damping, or permanence. Chaos and tipping points are not inferred.
- Class frequencies describe the chosen Sobol design and parameter ranges,
  not real-world occurrence probabilities or independent-trial frequencies.

## Validation

Targeted tests cover stationary thresholds, historical exclusion, short windows,
one versus two cycles, clear growth/damping/persistence, a persistent tail after
initial damping, small fast wiggles, irregular sampling, invalid samples,
continuous and annual event durations, repeated-event rearming and horizon
censoring. Integration tests check unchanged numeric Sobol inputs/inclusion,
classes without trajectory saving, all-row denominators and actual ODE/agent NPZ
reclassification without new simulations or source changes. An example vertical
bar chart was rendered and visually checked for readable English labels.

The complete suite passed 197 tests plus 109 subtests. Follow-up counterexamples
were added to the targeted classifier tests and rechecked after the final fixes.

## Source recovery

On 12 November 2026, `analysis/trajectory_classification.py` was found missing
from the working folder. A saved Git snapshot and the Python cache establish
that it previously existed; the available records do not identify what removed
it. The snapshot was restored and all reviewed corrections reapplied. All compiled
code-object fingerprints match the last tested cached implementation (ignoring
source-location metadata); the restored file has the recorded 13,547-byte size.
After recovery, 31 targeted tests plus 13 subtests passed, including actual Sensi
execution and archived trajectory handling. Sensi and classification CLI help
also load successfully again.
