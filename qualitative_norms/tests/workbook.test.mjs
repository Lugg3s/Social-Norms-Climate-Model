import test from 'node:test';
import assert from 'node:assert/strict';
await import('../dist/model-data.js');
await import('../dist/papers.js');
const { NORMS, NORM_FIELDS, PARAM_FIELDS, emptyWorkbook, validateWorkbook, progress, markdown } = globalThis.NormWorkbook;
test('all ten distinct active norms start with empty qualitative fields', () => {
  const book = emptyWorkbook();
  assert.equal(NORMS.length, 10);
  assert.equal(new Set(NORMS.map(model => model.key)).size, 10);
  for (const model of NORMS) {
    assert.deepEqual(NORM_FIELDS.map(key => book.notes[model.key][key]), ['', '', '']);
    assert.equal(progress(book, model).filled, 0);
    assert.equal(progress(book, model).total, 3 + 3 * (model.parameters.length + model.variables.length));
    for (const parameter of [...model.parameters, ...model.variables])
      assert.deepEqual(PARAM_FIELDS.map(key => book.notes[model.key].parameters[parameter][key]), ['', '', '']);
  }
});
test('backup roundtrip preserves every norm and does not share repeated parameter entries', () => {
  const book = emptyWorkbook();
  book.notes.baseline.parameters.beta.explanation = 'Meine eigene Notiz';
  book.notes.agents.parameters.beta.larger = 'Eine andere Hypothese';
  const restored = validateWorkbook(JSON.parse(JSON.stringify(book)));
  assert.equal(restored.notes.baseline.parameters.beta.explanation, 'Meine eigene Notiz');
  assert.equal(restored.notes.agents.parameters.beta.explanation, '');
  assert.equal(restored.notes.agents.parameters.beta.larger, 'Eine andere Hypothese');
  assert.equal(progress(restored, NORMS[0]).filled, 1);
  assert.match(markdown(restored), /Meine eigene Notiz/);
  assert.match(markdown(restored), /https:\/\/doi.org\/10.1371\/journal.pcbi.1007000/);
  assert.match(markdown(restored), /https:\/\/doi.org\/10.1038\/s41558-017-0031-7/);
});
test('malformed, incomplete and unsupported backups are rejected before replacing notes', () => {
  assert.throws(() => validateWorkbook({ version: 2 }));
  const book = emptyWorkbook(); delete book.notes.dynamic.parameters.tau_ref;
  assert.throws(() => validateWorkbook(book));
  const wrong = emptyWorkbook(); wrong.notes.agents.meaning = '<script>not executed</script>';
  assert.equal(validateWorkbook(wrong).notes.agents.meaning, '<script>not executed</script>');
  wrong.notes.agents.meaning = {};
  assert.throws(() => validateWorkbook(wrong));
});
test('retired approval notes survive import without restoring the alpha parameter', () => {
  const book = emptyWorkbook();
  book.notes.approval.parameters.social_norm_factor.explanation = 'Meine sf-Notiz';
  book.notes.approval.parameters.alpha = { explanation: 'Meine frühere alpha-Notiz', larger: 'Meine Erwartung', smaller: '' };
  const restored = validateWorkbook(book);
  assert.ok(!NORMS.find(model => model.key === 'approval').parameters.includes('alpha'));
  assert.ok(!('alpha' in restored.notes.approval.parameters));
  assert.match(restored.notes.approval.parameters.social_norm_factor.explanation, /Meine sf-Notiz/);
  assert.match(restored.notes.approval.parameters.social_norm_factor.explanation, /Meine frühere alpha-Notiz/);
  assert.match(restored.notes.approval.parameters.social_norm_factor.larger, /Meine Erwartung/);
  assert.deepEqual(validateWorkbook(restored), restored);
});
test('the annual agent model has no replicator parameters and preserves intention/behaviour distinction', () => {
  const agents = NORMS.find(model => model.key === 'agents');
  assert.ok(!agents.parameters.includes('kappa'));
  assert.ok(!agents.parameters.includes('social_norm_factor'));
  assert.ok(agents.variables.includes('BI_i') && agents.variables.includes('actual_behavior_i'));
  assert.match(agents.auxiliary.join(''), /BIᵢ ≥ ψ/);
  for (const model of NORMS.filter(model => model.key !== 'agents')) {
    assert.ok(model.parameters.includes('kappa'));
    assert.ok(model.parameters.includes('social_norm_factor'));
    assert.match(model.formula, />sf<\/mi>/);
  }
});
test('static c_inj notes migrate to sf while combined-norm c_inj notes stay separate', () => {
  const book = emptyWorkbook();
  book.notes['static-injunctive'].parameters.c_inj = { explanation: 'Meine alte Notiz', larger: '', smaller: '' };
  book.notes.combined.parameters.c_inj.explanation = 'Meine kombinierte Norm';
  const restored = validateWorkbook(book);
  assert.ok(!NORMS.find(model => model.key === 'static-injunctive').parameters.includes('c_inj'));
  assert.ok(!('c_inj' in restored.notes['static-injunctive'].parameters));
  assert.match(restored.notes['static-injunctive'].parameters.social_norm_factor.explanation, /Meine alte Notiz/);
  assert.equal(restored.notes.combined.parameters.c_inj.explanation, 'Meine kombinierte Norm');
  assert.deepEqual(validateWorkbook(restored), restored);
});
