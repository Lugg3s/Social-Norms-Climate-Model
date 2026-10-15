(() => {
  'use strict';
  const { NORMS, PARAMS, STATES, PAPERS, NORM_FIELDS, PARAM_FIELDS, emptyWorkbook, validateWorkbook, progress, markdown } = NormWorkbook;
  const STORAGE_KEY = 'loopcup.normen-werkbuch.v1';
  let book = emptyWorkbook();
  let saveTimer, equationObserver, importCandidate = null, storageUsable = true;
  const $ = selector => document.querySelector(selector);
  function notice(message) { $('#notice').textContent = message; $('#notice').hidden = !message; }
  try {
    const saved = localStorage.getItem(STORAGE_KEY);
    if (saved) book = validateWorkbook(JSON.parse(saved));
  } catch {
    storageUsable = false;
    notice('Der Browserspeicher konnte nicht gelesen werden. Vorhandene Daten werden nicht überschrieben. Sichere deine neuen Einträge über „Sicherung speichern“.');
  }
  const currentModel = () => NORMS.find(model => model.key === location.hash.slice(1)) || NORMS[0];
  function save() {
    clearTimeout(saveTimer);
    if (!storageUsable) { $('#save-label').textContent = 'Bitte als Datei sichern'; return; }
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(book));
      $('#save-label').textContent = 'Im Browser gespeichert';
      $('#save-state').classList.remove('unsaved');
    } catch {
      $('#save-label').textContent = 'Bitte als Datei sichern';
      $('#save-state').classList.add('unsaved');
      notice('Deine Einträge sind geöffnet, konnten aber nicht im Browser gespeichert werden. Lade sie über „Sicherung speichern“ herunter.');
    }
  }
  function scheduleSave() {
    book.updatedAt = new Date().toISOString();
    $('#save-label').textContent = 'Wird gespeichert …';
    $('#save-state').classList.add('unsaved');
    clearTimeout(saveTimer); saveTimer = setTimeout(save, 350);
  }
  function download(content, extension, mime) {
    save();
    const blob = new Blob([content], { type: mime });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement('a'); anchor.href = url;
    anchor.download = `normen-werkbuch-${new Date().toISOString().slice(0, 10)}.${extension}`;
    anchor.click(); setTimeout(() => URL.revokeObjectURL(url), 3000);
  }
  function renderNav() {
    const search = $('#search').value.trim().toLocaleLowerCase('de');
    const active = currentModel();
    const nav = $('#norm-nav'); nav.replaceChildren();
    let matches = 0;
    NORMS.forEach((model, index) => {
      if (search && !model.name.toLocaleLowerCase('de').includes(search)) return;
      matches++;
      const { filled, total } = progress(book, model);
      const anchor = document.createElement('a'); anchor.href = `#${model.key}`;
      anchor.className = 'norm-link' + (active.key === model.key ? ' active' : '');
      if (active.key === model.key) anchor.setAttribute('aria-current', 'page');
      const number = document.createElement('span'); number.className = 'norm-number'; number.textContent = String(index + 1).padStart(2, '0');
      const content = document.createElement('span'); content.className = 'norm-link-content';
      const title = document.createElement('span'); title.className = 'norm-link-title'; title.textContent = model.name;
      const meter = document.createElement('span'); meter.className = 'nav-meter'; meter.setAttribute('aria-hidden', 'true');
      const fill = document.createElement('span'); fill.style.width = `${filled / total * 100}%`; meter.append(fill);
      const count = document.createElement('span'); count.className = 'nav-count'; count.textContent = `${filled} / ${total} Felder`;
      content.append(title, meter, count); anchor.append(number, content); nav.append(anchor);
    });
    if (!matches) { const empty = document.createElement('p'); empty.className = 'nav-empty'; empty.textContent = 'Keine passende Norm gefunden.'; nav.append(empty); }
  }
  function field(label, placeholder, value, attributes = {}) {
    const wrap = document.createElement('label'); wrap.className = 'write-field';
    const caption = document.createElement('span'); caption.textContent = label;
    const input = document.createElement('textarea'); input.rows = 3; input.value = value; input.placeholder = placeholder;
    for (const [key, entry] of Object.entries(attributes)) input.dataset[key] = entry;
    input.maxLength = 100000; wrap.append(caption, input); return wrap;
  }
  function parameterCard(model, name, isVariable = false) {
    const displayName = name === 'temperature_factor' || name === 'social_norm_factor' ? PARAMS[name] : name;
    const note = book.notes[model.key].parameters[name];
    const details = document.createElement('details'); details.className = 'parameter-card'; details.dataset.parameter = name;
    if (!isVariable && model.specificParameters.includes(name)) details.open = true;
    const summary = document.createElement('summary');
    const symbol = document.createElement('span'); symbol.className = 'parameter-symbol'; symbol.textContent = (isVariable ? STATES : PARAMS)[name];
    const code = document.createElement('code'); code.textContent = name;
    const chip = document.createElement('span'); chip.className = 'parameter-chip';
    chip.textContent = isVariable ? 'Variable / Hilfsgröße' : model.specificParameters.includes(name) ? 'Normspezifisch' : 'Modellparameter';
    const count = document.createElement('span'); count.className = 'parameter-count'; count.textContent = `${PARAM_FIELDS.filter(key => note[key].trim()).length} / 3`;
    summary.append(symbol, code, chip, count);
    const body = document.createElement('div'); body.className = 'parameter-body';
    body.append(field('Meine Erklärung im Becherbeispiel', 'Was steht diese Größe in meinem Beispiel für?', note.explanation, { parameter: name, field: 'explanation' }));
    const rules = document.createElement('div'); rules.className = 'rule-grid';
    rules.append(field('Größerer Wert – ich erwarte …', `Je größer ${displayName}, desto …`, note.larger, { parameter: name, field: 'larger' }),
      field('Kleinerer Wert – ich erwarte …', `Je kleiner ${displayName}, desto …`, note.smaller, { parameter: name, field: 'smaller' }));
    body.append(rules); details.append(summary, body); return details;
  }
  function paperLink(paper, label) {
    const anchor = document.createElement('a'); anchor.href = paper.url;
    anchor.target = '_blank'; anchor.rel = 'noopener noreferrer';
    anchor.textContent = label; anchor.title = paper.title + ' (öffnet in einem neuen Tab)';
    return anchor;
  }
  function paperSources(model) {
    const section = document.createElement('div'); section.className = 'paper-sources';
    const heading = document.createElement('h3'); heading.textContent = 'Paper & Quellen';
    const links = document.createElement('div'); links.className = 'paper-links';
    for (const reference of model.paperReferences) {
      const paper = PAPERS[reference.paper];
      const link = paperLink(paper, paper.citation + ' ↗'); link.dataset.paper = reference.paper; links.append(link);
    }
    const details = document.createElement('details'); details.className = 'source-details';
    const summary = document.createElement('summary'); summary.textContent = 'Zuordnung zu Modell und Literatur';
    const list = document.createElement('ul');
    for (const reference of model.paperReferences) {
      const paper = PAPERS[reference.paper], item = document.createElement('li');
      const role = document.createElement('span'); role.className = 'source-role'; role.textContent = reference.role;
      const title = paperLink(paper, paper.title);
      const origin = document.createElement('p'); origin.textContent = reference.foundIn;
      item.append(role, title, origin);
      if (reference.note) { const note = document.createElement('p'); note.className = 'source-qualification'; note.textContent = reference.note; item.append(note); }
      if (paper.additionalUrl) item.append(paperLink({ ...paper, url: paper.additionalUrl }, paper.additionalLabel + ' ↗'));
      list.append(item);
    }
    details.append(summary, list);
    if (model.paperNote) { const note = document.createElement('p'); note.className = 'source-mapping-note'; note.textContent = model.paperNote; details.append(note); }
    section.append(heading, links, details); return section;
  }
  function render() {
    equationObserver?.disconnect();
    const model = currentModel(), index = NORMS.indexOf(model);
    document.title = `${model.name} · Normen-Werkbuch`;
    const content = $('#norm-content'); content.replaceChildren();
    const { filled, total } = progress(book, model);
    const heading = document.createElement('section'); heading.className = 'norm-heading';
    heading.innerHTML = `<div class="eyebrow">NORM ${String(index + 1).padStart(2, '0')} / ${NORMS.length} <span class="type-chip">${model.kind}</span></div><h1 tabindex="-1"></h1><div class="norm-meta"><span class="filled-count"></span><span>Formel lesen. Übertragen. Eigene Erwartungen festhalten.</span></div>`;
    heading.querySelector('h1').textContent = model.name;
    heading.querySelector('.filled-count').textContent = `${filled} von ${total} Feldern gefüllt`;
    content.append(heading);
    const layout = document.createElement('div'); layout.className = 'norm-workspace';
    const writing = document.createElement('div'); writing.className = 'writing-column';
    const formula = document.createElement('section'); formula.className = 'formula-card'; formula.setAttribute('aria-label', 'Vollständige Gleichung und Hilfsgleichungen');
    formula.innerHTML = `<div class="section-top"><div><span class="eyebrow">01 · DIE MODELLGLEICHUNG</span><h2>So wird x bestimmt.</h2></div><span class="formula-badge">${model.kind === 'DGL' ? 'Differentialgleichung' : 'Jährliche Entscheidung'}</span></div><div class="main-equation equation-scroll">${model.formula}</div><details class="auxiliary" open><summary>Alle Definitionen &amp; Hilfsgleichungen</summary><div class="auxiliary-equations">${model.auxiliary.map(eq => `<div class="equation-scroll">${eq}</div>`).join('')}</div></details><div class="model-boundary"></div><p class="formula-note"></p>`;
    formula.querySelector('.model-boundary').textContent = model.kind === 'DGL'
      ? 'Anfangsbedingung: x(0) = x0. Für t < 217 gilt dx/dt = 0; die gezeigte DGL gilt ab t ≥ 217.'
      : 'Für t < 217 bleibt der initialisierte Anteil konstant. Ab t = 217 wird jährlich entschieden; dazwischen bleibt x unverändert.';
    formula.querySelector('.formula-note').textContent = model.note;
    if (!model.note) formula.querySelector('.formula-note').remove();
    formula.append(paperSources(model));
    const primary = document.createElement('div'); primary.className = 'formula-primary';
    primary.append(formula.querySelector('.section-top'), formula.querySelector('.main-equation'));
    const aliases = document.createElement('p'); aliases.className = 'formula-aliases';
    aliases.textContent = model.kind === 'DGL' ? 'tf = temperature_factor · sf = social_norm_factor' : 'tf = temperature_factor';
    primary.append(aliases);
    const definitions = document.createElement('div'); definitions.className = 'formula-definitions';
    definitions.setAttribute('tabindex', '0');
    definitions.setAttribute('role', 'region');
    definitions.setAttribute('aria-label', 'Definitionen, Hilfsgleichungen und Quellen – separat scrollbar');
    definitions.append(...formula.childNodes);
    formula.append(primary, definitions);
    layout.append(formula, writing); content.append(layout);
    const notes = document.createElement('section'); notes.className = 'interpretation';
    notes.innerHTML = '<div class="section-top"><div><span class="eyebrow">02 · DEINE QUALITATIVE AUFARBEITUNG</span><h2>Was bedeutet diese Norm für LoopCup?</h2></div><span class="blank-badge">Deine Gedanken</span></div>';
    const current = book.notes[model.key];
    notes.append(field('Was wird mit dieser Norm qualitativ berechnet?', 'Beschreibe in deinen eigenen Worten, was die Gleichung im Beispiel berechnet.', current.calculation, { normField: 'calculation' }),
      field('Welche qualitative Bedeutung hat die Norm im Beispiel?', 'Übertrage die Norm auf den Markt für wiederverwendbare Becher.', current.meaning, { normField: 'meaning' }),
      field('Welchen Verlauf von x erwarte ich – und warum?', 'Deine Erwartung und ihre Begründung …', current.expectation, { normField: 'expectation' }));
    writing.append(notes);
    for (const [title, subtitle, items, variable] of [
      ['Jeden Parameter durchdenken.', '03 · PARAMETER', model.parameters, false],
      ['Variablen & Hilfsgrößen einordnen.', '04 · VARIABLEN', model.variables, true],
    ]) {
      const section = document.createElement('section'); section.className = 'parameter-section';
      section.innerHTML = `<div class="section-top"><div><span class="eyebrow">${subtitle}</span><h2>${title}</h2></div><button class="button expand-all" type="button">Alle aufklappen</button></div><div class="parameter-list"></div>`;
      items.forEach(name => section.querySelector('.parameter-list').append(parameterCard(model, name, variable)));
      section.querySelector('.expand-all').addEventListener('click', event => {
        const details = [...section.querySelectorAll('details')];
        const open = details.some(card => !card.open); details.forEach(card => { card.open = open; });
        event.currentTarget.textContent = open ? 'Alle zuklappen' : 'Alle aufklappen';
      });
      writing.append(section);
    }
    const navigation = document.createElement('div'); navigation.className = 'bottom-navigation';
    for (const [nextIndex, label] of [[index - 1, '← Vorherige Norm'], [index + 1, 'Nächste Norm →']]) {
      if (NORMS[nextIndex]) { const anchor = document.createElement('a'); anchor.href = `#${NORMS[nextIndex].key}`; anchor.className = 'button'; anchor.textContent = label; navigation.append(anchor); }
      else navigation.append(document.createElement('span'));
    }
    writing.append(navigation); renderNav();
    const equation = primary.querySelector('.main-equation'), equationMath = equation.querySelector('math');
    const fitEquation = () => {
      const style = getComputedStyle(equation);
      const available = equation.clientWidth - parseFloat(style.paddingLeft) - parseFloat(style.paddingRight);
      equationMath.style.fontSize = '18px';
      // Fractions and stretching brackets do not scale exactly linearly in MathML.
      for (let attempt = 0; attempt < 10; attempt++) {
        const currentSize = parseFloat(getComputedStyle(equationMath).fontSize);
        const width = equationMath.getBoundingClientRect().width;
        if (width <= 0 || available <= 0 || width <= available - 2) break;
        // Keep one line; on very narrow screens retain legible type and scrolling.
        const size = Math.max(14, Math.min(currentSize, currentSize * (available - 4) / width - .05));
        if (Math.abs(size - currentSize) <= .1) break;
        equationMath.style.fontSize = `${size}px`;
      }
    };
    equationObserver = new ResizeObserver(fitEquation); equationObserver.observe(equation);
    requestAnimationFrame(fitEquation);
  }
  $('#norm-content').addEventListener('input', event => {
    const input = event.target; if (!(input instanceof HTMLTextAreaElement)) return;
    const model = currentModel(), notes = book.notes[model.key];
    if (input.dataset.normField) notes[input.dataset.normField] = input.value;
    else notes.parameters[input.dataset.parameter][input.dataset.field] = input.value;
    const count = progress(book, model);
    $('.filled-count').textContent = `${count.filled} von ${count.total} Feldern gefüllt`;
    const card = input.closest('.parameter-card');
    if (card) card.querySelector('.parameter-count').textContent = `${PARAM_FIELDS.filter(key => notes.parameters[card.dataset.parameter][key].trim()).length} / 3`;
    renderNav(); scheduleSave();
  });
  $('#case-study').value = book.caseStudy;
  $('#case-study').addEventListener('input', event => { book.caseStudy = event.target.value; scheduleSave(); });
  $('#search').addEventListener('input', renderNav);
  $('#export-json').addEventListener('click', () => download(JSON.stringify(book, null, 2), 'json', 'application/json'));
  $('#export-markdown').addEventListener('click', () => download(markdown(book), 'md', 'text/markdown;charset=utf-8'));
  $('#import-button').addEventListener('click', () => $('#import-file').click());
  $('#import-file').addEventListener('change', async event => {
    const file = event.target.files[0]; event.target.value = ''; if (!file) return;
    try {
      if (file.size > 10000000) throw new Error('Die Sicherung ist zu groß (maximal 10 MB).');
      importCandidate = validateWorkbook(JSON.parse(await file.text()));
      $('#import-dialog').showModal();
    } catch (error) { importCandidate = null; notice(error instanceof SyntaxError ? 'Die Datei enthält kein gültiges JSON.' : error.message); }
  });
  $('#import-dialog').addEventListener('close', () => {
    if ($('#import-dialog').returnValue === 'import' && importCandidate) {
      book = importCandidate; storageUsable = true; $('#case-study').value = book.caseStudy;
      notice('Sicherung übernommen.'); scheduleSave(); save(); render();
    }
    importCandidate = null;
  });
  function closeMenu() { document.body.classList.remove('nav-open'); $('#menu-toggle').setAttribute('aria-expanded', 'false'); $('#nav-shade').hidden = true; }
  $('#menu-toggle').addEventListener('click', () => {
    if (document.body.classList.contains('nav-open')) return closeMenu();
    document.body.classList.add('nav-open'); $('#menu-toggle').setAttribute('aria-expanded', 'true'); $('#nav-shade').hidden = false;
  });
  $('#nav-shade').addEventListener('click', closeMenu);
  document.addEventListener('keydown', event => { if (event.key === 'Escape') closeMenu(); });
  window.addEventListener('hashchange', () => { save(); render(); closeMenu(); window.scrollTo(0, 0); $('h1').focus({ preventScroll: true }); });
  window.addEventListener('pagehide', save);
  document.addEventListener('visibilitychange', () => { if (document.visibilityState === 'hidden') save(); });
  // Keep the formula below the toolbar even when its buttons wrap or text is zoomed.
  const toolbar = $('.topbar');
  const updateToolbarHeight = () => document.documentElement.style.setProperty('--topbar-height', `${Math.ceil(toolbar.getBoundingClientRect().height)}px`);
  updateToolbarHeight();
  const toolbarObserver = new ResizeObserver(updateToolbarHeight); toolbarObserver.observe(toolbar);
  render();
  if (!storageUsable) $('#save-label').textContent = 'Bitte als Datei sichern';
})();
