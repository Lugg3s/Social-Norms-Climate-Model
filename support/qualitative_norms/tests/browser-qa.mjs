// Browser QA through local Edge DevTools; no additional packages required.
import { spawn } from 'node:child_process';
import { mkdirSync, mkdtempSync, readFileSync, readdirSync, writeFileSync } from 'node:fs';
import { pathToFileURL } from 'node:url';
import path from 'node:path';
import assert from 'node:assert/strict';
const qa = path.resolve('qa'); mkdirSync(qa, { recursive: true });
const profile = mkdtempSync(path.join(qa, 'edge-'));
const browser = spawn('C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe',
  ['--headless=new', '--disable-gpu', '--no-first-run', '--no-default-browser-check',
   '--disable-background-networking', '--disable-component-update', '--disable-sync',
   '--remote-debugging-address=127.0.0.1', '--remote-debugging-port=9236', `--user-data-dir=${profile}`, 'about:blank'],
  { windowsHide: true, stdio: 'ignore' });
let socket;
const pause = ms => new Promise(resolve => setTimeout(resolve, ms));
try {
  let target;
  for (let count = 0; count < 150; count++) {
    try { target = (await (await fetch('http://127.0.0.1:9236/json/list')).json()).find(item => item.type === 'page'); } catch {}
    if (target?.webSocketDebuggerUrl) break;
    await pause(200);
  }
  assert.ok(target?.webSocketDebuggerUrl, 'Headless Edge must be ready');
  socket = new WebSocket(target.webSocketDebuggerUrl);
  await new Promise((resolve, reject) => { socket.addEventListener('open', resolve, { once: true }); socket.addEventListener('error', reject, { once: true }); });
  let nextId = 0;
  const requests = new Map(), errors = [];
  socket.addEventListener('message', async event => {
    const raw = typeof event.data === 'string' ? event.data : await event.data.text();
    const message = JSON.parse(raw);
    if (message.method === 'Runtime.exceptionThrown') errors.push(message.params.exceptionDetails.text);
    if (message.id && requests.has(message.id)) {
      const { resolve, reject, timer } = requests.get(message.id); requests.delete(message.id); clearTimeout(timer);
      if (message.error) reject(new Error(message.error.message)); else resolve(message.result);
    }
  });
  const call = (method, params = {}) => new Promise((resolve, reject) => {
    const id = ++nextId;
    const timer = setTimeout(() => { requests.delete(id); reject(new Error(`Timeout: ${method}`)); }, 30000);
    requests.set(id, { resolve, reject, timer }); socket.send(JSON.stringify({ id, method, params }));
  });
  const evaluate = async expression => {
    const result = await call('Runtime.evaluate', { expression, returnByValue: true, awaitPromise: true });
    if (result.exceptionDetails) throw new Error(result.exceptionDetails.text);
    return result.result.value;
  };
  console.log('Edge connected. Checking page …');
  await call('Runtime.enable');
  await call('Emulation.setDeviceMetricsOverride', { width: 1400, height: 1080, deviceScaleFactor: 1, mobile: false });
  await call('Page.navigate', { url: 'http://127.0.0.1:8765/' });
  for (let count = 0; count < 50; count++) { if (await evaluate('!!document.querySelector("#norm-content h1")')) break; await pause(100); }
  assert.equal(await evaluate('document.querySelectorAll(".norm-link").length'), 10);
  assert.equal(await evaluate('[...document.querySelectorAll("#norm-content textarea")].every(t => t.value === "")'), true);
  assert.equal(await evaluate('document.querySelectorAll("math").length'), 2);
  // Persistence across refresh and separation between norms.
  await evaluate('let t=document.querySelector("textarea[data-norm-field=meaning]"); t.value="Meine eigene Testnotiz"; t.dispatchEvent(new Event("input",{bubbles:true}));');
  await pause(450); await call('Page.reload'); await pause(450);
  assert.equal(await evaluate('document.querySelector("textarea[data-norm-field=meaning]").value'), 'Meine eigene Testnotiz');
  await evaluate('location.hash="agents"'); await pause(150);
  assert.equal(await evaluate('document.querySelector("textarea[data-norm-field=meaning]").value'), '');
  assert.equal(await evaluate('!!document.querySelector("details[data-parameter=eta]")'), true);
  assert.equal(await evaluate('!!document.querySelector("details[data-parameter=kappa]")'), false);
  // All norms render with their complete mathematical definitions.
  const models = await evaluate('NormWorkbook.NORMS.map(m=>({key:m.key,name:m.name,params:m.parameters.length,variables:m.variables.length,papers:m.paperReferences.map(r=>NormWorkbook.PAPERS[r.paper].url)}))');
  for (const model of models) {
    await evaluate(`location.hash=${JSON.stringify(model.key)}`); await pause(100);
    assert.equal(await evaluate('document.querySelector("h1").textContent'), model.name);
    assert.equal(await evaluate('document.querySelectorAll(".parameter-card").length'), model.params + model.variables);
    assert.deepEqual(await evaluate('[...document.querySelectorAll(".paper-links a")].map(a=>a.href)'), model.papers);
    assert.equal(await evaluate('[...document.querySelectorAll(".paper-links a")].every(a=>a.target==="_blank" && a.rel.includes("noopener"))'), true);
    assert.equal(await evaluate('document.documentElement.scrollWidth <= innerWidth+1'), true, `desktop overflow: ${model.key}`);
  }
  // Equations must stay visible while the writing area moves, including narrow
  // layouts, short screens and the much longer agent definitions.
  for (const [width, height] of [[1400, 1080], [1280, 720], [1024, 768], [390, 844], [844, 390]]) {
    await call('Emulation.setDeviceMetricsOverride', { width, height, deviceScaleFactor: 1, mobile: width < 800 });
    for (const model of models) {
      await evaluate(`location.hash=${JSON.stringify(model.key)}`); await pause(70);
      await evaluate('document.querySelectorAll(".parameter-card").forEach(card=>card.open=true); window.scrollTo(0,1400)');
      await pause(70);
      const geometry = () => evaluate(`(() => {
        const f=document.querySelector('.formula-card').getBoundingClientRect();
        const p=document.querySelector('.formula-primary').getBoundingClientRect();
        const w=document.querySelector('.writing-column').getBoundingClientRect();
        const toolbar=document.querySelector('.topbar').getBoundingClientRect();
        const equation=document.querySelector('.main-equation');
        return {top:f.top,bottom:f.bottom,primaryBottom:p.bottom,toolbarBottom:toolbar.bottom,
          sideBySide:w.right<=f.left,overflow:document.documentElement.scrollWidth>innerWidth+1,
          equationOverflow:equation.scrollWidth>equation.clientWidth+1,
          equationWidth:equation.clientWidth,mathWidth:equation.querySelector('math').getBoundingClientRect().width,
          fontSize:getComputedStyle(equation.querySelector('math')).fontSize};
      })()`);
      const before = await geometry();
      const context = `${model.key}, ${width}x${height}`;
      assert.ok(before.top >= before.toolbarBottom, `toolbar covers formula: ${context}`);
      assert.ok(before.bottom <= height, `formula outside viewport: ${context}`);
      assert.ok(before.primaryBottom <= before.bottom, `main equation clipped: ${context}`);
      assert.equal(before.sideBySide, width >= 1400, `reference layout: ${context}`);
      assert.equal(before.overflow, false, `page overflow: ${context}`);
      if (width >= 1024) assert.equal(before.equationOverflow, false, `main equation needs horizontal scrolling: ${context}, ${JSON.stringify(before)}`);
      await evaluate('window.scrollBy(0,500); document.querySelector(".formula-definitions").scrollTop=10000');
      await pause(50);
      const after = await geometry();
      assert.ok(Math.abs(after.top-before.top)<1, `formula moved with notes: ${context}`);
      assert.ok(Math.abs(after.primaryBottom-before.primaryBottom)<1, `definitions moved main equation: ${context}`);
      if (model.key === 'combined2' && width === 1400) {
        const shot = await call('Page.captureScreenshot', { format: 'png', captureBeyondViewport: false });
        writeFileSync(path.join(qa, 'sticky-desktop.png'), Buffer.from(shot.data, 'base64'));
      }
      if (model.key === 'agents' && width === 390) {
        const shot = await call('Page.captureScreenshot', { format: 'png', captureBeyondViewport: false });
        writeFileSync(path.join(qa, 'sticky-mobile.png'), Buffer.from(shot.data, 'base64'));
      }
    }
  }
  await call('Emulation.setDeviceMetricsOverride', { width: 1400, height: 1080, deviceScaleFactor: 1, mobile: false });
  await evaluate('location.hash="baseline"'); await pause(150);
  // Test the actual backup buttons, confirmation, validation and safe string rendering.
  const downloads = path.join(profile, 'downloads'); mkdirSync(downloads);
  await call('Page.setDownloadBehavior', { behavior: 'allow', downloadPath: downloads });
  await evaluate('document.querySelector("#export-json").click()');
  let downloaded;
  for (let count = 0; count < 50; count++) {
    downloaded = readdirSync(downloads).find(name => name.endsWith('.json'));
    if (downloaded) break; await pause(100);
  }
  assert.ok(downloaded, 'Backup file must download');
  const backup = JSON.parse(readFileSync(path.join(downloads, downloaded), 'utf8'));
  assert.equal(backup.notes.baseline.meaning, 'Meine eigene Testnotiz');
  await call('DOM.enable');
  const fileInput = async filename => {
    const { root } = await call('DOM.getDocument');
    const { nodeId } = await call('DOM.querySelector', { nodeId: root.nodeId, selector: '#import-file' });
    await call('DOM.setFileInputFiles', { nodeId, files: [filename] }); await pause(150);
  };
  const brokenPath = path.join(qa, 'broken.json'); writeFileSync(brokenPath, '{invalid');
  await fileInput(brokenPath);
  assert.equal(await evaluate('document.querySelector("textarea[data-norm-field=meaning]").value'), 'Meine eigene Testnotiz');
  const restorePath = path.join(qa, 'restore.json');
  backup.notes.baseline.meaning = '<script>window.injected=true</script>';
  writeFileSync(restorePath, JSON.stringify(backup)); await fileInput(restorePath);
  assert.equal(await evaluate('document.querySelector("#import-dialog").open'), true);
  await evaluate('document.querySelector("#import-dialog button[value=import]").click()'); await pause(100);
  assert.equal(await evaluate('document.querySelector("textarea[data-norm-field=meaning]").value'), backup.notes.baseline.meaning);
  assert.equal(await evaluate('typeof window.injected'), 'undefined');
  // Reset only this isolated test profile before making clean preview screenshots.
  writeFileSync(restorePath, await evaluate('JSON.stringify(NormWorkbook.emptyWorkbook())'));
  await fileInput(restorePath); await evaluate('document.querySelector("#import-dialog button[value=import]").click()'); await pause(150);
  await call('Page.reload'); await pause(350);
  const screenshot = async filename => { const result = await call('Page.captureScreenshot', { format: 'png', captureBeyondViewport: false }); writeFileSync(path.join(qa, filename), Buffer.from(result.data, 'base64')); };
  await screenshot('desktop.png');
  await call('Emulation.setDeviceMetricsOverride', { width: 390, height: 844, deviceScaleFactor: 1, mobile: true });
  await pause(100);
  assert.equal(await evaluate('document.documentElement.scrollWidth <= innerWidth+1'), true, 'mobile viewport overflow');
  await evaluate('document.querySelector("#menu-toggle").click()');
  assert.equal(await evaluate('document.querySelector("#menu-toggle").getAttribute("aria-expanded")'), 'true');
  await evaluate('document.querySelector("#nav-shade").click()');
  await pause(250);
  await screenshot('mobile.png');
  // The delivered index.html must work directly, without a local server.
  await call('Page.navigate', { url: pathToFileURL(path.resolve('dist/index.html')).href });
  for (let count = 0; count < 50; count++) { if (await evaluate('!!document.querySelector("#norm-content h1")')) break; await pause(100); }
  assert.equal(await evaluate('document.querySelectorAll(".norm-link").length'), 10);
  assert.equal(await evaluate('[...document.querySelectorAll("#norm-content textarea")].every(t => t.value === "")'), true);
  assert.deepEqual(errors, []);
  console.log('Browser QA passed: ten norms, corresponding paper links, blank fields, persistence, separated notes, equations, desktop/mobile layout, navigation, actual backup download/import, safe string rendering, direct file opening, no JS exceptions.');
} finally {
  socket?.close();
  browser.kill();
}
