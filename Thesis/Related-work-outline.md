# Related Work: ordered paper outline

Updated: 24 October 2026. The tables follow the intended order of discussion.
The outline combines the previous 13 papers with nine additions marked **NEW**.

Ratings express relevance to this chapter, not scientific quality or citation
counts: 10 = direct foundation; 9 = strong contribution; 8 = useful comparator;
7 = supporting evidence for a short discussion. Only ratings above 6 are included.
Papers can share a paragraph; each entry does not need its own subsection.
The relevance column gives the proposed role in this thesis; it is an editorial
assessment. Outcomes describe the cited study or its model, not universal claims.
For reviews, the outcome is the main synthesis or framework contribution.

## 1. How social norms and social influence are modelled

| Paper | Relevance rating | OpenAlex citations | What was investigated? | Main outcome | Relevance to this thesis |
| --- | --- | ---: | --- | --- | --- |
| **1. Prawitz, Schwarz & Donges (2026)**<br>[Modeling social norms in social-ecological systems: a systematic literature review](https://doi.org/10.1088/1748-9326/ae3b55) | 10/10 | [2](https://openalex.org/W7125503127) | Systematic review of 153 studies modelling social norms in social–ecological systems. | Observation-based norms dominate; interactions between norm types and dynamic norm signalling remain under-explored. | Main basis for selecting norm mechanisms and identifying the comparison gap. |
| **2. Flache et al. (2017)**<br>[Models of Social Influence: Towards the Next Frontiers](https://doi.org/10.18564/jasss.3521) | 9/10 · **NEW** | [599](https://openalex.org/W2765195368) | Review of alternative social-influence mechanisms and their collective outcomes. | Different assumptions generate consensus, clustering or polarisation; model comparison and empirical validation need more attention. | Explains why the mathematical representation of social influence matters. |
| **3. Müller-Hansen et al. (2017)**<br>[Towards representing human behavior and decision making in Earth system models – an overview of techniques and approaches](https://doi.org/10.5194/esd-8-977-2017) | 8/10 · **NEW** | [115](https://openalex.org/W2767224275) | Review of individual decision rules, social interactions and aggregation in Earth-system modelling. | Maps alternative approaches and shows how consequential modelling assumptions can be. | Frames the differences between agent-based and aggregate behavioural models. |

## 2. Concrete implementations and interacting norms

| Paper | Relevance rating | OpenAlex citations | What was investigated? | Main outcome | Relevance to this thesis |
| --- | --- | ---: | --- | --- | --- |
| **4. Sigdel, Anand & Bauch (2019)**<br>[Convergence of socio-ecological dynamics in disparate ecological systems under strong coupling to human social systems](https://doi.org/10.1007/s12080-018-0394-z) | 8/10 | [11](https://openalex.org/W2950315426) | Coupled harvesting and social-ostracism models with three different resource dynamics. | Strong coupling can make otherwise different systems behave similarly; high social-learning rates can generate stable cycles. | Comparator for differential-equation models, feedbacks and oscillatory behaviour. |
| **5. James & Rosenberg (2022)**<br>[Agent-Based Model to Manage Household Water Use Through Social-Environmental Strategies of Encouragement and Peer Pressure](https://doi.org/10.1029/2020EF001883) | 8/10 | [12](https://openalex.org/W4210676173) | Agent-based household water conservation under peer pressure and manager encouragement. | Simulated peer pressure saved more water than encouragement; combining both saved the most. | Concrete comparison of neighbourhood influence and household decision rules. |
| **6. Torren-Peraire, Savin & van den Bergh (2024)**<br>[An Agent-Based Model of Cultural Change for a Low-Carbon Transition](https://doi.org/10.18564/jasss.5291) | 8/10 · **NEW** | [18](https://openalex.org/W4391546180) | Agent-based diffusion of low-carbon attitudes, cultural identity and behaviour with individual barriers. | Cultural links and low confirmation bias favoured decarbonisation; green influencers alone produced limited reductions. | Comparator for heterogeneous barriers, attitude–action differences and Sobol analysis. |
| **7. Bechthold et al. (2025)**<br>[Social norms and groups structure safe operating spaces in renewable resource use in a social–ecological multi-layer network model](https://doi.org/10.5194/esd-16-1365-2025) | 9/10 · **NEW** | [5](https://openalex.org/W4413621686) | Coupled resource use with separately evolving descriptive and injunctive norms in social groups. | Opposing norms can create intermediate equilibria; network structure and group inertia shape outcomes. | Direct precedent for interacting norm types and their distinct effects. |
| **8. Bhalla et al. (2024)**<br>[The role of interacting social and institutional norms in stressed groundwater systems](https://doi.org/10.1016/j.jenvman.2024.120389) | 8/10 · **NEW** | [13](https://openalex.org/W4392743126) | Norms, trust and governance in a behavioural model of Tunisian groundwater-user groups. | Norms could delay financial collapse but did not prevent hydrogeological collapse under the modelled conditions. | Comparator for norm interactions and tree-based simulation analysis using XGBoost. |

## 3. Dynamic norm signals and perceived support

| Paper | Relevance rating | OpenAlex citations | What was investigated? | Main outcome | Relevance to this thesis |
| --- | --- | ---: | --- | --- | --- |
| **9. Sparkman & Walton (2017)**<br>[Dynamic Norms Promote Sustainable Behavior, Even if It Is Counternormative](https://doi.org/10.1177/0956797617719950) | 9/10 | [636](https://openalex.org/W2758069137) | Five experiments testing messages about changing rather than only current behaviour. | Dynamic norm messages encouraged sustainable behaviour despite contrary static norms. | Empirical motivation for including behavioural trends as norm signals. |
| **10. Mortensen et al. (2019)**<br>[Trending Norms: A Lever for Encouraging Behaviors Performed by the Minority](https://doi.org/10.1177/1948550617734615) | 7/10 | [221](https://openalex.org/W2778068175) | Experiments comparing growing minority norms with static minority information and controls. | Trending minority norms increased conformity; expectations of continued growth helped explain the effect. | Supports distinguishing current prevalence from perceived behavioural trends. |
| **11. Andre, Boneva, Chopra & Falk (2024)**<br>[Globally representative evidence on the actual and perceived support for climate action](https://doi.org/10.1038/s41558-024-01925-3) | 7/10 · **NEW** | [333](https://openalex.org/W4391680818) | Survey of climate-action willingness, norm support and perceptions across 125 countries. | Support was widespread, but respondents systematically underestimated others' willingness to act. | Motivates distinguishing perceived support from observed behaviour; not direct parameter calibration. |
| **12. Álvarez-Antelo et al. (2025)**<br>[Towards a sustainable mobility lifestyle: Exploring the flight to rail shift through model-based behavioural change scenarios](https://doi.org/10.1016/j.ecolecon.2024.108498) | 9/10 | [8](https://openalex.org/W4405508054) | System-dynamics scenarios coupling behavioural change with a flight-to-rail transport shift. | Personal environmental values accelerated change; policy combinations could also support mitigation when values were weaker. | Applied precedent for dynamic norm signals and behavioural scenario discovery. |

## 4. Coupled behaviour–climate models

| Paper | Relevance rating | OpenAlex citations | What was investigated? | Main outcome | Relevance to this thesis |
| --- | --- | ---: | --- | --- | --- |
| **13. Beckage, Moore & Lacasse (2022)**<br>[Incorporating human behaviour into Earth system modelling](https://doi.org/10.1038/s41562-022-01478-5) | 9/10 | [72](https://openalex.org/W4309565773) | Review of how human behaviour is represented in coupled social–climate models. | Proposes a framework linking cognition, contagion and behavioural response. | Organises the behavioural mechanisms and feedbacks compared in the thesis. |
| **14. Beckage et al. (2018)**<br>[Linking models of human behaviour and climate alters projected climate change](https://doi.org/10.1038/s41558-017-0031-7) | 9/10 | [185](https://openalex.org/W2777536078) | Coupling of perceived extreme-event risk and planned behaviour with the C-ROADS climate model. | Behavioural feedbacks could increase or decrease warming; behavioural uncertainty was comparable to physical uncertainty. | Key belief-based comparator showing that behavioural assumptions affect climate outcomes. |
| **15. Bury, Bauch & Anand (2019)**<br>[Charting pathways to climate change mitigation in a coupled socio-climate model](https://doi.org/10.1371/journal.pcbi.1007000) | 10/10 | [68](https://openalex.org/W2948917180) | Coupled imitation dynamics, majority-reinforcing social norms and climate-dependent mitigation incentives. | Social learning strongly affected warming; majority norms could suppress early mitigation uptake. | Direct model foundation and motivation for testing alternative norm representations. |
| **16. Menard, Bury, Bauch & Anand (2021)**<br>[When conflicts get heated, so does the planet: coupled social-climate dynamics under inequality](https://doi.org/10.1098/rspb.2021.1357) | 9/10 · **NEW** | [24](https://openalex.org/W3200111347) | Evolutionary-game socio-climate dynamics with inequality, group structure and homophily. | Greater inequality and homophily increased peak warming in the simulations; climate change could reinforce polarisation. | Extension of the baseline showing consequences of social heterogeneity. |
| **17. Eker, Reese & Obersteiner (2019)**<br>[Modelling the drivers of a widespread shift to sustainable diets](https://doi.org/10.1038/s41893-019-0331-1) | 9/10 · **NEW** | [187](https://openalex.org/W2962928006) | Endogenous dietary change linked to the FeliX integrated assessment model. | Social-norm effects and self-efficacy were the main model drivers of widespread diet change. | Close precedent for norm-driven behaviour, Sobol analysis and scenario discovery. |
| **18. Moore et al. (2022)**<br>[Determinants of emissions pathways in the coupled climate–social system](https://doi.org/10.1038/s41586-022-04423-8) | 9/10 · **NEW** | [256](https://openalex.org/W4213197433) | Coupled social, political, technological and climate feedbacks generating emissions pathways. | Climate perceptions, technology and political responsiveness strongly shaped simulated pathways. | Broader comparator for the scope and limitations of the thesis's simpler coupling. |
| **19. Rajah et al. (2025)**<br>[An endogenous modelling framework of dietary behavioural change in the fully coupled human-climate FRIDA v2.1 model](https://doi.org/10.5194/gmd-18-5997-2025) | 9/10 | [8](https://openalex.org/W4414248834) | Endogenous dietary behaviour in FRIDA, including norms, accessibility and past behaviour. | Behavioural feedbacks lowered projected demand relative to GDP-driven modelling; some scenarios showed later reversals. | Source of adapted perception and adjustment mechanisms; comparator for reversibility. |
| **20. Schwarz et al. (2025, preprint)**<br>[From Farm to Planet: The InSEEDS World-Earth Model for Simulating Transitions to Regenerative Agriculture](https://doi.org/10.5194/egusphere-2025-4079) | 8/10 | [0](https://openalex.org/W4414668089) | Farmer-agent adoption of conservation tillage coupled to the LPJmL vegetation model. | Networks, ecological heterogeneity and inertia shaped adoption; soil-carbon and yield benefits were context-dependent. | Comparator for intentions, realised behaviour and coupled environmental feedbacks. |

## 5. Comparing formal representations and positioning the thesis

| Paper | Relevance rating | OpenAlex citations | What was investigated? | Main outcome | Relevance to this thesis |
| --- | --- | ---: | --- | --- | --- |
| **21. Schlüter et al. (2017)**<br>[A framework for mapping and comparing behavioural theories in models of social-ecological systems](https://doi.org/10.1016/j.ecolecon.2016.08.008) | 9/10 | [475](https://openalex.org/W2513172296) | Framework for mapping behavioural theories used in natural-resource models. | MoHuB provides a common language for comparing decision-making assumptions and mechanisms. | Supports systematic comparison beyond parameter names or modelling labels. |
| **22. Muelder & Filatova (2018)**<br>[One Theory—Many Formalizations: Testing Different Code Implementations of the Theory of Planned Behaviour in Energy Agent-Based Models](https://doi.org/10.18564/jasss.3855) | 10/10 | [71](https://openalex.org/W2899485510) | Alternative implementations of planned-behaviour theory in a household solar-investment ABM. | The same theory and data still produced qualitatively and quantitatively different simulation outcomes. | Direct methodological justification for comparing alternative formal representations. |

Close the chapter by proposing the thesis's contribution: compare selected norm
representations in a shared socio-climate setting and examine their behavioural
dynamics, climate outcomes and parameter sensitivities. Establish the precise
gap from the reviewed studies; do not claim that dynamic or interacting norms
have never been modelled.

## Citation check: 24 October 2026

Citation counts in the tables were retrieved directly from OpenAlex by DOI.
Each count links to its OpenAlex record; the reproducible snapshot is saved in
[Related-work-citation-audit.json](Related-work-citation-audit.json).
Counts refer to the exact indexed record and may include self-citations.
They are not independent, self-citation-adjusted counts or totals across
all preprint and journal versions. Other databases can report different totals.

The existing 7–10 ratings measure relevance, not methodological quality or
citation impact. No minimum citation count has been agreed. The following
flags identify limited citation histories; they are not automatic exclusions
or evidence that a study is unreliable.

- **Older studies with comparatively modest reception:** Sigdel et al. (2019):
  **11**; James & Rosenberg (2022): **12**. Check their methodological strength
  and specific contribution before treating them as central evidence.
- **Recent studies with limited citation histories:** Prawitz et al. (2026):
  **2**; Bechthold et al. (2025): **5**; Álvarez-Antelo et al. (2025): **8**;
  Rajah et al. (2025): **8**. Their recent publication dates limit the time
  available to accumulate citations.
- **Other studies with modest counts:** Torren-Peraire et al. (2024): **18**;
  Bhalla et al. (2024): **13**. Their mechanism-specific relevance should
  be weighed alongside the limited citation evidence.
- **Preprint requiring explicit qualification:** Schwarz et al. (2025):
  **0** for the cited preprint record. Treat it as a source for the described
  model, with its preprint status explicit; it does not yet meet a preference
  for an already widely cited source.

**Recommended use:** build the chapter's foundations around established,
well-cited studies. Retain directly relevant newer model sources where needed
to explain adapted mechanisms, while stating their evidence and publication
status. In particular, a direct mechanism source must not be replaced by an
unrelated highly cited paper. The current audit does not remove any entries
or silently change their relevance ratings.

## Boundaries to preserve when drafting

- Compare papers by mechanism and assumptions; avoid a sequence of isolated abstracts.
- Bechthold et al. model norms that evolve endogenously. This is not automatically
  the same mechanism as a norm signal based on an observed behavioural trend.
- Andre et al. measure support and willingness, including perceptions of others.
  Their survey percentages are not observed mitigation shares or direct parameter estimates.
- Bhalla et al. use XGBoost, an ensemble of boosted trees. It is a methodological
  comparator, not the same estimator as the thesis's single regression trees.
- Torren-Peraire et al. distinguish attitudes and actions. Their barriers are a
  modelling precedent, not empirical validation of this project's cost rescaling.
- The cited InSEEDS source is the 2025 preprint version. Identify that version explicitly.
- Sigdel et al. is cited by its 2019 journal volume; the article appeared online in 2018.
- Keep detailed norm definitions in Theory, the implemented equations in Model,
  and explanations of Sobol indices and regression-tree algorithms in Methods.

## Source check

Summaries were checked against Anara source texts and publisher or
author-institution sources. The Anara copy of Sigdel et al. is a preprint;
its summary and publication year were also checked against the published
journal abstract. The four papers checked outside Anara are Müller-Hansen,
Torren-Peraire, Eker and Moore. All table entries link to the cited publication.
The InSEEDS summary refers specifically to the cited 2025 preprint. External
source checks do not imply that those papers were uploaded to Anara.
