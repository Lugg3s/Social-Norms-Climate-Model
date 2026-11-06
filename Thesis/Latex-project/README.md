# Master's thesis LaTeX project

This layout is adapted from `thesis_CG_template_v173/thesis_CG.cls` and
`unilogo.jpg` in the supplied `Bachelorarbeit.zip`. It preserves the bachelor
project's 11 pt Computer Modern typography, A4 two-sided layout, right-hand
chapter starts, 16 x 21 cm type area, 0.75 cm binding correction, paragraph
spacing, caption styling, running headings and title-page hierarchy.

The project uses English and UTF-8. The logo is copied without changes.
The eight existing thesis sections remain in `chapters/`; no bachelor thesis
text, results, figures, references or supervisor details have been imported.

## Writing style

Follow [Writing-style-guide.md](../Writing-style-guide.md) when drafting or
revising thesis text. It preserves the explanatory, concrete and reasoned
approach of the bachelor thesis in natural academic English. The detailed
German analysis and source evidence are in
[Writing-style-analysis.md](../Writing-style-analysis.md).

## Files to edit

- `metadata.tex`: title, short title for the footer, author, institute/research
  group, supervisors, submission date, and place/date for the signature.
  Bracketed fields are placeholders, not confirmed thesis details.
  The cover date automatically uses the current English month and year when
  LaTeX compiles the document.
- `chapters/*.tex`: the thesis text, ordered by `main.tex`.
- `frontmatter/declaration.tex`: space for the applicable declaration and
  signature; the old bachelor declaration has not been copied.
- `references.bib`: verified references, included through
  `\bibliography{references}` in `main.tex`. The class
  retains the original numerical `abbrv` BibTeX style (the bachelor class's
  `alpha` option also selected `abbrv`).
- `thesis_master.cls`: shared formatting derived from the bachelor class.

Roman numerals are used before the main text, which starts at Arabic page 1.
Blank verso pages are intentional in the original double-sided layout.
The full title is used on the cover; the separate short title prevents a long
master's thesis title from overflowing the running footer.

## Build and preview

From this directory:

```powershell
latexmk
```

The PDF is written to `build/main.pdf`; SyncTeX data is generated for the
LaTeX Workshop preview. Generated files under `build/` are ignored by Git.
LaTeX Workshop can use `latex-workshop.latex.outDir = "%DIR%/build"` and
`latex-workshop.latex.autoBuild.run = "onFileChange"`.

This adapts the supplied layout; it does not establish current departmental
requirements for the master's thesis.
