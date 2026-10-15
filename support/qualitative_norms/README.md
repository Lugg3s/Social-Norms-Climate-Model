# Normen-Werkbuch

Private, buildless web interface for qualitative work on the ten distinct active
norm types in `model/model_equations.py` / `config/scenarios.json`. All interpretation fields
start empty. Only the fictional Reusable Cups case and mathematical definitions
are supplied. Equivalent testing configurations are not separate norm types;
disabled/unimplemented norms are omitted. No model parameter or equation is changed.

Open `dist/index.html` directly in a browser or run, from the model repository:

```powershell
python support/qualitative_norms/serve.py
```

Notes are saved in localStorage in this browser/origin. Export JSON for portable
backup and import; Markdown exports the written notes. Different origins (local
file, localhost, hosted Site) have separate browser storage. Restore an exported
JSON file to transfer notes. Invalid backups leave current notes intact; valid
imports require confirmation. There is no server-side database or external CDN.

After the repository reorganization, direct `file://` opening uses a new file
URL under `support/qualitative_norms/`. If you used the old file URL, export a
JSON backup from an existing old browser tab and import it at the new location.
Serving on the same `http://127.0.0.1:8765` origin preserves that origin's notes.

While you scroll through notes and parameters, the equation remains visible in
a reference column on the right. On narrower screens it stays above the writing
area. Definitions and paper references scroll separately within the formula
card; the main equation remains visible. Equations use the display aliases
`tf = temperature_factor` and `sf = social_norm_factor` and stay on one line.
The reference column is wider and the equation font adapts down to 14 px; very
narrow screens can scroll long equations horizontally. The original Python
parameter names and saved-note keys remain unchanged.
The toolbar height is measured so that
neither wrapped buttons nor zoomed text cover the equation. Printing returns to
a single column. Existing notes and backup files are unchanged.

Approval now uses only `sf*x`; its redundant `alpha` parameter card has been
removed. When loading older browser notes or JSON backups, any written alpha
notes are retained, labelled, in the corresponding sf fields. Note keys for
active parameters and the backup version remain unchanged.

Likewise, standalone `Static injunctive` now uses `sf*(x_target-x)` without its
own `c_inj` card. Older static c_inj notes migrate, labelled, into sf notes.
Combined norms keep their c_inj fields, notes and formulas unchanged.

The complete x equation uses each norm term explicitly. The temperature response
and dynamic perception/delay definitions are provided separately. Actual model
time, historical-phase rule, zero-reference guard and annual agent decisions are
retained. `T` stays the original climate variable; its proposed analogy is a blank
exercise field, not a silently modified model. BI stays continuous; actual
behaviour is binary. The case describes decision phase t >= 217 as market entry.

Paper links are defined in `dist/papers.js` and shown below each norm equation.
Each reference records its provenance in code, README or Anara, and whether it is
a direct code reference, a structural/parameter analogy, a review example or
conceptual background. Composite, target-value and delay formulas without a
verified direct reference are labelled accordingly. Links open in separate tabs.
Markdown exports include the references; interpretation fields and the v1 note
backup schema are unchanged. No Anara library documents are uploaded or embedded.

From `support/qualitative_norms/`, run `npm.cmd run check` and `npm.cmd test`.
Browser QA uses an isolated
headless Edge profile through the built-in DevTools protocol, without installing
dependencies or touching the user's browser profile.
