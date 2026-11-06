# Writing style for the master's thesis

This is the working style guide for English thesis prose in
`Thesis/Latex-project/`. It is derived from the complete chapter texts in
the supplied bachelor thesis, analysed in
[Writing-style-analysis.md](Writing-style-analysis.md) on 23 October 2026.
The detailed analysis distinguishes observed features from improvements.

The bachelor thesis is in German. These English rules preserve its
explanatory approach; they do not claim to reproduce a previously observed
English writing sample. Content and scope follow
[Chapter-overview.md](Chapter-overview.md).

## 1. Core voice

Write clear, concrete academic English that helps the reader understand
the problem, the mechanism and the reason for a modelling decision.
Keep the author's practical, step-by-step explanations and attention to
parameter effects. Retain technical depth without making the prose
unnecessarily abstract.

The typical reasoning sequence is:

> State the problem or requirement. Explain the mechanism. Describe the
> chosen representation. Explain its consequences and relevant limits.

Use this sequence when it helps the subject. It is not a compulsory
four-sentence template for every paragraph.

## 2. What to preserve

- Introduce a method through the problem it addresses.
- Explain why a modelling choice fits the research question.
- Introduce unfamiliar terms before relying on them.
- Explain equations in words and relate parameters to their effects.
- Use small examples to clarify a difficult distinction or boundary case.
- Compare approaches along concrete differences rather than listing them.
- Report the settings and limitations needed to interpret a result.
- Connect statements so the reader can follow the argument without guessing.

Do not preserve accidental spelling, punctuation or notation errors, heavy
repetition, unnecessarily long sentences, or unsupported generalisations
from the bachelor text. Its detailed code walkthroughs are useful examples
of explanation, not a requirement to narrate every implementation step.

## 3. Sentences and paragraphs

Put the central statement early in the sentence. Prefer ordinary technical
verbs such as represent, compare, calculate, increase, decrease, depend,
estimate and observe. Keep one main relationship per sentence when several
conditions would otherwise obscure it. Longer sentences are appropriate
when their structure remains easy to follow.

A paragraph develops one main question or claim. Start with that subject,
add the necessary explanation or evidence, and end with the consequence
when it is useful. Split the paragraph when the subject changes from a
general rule to a substantial exception or a different experiment.

Use connected prose for explanations. Use lists for genuinely parallel
requirements or steps, and tables for comparisons and parameter overviews.
Do not turn the thesis into a collection of disconnected bullet points.

Avoid excessive chapter announcements. A brief orientation is useful at
the beginning of a complex chapter. Subsequent transitions should explain
the connection between topics, rather than repeatedly saying that the next
section will explain the next topic.

## 4. Perspective and tense

Use an impersonal authorial voice by default, consistent with the bachelor
thesis: "This thesis compares ...", "The model represents ...", "The
analysis examines ...". Do not introduce autobiographical "I" or an
unnecessary authorial "we". This does not prohibit active sentences with
an informative subject.

Use active voice when the subject explains the mechanism: "The norm
reinforces the majority behaviour." Use passive voice when the procedure
or object matters more than the actor: "The parameters were sampled ...".
Do not mechanically convert every sentence to either voice.

| Purpose | Usual tense or wording |
| --- | --- |
| Mathematical property or current model definition | Present: "The term depends on ..." |
| Description of what a paper contains | Present: "The study represents ..." |
| Specific experiment or finding reported by another study | Past when appropriate: "The authors found ..." |
| Completed simulation procedure | Past: "The simulations were evaluated ..." |
| Referring to a displayed result | Present: "Figure ... shows ..." |
| Plausible interpretation | "may", "could", or "is consistent with", with a reason |
| Further research | Specific conditional proposal, not a promise |

## 5. Natural English and terminology

Use British English consistently: behaviour, behavioural, modelling,
analyse, normalisation and parameterisation. This is an editorial choice
for the English thesis. Keep paper titles, quotations, software identifiers
and existing code names in their original spelling.

Translate the function of German expressions, not their surface form:

| German tendency in the bachelor text | English treatment |
| --- | --- |
| "In dieser Arbeit ..." | "This thesis ..." when the reference to the contribution matters; otherwise name the actual subject |
| "Zunächst ... anschließend ..." | "First ... then ..." for a real sequence; avoid labelling every sentence |
| "Darüber hinaus / des Weiteren ..." | Continue the argument directly; use an explicit connector only when needed |
| "Besagter / jener Parameter ..." | Repeat the parameter name or use an unambiguous "this parameter" |
| "Dies führt dazu, dass ..." | Name the consequence directly when possible |
| "Da / aufgrund ..." | State a supported reason with "because" or another direct construction |
| "Es hat sich herausgestellt ..." | Name the observation or analysis that supports the finding |
| "Umso größer ..., umso ..." | State the direction, what is held fixed, and relevant conditions |

Do not replace repeated connectors with a rotating set of ornate synonyms.
Avoid stock expressions such as "it is worth noting", "delve into",
"leverage" as a generic verb, "a comprehensive and robust framework", or
"provides valuable insights" without saying what the insight is.
Do not force distinct terms into an "X, not Y" construction when no actual
misunderstanding needs to be addressed.

