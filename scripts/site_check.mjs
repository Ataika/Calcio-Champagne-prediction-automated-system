/** Browser QA for the offline defense academy and generated download set. */
import { spawn } from "node:child_process";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import assert from "node:assert/strict";

const root = path.resolve(import.meta.dirname, "..");
const site = path.join(root, "defense/site");
const port = 8510;
const chromeBin = process.env.CHROME_BIN || (process.platform === "darwin"
  ? "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" : "google-chrome");
const profile = fs.mkdtempSync(path.join(os.tmpdir(), "calcio-academy-check-"));
const server = spawn(process.env.PYTHON_BIN || "python3", ["-m", "http.server", String(port), "--bind", "127.0.0.1", "--directory", site], { stdio: "ignore" });
const chrome = spawn(chromeBin, ["--headless", "--disable-gpu", "--no-first-run", "--no-default-browser-check",
  `--user-data-dir=${profile}`, "--remote-debugging-port=0", "about:blank"], { stdio: "ignore" });
const pause = ms => new Promise(resolve => setTimeout(resolve, ms));
let ws;
const results = [], errors = [];
try {
  let siteReady = false;
  for (let i = 0; i < 50; i++) { try { siteReady = (await fetch(`http://127.0.0.1:${port}/`)).ok; if (siteReady) break; } catch {} await pause(100); }
  assert.ok(siteReady, "static study-site server did not start");
  const activePortFile = path.join(profile, "DevToolsActivePort");
  let debugPort;
  for (let i = 0; i < 100; i++) { if (fs.existsSync(activePortFile)) { debugPort = Number(fs.readFileSync(activePortFile, "utf8").split("\n")[0]); break; } await pause(100); }
  assert.ok(debugPort, "Chrome DevTools port did not start");
  let pages;
  for (let i = 0; i < 50; i++) { try { pages = await (await fetch(`http://127.0.0.1:${debugPort}/json/list`)).json(); if (pages.some(p => p.type === "page")) break; } catch {} await pause(100); }
  const target = pages?.find(p => p.type === "page"); assert.ok(target, "Chrome page target is unavailable");
  ws = new WebSocket(target.webSocketDebuggerUrl);
  await new Promise((resolve, reject) => { ws.addEventListener("open", resolve, { once: true }); ws.addEventListener("error", reject, { once: true }); });
  let seq = 0; const pending = new Map();
  ws.addEventListener("message", event => { const data = JSON.parse(event.data);
    if (data.method === "Runtime.exceptionThrown") errors.push(data.params.exceptionDetails.text);
    if (pending.has(data.id)) { const { resolve, reject } = pending.get(data.id); pending.delete(data.id); data.error ? reject(new Error(JSON.stringify(data.error))) : resolve(data.result); }
  });
  const call = (method, params = {}) => new Promise((resolve, reject) => { const id=++seq; const timer=setTimeout(()=>{pending.delete(id);reject(new Error(`CDP timeout: ${method}`));},15000);pending.set(id,{resolve:r=>{clearTimeout(timer);resolve(r);},reject});ws.send(JSON.stringify({id,method,params})); });
  const evaluate = async expression => { const r=await call("Runtime.evaluate",{expression,returnByValue:true,awaitPromise:true});if(r.exceptionDetails)throw new Error(r.exceptionDetails.exception?.description||r.exceptionDetails.text);return r.result.value; };
  const wait = async (expression, name) => { for(let i=0;i<50;i++){if(await evaluate(expression))return;await pause(100);}throw new Error(`Timed out: ${name}`); };
  const ready = () => wait("document.querySelector('#main')?.children.length>0", "site view");
  const go = async hash => { await evaluate(`location.hash=${JSON.stringify(hash)}`);await pause(50);await ready(); };
  const check = async (name, fn) => { await fn();results.push(name);console.log(`PASS ${name}`); };
  await call("Runtime.enable"); await call("Page.enable");
  await call("Page.navigate",{url:`http://127.0.0.1:${port}/`});await ready();
  await check("Offline home and four study roles render",async()=>{
    assert.equal(await evaluate("document.querySelectorAll('.role-card').length"),4);
    assert.equal(await evaluate("document.querySelectorAll('nav a').length"),7);
  });
  await check("Personal role checks persist in local browser storage",async()=>{
    await go("roles/jacopo");assert.ok((await evaluate("document.body.innerText")).includes("79 GF"));
    await evaluate("document.querySelector('[data-check]')?.click()");await evaluate("document.querySelector('[data-check]')?.dispatchEvent(new Event('change',{bubbles:true}))");
    assert.ok(await evaluate("Object.keys(JSON.parse(localStorage.getItem('calcio-defense-v1')||'{}')).length>0"));
    await go("home");await go("roles/jacopo");assert.ok(await evaluate("document.querySelector('[data-check]')?.checked"));
  });
  await check("Pipeline walkthrough shows five stages and repository links",async()=>{
    await go("system/store");assert.equal(await evaluate("document.querySelectorAll('.stage').length"),5);
    assert.ok(await evaluate("[...document.querySelectorAll('.file-link')].every(a=>a.href.includes('github.com/Ataika/'))"));
  });
  await check("Evidence explains the score ranks and missing xG",async()=>{
    await go("evidence");const t=(await evaluate("document.body.innerText")).toLowerCase();
    for(const part of ["79/35/+44","61/43/+18","xg coverage in loaded match source","not available","145.4×"])assert.ok(t.includes(part),`${part} missing from evidence: ${t.slice(-1400)}`);
  });
  await check("Question search and examiner answer reveal work",async()=>{
    await go("questions/all");await evaluate("document.querySelector('#question-search').value='xG';document.querySelector('#question-search').dispatchEvent(new Event('input',{bubbles:true}))");
    assert.equal(await evaluate("document.querySelectorAll('#question-list details').length"),2);
    await evaluate("[...document.querySelectorAll('#question-list details')].find(d=>d.textContent.toLowerCase().includes('do we have xg'))?.querySelector('summary').click()");
    assert.ok((await evaluate("[...document.querySelectorAll('#question-list details')].find(d=>d.textContent.toLowerCase().includes('do we have xg'))?.querySelector('.answer').textContent")).includes("No xG field"));
    await evaluate("document.querySelector('#question-search').value='';document.querySelector('#question-search').dispatchEvent(new Event('input',{bubbles:true}))");
    assert.equal(await evaluate("document.querySelectorAll('#question-list details').length"),35);
  });
  await check("15-minute rehearsal timer starts and pauses",async()=>{
    await go("rehearsal");assert.equal(await evaluate("document.querySelectorAll('.timeline-card').length"),10);
    await evaluate("document.querySelector('[data-action=timer-toggle]').click()");await pause(1100);
    const value=await evaluate("document.querySelector('#timer').textContent");assert.notEqual(value,"15:00");
    await evaluate("document.querySelector('[data-action=timer-toggle]').click()");
  });
  await check("Presentation deck supports arrows and speaker notes",async()=>{
    await call("Page.navigate",{url:`http://127.0.0.1:${port}/presentation.html`});
    await wait("document.querySelector('.slide.active')", "presentation deck");
    assert.equal(await evaluate("document.querySelectorAll('.slide').length"),10);
    await evaluate("document.dispatchEvent(new KeyboardEvent('keydown',{key:'ArrowRight'}))");
    assert.ok((await evaluate("document.querySelector('.slide.active .kicker').textContent")).startsWith("02 /"));
    await evaluate("document.dispatchEvent(new KeyboardEvent('keydown',{key:'n'}))");
    assert.ok(await evaluate("document.body.classList.contains('show-notes') && !document.querySelector('.slide.active .speaker-notes').hidden"));
  });
  await check("Seven PDFs and both project archives are downloadable",async()=>{
    const files=["Project-Report.pdf","Team-Defense-Guide.pdf","Presentation.pdf","Role-neda.pdf","Role-lill.pdf","Role-jacopo.pdf","Role-atai.pdf","Defense-Materials.zip","Project-Package.zip"];
    const status=await evaluate(`Promise.all(${JSON.stringify(files)}.map(async f=>(await fetch('downloads/'+f,{method:'HEAD'})).status))`);
    assert.deepEqual(status,files.map(()=>200));
    await call("Page.navigate",{url:`http://127.0.0.1:${port}/#materials`});await ready();
    const links=await evaluate("[...document.querySelectorAll('a[download]')].map(a=>a.getAttribute('href'))");assert.ok(links.some(x=>x.endsWith('Project-Report.pdf')));
  });
  await check("390px study site has no horizontal page overflow",async()=>{
    await call("Emulation.setDeviceMetricsOverride",{width:390,height:844,deviceScaleFactor:1,mobile:true});
    await call("Page.navigate",{url:`http://127.0.0.1:${port}/#roles/jacopo`});await ready();
    assert.ok(await evaluate("document.documentElement.scrollWidth<=window.innerWidth"));
    await call("Emulation.clearDeviceMetricsOverride");
  });
  if(errors.length)throw new Error(`Browser exceptions: ${errors.join("; ")}`);
  const output={checked_at:new Date().toISOString(),passed:results.length,checks:results,exceptions:errors};
  fs.writeFileSync(path.join(root,"defense/site-check.json"),JSON.stringify(output,null,2)+"\n");
  console.log(`Completed ${results.length} academy checks.`);
} finally {
  ws?.close();chrome.kill("SIGTERM");server.kill("SIGTERM");
  await Promise.all([chrome,server].map(child=>new Promise(resolve=>{const timer=setTimeout(resolve,1200);child.once("exit",()=>{clearTimeout(timer);resolve();});})));
  fs.rmSync(profile,{recursive:true,force:true});
}
