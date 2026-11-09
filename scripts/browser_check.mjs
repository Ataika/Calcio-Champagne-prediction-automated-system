/** Browser integration checks without a downloaded browser or npm dependencies.
 * Run: node scripts/browser_check.mjs (uses an isolated Chrome profile).
 */
import { spawn } from "node:child_process";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import assert from "node:assert/strict";

const base = process.env.CALCIO_URL || "http://localhost:8502";
const chromeBin =
  process.env.CHROME_BIN ||
  (process.platform === "darwin"
    ? "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
    : "google-chrome");
const profile = fs.mkdtempSync(path.join(os.tmpdir(), "calcio-browser-"));
const artifact = path.resolve("artifacts");
fs.mkdirSync(artifact, { recursive: true });
const pause = (ms) => new Promise((r) => setTimeout(r, ms));
const chrome = spawn(
  chromeBin,
  [
    "--headless",
    "--disable-gpu",
    "--no-first-run",
    "--no-default-browser-check",
    `--user-data-dir=${profile}`,
    "--remote-debugging-port=9347",
    "about:blank",
  ],
  { stdio: "ignore" },
);
let ws;
const errors = [],
  results = [];
try {
  let pages;
  for (let i = 0; i < 50; i++) {
    try {
      pages = await (await fetch("http://127.0.0.1:9347/json/list")).json();
      if (pages.some((p) => p.type === "page")) break;
    } catch {}
    await pause(200);
  }
  assert.ok(pages, "Chrome debugging endpoint did not start");
  ws = new WebSocket(pages.find((p) => p.type === "page").webSocketDebuggerUrl);
  await new Promise((resolve, reject) => {
    ws.addEventListener("open", resolve, { once: true });
    ws.addEventListener("error", reject, { once: true });
  });
  let seq = 0;
  const pending = new Map();
  ws.addEventListener("message", (event) => {
    const data = JSON.parse(event.data);
    if (data.method === "Runtime.exceptionThrown")
      errors.push(
        data.params.exceptionDetails.text +
          ": " +
          (data.params.exceptionDetails.exception?.description || ""),
      );
    if (pending.has(data.id)) {
      pending.get(data.id)(data);
      pending.delete(data.id);
    }
  });
  const call = (method, params = {}) =>
    new Promise((resolve, reject) => {
      const id = ++seq;
      const timeout = setTimeout(() => {
        pending.delete(id);
        reject(new Error("CDP timeout: " + method));
      }, 15000);
      pending.set(id, (m) => {
        clearTimeout(timeout);
        m.error
          ? reject(new Error(JSON.stringify(m.error)))
          : resolve(m.result);
      });
      ws.send(JSON.stringify({ id, method, params }));
    });
  const evaluate = async (expression) => {
    const result = await call("Runtime.evaluate", {
      expression,
      returnByValue: true,
      awaitPromise: true,
    });
    if (result.exceptionDetails)
      throw new Error(
        result.exceptionDetails.exception?.description ||
          result.exceptionDetails.text,
      );
    return result.result.value;
  };
  const wait = async (expression, description) => {
    for (let i = 0; i < 80; i++) {
      if (await evaluate(expression)) return;
      await pause(150);
    }
    throw new Error("Timed out: " + description);
  };
  const ready = () =>
    wait(
      "document.querySelector('#app')?.getAttribute('aria-busy')==='false'",
      "page ready",
    );
  const go = async (fragment) => {
    await evaluate(`location.hash=${JSON.stringify(fragment)}`);
    await pause(80);
    await ready();
  };
  const check = async (name, fn) => {
    await fn();
    results.push(name);
    console.log("PASS " + name);
  };
  const screenshot = async (name, full = true) => {
    await pause(350);
    const metrics = await call("Page.getLayoutMetrics");
    const shot = await call("Page.captureScreenshot", {
      format: "png",
      captureBeyondViewport: true,
      clip: {
        x: 0,
        y: 0,
        width: await evaluate("window.innerWidth"),
        height: full
          ? metrics.cssContentSize.height
          : await evaluate("window.innerHeight"),
        scale: 1,
      },
    });
    fs.writeFileSync(
      path.join(artifact, name),
      Buffer.from(shot.data, "base64"),
    );
  };
  await call("Runtime.enable");
  await call("Page.enable");
  await call("Emulation.setDeviceMetricsOverride", {
    width: 1440,
    height: 1100,
    deviceScaleFactor: 1,
    mobile: false,
  });
  await call("Page.navigate", { url: base });
  await ready();
  await check(
    "Default is a complete Serie A season with 20 clubs",
    async () => {
      assert.equal(
        await evaluate("document.querySelectorAll('#ranking-body tr').length"),
        20,
      );
      assert.equal(
        await evaluate("document.querySelector('#season-select').value"),
        "24/25",
      );
      assert.ok(
        await evaluate(
          "document.querySelector('#app').innerText.includes('Inter Milan')",
        ),
      );
    },
  );
  await screenshot("overview-desktop.png");
  await screenshot("overview-first-screen.png", false);
  await check("Next-season chart uses its own visible sample", async () => {
    await evaluate("document.querySelector('[data-chart=next]').click()");
    await wait(
      "(() => { const rows = document.querySelectorAll('#analysis-detail tbody tr').length; return rows > 20 && document.querySelector('#chart-sample')?.textContent.includes(`n = ${rows} ·`); })()",
      "analysis table matches the displayed sample count",
    );
  });
  await check("League and season filters update real rows", async () => {
    await evaluate("document.querySelector('[data-league=GB1]').click()");
    await pause(100);
    await ready();
    assert.ok(
      await evaluate(
        "document.querySelector('#app').innerText.includes('Premier League')",
      ),
    );
    await evaluate(
      "let s=document.querySelector('#season-select');s.value='23/24';s.dispatchEvent(new Event('change',{bubbles:true}))",
    );
    await pause(100);
    await ready();
    assert.equal(
      await evaluate("document.querySelector('#season-select').value"),
      "23/24",
    );
  });
  await check("Club directory and profile share the same scope", async () => {
    await go("clubs");
    assert.equal(
      await evaluate("document.querySelectorAll('.club-card').length"),
      20,
    );
    await evaluate("document.querySelector('.club-card a').click()");
    await pause(100);
    await ready();
    assert.ok(await evaluate("document.querySelector('.trend-svg')!==null"));
    assert.equal(
      await evaluate("document.querySelector('#season-select').value"),
      "23/24",
    );
  });
  await check("Two selected clubs open a real comparison", async () => {
    await go("clubs");
    await evaluate(
      "document.querySelectorAll('[data-compare]')[0].click();document.querySelectorAll('[data-compare]')[1].click();document.querySelector('[data-action=compare]').click()",
    );
    await pause(100);
    await ready();
    assert.equal(
      await evaluate("document.querySelectorAll('.comparison-heading').length"),
      2,
    );
    const comparisonLabels = await evaluate("Array.from(document.querySelectorAll('.comparison-table tbody tr td:first-child'), cell => cell.textContent.trim())");
    for (const label of ["League goals scored · GF", "League goals conceded · GA", "League goal difference · GF − GA", "Attacking rank · goals per match", "Defensive rank · fewest conceded per match", "Shots per match · for / against", "Shots on target per match · for / against", "Poisson model rank · attack / defense", "SOT-based goal estimate · not measured xG"])
      assert.ok(comparisonLabels.includes(label), `Season comparison includes ${label}`);
    assert.ok(await evaluate("document.querySelector('.trend-svg')!==null"));
    assert.ok(await evaluate("document.querySelector('#head-to-head')!==null"));
  });
  const derbyResponse = await fetch(`${base}/api/head-to-head?team_a=46&team_b=5&competition=IT1&season=24%2F25`);
  assert.ok(derbyResponse.ok, "Derby API must be available");
  const derby = await derbyResponse.json();
  const interProfile = await (await fetch(`${base}/api/clubs/46?competition=IT1&season=24%2F25`)).json();
  assert.equal(interProfile.current.shots_matches, 38);
  assert.equal(interProfile.current.sot_matches, 38);
  assert.ok(interProfile.current.attack_model_rank != null);
  assert.ok(interProfile.current.proxy_xg_per_match != null);
  await check("Head-to-head reflects recorded scores or missing source coverage", async () => {
    await evaluate("location.href='/?league=IT1&season=24%2F25&teams=46,5#compare'");
    await wait("document.querySelector('#head-to-head') && document.querySelector('.comparison-heading')?.textContent.includes('Inter') && document.querySelector('#season-select')?.value==='24/25'", "derby comparison");
    assert.equal(await evaluate("document.querySelectorAll('#head-to-head .h2h-match').length"), derby.matches.length);
    if (derby.matches.length) {
      assert.deepEqual(
        await evaluate("Array.from(document.querySelectorAll('[data-h2h-stat=goals_for]'), cell => Number(cell.textContent))"),
        derby.teams.map(team => team.goals_for),
      );
      assert.deepEqual(
        await evaluate("Array.from(document.querySelectorAll('[data-h2h-stat=shots_on_target_per_match]'), cell => Number(cell.textContent))"),
        derby.teams.map(team => team.shots_on_target_per_match),
      );
      assert.deepEqual(
        await evaluate("Array.from(document.querySelectorAll('[data-h2h-stat=goals_against]'), cell => Number(cell.textContent))"),
        derby.teams.map(team => team.goals_against),
      );
      assert.deepEqual(
        await evaluate("Array.from(document.querySelectorAll('.h2h-score'), score => score.textContent.replace(/\\s/g,''))"),
        derby.matches.map(match => `${match.home_goals}–${match.away_goals}`),
      );
    } else {
      assert.ok(await evaluate("document.querySelector('#head-to-head .notice')!==null"));
    }
  });
  await screenshot("comparison-desktop.png");
  await check("Comparison keeps match coverage scoped to the selected season", async () => {
    const coverage = await (await fetch(`${base}/api/head-to-head?team_a=46&team_b=5&competition=IT1&season=20%2F21`)).json();
    await evaluate("location.href='/?league=IT1&season=20%2F21&teams=46,5#compare'");
    await wait("document.querySelector('#head-to-head') && document.querySelector('#season-select')?.value==='20/21'", "historical match coverage");
    assert.equal(await evaluate("document.querySelectorAll('.h2h-match').length"), coverage.matches.length);
    if (!coverage.matches.length)
      assert.ok(await evaluate("document.querySelector('#head-to-head .notice')!==null"));
  });
  await check(
    "Lab preloads five real inputs and clamps the attack budget",
    async () => {
      await go("lab");
      assert.equal(
        await evaluate("document.querySelectorAll('[data-feature]').length"),
        5,
      );
      await evaluate(
        "let s=document.querySelector('#input-total_spend');s.value=1000000;s.dispatchEvent(new Event('input',{bubbles:true}))",
      );
      await pause(900);
      assert.ok(
        await evaluate(
          "Number(document.querySelector('#input-attacking_spend').value)<=1000000",
        ),
      );
      assert.ok(
        await evaluate(
          "document.querySelector('#scenario-impact').innerText.includes('versus')",
        ),
      );
      await evaluate(
        "document.querySelector('[data-action=reset-lab]').click()",
      );
      await pause(600);
      assert.ok(
        await evaluate(
          "document.querySelector('#lab-evidence').innerText.includes('Chronological')",
        ),
      );
    },
  );
  await screenshot("lab-desktop.png");
  await check(
    "Project exposes methods, sources and measurement evidence",
    async () => {
      const evidence = await (await fetch(`${base}/api/project`)).json();
      await go("project");
      for (const id of [
        "architecture",
        "findings",
        "measurements",
        "sources",
        "course",
      ])
        assert.ok(await evaluate(`document.getElementById('${id}')!==null`));
      assert.ok(
        await evaluate(
          "document.querySelector('#app').innerText.includes('R²')",
        ),
      );
      assert.ok(
        await evaluate(
          "document.querySelector('#findings').innerText.toLowerCase().includes('defender spending') && document.querySelector('#findings').innerText.toLowerCase().includes('no useful linear signal')",
        ),
      );
      assert.ok(evidence.model_showdown.attack_defense.r2_score > evidence.model_showdown.attack_only.r2_score);
      assert.equal(evidence.shap[0].feature, "champagne_index");
      assert.equal(evidence.match_stats_coverage.sot_matches, 8907);
      assert.ok(await evaluate("document.querySelector('#findings').innerText.includes('descriptive association')"));
      const measurementText = await evaluate("document.querySelector('#measurements').innerText.toLowerCase()");
      assert.ok(measurementText.includes(evidence.benchmark?.system_runs?.length
        ? "complete startup" : evidence.benchmark ? "difference an index makes" : "no benchmark artifact"));
      assert.ok(
        await evaluate(
          "document.querySelector('#course').innerText.includes('Original brief checked')",
        ),
      );
    },
  );
  await screenshot("project-desktop.png");
  await check("Methodology dialog opens and closes with Escape", async () => {
    await evaluate(
      "document.querySelector('[data-action=methodology]').click()",
    );
    assert.ok(await evaluate("document.querySelector('dialog').open"));
    await call("Input.dispatchKeyEvent", {
      type: "keyDown",
      key: "Escape",
      code: "Escape",
      windowsVirtualKeyCode: 27,
    });
    await call("Input.dispatchKeyEvent", {
      type: "keyUp",
      key: "Escape",
      code: "Escape",
      windowsVirtualKeyCode: 27,
    });
    assert.equal(
      await evaluate("document.querySelector('dialog').open"),
      false,
    );
  });
  await call("Emulation.setDeviceMetricsOverride", {
    width: 390,
    height: 844,
    deviceScaleFactor: 1,
    mobile: true,
  });
  await evaluate("location.href='/?league=IT1&season=24%2F25#overview'");
  await pause(250);
  await ready();
  await evaluate("document.querySelector('[data-chart=season]').click()");
  await pause(200);
  await check("390px mobile overview has no page overflow", async () =>
    assert.ok(
      await evaluate(
        "document.documentElement.scrollWidth<=window.innerWidth+1",
      ),
    ),
  );
  await screenshot("overview-mobile.png");
  await check("Mobile head-to-head comparison fits within the viewport", async () => {
    await evaluate("location.href='/?league=IT1&season=24%2F25&teams=46,5#compare'");
    await wait("document.querySelector('#head-to-head') && document.querySelector('#season-select')?.value==='24/25'", "mobile derby results");
    assert.equal(await evaluate("document.querySelectorAll('#head-to-head .h2h-match').length"), derby.matches.length);
    assert.ok(await evaluate("document.documentElement.scrollWidth<=window.innerWidth+1"));
  });
  await screenshot("comparison-mobile.png");
  await go("clubs");
  await check("Mobile club grid stays within viewport", async () =>
    assert.ok(
      await evaluate(
        "document.documentElement.scrollWidth<=window.innerWidth+1",
      ),
    ),
  );
  await go("lab");
  await check("Mobile Lab stays within viewport", async () => {
    assert.equal(
      await evaluate("document.querySelectorAll('[data-feature]').length"),
      5,
    );
    assert.ok(
      await evaluate(
        "document.documentElement.scrollWidth<=window.innerWidth+1",
      ),
    );
  });
  await screenshot("lab-mobile.png");
  await go("project");
  await check("Mobile project evidence stays within viewport", async () =>
    assert.ok(
      await evaluate(
        "document.documentElement.scrollWidth<=window.innerWidth+1",
      ),
    ),
  );
  assert.deepEqual(errors, [], "Browser JavaScript exceptions");
  fs.writeFileSync(
    path.join(artifact, "browser-check.json"),
    JSON.stringify(
      { checked_at: new Date().toISOString(), base, checks: results, errors },
      null,
      2,
    ),
  );
  console.log(
    `Completed ${results.length} browser checks. Screenshots: ${artifact}`,
  );
} finally {
  ws?.close();
  chrome.kill("SIGTERM");
  setTimeout(() => fs.rmSync(profile, { recursive: true, force: true }), 1000);
}