Prefer a repeated technical noun to an ambiguous pronoun. Use one agreed
term for each concept. Do not rename parameters or variables to improve
the prose. Explain their meaning alongside the existing notation.

## 6. Equations and parameters

The bachelor thesis explains mathematical objects and then walks through
their consequences. Preserve that approach:

1. State what is represented.
2. Define the needed variables and their units or domains.
3. Give the equation.
4. Explain the role of its terms in words.
5. Explain the relevant direction, threshold or timescale.
6. Add an example or limitation when it resolves a real difficulty.

Not every equation needs all six steps as separate sentences. Avoid
repeating definitions immediately after an equation if they were just
introduced.

For a parameter, identify its role, unit, reference quantity and the
conditions under which an increase has the stated effect. Distinguish a
direct effect at a fixed model state from a long-term outcome involving
feedbacks. A larger social influence coefficient or adjustment rate does
not by itself establish a monotonic improvement in mitigation.

Distinguish changes in levels, relative changes, and rates of change.
Distinguish a relaxation timescale from an exact time delay. Explain
thresholds using the actual inequality in the code. Preserve the distinction
between continuous behavioural intention and realised binary behaviour.

Check every model equation and parameter description against the current
code. Make clear whether a mechanism is taken from a paper, adapted from
it, or introduced in this project. An empirical study motivating dynamic
norms does not, by itself, validate a particular delay or relative-change
formula.

## 7. Literature and Related Work

Organise the chapter around mechanisms, modelling approaches and the
comparison question. The planned paper order is an argument structure,
not a requirement to write one isolated mini-summary per paper.

For a study, select only the aspects needed for that argument:

- What behaviour and environmental system does it represent?
- How is the norm derived and how does it affect behaviour?
- What modelling approach and aggregation level does it use?
- What relevant finding or limitation does it contribute?
- How does that connect to the next study or the present comparison?

Compare imitation, approval, intention motivation and dynamic signals
through their actual representations. ABM and aggregate differential
equations differ in more than their labels: describe relevant differences
in heterogeneity, interaction and decision rules.

Attach citations to the claims they support. Verify papers through the
available primary text, including Anara sources when relevant. Check
authors, title, year and publication version. Label preprints explicitly.
Do not invent references, empirical ranges or calibration claims.

For every future paper recommendation, check its citation count and report
the database, exact paper/DOI and retrieval date. Prefer well-cited,
academically credible sources, as requested by the user on 24 October 2026.
Use one citation database consistently within comparisons where possible;
identify differences in databases or publication versions. State when counts
are unavailable or include self-citations. Missing data are not zero citations.

Interpret citation counts alongside publication age, field, publication
status and methodological quality. Counts indicate indexed reception, not
proof of quality. Flag papers with limited citation histories and justify
their use where they directly underpin a model mechanism. Keep relevance
ratings separate from citation counts. No fixed citation threshold has been
agreed; do not invent an automatic exclusion rule.

Relevant papers with few citations may still be recommended, as explicitly
confirmed by the user on 24 October 2026. Label each such recommendation
visibly as **low citation count** (or **wenig zitiert** in German), report the
verified count with its source and retrieval date, and briefly explain its
relevance. Do not exclude a relevant paper solely because its count is low.

Scope statements such as "most models" or "few studies" to the evidence:
attribute a systematic review, identify the reviewed sample, or limit the
statement to the studies actually discussed. Do not claim that a topic
has never been modelled solely because it is absent from a small selection.

Detailed concept definitions belong in Theory; the implemented equations
belong in Model. Related Work explains what previous studies did and why
their similarities, differences and limitations matter for this thesis.

## 8. Results, interpretation and limitations

Explain which runs, norm variants, parameter ranges, output metrics and
evaluation periods support a finding. Refer to saved results rather than
inventing representative numbers. Use the actual metric name and its
definition; a convenient label must not change what was measured.

Separate the following kinds of statements through clear wording:

| Statement | Suitable wording |
| --- | --- |
| Model assumption | "The model assumes ..." |
| Published finding | "The study reports ...", with the source |
| Simulation observation | "Within the sampled range, ...", supported by the output |
| Mathematical consequence | Explain the derivation and its conditions |
| Interpretation | "A possible explanation is ...", with the mechanism |
| Unresolved issue | State what cannot yet be established |

Report observations before expanding their interpretation. Use the
Discussion chapter for broader implications and competing explanations.
Do not describe an association in sampled runs or a regression-tree split
as proof of a causal mechanism. Do not describe conditional model outcomes
as unconditional predictions of real-world behaviour.

Use "significant" in a statistical sense only when a corresponding
analysis supports it. Replace vague intensifiers such as "enormous",
"clearly better" or "only a small error" with a stated quantity, comparison
or bounded assessment.

For percentages, identify the denominator. Distinguish percentages from
percentage points. State what a standard deviation describes; it is not
automatically a range containing every observation or a confidence
interval. Describe missing, undefined or encoded metric values accurately.

