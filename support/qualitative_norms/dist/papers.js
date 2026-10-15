/* Checked against model/model_equations.py, model/agent.py, README.md and the Anara library.
 * References identify provenance, not prefilled qualitative interpretations.
 * Publisher/DOI links refer to the cited versions; no library files are uploaded. */
(() => {
  const PAPERS = {
    bury: {
      citation: 'Bury, Bauch & Anand (2019)',
      title: 'Charting pathways to climate change mitigation in a coupled socio-climate model',
      url: 'https://doi.org/10.1371/journal.pcbi.1007000',
    },
    prawitz: {
      citation: 'Prawitz, Schwarz & Donges (2026)',
      title: 'Modeling social norms in social-ecological systems: a systematic literature review',
      url: 'https://doi.org/10.1088/1748-9326/ae3b55',
    },
    beckage: {
      citation: 'Beckage et al. (2018)',
      title: 'Linking models of human behaviour and climate alters projected climate change',
      url: 'https://doi.org/10.1038/s41558-017-0031-7',
    },
    sigdel: {
      citation: 'Sigdel, Anand & Bauch (2019)',
      title: 'Convergence of socio-ecological dynamics in disparate ecological systems under strong coupling to human social systems',
      url: 'https://doi.org/10.1007/s12080-018-0394-z',
      additionalUrl: 'https://doi.org/10.1101/296202',
      additionalLabel: 'Preprint (2018), in Anara vorhanden',
    },
    rajah: {
      citation: 'Rajah et al. (2025)',
      title: 'An endogenous modelling framework of dietary behavioural change in the fully coupled human-climate FRIDA v2.1 model',
      url: 'https://doi.org/10.5194/gmd-18-5997-2025',
    },
    sparkman: {
      citation: 'Sparkman & Walton (2017)',
      title: 'Dynamic Norms Promote Sustainable Behavior, Even if It Is Counternormative',
      url: 'https://doi.org/10.1177/0956797617719950',
    },
    mortensen: {
      citation: 'Mortensen et al. (2019)',
      title: 'Trending Norms: A Lever for Encouraging Behaviors Performed by the Minority',
      url: 'https://doi.org/10.1177/1948550617734615',
    },
    schwarz: {
      citation: 'Schwarz et al. (2025, Preprint)',
      title: 'From Farm to Planet: The InSEEDS World-Earth Model for Simulating Transitions to Regenerative Agriculture',
      url: 'https://doi.org/10.5194/egusphere-2025-4079',
    },
    torren: {
      citation: 'Torren-Peraire, Savin & van den Bergh (2024)',
      title: 'An Agent-Based Model of Cultural Change for a Low-Carbon Transition',
      url: 'https://doi.org/10.18564/jasss.5291',
    },
    abebe: {
      citation: 'Abebe et al. (2020)',
      title: 'The role of household adaptation measures in reducing vulnerability to flooding: a coupled agent-based and flood modelling approach',
      url: 'https://doi.org/10.5194/hess-24-5329-2020',
    },
    james: {
      citation: 'James & Rosenberg (2022)',
      title: 'Agent-Based Model to Manage Household Water Use Through Social-Environmental Strategies of Encouragement and Peer Pressure',
      url: 'https://doi.org/10.1029/2020EF001883',
    },
  };
  const reference = (paper, role, foundIn, note = '') => ({ paper, role, foundIn, note });
  const foundation = reference('bury', 'Gemeinsame Modellgrundlage',
    'model/model_equations.py: Bury-Kommentar zur Temperaturfunktion; Anara: Hauptpaper und S1 Text.',
    'Die hier verwendete Temperaturvariable ist T; das Original arbeitet mit T_f.');
  const review = reference('prawitz', 'Review / Einordnung der Normtypen',
    'Anara: Review, Abschnitt 4.3; model/agent.py verweist ebenfalls auf das Review.');
  const trendBackground = [
    reference('sparkman', 'Konzeptueller Hintergrund', 'Anara: Paper vorhanden.',
      'Hintergrundliteratur zu dynamischen Normen; kein Beleg für die konkrete Projektgleichung.'),
    reference('mortensen', 'Konzeptueller Hintergrund', 'Anara: Paper vorhanden.',
      'Hintergrundliteratur zu Trending Norms; kein Beleg für den konkreten Delay-Term.'),
  ];
  const perception = reference('rajah', 'Strukturelle Literaturanalogie',
    'model/model_equations.py: get_social_norm_term / diff_x_p / diff_x_ref; Anara: FRIDA-Paper.',
    'Abschnitt 3.1.3 und Tabelle A1. Die Übertragung auf das vorliegende Modell ist eine Adaption.');
  const assignments = {
    baseline: {
      references: [reference('bury', 'Direkte Code-Referenz der Baseline',
        'model/model_equations.py: „Baseline from Bury“; Anara: Hauptpaper und S1 Text.'), review],
      note: '',
    },
    belief: {
      references: [reference('beckage', 'Direkte Code-Referenz / Literaturvorbild',
        'model/model_equations.py nennt Beckage; Anara: Hauptpaper, Supplement und Prawitz-Review, Abschnitt 4.3.',
        'Die Einbettung des konstanten N in diese Replicator-Gleichung und der vorzeichenbehaftete Sensi-Bereich [−1, 1] sind Projektannahmen, kein kalibriertes Literaturintervall.'), foundation, review],
      note: '',
    },
    approval: {
      references: [reference('sigdel', 'Im Code genanntes Literaturvorbild',
        'model/model_equations.py nennt Sigdel und Bury; Prawitz-Review, Abschnitt 4.3, nennt Sigdel (2019). Anara enthält den Preprint.',
        'Der Code kombiniert Ansätze; der Normterm x wird einmalig mit sf gewichtet. Die frühere zusätzliche Skalierung ist in sf zusammengefasst.'), foundation, review],
      note: '',
    },
    'static-injunctive': {
      references: [review, foundation],
      note: 'Für den konkreten Zielwertterm (x_target − x), gewichtet mit sf, wurde im Code und in den geprüften Anara-Zuordnungen keine eigene Paperreferenz gefunden. Die Links belegen Hintergrund und Modellgrundlage.',
    },
    dynamic: { references: [perception, foundation, review, ...trendBackground], note: '' },
    combined: {
      references: [perception, foundation, review, ...trendBackground],
      note: 'Die additive Kombination der drei Terme ist eine Projektkombination. Die Quellen beziehen sich auf Grundlagen und einzelne Komponenten; sie belegen nicht die gesamte Gleichung als unverändert übernommene Paperformel.',
    },
    dynamic2: {
      references: [foundation, review, ...trendBackground],
      note: 'Für den konkreten Delay-Term c_dyn · [x(t−τ) − x(t−τ−θ)] / θ wurde keine direkte Paperzuordnung gefunden. Die dynamischen Paper sind als konzeptueller Hintergrund verlinkt.',
    },
    combined2: {
      references: [foundation, review, ...trendBackground],
      note: 'Für diese additive Kombination und den konkreten Delay-Term wurde keine direkte Paperzuordnung gefunden. Die Links belegen Modellgrundlage und konzeptuellen Hintergrund.',
    },
    injunctive2: {
      references: [foundation, review, ...trendBackground],
      note: 'Für diese Kombination aus Zielwert- und Delay-Term wurde keine direkte Paperzuordnung gefunden. Die Links belegen Modellgrundlage und konzeptuellen Hintergrund.',
    },
    agents: {
      references: [
        reference('prawitz', 'Direkte Code-Referenz der BI-Regel', 'model/agent.py: evaluate_intentions; Anara: Review, Abschnitt 4.3.',
          'Die temperaturabhängige Erweiterung A_i(t) ist projektspezifisch.'),
        reference('abebe', 'Im Review genanntes Beispielmodell', 'Prawitz-Review, Abschnitt 4.3; Originalpaper in Anara.'),
        reference('james', 'Im Review genanntes Beispielmodell', 'Prawitz-Review, Abschnitt 4.3; Originalpaper in Anara.'),
        reference('schwarz', 'Parameteranalogie: Normgewicht', 'model/agent.py: Literaturkommentar; README.md; Originalpaper in Anara.',
          'Gleichung (2) und Tabelle 1 des zitierten Preprints. Keine Kalibrierung dieser Modellversion.'),
        reference('torren', 'Parameteranalogie: Initialisierung', 'README.md: Literaturverweis zu individuellen Barrieren.',
          'Gleichung (1). Die uniforme Verteilung und Skalierung im Projekt sind eigene Annahmen.'),
        foundation,
      ],
      note: '',
    },
  };
  for (const norm of NormWorkbook.NORMS) {
    norm.paperReferences = assignments[norm.key].references;
    norm.paperNote = assignments[norm.key].note;
  }
  NormWorkbook.PAPERS = PAPERS;
})();
