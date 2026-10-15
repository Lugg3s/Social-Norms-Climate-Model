/* Formula source: ../../../model/model_equations.py, ../../../model/agent.py and ../../../config/scenarios.json.
 * Only active, distinct norm types are included. No qualitative answers are provided.
 * This classic script also works when index.html is opened directly from disk. */
(() => {
  const row = (...parts) => `<mrow>${parts.join('')}</mrow>`;
  const id = name => `<mi mathvariant="normal">${name}</mi>`;
  const op = text => `<mo>${text}</mo>`;
  const n = value => `<mn>${value}</mn>`;
  const sub = (base, suffix) => `<msub>${id(base)}${id(suffix)}</msub>`;
  const frac = (a, b) => `<mfrac>${a}${b}</mfrac>`;
  const par = x => row(op('('), x, op(')'));
  const times = (...parts) => row(...parts.flatMap((part, index) => index ? [op('\u2062'), part] : [part]));
  const math = body => `<math xmlns="http://www.w3.org/1998/Math/MathML" display="block">${body}</math>`;
  const equation = (left, right) => math(row(left, op('='), right));
  const derivative = name => frac(row(id('d'), name), row(id('d'), id('t')));
  const x = id('x'), xp = sub('x', 'p'), xr = sub('x', 'ref');
  const ft = row(sub('f', 'T'), par(id('T')));
  const temperature = times(id('tf'), ft);
  const descriptive = row(n(2), x, op('−'), n(1));
  const injunctive = times(sub('c', 'inj'), par(row(sub('x', 'target'), op('−'), x)));
  const relative = frac(row(xp, op('−'), xr), xr);
  const delayed = frac(row(row(x, par(row(id('t'), op('−'), id('τ')))), op('−'),
    row(x, par(row(id('t'), op('−'), id('τ'), op('−'), id('θ'))))), id('θ'));
  const dynamic = times(sub('c', 'dyn'), relative);
  const dynamic2 = times(sub('c', 'dyn'), delayed);
  // Display aliases only; stored notes retain the Python parameter names.
  const ode = norm => equation(derivative(x), times(id('κ'), x, par(row(n(1), op('−'), x)),
    par(row(op('−'), id('β'), op('+'), temperature, op('+'),
      times(id('sf'), par(Array.isArray(norm) ? row(...norm) : norm))))));
  const exponent = par(row(op('−'), id('ω'), par(row(id('T'), op('−'), sub('T', 'c')))));
  const sigmoid = equation(ft, frac(sub('f', 'max'), row(n(1), op('+'), id('exp'), exponent)));
  const perceptual = [
    equation(derivative(xp), frac(row(x, op('−'), xp), sub('τ', 'xp'))),
    equation(derivative(xr), frac(row(xp, op('−'), xr), sub('τ', 'ref'))),
    equation(row(xp, par(n(0))), sub('x', '0')),
    equation(row(xr, par(n(0))), sub('x', '0')),
  ];
  const delayDefinition = [equation(id('θ'), times(id('τ'), id('ρ'))), math(row(id('τ'), op('>'), n(0), op(','), id('ρ'), op('>'), n(1)))];
  const PARAMS = {
    social_norm_factor: 'sf', temperature_factor: 'tf',
    beta: 'β', kappa: 'κ', x0: 'x₀', f_max: 'fₘₐₓ', omega: 'ω', T_c: 'T꜀',
    N: 'N', c_inj: 'cᵢₙⱼ', x_target: 'xₜₐᵣɡₑₜ', c_dyn: 'c_dᵧₙ',
    tau_ref: 'τᵣₑ𝒻', tau_xp: 'τₓₚ', tau: 'τ', rho: 'ρ',
    network_size: 'network_size', eta: 'η', phi: 'φ', psi: 'ψ', n_agents: 'n_agents',
  };
  const STATES = { x: 'x', t: 't', T: 'T', x_p: 'xₚ', x_ref: 'xᵣₑ𝒻', theta: 'θ',
    A_i: 'Aᵢ', BI_i: 'BIᵢ', actual_behavior_i: 'actual_behaviorᵢ', q_i: 'qᵢ', beta_i: 'βᵢ', P_i: 'Pᵢ' };
  const common = ['social_norm_factor', 'temperature_factor', 'beta', 'kappa'];
  const response = ['f_max', 'omega', 'T_c', 'x0'];
  const baseVariables = ['x', 't', 'T'];
  const norm = (key, name, term, specifics = [], variables = [], auxiliary = [], note = '') => ({
    key, name, kind: 'DGL', formula: ode(term), auxiliary: [sigmoid, ...auxiliary],
    parameters: [...common, ...specifics, ...response], variables: [...baseVariables, ...variables],
    specificParameters: specifics, note,
    source: 'model/model_equations.py · get_social_norm_term / diff_x',
  });
  const refGuard = 'Für |x_ref| < 10⁻¹² wird der gesamte relative dynamische Summand auf 0 gesetzt.';
  const history = 'Für Abfragen vor dem Beginn der gespeicherten Zeitreihe wird x(0) = x0 verwendet.';
  const NORMS = [
    norm('baseline', 'Observation-based / imitation (baseline)', descriptive),
    norm('belief', 'Belief-based / intention motivation', id('N'), ['N']),
    norm('approval', 'Observation based / approval (punish only one behaviour)', x),
    norm('static-injunctive', 'Static injunctive', row(sub('x', 'target'), op('−'), x), ['x_target']),
    norm('dynamic', 'Dynamic social norm', relative, ['tau_ref', 'tau_xp'], ['x_p', 'x_ref'], perceptual, refGuard),
    norm('combined', 'Descriptive, injunctive, dynamic', [descriptive, row(op('+'), injunctive), row(op('+'), dynamic)],
      ['c_inj', 'x_target', 'c_dyn', 'tau_ref', 'tau_xp'], ['x_p', 'x_ref'], perceptual, refGuard),
    norm('dynamic2', 'dynamic social norm2', dynamic2, ['c_dyn', 'tau', 'rho'], ['theta'], delayDefinition, history),
    norm('combined2', 'Descriptive, injunctive, dynamic2', [descriptive, row(op('+'), injunctive), row(op('+'), dynamic2)],
      ['c_inj', 'x_target', 'c_dyn', 'tau', 'rho'], ['theta'], delayDefinition, history),
    norm('injunctive2', 'Injunctive, dynamic2', [injunctive, row(op('+'), dynamic2)],
      ['c_inj', 'x_target', 'c_dyn', 'tau', 'rho'], ['theta'], delayDefinition, history),
  ];
  const ai = sub('A', 'i'), bi = sub('BI', 'i'), qi = sub('q', 'i'), actual = sub('actual_behavior', 'i');
  const cases = entries => row(op('{'), `<mtable columnalign="left left">${entries.map(([value, condition]) =>
    `<mtr><mtd>${value}</mtd><mtd><mtext>${condition}</mtext></mtd></mtr>`).join('')}</mtable>`);
  NORMS.push({
    key: 'agents', name: 'Observation-based / intention motivation (agents)', kind: 'Agenten',
    formula: equation(row(x, par(sub('t', 'k'))), frac(row(`<munderover><mo>∑</mo><mrow><mi>i</mi><mo>=</mo><mn>1</mn></mrow>${id('n_agents')}</munderover>`, actual, par(row(sub('t', 'k'), op('⁺')))), id('n_agents'))),
    auxiliary: [
      equation(ai, row(op('−'), sub('β', 'i'), op('+'), temperature)),
      equation(bi, cases([[row(ai, op('+'), times(id('η'), qi)), 'qᵢ ≥ φ'], [ai, 'qᵢ < φ']])),
      equation(row(actual, par(row(sub('t', 'k'), op('⁺')))), cases([[n(1), 'BIᵢ ≥ ψ'], [n(0), 'BIᵢ < ψ']])),
      equation(qi, cases([[frac(row('<munder><mo>∑</mo><mrow><mi>j</mi><mo>∈</mo><msub><mi>P</mi><mi>i</mi></msub></mrow></munder>', sub('actual_behavior', 'j'), par(row(sub('t', 'k'), op('⁻')))), row(op('|'), sub('P', 'i'), op('|'))), '|Pᵢ| > 0'], [n(0), '|Pᵢ| = 0']])),
      math(row(sub('β', 'i'), op('∼'), id('Uniform'), par(row(n(0), op(','), n(2), id('β'))))),
      math(row(id('i'), op('∉'), sub('P', 'i'), op(','), op('|'), sub('P', 'i'), op('|'), op('='), id('network_size'))),
      equation(sub('t', 'k'), row(n(217), op('+'), id('k'), op(','), id('k'), op('='), n(0), op(','), n(1), op(','), op('…'))),
      equation(row(x, par(id('t'))), row(x, par(sub('t', 'k')), op(','), sub('t', 'k'), op('≤'), id('t'), op('<'), sub('t', 'k+1'))),
      equation(row(x, par(n(0))), frac(row(id('round'), par(times(id('n_agents'), sub('x', '0')))), id('n_agents'))),
      sigmoid,
    ],
    parameters: ['temperature_factor', 'beta', 'network_size', 'eta', 'phi', 'psi', 'n_agents', ...response],
    specificParameters: ['network_size', 'eta', 'phi', 'psi', 'n_agents'],
    variables: [...baseVariables, 'A_i', 'BI_i', 'actual_behavior_i', 'q_i', 'beta_i', 'P_i'],
    note: 'Alle Agenten entscheiden gleichzeitig auf Basis des vorherigen Verhaltens. BI_i bleibt ein kontinuierlicher Wert. β_i und P_i werden bei der Initialisierung gezogen und anschließend beibehalten.',
    source: 'model/agent.py · initialize_agents / evaluate_intentions / update_agents; model/model_equations.py · jährliche Ereignisse',
  });
  const CASE_STUDY = 'Die fiktive Firma LoopCup möchte wiederverwendbare Becher in einem Markt mit 10.000 regelmäßigen Kaffeekundinnen und -kunden anbieten. Zu Beginn nutzen 30 % dieser Gruppe Mehrwegbecher. Die Firma betrachtet verschiedene mögliche Entwicklungen; ein Gedankenfall ist eine angestrebte Mehrwegquote von 70 %.\n\nFür dieses Arbeitsbeispiel ist x der Anteil der Menschen, die tatsächlich einen Mehrwegbecher nutzen (0 bis 1). Die betrachtete Marktphase beginnt beim Entscheidungsbeginn des bestehenden Modells, t = 217; Zeiteinheit ist ein Jahr. Die Originalparameter und T bleiben in den Gleichungen erhalten. Wie du sie auf den Bechermarkt überträgst und welche Wirkung du erwartest, trägst du selbst ein.';
  const NORM_FIELDS = ['calculation', 'meaning', 'expectation'];
  const PARAM_FIELDS = ['explanation', 'larger', 'smaller'];
  function emptyWorkbook() {
    return { version: 1, caseStudy: CASE_STUDY, updatedAt: null,
      notes: Object.fromEntries(NORMS.map(model => [model.key, {
        calculation: '', meaning: '', expectation: '',
        parameters: Object.fromEntries([...model.parameters, ...model.variables].map(key => [key,
          { explanation: '', larger: '', smaller: '' }])),
      }])) };
  }
  function validateWorkbook(input) {
    if (!input || input.version !== 1 || typeof input.caseStudy !== 'string' || input.caseStudy.length > 100000 || !input.notes) {
      throw new Error('Diese Datei ist keine gültige Sicherung des Normen-Werkbuchs.');
    }
    const clean = emptyWorkbook();
    clean.caseStudy = input.caseStudy;
    clean.updatedAt = typeof input.updatedAt === 'string' ? input.updatedAt : null;
    const string = value => {
      if (typeof value !== 'string' || value.length > 100000) throw new Error('Die Sicherung enthält ungültige Notizfelder.');
      return value;
    };
    for (const model of NORMS) {
      const note = input.notes[model.key];
      if (!note || !note.parameters) throw new Error(`Notizen für „${model.name}“ fehlen.`);
      for (const key of NORM_FIELDS) clean.notes[model.key][key] = string(note[key]);
      for (const name of [...model.parameters, ...model.variables]) {
        if (!note.parameters[name]) throw new Error(`Der Bereich ${name} fehlt.`);
        for (const key of PARAM_FIELDS) clean.notes[model.key].parameters[name][key] = string(note.parameters[name][key]);
      }
      // Preserve existing user notes when retiring the redundant parameter.
      const retired = model.key === 'approval' ? 'alpha' : model.key === 'static-injunctive' ? 'c_inj' : null;
      if (retired && note.parameters[retired]) {
        for (const key of PARAM_FIELDS) {
          const previous = string(note.parameters[retired][key]);
          if (previous.trim()) {
            const target = clean.notes[model.key].parameters.social_norm_factor;
            target[key] += `${target[key].trim() ? '\n\n' : ''}Frühere Notiz zu ${retired} (jetzt in sf zusammengefasst):\n${previous}`;
          }
        }
      }
    }
    return clean;
  }
  function progress(book, model) {
    const note = book.notes[model.key];
    const values = [...NORM_FIELDS.map(key => note[key]), ...Object.values(note.parameters).flatMap(param => PARAM_FIELDS.map(key => param[key]))];
    return { filled: values.filter(value => value.trim()).length, total: values.length };
  }
  function markdown(book) {
    const lines = ['# Normen-Werkbuch · Reusable Cups', '', book.caseStudy, ''];
    for (const model of NORMS) {
      const note = book.notes[model.key];
      lines.push(`## ${model.name}`, '');
      if (model.paperReferences?.length) {
        lines.push('### Paper & Quellen', '');
        for (const reference of model.paperReferences) {
          const paper = globalThis.NormWorkbook.PAPERS[reference.paper];
          lines.push(`- [${paper.citation}: ${paper.title}](${paper.url}) — ${reference.role}. ${reference.foundIn}`);
        }
        if (model.paperNote) lines.push('', model.paperNote);
        lines.push('');
      }
      lines.push('### Was wird berechnet?', note.calculation, '', '### Meine qualitative Bedeutung', note.meaning, '', '### Erwarteter Verlauf von x', note.expectation, '');
      for (const name of [...model.parameters, ...model.variables]) {
        const value = note.parameters[name];
        lines.push(`### ${name}`, '', '**Meine Erklärung**', value.explanation, '', '**Größerer Wert**', value.larger, '', '**Kleinerer Wert**', value.smaller, '');
      }
    }
    return lines.join('\n');
  }
  globalThis.NormWorkbook = { NORMS, PARAMS, STATES, CASE_STUDY, NORM_FIELDS, PARAM_FIELDS, emptyWorkbook, validateWorkbook, progress, markdown };
})();