Preserve the bachelor thesis's willingness to discuss difficult cases.
Give a limitation its practical consequence and identify an appropriate
next check. Avoid adding a generic limitations sentence to every paragraph.

## 9. Figures and tables

Use figures and tables as evidence in the explanation. State the main
pattern and why it matters, instead of merely announcing that a figure
exists. Do not repeat every tabulated value in the prose.

Captions should make the display interpretable: identify the quantity,
units, norm variants, relevant parameter settings, time interval and visual
encoding when needed. A caption can explain how to read a plot without
duplicating the entire discussion.

Keep observations about an illustrative run separate from conclusions
about the full sampled ensemble. Identify selection rules for shown cases
and report any uncertainty or aggregation actually displayed.

## 10. Chapter-specific application

| Chapter | Writing task |
| --- | --- |
| Abstract | State aim, approach, actual main findings and a bounded implication. Fill findings only when supported by results. |
| Introduction | Narrow the problem to the norm-formalisation comparison. Make the questions, contribution and scope visible early. |
| Related Work | Synthesise studies by mechanisms and model choices, then position the thesis. |
| Theory | Explain the concepts and mechanisms needed to understand the comparison. |
| Model | Explain the actual shared climate model and behavioural variants, with checked notation and assumptions. |
| Methods | Describe simulation settings, parameter ranges, metrics and analyses sufficiently for reproduction. |
| Results | Present supported patterns and comparisons with their evaluation conditions. |
| Discussion | Interpret findings, answer the questions and connect limitations to specific further work. |

Do not change the agreed chapter structure simply to reproduce the bachelor
thesis's combined chapters. Keep language, document structure and visual
formatting as separate decisions.

## 11. Constructed examples of the target voice

The examples below demonstrate phrasing. They are not manuscript inserts,
new simulation findings, or substitutes for checking the current model.

### Explaining a mechanism

> In the imitation variant, the descriptive norm depends on the current
> mitigation share. For a positive norm weight, it favours mitigation when
> more than half of the population mitigates and favours non-mitigation
> below this threshold. The norm therefore reinforces the majority
> behaviour.

This moves from definition to a condition and then to its interpretation,
as the bachelor text often does when explaining an algorithm.

### Explaining a parameter without overstating its effect

> In the replicator variants, a larger social learning rate scales the
> instantaneous change in the mitigation share at a fixed state. The
> direction of this change still depends on the combined incentive.

This preserves the author's interest in larger/smaller parameter effects
while stating what the equation actually establishes.

### Contrasting mechanisms

> The imitation term responds to the current mitigation share. The
> trend-based term instead responds to a change in that share. It can
> therefore provide a different signal while mitigation remains a minority
> behaviour.

The contrast is tied to a meaningful modelling difference, rather than to
a general claim that one approach is superior.

### Reporting a result once its evidence exists

> Within [the evaluated parameter range], [the specified metric] changes
> from [verified value] to [verified value]. Figure [reference] shows the
> corresponding trajectories. This pattern is consistent with [an
> explicitly justified interpretation].

Bracketed text is a drafting prompt. Replace it with verified information
or omit the sentence; never leave placeholders as apparent findings.

### Stating a limitation

> The comparison uses assumed parameter ranges rather than empirical
> calibration of every norm variant. The results therefore describe the
> behaviour of the specified model within these ranges.

Use such a statement only where it accurately describes the actual
analysis. A precise scope statement is more useful than a vague claim
that the study has limitations.

## 12. Drafting and review workflow

Before drafting, read this guide and the chapter overview, identify the
agreed section, and inspect the sources, code or results needed to support
its claims. Draft directly in the appropriate chapter file.

During revision, check that:

- The section advances its intended question and fits its chapter.
- Each paragraph has a clear subject and an understandable connection.
- Claims can be traced to sources, code, assumptions or results.
- Variables, units, conditions and reference periods are correct.
- Equations and numerical statements have explanations that add meaning.
- Findings are distinguished from interpretations and real-world claims.
- Unnecessary transitions, intensifiers and vague pronouns are removed.
- English spelling and technical terminology are consistent.
- No unsupported findings, citations or reasons have been added.

Preserve the user's agreed section scope and existing formatting unless a
change is authorised. Record lasting changes to writing preferences here.
The root `AGENTS.md` rules for editing `Masterarbeit.docx` still apply when
that document is edited; this guide does not replace them or create a new
automatic commit/push requirement for LaTeX files.

## 13. Length requirement and planning

The main text must contain **10,000–20,000 words**, excluding the title page,
contents and other lists, tables, figures and appendices. This requirement
was supplied by the user on 24 October 2026.

Use **approximately 15,000 words** as the initial drafting target. The
provisional chapter budgets are recorded in
[Chapter-overview.md](Chapter-overview.md). They are planning estimates,
not separate minimum or maximum lengths for each chapter.

Use broad page ranges rather than fixed page targets. These ranges describe
the approximate space occupied by the main chapters,
including their equations, figures and tables. They are not a conversion
rule for the required word count. Reassess the page estimates once several
representative chapters have been typeset. Check the main-text word count
separately, respecting the stated exclusions.
