/** Render print-ready defense HTML to PDF with the installed Chrome; no npm deps. */
import { spawn } from "node:child_process";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { pathToFileURL } from "node:url";

const root = path.resolve(import.meta.dirname, "..");
const htmlDir = path.join(root, "defense/materials");
const outputDir = path.join(root, "defense/site/downloads");
const chromeBin = process.env.CHROME_BIN || (process.platform === "darwin"
  ? "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
  : "google-chrome");
const profile = fs.mkdtempSync(path.join(os.tmpdir(), "calcio-defense-print-"));
const chrome = spawn(chromeBin, ["--headless", "--disable-gpu", "--no-first-run",
  "--no-default-browser-check", "--allow-file-access-from-files", `--user-data-dir=${profile}`,
  "--remote-debugging-port=0", "about:blank"], { stdio: "ignore" });
const pause = ms => new Promise(resolve => setTimeout(resolve, ms));
let ws;
try {
  const activePortFile = path.join(profile, "DevToolsActivePort");
  let port;
  for (let i = 0; i < 100; i++) {
    if (fs.existsSync(activePortFile)) { port = Number(fs.readFileSync(activePortFile, "utf8").split("\n")[0]); break; }
    await pause(100);
  }
  if (!port) throw new Error("Chrome did not open its DevTools port");
  let pages;
  for (let i = 0; i < 50; i++) {
    try { pages = await (await fetch(`http://127.0.0.1:${port}/json/list`)).json(); if (pages.some(p => p.type === "page")) break; } catch {}
    await pause(100);
  }
  const page = pages?.find(p => p.type === "page");
  if (!page) throw new Error("Chrome page target is unavailable");
  ws = new WebSocket(page.webSocketDebuggerUrl);
  await new Promise((resolve, reject) => { ws.addEventListener("open", resolve, { once: true }); ws.addEventListener("error", reject, { once: true }); });
  let seq = 0;
  const pending = new Map();
  ws.addEventListener("message", event => {
    const data = JSON.parse(event.data);
    if (pending.has(data.id)) { const { resolve, reject } = pending.get(data.id); pending.delete(data.id); data.error ? reject(new Error(JSON.stringify(data.error))) : resolve(data.result); }
  });
  const call = (method, params = {}) => new Promise((resolve, reject) => {
    const id = ++seq; const timeout = setTimeout(() => { pending.delete(id); reject(new Error(`CDP timeout: ${method}`)); }, 20000);
    pending.set(id, { resolve: result => { clearTimeout(timeout); resolve(result); }, reject }); ws.send(JSON.stringify({ id, method, params }));
  });
  await call("Page.enable"); await call("Runtime.enable");
  const files = [
    [path.join(htmlDir, "Project-Report.html"), "Project-Report.pdf", false],
    [path.join(htmlDir, "Team-Defense-Guide.html"), "Team-Defense-Guide.pdf", false],
    ...["neda", "lill", "jacopo", "atai"].map(id => [path.join(htmlDir, `Role-${id}.html`), `Role-${id}.pdf`, false]),
    [path.join(root, "defense/site/presentation.html"), "Presentation.pdf", true],
  ];
  for (const [input, filename, landscape] of files) {
    await call("Page.navigate", { url: pathToFileURL(input).href });
    for (let i = 0; i < 100; i++) {
      const state = await call("Runtime.evaluate", { expression: "document.readyState === 'complete' && document.body?.innerText.length > 20", returnByValue: true, awaitPromise: true });
      if (state.result?.value) break;
      await pause(100);
    }
    await call("Runtime.evaluate", { expression: "document.fonts?.ready", awaitPromise: true, returnByValue: true });
    await pause(200);
    const pdf = await call("Page.printToPDF", { printBackground: true, preferCSSPageSize: true, displayHeaderFooter: false,
      landscape, paperWidth: landscape ? 13.333 : 8.267, paperHeight: landscape ? 7.5 : 11.693, transferMode: "ReturnAsBase64" });
    fs.writeFileSync(path.join(outputDir, filename), Buffer.from(pdf.data, "base64"));
    const stats = fs.statSync(path.join(outputDir, filename));
    console.log(`${filename}: ${(stats.size / 1024).toFixed(0)} KiB`);
  }
} finally {
  ws?.close(); chrome.kill("SIGTERM");
  await new Promise(resolve => { const timer = setTimeout(resolve, 1500); chrome.once("exit", () => { clearTimeout(timer); resolve(); }); });
  fs.rmSync(profile, { recursive: true, force: true });
}
