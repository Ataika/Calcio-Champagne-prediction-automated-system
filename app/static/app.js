const $ = (selector, root = document) => root.querySelector(selector);
const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];
const escape = (value) =>
  String(value ?? "").replace(
    /[&<>"']/g,
    (c) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[
        c
      ],
  );
const number = (value, digits = 2) =>
  value == null
    ? "—"
    : Number(value).toLocaleString("en-GB", {
        minimumFractionDigits: digits,
        maximumFractionDigits: digits,
      });
const integer = (value) => number(value, 0);
const euro = (value) =>
  value == null
    ? "—"
    : Math.abs(value) >= 1e9
      ? `€${number(value / 1e9, 2)}bn`
      : Math.abs(value) >= 1e6
        ? `€${number(value / 1e6, 1)}m`
        : `€${integer(value)}`;
const signed = (value) =>
  value == null ? "—" : `${value > 0 ? "+" : ""}${number(value)}`;
const mean = (values) =>
  values.length ? values.reduce((a, b) => a + b, 0) / values.length : 0;
const median = (values) => {
  const sorted = [...values].sort((a, b) => a - b);
  const m = sorted.length >> 1;
  return sorted.length
    ? sorted.length % 2
      ? sorted[m]
      : (sorted[m - 1] + sorted[m]) / 2
    : 0;
};
const initials = (name) =>
  name
    .replace(/\b(FC|BC|AC|SSC|CF|SC|AFC|Club|Calcio|de|1899|1909)\b/gi, "")
    .trim()
    .split(/[\s-]+/)
    .slice(0, 2)
    .map((w) => w[0])
    .join("")
    .toUpperCase() || "FC";
const badge = (name, olive = false) =>
  `<span class="club-badge${olive ? " olive" : ""}" aria-hidden="true">${escape(initials(name))}</span>`;
const pValue = (value) =>
  value == null ? "—" : value < 0.0001 ? "< 0.0001" : number(value, 4);
let meta,
  currentData,
  routeVersion = 0,
  chartMode = "season",
  tableSort = "champagne_index",
  tableSearch = "",
  labState = null,
  labTimer,
  labSequence = 0;
let selected = [];
const cache = new Map();

function currentScope() {
  const params = new URLSearchParams(location.search);
  const league =
    meta.leagues.find((l) => l.id === params.get("league")) || meta.leagues[0];
  const picked = league.seasons.find(
    (s) => s.season_name === params.get("season") && s.complete,
  );
  return {
    league,
    competition: league.id,
    season: picked?.season_name || league.default_season,
  };
}
function scoped(path, extra = {}) {
  const { competition, season } = currentScope();
  return `${path}?${new URLSearchParams({ competition, season, ...extra })}`;
}
async function request(path, options = {}) {
  const response = await fetch(path, options);
  const data = await response.json();
  if (!response.ok)
    throw new Error(
      Array.isArray(data.detail)
        ? data.detail.map((e) => e.msg).join(". ")
        : data.detail || "Something went wrong. Please retry.",
    );
  return data;
}
async function seasonData() {
  const key = scoped("/api/season");
  if (!cache.has(key))
    cache.set(
      key,
      request(key).catch((error) => {
        cache.delete(key);
        throw error;
      }),
    );
  return cache.get(key);
}
function toast(message) {
  const el = $("#toast");
  el.textContent = message;
  el.classList.add("visible");
  clearTimeout(toast.timer);
  toast.timer = setTimeout(() => el.classList.remove("visible"), 3600);
}
function href(view, extra = {}) {
  const url = new URL(location.href);
  for (const [key, value] of Object.entries(extra))
    url.searchParams.set(key, value);
  url.hash = view;
  return `${url.search}${url.hash}`;
}
function routeName() {
  return location.hash.slice(1) || "overview";
}
function setScope(leagueId, seasonName) {
  const changedLeague = leagueId !== currentScope().competition;
  const league = meta.leagues.find((l) => l.id === leagueId);
  const url = new URL(location.href);
  url.searchParams.set("league", league.id);
  url.searchParams.set("season", seasonName || league.default_season);
  url.searchParams.delete("team");
  url.searchParams.delete("teams");
  if (
    (changedLeague && routeName().startsWith("club/")) ||
    routeName() === "compare"
  )
    url.hash = "clubs";
  selected = [];
  tableSearch = "";
  updateTray();
  history.pushState({}, "", url);
  render();
}
function filters() {
  const { league, season } = currentScope();
  return `<div class="filters"><span class="filter-label hide-tablet">The competition</span><div class="league-tabs" role="group" aria-label="Competition">${meta.leagues.map((l) => `<button class="league-tab ${l.id === league.id ? "active" : ""}" data-league="${l.id}" aria-pressed="${l.id === league.id}">${escape(l.name)}</button>`).join("")}</div><div class="season-filter"><label class="filter-label" for="season-select">Season</label><select id="season-select">${league.seasons.map((s) => `<option value="${s.season_name}" ${s.season_name === season ? "selected" : ""} ${!s.complete ? "disabled" : ""}>${s.season_name}${!s.complete ? " · partial" : ""}</option>`).join("")}</select></div><span class="coverage-chip">Season sample · 15+ matches</span></div>`;
}
function hero(eyebrow, title, copy, extra = "", small = false) {
  return `<section class="hero ${small ? "hero-small" : ""}"><div><span class="eyebrow">${eyebrow}</span><h1>${title}</h1>${copy ? `<p class="hero-copy">${copy}</p>` : ""}</div>${extra}</section>`;
}
function metric(label, value, note = "") {
  return `<div class="metric"><div class="metric-label">${label}</div><div class="metric-value">${value}</div>${note ? `<div class="metric-note">${note}</div>` : ""}</div>`;
}
function stat(label, value, note = "") {
  return `<div class="stat-row"><div class="stat-label">${label}${note ? `<small>${note}</small>` : ""}</div><strong>${value}</strong></div>`;
}

function scatter(
  rows,
  {
    x = "total_spend",
    y = "champagne_index",
    fit = null,
    target = "chart",
    mode = "season",
  } = {},
) {
  const valid = rows.filter((r) => r[x] != null && r[y] != null);
  if (!valid.length)
    return '<div class="chart-empty">No comparable season pairs in this window. Select another season or league.</div>';
  const mobile = window.innerWidth < 600;
  const width = mobile ? Math.max(320, window.innerWidth - 70) : 820,
    height = 350;
  const left = 58,
    right = 22,
    top = 33,
    bottom = 58,
    w = width - left - right,
    h = height - top - bottom;
  const xMax = Math.max(...valid.map((r) => r[x]), 1) * 1.12;
  const ys = valid.map((r) => r[y]),
    yMin = y === "delta_index" ? Math.min(...ys, 0) * 1.18 : 0;
  const yMax = Math.max(...ys, 0.2) * 1.15,
    ySpan = yMax - yMin || 1;
  const X = (v) => left + (v / xMax) * w,
    Y = (v) => top + h - ((v - yMin) / ySpan) * h;
  const tickX = (v) =>
    x === "champagne_index" ? number(v, 1) : `€${integer(v / 1e6)}m`;
  let svg = `<svg viewBox="0 0 ${width} ${height}" class="scatter-svg" role="img" aria-labelledby="${target}-title ${target}-desc"><title id="${target}-title">${y === "delta_index" ? "Transfer spending and change in next season’s index" : y === "position" ? "Champagne Index and final league position" : "Transfer spending and attacking output"}</title><desc id="${target}-desc">${valid.length} club-seasons. Each point can be opened as a club profile. An equivalent data table is provided below the chart.</desc>`;
  for (let i = 0; i <= 4; i++) {
    const yy = yMin + (ySpan * i) / 4,
      xx = (xMax * i) / 4;
    svg += `<line class="gridline" x1="${left}" y1="${Y(yy)}" x2="${width - right}" y2="${Y(yy)}"/><text x="${left - 11}" y="${Y(yy) + 3}" text-anchor="end">${number(yy, 1)}</text><text x="${X(xx)}" y="${height - 32}" text-anchor="middle">${tickX(xx)}</text>`;
  }
  if (y === "champagne_index") {
    const medX = median(valid.map((r) => r[x])),
      medY = median(ys);
    svg += `<line x1="${X(medX)}" y1="${top}" x2="${X(medX)}" y2="${top + h}" stroke="#bbb6a7" stroke-dasharray="3 5"/><line x1="${left}" y1="${Y(medY)}" x2="${width - right}" y2="${Y(medY)}" stroke="#bbb6a7" stroke-dasharray="3 5"/>${mobile ? `<text x="${left}" y="16">Champagne Index</text>` : `<text class="quadrant" x="${left + 8}" y="18">LESS SPEND / MORE OUTPUT</text><text class="quadrant" x="${width - right}" y="18" text-anchor="end">MORE SPEND / MORE OUTPUT</text>`}`;
  } else if (y === "delta_index" && yMin < 0)
    svg += `<line x1="${left}" y1="${Y(0)}" x2="${width - right}" y2="${Y(0)}" stroke="#aaa593"/>`;
  if (fit?.slope != null) {
    const a = fit.intercept,
      b = fit.slope * xMax + fit.intercept;
    const clipId = `${target}-clip`;
    svg += `<defs><clipPath id="${clipId}"><rect x="${left}" y="${top}" width="${w}" height="${h}"/></clipPath></defs><line x1="${X(0)}" y1="${Y(a)}" x2="${X(xMax)}" y2="${Y(b)}" stroke="#752d40" stroke-width="1.5" stroke-dasharray="6 4" clip-path="url(#${clipId})"/>`;
  }
  const leader = [...valid].sort((a, b) => b[y] - a[y])[0],
    highSpend = [...valid].sort((a, b) => b[x] - a[x])[0];
  for (const row of valid) {
    const cx = X(row[x]),
      cy = Y(row[y]),
      isLeader = row === leader;
    svg += `<g class="point" tabindex="0" role="link" data-team="${row.team_id}" data-x="${row[x]}" data-y="${row[y]}" data-name="${escape(row.team_name)}" data-season="${escape(row.season_name)}" data-mode="${mode}" aria-label="${escape(row.team_name)} ${escape(row.season_name)}, ${euro(row[x])}, index ${number(row[y])}. Open club profile"><circle class="dot" cx="${cx}" cy="${cy}" r="${valid.length > 50 ? 4.5 : isLeader ? 8 : 6}" fill="${isLeader ? "#752d40" : "#51634b"}" opacity="${valid.length > 50 ? 0.5 : 0.8}"/>`;
    if (valid.length <= 25 && (isLeader || row === highSpend)) {
      const end = cx > width * 0.72;
      svg += `<text class="point-label" x="${cx + (end ? -12 : 12)}" y="${cy - 10}" text-anchor="${end ? "end" : "start"}">${escape(mobile ? initials(row.team_name) : row.team_name.replace(/ FC| BC| 1909/g, ""))}</text>`;
    }
    svg += "</g>";
  }
  svg += `<text class="axis-label" x="${left}" y="${height - 7}">${x === "total_spend" ? "Transfer spend · €" : "Champagne Index"}</text>${mobile ? "" : `<text x="${width - right}" y="${height - 7}" text-anchor="end">${y === "delta_index" ? "Δ Index · next consecutive season" : "Index · (goals + assists) / match"}</text>`}</svg><div class="tooltip" hidden></div>`;
  return svg;
}

function tableRows(rows) {
  const sorted = rows
    .filter((r) =>
      r.team_name.toLowerCase().includes(tableSearch.toLowerCase()),
    )
    .sort((a, b) =>
      tableSort === "team_name"
        ? a.team_name.localeCompare(b.team_name)
        : tableSort === "position"
          ? (a.position ?? 999) - (b.position ?? 999)
          : (b[tableSort] ?? -Infinity) - (a[tableSort] ?? -Infinity),
    );
  if (!sorted.length)
    return '<tr><td colspan="8" class="empty-state">No clubs match your search.</td></tr>';
  const max = Math.max(...rows.map((r) => r.champagne_index), 1);
  return sorted
    .map(
      (r, i) =>
        `<tr><td class="rank">${String(i + 1).padStart(2, "0")}</td><td class="club-cell"><a class="club-link" href="${href(`club/${r.team_id}`)}">${badge(r.team_name, i % 3 === 2)}<span class="club-name">${escape(r.team_name)}</span></a></td><td class="numeric">${r.position ? `${integer(r.position)}<span class="screen-reader-only"> place</span>` : "—"}</td><td><div class="index-cell"><span class="index-bar" aria-hidden="true"><i style="width:${(r.champagne_index / max) * 100}%"></i></span>${number(r.champagne_index)}</div></td><td class="numeric ${r.change_from_previous > 0 ? "change-positive" : r.change_from_previous < 0 ? "change-negative" : ""}">${signed(r.change_from_previous)}</td><td class="numeric">${euro(r.total_spend)}</td><td class="numeric">${integer(r.matches)}</td><td><label class="compare-check"><input type="checkbox" data-compare="${r.team_id}" ${selected.includes(r.team_id) ? "checked" : ""} aria-label="Compare ${escape(r.team_name)}"><span class="screen-reader-only">Compare</span></label></td></tr>`,
    )
    .join("");
}
function ranking(data) {
  return `<section class="table-section"><div class="table-toolbar"><div class="section-heading"><div><span class="eyebrow">02 / The season book</span><h2>Every club. Same playing field.</h2></div></div><div class="table-tools"><label class="screen-reader-only" for="club-search">Search clubs</label><input id="club-search" type="search" placeholder="Search a club…" value="${escape(tableSearch)}"><a class="text-button" href="${scoped("/api/export")}">Export CSV ↗</a></div></div><div class="data-table-wrap"><table aria-label="Club attacking output and transfer spending"><thead><tr><th>#</th><th><button data-sort="team_name">Club ↕</button></th><th class="numeric"><button data-sort="position">League ↕</button></th><th class="numeric"><button data-sort="champagne_index">Champagne Index ↕</button></th><th class="numeric">vs. previous season</th><th class="numeric"><button data-sort="total_spend">Transfer spend ↕</button></th><th class="numeric">Matches*</th><th>Compare</th></tr></thead><tbody id="ranking-body">${tableRows(data.rows)}</tbody></table></div><div class="table-caption"><span>* Source match-count proxy. Δ compares the same competition with the preceding season; missing history is shown as —.</span><span>Select two clubs to compare ↗</span></div></section>`;
}
async function overview(version) {
  const fetched = await seasonData();
  if (version !== routeVersion) return "";
  currentData = fetched;
  const data = currentData,
    { league, season } = currentScope(),
    rows = data.rows;
  const leader = rows[0],
    total = rows.reduce((a, r) => a + r.total_spend, 0),
    avg = mean(rows.map((r) => r.champagne_index));
  const valueClub = rows
    .filter((r) => r.total_spend > 0 && r.champagne_index >= avg)
    .sort((a, b) => a.total_spend - b.total_spend)[0];
  const aside = `<aside class="hero-aside"><svg viewBox="0 0 70 96" class="pitch-icon" aria-hidden="true"><rect x="5" y="5" width="60" height="86"/><path d="M5 48h60M20 5v16h30V5M20 91V75h30v16M27 5v7h16V5M27 91v-7h16v7"/><circle cx="35" cy="48" r="12"/><circle cx="35" cy="48" r="1"/><path d="M25 21a12 12 0 0 0 20 0M25 75a12 12 0 0 1 20 0"/></svg><div><strong>Good football.<br>What’s the price?</strong><p>Five leagues. Decades of seasons.<br>One question worth asking.</p></div></aside>`;
  return `${hero("Vol. 01 / Follow the money. Find the football.", "The price of<br><em>beautiful football.</em>", "Explore what clubs spend, how much attacking output they record, and what actually changes the following season.", aside)}${filters()}${!rows.length ? '<div class="empty-state"><h2>No season sample available.</h2><p>Select another complete season.</p></div>' : `<section><div class="section-heading"><span class="eyebrow">01 / ${escape(league.name)} · ${season}</span><span class="sample-note">${rows.length} clubs · One competition · One season</span></div><div class="overview-grid"><div class="chart-panel"><div class="chart-top"><div><h2 id="chart-heading">What did the money buy?</h2><p id="chart-description">Recorded spending and attacking output in the same season.</p></div><div class="segmented" role="group" aria-label="Chart view"><button data-chart="season" class="${chartMode === "season" ? "active" : ""}" aria-pressed="${chartMode === "season"}">This season</button><button data-chart="next" class="${chartMode === "next" ? "active" : ""}" aria-pressed="${chartMode === "next"}">Next-season change</button></div></div><div id="main-chart" class="chart-wrap">${scatter(rows, { fit: null, target: "main" })}</div><div class="chart-foot"><span id="chart-sample">Each dot is a club. Dashed guides show league medians.</span><span class="chart-legend"><span><i class="legend-dot"></i>Highest index</span><span><i class="legend-dot olive"></i>Other clubs</span></span></div></div><aside class="season-aside"><span class="eyebrow">The season, in four numbers</span>${stat("Recorded transfer spend", euro(total), "Incoming fees · all positions")}${stat("Average attacking output", number(avg), "Champagne Index")}${stat("Highest index", number(leader.champagne_index), escape(leader.team_name))}${stat("Index ↔ league position", number(data.position_correlation.r, 3), `${data.position_correlation.n} comparable clubs`)}${valueClub ? `<div class="editor-note"><span class="eyebrow">From the season book</span><h3>Above the average.<br>Below the biggest budgets.</h3><p>${escape(valueClub.team_name)} recorded an index of <strong>${number(valueClub.champagne_index)}</strong> with ${euro(valueClub.total_spend)} in incoming fees. A comparison worth exploring.</p><a href="${href(`club/${valueClub.team_id}`)}">Open the club profile ↗</a></div>` : ""}</aside></div></section>${ranking(data)}<section class="story-band"><div><span class="eyebrow">03 / Change the question</span><h2>A bigger budget.<br><em>A better next season?</em></h2></div><div><p>Same-season spending and next-season improvement are different questions. Follow the second in the chart above, or take a club into the Lab and compare two model scenarios. The model learns associations in historical seasons; changing a slider does not prove a transfer would cause that outcome.</p><a href="${href("lab", { team: leader.team_id })}" class="button button-dark">Take a club into the Lab <span>↗</span></a></div></section>`}`;
}
async function switchChart(mode) {
  chartMode = mode;
  $$("[data-chart]").forEach((b) => {
    b.classList.toggle("active", b.dataset.chart === mode);
    b.setAttribute("aria-pressed", String(b.dataset.chart === mode));
  });
  const chart = $("#main-chart");
  if (!chart) return;
  $("#analysis-detail")?.remove();
  if (mode === "season") {
    $("#chart-heading").textContent = "What did the money buy?";
    $("#chart-description").textContent =
      "Recorded spending and attacking output in the same season.";
    chart.innerHTML = scatter(currentData.rows, { target: "main" });
    $("#chart-sample").textContent =
      "Each dot is a club. Dashed guides show league medians.";
    $(".chart-legend").innerHTML =
      '<span><i class="legend-dot"></i>Highest index</span><span><i class="legend-dot olive"></i>Other clubs</span>';
    return;
  }
  chart.innerHTML =
    '<div class="chart-empty">Opening consecutive seasons…</div>';
  const scopeAtStart = scoped("/api/analysis");
  try {
    const data = await request(scopeAtStart);
    if (
      chartMode !== "next" ||
      !$("#main-chart") ||
      scopeAtStart !== scoped("/api/analysis")
    )
      return;
    $("#chart-heading").textContent = "Did the next season improve?";
    $("#chart-description").textContent =
      `${data.from_year}–${data.to_year}: spending in season t vs. index change in t+1. Consecutive, adequately covered seasons only.`;
    chart.innerHTML = scatter(data.rows, {
      y: "delta_index",
      fit: data.correlation,
      target: "main",
      mode: "next",
    });
    $("#chart-sample").textContent =
      `Visible sample: n = ${data.correlation.n} · r = ${number(data.correlation.r, 3)} · p ${data.correlation.p < 0.0001 ? "< 0.0001" : `= ${pValue(data.correlation.p)}`}`;
    $(".chart-legend").innerHTML =
      "<span>Dashed line: fit to this sample</span>";
    chart
      .closest(".chart-panel")
      .insertAdjacentHTML(
        "beforeend",
        `<details class="disclosure" id="analysis-detail"><summary>Inspect the ${data.rows.length} plotted club-seasons</summary><div class="data-table-wrap benchmark-table"><table><thead><tr><th>Club</th><th>Season</th><th class="numeric">Spend</th><th class="numeric">Next-season Δ</th></tr></thead><tbody>${data.rows.map((r) => `<tr><td><a href="${href("club/" + r.team_id)}">${escape(r.team_name)}</a></td><td>${r.season_name}</td><td class="numeric">${euro(r.total_spend)}</td><td class="numeric">${signed(r.delta_index)}</td></tr>`).join("")}</tbody></table></div></details>`,
      );
  } catch (error) {
    if (chart.isConnected)
      chart.innerHTML = `<div class="chart-empty">${escape(error.message)}</div>`;
  }
}

async function clubs(version) {
  const fetched = await seasonData();
  if (version !== routeVersion) return "";
  currentData = fetched;
  const { league, season } = currentScope();
  return `${hero("The club directory / " + escape(league.name), "Know your <em>club.</em>", "Open a season profile, follow the historical trend, or pick two clubs to put their numbers side by side.", "", true)}${filters()}<div class="section-heading"><span class="eyebrow">${currentData.rows.length} clubs / ${season}</span><span class="sample-note">Select two to compare</span></div><div class="club-grid">${currentData.rows.map((r, i) => `<article class="club-card"><a href="${href(`club/${r.team_id}`)}">${badge(r.team_name, i % 3 === 2)}<h3>${escape(r.team_name)}</h3><div class="club-card-index">${number(r.champagne_index)}</div><span class="filter-label">Champagne Index</span></a><label class="compare-check"><input type="checkbox" data-compare="${r.team_id}" ${selected.includes(r.team_id) ? "checked" : ""} aria-label="Compare ${escape(r.team_name)}">Compare</label><div class="club-card-meta"><span>${euro(r.total_spend)} spent</span><span>${r.position ? "League #" + r.position : "No standings"} ↗</span></div></article>`).join("")}</div>`;
}
function trend(histories, names) {
  const cutoff = Math.max(...histories.flat().map((r) => r.season_key)) - 10;
  const series = histories.map((rows) =>
    rows.filter((r) => r.season_key >= cutoff && r.matches >= 30),
  );
  const all = series.flat();
  if (!all.length)
    return '<div class="chart-empty">No sufficiently covered historical seasons.</div>';
  const width =
      window.innerWidth < 600 ? Math.max(320, window.innerWidth - 70) : 750,
    height = 290,
    left = 42,
    right = 20,
    top = 20,
    bottom = 45;
  const min = Math.min(...all.map((r) => r.season_key)),
    max = Math.max(...all.map((r) => r.season_key)),
    ymax = Math.max(...all.map((r) => r.champagne_index)) * 1.15;
  const X = (v) =>
      left + ((v - min) / (max - min || 1)) * (width - left - right),
    Y = (v) => height - bottom - (v / ymax) * (height - top - bottom);
  let svg = `<svg class="trend-svg" viewBox="0 0 ${width} ${height}" role="img" aria-label="Champagne Index by season. ${escape(names.join(" and "))}. Only seasons with 30 or more source matches.">`;
  for (let i = 0; i <= 3; i++) {
    const y = (ymax * i) / 3;
    svg += `<line class="gridline" x1="${left}" y1="${Y(y)}" x2="${width - right}" y2="${Y(y)}"/><text x="${left - 10}" y="${Y(y) + 3}" text-anchor="end">${number(y, 1)}</text>`;
  }
  for (
    let year = min;
    year <= max;
    year += Math.max(1, Math.ceil((max - min) / 5))
  ) {
    svg += `<text x="${X(year)}" y="${height - 18}" text-anchor="middle">${String(year).slice(2)}/${String(year + 1).slice(2)}</text>`;
  }
  series.forEach((rows, index) => {
    const color = index ? "#51634b" : "#752d40";
    let previous = null;
    const path = rows
      .map((r) => {
        const cmd =
          previous != null && r.season_key === previous + 1 ? "L" : "M";
        previous = r.season_key;
        return `${cmd}${X(r.season_key)},${Y(r.champagne_index)}`;
      })
      .join(" ");
    svg += `<path d="${path}" fill="none" stroke="${color}" stroke-width="2"/>`;
    for (const row of rows) {
      svg += `<circle cx="${X(row.season_key)}" cy="${Y(row.champagne_index)}" r="3.8" fill="${color}" stroke="#fffcf6" stroke-width="1.5"><title>${escape(names[index])} · ${row.season_name}: ${number(row.champagne_index)}</title></circle>`;
    }
  });
  return svg + "</svg>";
}

async function clubView(teamId) {
  const data = await request(scoped(`/api/clubs/${teamId}`));
  const { league, season } = currentScope(),
    row = data.current;
  const eligible = data.history
    .filter((r) => r.matches >= 30)
    .slice(-11)
    .reverse();
  return `<a class="back-link" href="${href("clubs")}">← All ${escape(league.name)} clubs</a><section class="club-header">${badge(data.team_name)}<div><span class="eyebrow">The club file / ${escape(league.name)} · ${season}</span><h1>${escape(data.team_name)}</h1></div><div class="header-actions"><a class="button button-dark" href="${href("lab", { team: teamId })}">Open in the Lab ↗</a><button class="button" data-pin="${teamId}">Add to comparison +</button></div></section>${filters()}${row ? `<div class="metrics-row">${metric("Champagne Index", number(row.champagne_index), "Recorded attacking output / match")}${metric("Transfer spending", euro(row.total_spend), "All incoming positions")}${metric("Attack spending", euro(row.attacking_spend), row.total_spend ? `${number((row.attacking_spend / row.total_spend) * 100, 0)}% of recorded fees` : "No recorded fees")}${metric("League finish", row.position ? "#" + row.position : "—", row.points != null ? `${row.points} points · ${season}` : "Match enrichment unavailable")}</div>` : `<div class="notice">This club does not have a ${season} season in ${escape(league.name)}. Select a season from its history.</div>`}<section class="two-col"><div class="panel"><span class="eyebrow">01 / The longer view</span><h2>Form has a history.</h2><p>Same club, same competition. Recent seasons with 30+ source matches; gaps are left unconnected.</p>${trend([data.history], [data.team_name])}</div><div class="panel"><span class="eyebrow">02 / Read the context</span><h2>One season.<br>Several perspectives.</h2><p>The index combines recorded goals and assists. Spending covers the whole club-season, including signings used in other competitions.</p>${row ? stat("Source matches", integer(row.matches), row.matches < 30 ? "Partial season snapshot" : "Season-level denominator") : ""}${row ? stat("Goals + assists", `${integer(row.total_goals)} + ${integer(row.total_assists)}`) : ""}${data.style ? `<div class="editor-note"><span class="eyebrow">Exploratory K-Means grouping</span><h3>${escape(data.style.cluster_name)}</h3><p>A historical statistical grouping, sensitive to source coverage. It is not a tactical scouting verdict.</p></div>` : ""}</div></section><section class="table-section"><div class="section-heading"><div><span class="eyebrow">03 / The archive</span><h2>Season by season.</h2></div></div><div class="data-table-wrap"><table><caption class="screen-reader-only">${escape(data.team_name)} recent complete season history</caption><thead><tr><th>Season</th><th class="numeric">Champagne Index</th><th class="numeric">Transfer spend</th><th class="numeric">Attack spend</th><th class="numeric">Source matches</th><th class="numeric">League finish</th></tr></thead><tbody>${eligible.map((r) => `<tr><td><button class="text-button" data-season-link="${r.season_name}">${r.season_name} ↗</button></td><td class="numeric">${number(r.champagne_index)}</td><td class="numeric">${euro(r.total_spend)}</td><td class="numeric">${euro(r.attacking_spend)}</td><td class="numeric">${r.matches}</td><td class="numeric">${r.position ? "#" + r.position : "—"}</td></tr>`).join("")}</tbody></table></div></section>`;
}

function headToHeadView(data) {
  const { league, season } = currentScope();
  const heading = `<div class="section-heading"><div><span class="eyebrow">Head to head / ${escape(league.name)} · ${season}</span><h2>When they meet.</h2></div><span class="sample-note">${data.matches.length} recorded ${data.matches.length === 1 ? "meeting" : "meetings"}</span></div>`;
  if (!data.matches.length)
    return `<section class="table-section" id="head-to-head">${heading}<div class="notice">${data.enrichment_available ? "No completed meetings between these clubs are recorded in the selected league season." : "Match results have not been loaded for this league season. Choose another season to explore their meetings."}</div></section>`;
  const metrics = [
    ["Matches against each other", "matches", integer],
    ["Wins", "wins", integer],
    ["Draws", "draws", integer],
    ["Losses", "losses", integer],
    ["Goals scored", "goals_for", integer],
    ["Goals conceded", "goals_against", integer],
    ["Goal difference", "goal_difference", (value) => `${value > 0 ? "+" : ""}${integer(value)}`],
    ["Goals per match", "goals_per_match", (value) => number(value)],
    ["Clean sheets", "clean_sheets", integer],
    ["Points from meetings", "points", integer],
  ];
  const dateLabel = (date) => date
    ? new Date(`${date}T12:00:00`).toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric" })
    : "Date unavailable";
  return `<section class="table-section" id="head-to-head">${heading}<div class="data-table-wrap comparison-table"><table><caption class="screen-reader-only">Head-to-head statistics for ${escape(data.teams[0].team_name)} and ${escape(data.teams[1].team_name)}, ${season}</caption><thead><tr><th>Against each other</th>${data.teams.map((team) => `<th scope="col">${escape(team.team_name)}</th>`).join("")}</tr></thead><tbody>${metrics.map(([label, key, format]) => `<tr><th scope="row">${label}</th>${data.teams.map((team) => `<td class="numeric" data-h2h-stat="${key}" data-team="${team.team_id}">${format(team[key])}</td>`).join("")}</tr>`).join("")}</tbody></table></div><ul class="h2h-fixtures" aria-label="Recorded head-to-head match results">${data.matches.map((match) => `<li class="h2h-match">${match.match_date ? `<time datetime="${match.match_date}">${dateLabel(match.match_date)}</time>` : `<span class="sample-note">${dateLabel(null)}</span>`}<span class="h2h-home">${escape(match.home_team_name)}<small>Home</small></span><strong class="h2h-score" aria-label="${match.home_goals} goals to ${match.away_goals}">${match.home_goals} <span aria-hidden="true">–</span> ${match.away_goals}</strong><span class="h2h-away">${escape(match.away_team_name)}<small>Away</small></span></li>`).join("")}</ul><p class="sample-note">Completed league meetings in ${season}, from ${escape(data.source)}. Season goals and assists above use Transfermarkt, whose coverage can differ. Match-level assists are not available in this source.</p></section>`;
}

async function comparison() {
  const queryIds = new URLSearchParams(location.search).get("teams");
  const ids = queryIds
    ? queryIds
        .split(",")
        .map(Number)
        .filter(Number.isInteger)
        .filter((n) => n > 0)
        .slice(0, 2)
    : selected;
  if (ids.length !== 2 || ids[0] === ids[1])
    return `${hero("The side-by-side view", "Two clubs.<br><em>One conversation.</em>", "Select two clubs in the directory or season table to compare them.", "", true)}<a class="button button-dark" href="${href("clubs")}">Choose your clubs ↗</a>`;
  const [data, headToHead] = await Promise.all([
    Promise.all(ids.map((id) => request(scoped(`/api/clubs/${id}`)))),
    request(scoped("/api/head-to-head", { team_a: ids[0], team_b: ids[1] })),
  ]);
  const { league, season } = currentScope();
  const rows = [
    ["Champagne Index", (r) => number(r.champagne_index)],
    ["Recorded transfer spend", (r) => euro(r.total_spend)],
    ["Spending on attackers", (r) => euro(r.attacking_spend)],
    ["Recorded goals", (r) => integer(r.total_goals)],
    ["Recorded assists", (r) => integer(r.total_assists)],
    ["Source matches", (r) => integer(r.matches)],
    ["Final league position", (r) => (r.position ? "#" + r.position : "—")],
    ["League points", (r) => integer(r.points)],
  ];
  return `${hero("The comparison / " + escape(league.name) + " · " + season, "Side by <em>side.</em>", "Same league, same season. The numbers become more useful when they have company.", `<a class="button" href="${href("clubs")}">Change clubs ↗</a>`, true)}${filters()}<div class="data-table-wrap comparison-table"><table><thead><tr><th>Season ${season}</th>${data.map((d) => `<th>${badge(d.team_name)}<br><a class="comparison-heading" href="${href("club/" + (d.current?.team_id || ids[data.indexOf(d)]))}">${escape(d.team_name)}</a></th>`).join("")}</tr></thead><tbody>${rows.map(([label, format]) => `<tr><td>${label}</td>${data.map((d) => `<td class="numeric">${d.current ? format(d.current) : "No season data"}</td>`).join("")}</tr>`).join("")}</tbody></table></div>${headToHeadView(headToHead)}<section class="panel" style="margin-top:30px"><span class="eyebrow">The longer view / 30+ source matches</span><h2>A rivalry, over time.</h2>${trend(
    data.map((d) => d.history),
    data.map((d) => d.team_name),
  )}<div class="chart-legend sample-note">${data.map((d, i) => `<span><i class="legend-dot ${i ? "olive" : ""}"></i>${escape(d.team_name)}</span>`).join("")}</div></section><p class="notice">Spending is recorded incoming fees, not wages or total squad cost. The index describes attacking output; it does not establish which club recruited better.</p>`;
}
function updateTray() {
  $("#compare-tray")?.remove();
  if (!selected.length || routeName() === "compare") return;
  const rows = currentData?.rows || [],
    names = selected.map(
      (id) => rows.find((r) => r.team_id === id)?.team_name || "Club",
    );
  const tray = document.createElement("aside");
  tray.id = "compare-tray";
  tray.className = "compare-tray";
  tray.setAttribute("aria-label", "Selected clubs");
  tray.innerHTML = `<div><p>${escape(names.join(" + "))}</p><small>${selected.length}/2 clubs selected</small></div><button class="button button-small" data-action="compare" ${selected.length < 2 ? "disabled" : ""}>Compare ↗</button><button data-action="clear-compare" aria-label="Clear comparison">×</button>`;
  document.body.append(tray);
}
function toggleComparison(id, force = false) {
  if (selected.includes(id)) {
    if (!force) selected = selected.filter((x) => x !== id);
    else
      toast("This club is already selected. Choose another in the directory.");
  } else if (selected.length < 2) selected.push(id);
  else toast("Two clubs are selected. Clear one to add a different club.");
  $$("[data-compare]").forEach(
    (el) => (el.checked = selected.includes(Number(el.dataset.compare))),
  );
  updateTray();
}

const FEATURE_LABELS = {
  champagne_index: "Current Champagne Index",
  total_spend: "Total transfer budget",
  attacking_spend: "Of which, attacking players",
  squad_avg_age: "Squad average age",
  market_value_change: "Change in average player value",
};
function formatFeature(key, value) {
  return key.includes("spend") || key === "market_value_change"
    ? `${value < 0 ? "−" : ""}${euro(Math.abs(value))}`
    : key === "squad_avg_age"
      ? `${number(value, 1)} years`
      : number(value);
}
function control(key, values, ranges) {
  const current = values[key],
    range = ranges[key];
  let min = 0,
    max = 1,
    step = 0.01,
    note = "";
  if (key === "champagne_index") {
    max = Math.max(6, current, range.p99 || 6);
    note = "Recorded goals + assists per source match.";
  }
  if (key === "total_spend") {
    max = Math.min(2e9, Math.max(500e6, current, range.p99 || 0));
    step = 1;
    note = "Incoming transfer fees across all positions. This excludes wages.";
  }
  if (key === "attacking_spend") {
    max = values.total_spend;
    step = 1;
    note = "A share of the total budget, not an additional budget.";
  }
  if (key === "squad_avg_age") {
    min = 16;
    max = 38;
    step = 0.01;
    min = Math.min(min, current);
    max = Math.max(max, current);
    note = "Average age of players appearing in the club-season roster.";
  }
  if (key === "market_value_change") {
    min = Math.min(-5e6, current, range.p01 || 0);
    max = Math.max(5e6, current, range.p99 || 0);
    step = 1;
    note = "Change in the average player valuation, not the total squad value.";
  }
  return `<div class="control-group"><div class="control-label"><label for="input-${key}">${FEATURE_LABELS[key]}</label><output id="output-${key}" for="input-${key}">${formatFeature(key, current)}</output></div><input id="input-${key}" data-feature="${key}" type="range" min="${min}" max="${max}" step="${step}" value="${current}" ${max === 0 ? "disabled" : ""}><div class="range-ends"><span>${formatFeature(key, min)}</span><span id="max-${key}">${formatFeature(key, max)}</span></div><small>${note}</small></div>`;
}
async function labView(version) {
  const fetched = await seasonData();
  if (version !== routeVersion) return "";
  currentData = fetched;
  const { season, league } = currentScope();
  const requested = Number(new URLSearchParams(location.search).get("team"));
  const selectedClub =
    currentData.rows.find((r) => r.team_id === requested) ||
    currentData.rows[0];
  if (!selectedClub)
    return `${hero("The scenario room", "What if <em>you decided?</em>", "Choose a season with enough club data.", "", true)}${filters()}`;
  const config = await request(
    scoped("/api/lab/config", { team_id: selectedClub.team_id }),
  );
  const picker = `<div class="lab-picker"><label class="filter-label" for="lab-club">Start with a real club</label><select id="lab-club">${currentData.rows.map((r) => `<option value="${r.team_id}" ${r.team_id === selectedClub.team_id ? "selected" : ""}>${escape(r.team_name)}</option>`).join("")}</select><span class="sample-note">${escape(league.name)} · ${season}</span></div>`;
  const head =
    hero(
      "The Lab / A historical model. Your scenario.",
      "What if <em>you decided?</em>",
      "Keep the original club-season on one side. Change its inputs on the other. See how the model responds.",
      "",
      true,
    ) +
    filters() +
    picker;
  if (config.missing.length)
    return (
      head +
      `<div class="notice">This club-season is missing ${config.missing.map((f) => FEATURE_LABELS[f]).join(" and ")}. Choose another club; missing inputs are not silently replaced with averages.</div>`
    );
  const base = await request("/api/lab/predict", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(config.features),
  });
  if (version !== routeVersion) return "";
  labState = {
    config,
    values: { ...config.features },
    baseline: { ...config.features },
    base,
    prediction: base,
    teamId: selectedClub.team_id,
  };
  const next =
    String((Number(season.slice(0, 2)) + 1) % 100).padStart(2, "0") +
    "/" +
    String((Number(season.slice(3)) + 1) % 100).padStart(2, "0");
  return (
    head +
    `<section class="lab-grid"><div class="lab-controls"><span class="eyebrow">01 / Your starting eleven, in five inputs</span>${Object.keys(
      FEATURE_LABELS,
    )
      .map((key) => control(key, config.features, config.ranges))
      .join(
        "",
      )}<div class="control-reset"><button class="text-button" data-action="reset-lab">↺ Reset to ${escape(selectedClub.team_name)}</button><small>Real inputs · ${season}</small></div></div><aside class="lab-result" aria-live="polite" aria-atomic="false"><span class="eyebrow">02 / The model’s response · ${next}</span><h2>Change the inputs.<br><em>Read the difference.</em></h2><div class="scenario-score"><div><span class="metric-label">Original inputs</span><div class="metric-value">${number(base.next_index)}</div><div class="metric-note">Model’s next-season index</div></div><div id="scenario-output"><span class="metric-label">Your scenario</span><div class="metric-value" id="scenario-index">${number(base.next_index)}</div><div class="metric-note" id="scenario-delta">Δ ${signed(base.delta)} from current index</div></div></div><p class="scenario-impact" id="scenario-impact">Start moving a slider to compare your scenario.</p><div id="scenario-bars" aria-hidden="true"></div><p id="scenario-range" class="notice" hidden></p><div class="model-evidence"><span class="eyebrow">A model, with its limits</span><p id="lab-evidence">${config.evaluation ? `Chronological holdout from ${config.evaluation.test_from_season}. Test MAE: <strong>${number(config.evaluation.mae)}</strong> index points across ${integer(config.evaluation.test_rows)} club-seasons. Zero-change baseline MAE: ${number(config.evaluation.baseline_mae)}.` : "Evaluation metadata is unavailable; regenerate the model with the updated pipeline."}</p><p style="margin-top:12px">A retrospective, all-data model used for exploration. The source club-season may have appeared in training. Slider changes show model associations, not the causal effect of buying a player. No calibrated prediction interval or league-place forecast is available.</p><a class="text-button" href="${href("project")}">Inspect the model & evaluation ↗</a></div></aside></section>`
  );
}
async function updatePrediction() {
  if (!labState) return;
  const seq = ++labSequence,
    active = labState;
  $("#scenario-output")?.classList.add("result-updating");
  try {
    const prediction = await request("/api/lab/predict", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(active.values),
    });
    if (seq !== labSequence || active !== labState || routeName() !== "lab")
      return;
    active.prediction = prediction;
    $("#scenario-index").textContent = number(prediction.next_index);
    $("#scenario-delta").textContent =
      `Δ ${signed(prediction.delta)} from current index`;
    const diff = prediction.next_index - active.base.next_index;
    $("#scenario-impact").innerHTML =
      `<strong class="${diff >= 0 ? "change-positive" : "change-negative"}">${signed(diff)}</strong> index points versus the original-input model response.`;
    const current = active.values.champagne_index,
      max = Math.max(current, prediction.next_index, active.base.next_index, 1);
    $("#scenario-bars").innerHTML =
      `<div class="benchmark-bars"><div class="benchmark-bar"><span>Original</span><i style="width:${(Math.max(0, active.base.next_index) / max) * 100}%"></i><span>${number(active.base.next_index)}</span></div><div class="benchmark-bar"><span>Scenario</span><i style="width:${(Math.max(0, prediction.next_index) / max) * 100}%"></i><span>${number(prediction.next_index)}</span></div></div>`;
    const notice = $("#scenario-range");
    notice.hidden = !prediction.outside_training_range.length;
    notice.textContent = `Outside the observed training range: ${prediction.outside_training_range.map((k) => FEATURE_LABELS[k]).join(", ")}. The model has little support for this scenario.`;
  } catch (error) {
    if (seq === labSequence) toast(error.message);
  } finally {
    if (seq === labSequence)
      $("#scenario-output")?.classList.remove("result-updating");
  }
}

function systemEvidence(bench) {
  if (!bench.system_runs?.length) return "";
  const runs = bench.system_runs;
  const h = bench.hardware;
  return `<div class="metrics-row">${metric("Complete startup", `${number(bench.system_run_seconds)} s`, "Three cached-source runs → API ready")}${metric("Loader", `${number(mean(runs.map((r) => r.loader.full_seconds)))} s`, "Source checks, COPY, indices, matches")}${metric("Pipeline", `${number(mean(runs.map((r) => r.pipeline.full_seconds)))} s`, "Aggregation, fitting, saved outputs")}${metric("Source CSVs", `${number(bench.raw_csv_mb, 1)} MiB`, "Local source + match enrichment")}</div>${h ? `<p style="margin-bottom:22px">Measured laptop: <strong>${escape(h.processor)}</strong>, ${number(h.host_ram_gb, 0)} GiB RAM, ${h.logical_cpus} logical CPUs. Docker VM: ${h.docker_cpus} CPUs, ${number(h.docker_ram_gb, 2)} GiB memory. Query and growth results below are means of ${bench.repeats || 3} repetitions. Prepared sources and persistent volume retained; caches and other host workloads were not controlled.</p>` : ""}`;
}

async function projectView() {
  const data = await request("/api/project"),
    linear = data.linear,
    ml = data.ml,
    position = data.position,
    bench = data.benchmark,
    ev = ml?.evaluation;
  const sourceRows = data.tables
    .filter((t) => t.name !== "match_results")
    .reduce((s, t) => s + t.rows, 0);
  const speed = bench?.query_with_index_seconds
    ? bench.query_without_index_seconds / bench.query_with_index_seconds
    : null;
  const checklist = [
    [
      "Public dataset",
      "Pinned public 11-table snapshot with hashes. Upstream licence is not explicit; see source notes.",
      "Licence unresolved",
    ],
    [
      "GET",
      "Missing source CSVs are downloaded without login from a pinned revision; headers and checksums checked. Match enrichment remains manual.",
      "Implemented",
    ],
    [
      "STORE",
      "PostgreSQL schema, native COPY, indices, persistent named volume; choice explained below.",
      "Implemented",
    ],
    [
      "PROCESS",
      "SQL aggregation, valid consecutive-season targets, regression, chronological RandomForest evaluation.",
      "Implemented",
    ],
    [
      "SHOW",
      "Interactive overview, club histories, comparison, live scenario inference and CSV export.",
      "Implemented",
    ],
    [
      "MEASURE",
      "Index/query timings, database size, 25/50/100% growth experiment and recorded resource evidence.",
      "See measurements",
    ],
    [
      "Enrichment",
      "Independent match-results source; verified club-name mapping; real league standings.",
      "Implemented",
    ],
    [
      "Reproducibility",
      "Docker Compose orders database → loader → pipeline → application. Dependencies pinned.",
      "Implemented",
    ],
    [
      "Team / presentation rules",
      "The slides require four real team members. Four accounts owned by one author remain a solo portfolio exercise.",
      "Solo exercise",
    ],
  ];
  return `${hero("Under the touchline / Sources, methods & evidence", "The football.<br><em>The working behind it.</em>", "A reproducible data system, with its assumptions on the page. Follow a CSV from the source to the screen.", `<a class="button" href="https://github.com/Ataika/Calcio-Champagne-prediction-automated-system" target="_blank" rel="noopener noreferrer">Read the source ↗</a>`, true)}<div class="project-lead"><p>Does spending on attacking players improve a club’s attacking output next season? And does that output track where the club finishes?</p><div class="project-facts">${stat("Source rows", `~${number(sourceRows / 1e6, 1)}m`, "PostgreSQL table estimates")}${stat("Team-season-competition rows", integer(data.coverage.team_seasons))}${stat("Historical coverage", `${data.coverage.from_year}–${data.coverage.to_year}`)}${stat("Architecture", "4 services", "Plus on-demand measurements")}</div></div><nav class="project-nav" aria-label="Project sections"><a href="#project" data-scroll="architecture">01 System</a><a href="#project" data-scroll="findings">02 Findings</a><a href="#project" data-scroll="measurements">03 Measurements</a><a href="#project" data-scroll="sources">04 Sources</a><a href="#project" data-scroll="course">05 Course evidence</a></nav>
  <section class="project-section" id="architecture"><div class="section-heading"><h2>01 / From source to screen.</h2><span class="sample-note">One Docker Compose command</span></div><div class="pipeline-map"><div class="pipeline-step"><span class="step-number">01 / GET</span><h3>The sources</h3><p>Pinned public Transfermarkt CSVs, downloaded without login when missing, plus optional local match results.</p></div><div class="pipeline-step"><span class="step-number">02 / STORE</span><h3>The database</h3><p>PostgreSQL 16. Native <code>COPY</code>, relational joins and indexed club-season lookups. Persistent volume.</p></div><div class="pipeline-step"><span class="step-number">03 / PROCESS</span><h3>The pipeline</h3><p>SQL views → season features → regression & RandomForest → output tables and saved scenario model.</p></div><div class="pipeline-step"><span class="step-number">04 / SHOW</span><h3>The journal</h3><p>A read-only FastAPI data layer serves this interface. Scenario requests call the saved model; no retraining on clicks.</p></div><div class="pipeline-step"><span class="step-number">05 / MEASURE</span><h3>The evidence</h3><p>On-demand benchmark: indexed lookups, database footprint, data growth and resource sampling. Saved as JSON.</p></div></div><p>Why a relational database? The source has stable player, club, competition and season identifiers. Its work is aggregation and joins across structured tables. The loader runs after database health, the pipeline after successful loading, and the app after successful processing. The application queries small pipeline outputs, not millions of raw player rows.</p><pre class="code-block">cp .env.example .env
# Missing source CSVs download automatically; optional match CSVs stay manual.
docker compose up --build
# http://localhost:8502
docker compose run --rm measure</pre></section>
  <section class="project-section" id="findings"><div class="section-heading"><h2>02 / What the data supports.</h2><span class="sample-note">Metrics read from the running pipeline</span></div><div class="evidence-grid"><article class="evidence-card"><span class="eyebrow">Spending → next-season change</span><h3>A tiny linear relationship.</h3><div class="evidence-number">r ${number(linear?.r_value, 3)}</div><p>${integer(linear?.n_observations)} eligible club-seasons across competitions. p ${linear?.p_value < 0.0001 ? "< 0.0001" : `= ${pValue(linear?.p_value)}`}. Statistical significance and practical effect size answer different questions; spending alone explains little.</p></article><article class="evidence-card"><span class="eyebrow">Attacking output ↔ league position</span><h3>The index tracks the table.</h3><div class="evidence-number">r ${number(position?.r_value, 3)}</div><p>${integer(position?.n_observations)} comparable top-five league club-seasons. Partial source seasons are excluded. Negative r means higher output accompanies a lower-numbered, better finish. This is same-season association.</p></article><article class="evidence-card"><span class="eyebrow">Five-feature RandomForest</span><h3>Tested on later seasons.</h3><div class="evidence-number">R² ${number(ml?.r2_score, 3)}</div><p>${ev ? `${integer(ev.train_rows)} earlier training rows, ${integer(ev.test_rows)} held-out rows from ${ev.test_from_season}. MAE ${number(ev.mae)}, compared with ${number(ev.baseline_mae)} for predicting no change.` : "Evaluation metadata is not available."} This score is not the proportion of predictions that are correct.</p></article></div><details class="disclosure"><summary>Model inputs, target and validation</summary><p>Unit: club × season × competition. Target: the change in Champagne Index in the next consecutive season. Inputs: current index, incoming total fees, attacking fees, roster average age and change in average player valuation. Top-five league pairs require at least 30 source matches in each season; other competitions require five. Reserve/youth squads are excluded from training. Seasons are split chronologically, keeping a season’s competitions together. A separate all-data model powers the exploratory Lab.</p><p>Market value is the latest available observation per player in the season’s starting calendar year; club means give each observed player one weight. The previous value is joined by the exact preceding year before competition rows are introduced. These are retrospective season-level features, not a claim about information available before a transfer window.</p></details><details class="disclosure"><summary>Why the audit changed earlier headline numbers</summary><p>The original 25/26 Transfermarkt snapshot had only 2–4 league matches per club, while match enrichment had full final standings. Combining those gave r ≈ −0.663 over 484 rows. Restricting the index/position comparison to adequately covered seasons gives the current result above. The earlier RandomForest score of ≈0.15 used a random row split and an incorrect within-season market-value lag; it is not directly comparable with the corrected temporal evaluation.</p></details><details class="disclosure"><summary>What a cluster label does — and does not — mean</summary><p>The optional K-Means side analysis groups historical club-seasons by output, fees, discipline and recorded defensive statistics. Missing defensive coverage can create a cluster of its own. Names are assigned from actual centroids on each run; cluster integers are not stable identities. These groups are exploratory summaries, not tactical styles or proof of recruitment efficiency. The optional transfer-fee model is also a retrospective side analysis, not an independent live valuation service.</p></details></section>
  <section class="project-section" id="measurements"><div class="section-heading"><h2>03 / Measure the infrastructure.</h2><span class="sample-note">Observed results, not performance promises</span></div>${
    bench
      ? `${systemEvidence(bench)}<div class="benchmark-grid"><article class="panel"><span class="eyebrow">300 distinct club lookups</span><h2>The difference an index makes.</h2><div class="benchmark-number">${number(speed, 1)}×</div><div class="benchmark-bars"><div class="benchmark-bar"><span>No index</span><i style="width:100%"></i><span>${number(bench.query_without_index_seconds, 3)} s</span></div><div class="benchmark-bar"><span>With index</span><i style="width:${Math.max(1, 100 / speed)}%"></i><span>${number(bench.query_with_index_seconds, 3)} s</span></div></div><p>Same lookup query over the raw player-performance table, same set of clubs. Aggregate wall time depends on hardware, caches and sample. The full GROUP BY has different access patterns.</p></article><article class="panel"><span class="eyebrow">25% → 50% → 100% of the largest table</span><h2>What happens as data grows?</h2><div class="data-table-wrap benchmark-table"><table><thead><tr><th>Share</th><th class="numeric">Rows</th><th class="numeric">Load</th><th class="numeric">Query</th></tr></thead><tbody>${(bench.growth_test || []).map((r) => `<tr><td>${r.pct}%</td><td class="numeric">${integer(r.rows)}</td><td class="numeric">${number(r.load_seconds)} s</td><td class="numeric">${number(r.query_seconds, 3)} s</td></tr>`).join("")}</tbody></table></div><p>CSV preparation + COPY loading, followed by a full team-season aggregation. Database footprint: <strong>${number(bench.db_size_mb, 1)} MiB</strong>. ${escape(bench.machine || "Hardware not recorded")}.</p></article></div><div class="notice">${bench.measured_at ? `Benchmark recorded ${escape(bench.measured_at)}. ` : ""}${
          Object.values(bench.peak_memory_mb || {}).some((v) => v != null)
            ? `Observed container memory: ${Object.entries(bench.peak_memory_mb)
                .filter(([, v]) => v != null)
                .map(
                  ([name, value]) => `${escape(name)} ${number(value, 1)} MiB`,
                )
                .join(
                  " · ",
                )}. Sampling method and limitations are saved with the benchmark.`
            : "Container peak memory is not present in this benchmark file. Missing measurements are not shown as zero; see the resource-sampling command in README."
        }</div>`
      : '<div class="notice">No benchmark artifact is available yet. Run <code>docker compose run --rm measure</code> and reload this page.</div>'
  }</section>
  <section class="project-section" id="sources"><div class="section-heading"><h2>04 / Know the source.</h2></div><div class="source-list"><article class="source-block"><span class="eyebrow">Primary dataset</span><h3>Transfermarkt, from a pinned source.</h3><p>11 CSV tables, about 353 MiB. Player profiles, seasonal performances, transfers, market-value history and related metadata. The source revision and file hashes are recorded in the repository. See the <a href="https://github.com/salimt/football-datasets/tree/da9227e1f42baf74561324290dbf1ad2e3c00edd" target="_blank" rel="noopener noreferrer">pinned source ↗</a>. No explicit upstream licence was found at this revision; that course requirement remains unresolved. Ten local files match upstream exactly; a locally prepared club-competition metadata table differs, and fresh downloads normalize the upstream table to the expected fields. The core index and model do not use that metadata table. The local snapshot contains historical club seasons through ${data.coverage.to_year}.</p><p style="margin-top:12px">Data caveats: match counts are a proxy; zero fees include undisclosed values; defensive coverage is uneven; seasonal output is not match-event or xG data.</p></article><article class="source-block"><span class="eyebrow">Independent enrichment</span><h3>Real matches. Real standings.</h3><p>Five European leagues, 21/22–25/26, from <a href="https://www.football-data.co.uk/data.php" target="_blank" rel="noopener noreferrer">football-data.co.uk ↗</a>. Manually downloaded CSVs, with a hand-verified club-name mapping. Points and positions are computed from results using points and goal difference; competition-specific tie-breaks, deductions and official disciplinary adjustments are not modeled.</p><p style="margin-top:12px">Only adequately covered index snapshots are paired with final standings. The overview defaults to a complete source season.</p></article></div><details class="disclosure" style="margin-top:22px"><summary>Source tables and row counts</summary><div class="data-table-wrap benchmark-table"><table><thead><tr><th>Table</th><th class="numeric">Rows · PostgreSQL estimate</th></tr></thead><tbody>${data.tables.map((t) => `<tr><td><code>${escape(t.name)}</code></td><td class="numeric">${integer(t.rows)}</td></tr>`).join("")}</tbody></table></div></details></section>
  <section class="project-section" id="course"><div class="section-heading"><h2>05 / Course-shaped, evidence-led.</h2></div><p>Verified against Vincenzo Lomonaco’s LUISS CIDS Lecture 15, dated 29 October 2026: the mandatory checklist is GitHub, a runnable README, a justified database, Docker Compose and measured performance. Pages 10–11 specify timing, memory, disk, growth and three repetitions. It is a solo portfolio exercise using four accounts to practice review and pull-request workflows, not a four-person course submission.</p><div class="notice"><strong>Original brief checked.</strong> See docs/COURSE_REQUIREMENTS.md for page-level evidence. Two boundaries remain explicit: this is a solo exercise, and the public source’s licence is not stated. No claim of full course-submission compliance is made.</div><div class="data-table-wrap check-table"><table><thead><tr><th>Requirement</th><th>Concrete evidence</th><th>Status</th></tr></thead><tbody>${checklist.map(([name, evidence, status]) => `<tr><td>${name}</td><td>${evidence}</td><td><span class="status-label ${status.includes("unresolved") || status.includes("Solo") ? "pending" : ""}">${status}</span></td></tr>`).join("")}</tbody></table></div></section>`;
}

async function render() {
  const version = ++routeVersion,
    route = routeName(),
    root = $("#app");
  root.setAttribute("aria-busy", "true");
  const active =
    route.startsWith("club") || route === "compare" ? "clubs" : route;
  $$(".main-nav a").forEach((a) => {
    a.classList.toggle("active", a.dataset.view === active);
    if (a.dataset.view === active) a.setAttribute("aria-current", "page");
    else a.removeAttribute("aria-current");
  });
  try {
    let html;
    if (route === "overview") html = await overview(version);
    else if (route === "clubs") html = await clubs(version);
    else if (/^club\/\d+$/.test(route))
      html = await clubView(Number(route.split("/")[1]));
    else if (route === "compare") html = await comparison();
    else if (route === "lab") html = await labView(version);
    else if (route === "project") html = await projectView();
    else
      html =
        '<div class="empty-state"><h2>This page is off the pitch.</h2><a class="button" href="#overview">Back to overview ↗</a></div>';
    if (version !== routeVersion) return;
    root.innerHTML = html;
    root.classList.remove("fade-in");
    void root.offsetWidth;
    root.classList.add("fade-in");
    document.title =
      route === "overview"
        ? "Calcio Champagne — The price of beautiful football"
        : `Calcio Champagne — ${route.startsWith("club/") ? "Club profile" : active === "project" ? "The project" : active === "lab" ? "The Lab" : "Clubs"}`;
    updateTray();
    if (route === "overview" && chartMode === "next") await switchChart("next");
  } catch (error) {
    if (version !== routeVersion) return;
    root.innerHTML = `<div class="empty-state"><span class="eyebrow">The data room</span><h2>We couldn’t open this page.</h2><p>${escape(error.message)}</p><button class="button" data-action="retry" style="margin-top:20px">Try again ↻</button><a class="text-button" href="#overview" style="margin-left:20px">Back to overview</a></div>`;
  } finally {
    if (version === routeVersion) root.setAttribute("aria-busy", "false");
  }
}

document.addEventListener("click", (event) => {
  const league = event.target.closest("[data-league]");
  if (league) {
    setScope(league.dataset.league);
    return;
  }
  const sort = event.target.closest("[data-sort]");
  if (sort) {
    tableSort = sort.dataset.sort;
    $("#ranking-body").innerHTML = tableRows(currentData.rows);
    return;
  }
  const chart = event.target.closest("[data-chart]");
  if (chart) {
    switchChart(chart.dataset.chart);
    return;
  }
  const pin = event.target.closest("[data-pin]");
  if (pin) {
    toggleComparison(Number(pin.dataset.pin), true);
    return;
  }
  const seasonLink = event.target.closest("[data-season-link]");
  if (seasonLink) {
    setScope(currentScope().competition, seasonLink.dataset.seasonLink);
    return;
  }
  const point = event.target.closest(".point");
  if (point) {
    location.href = href("club/" + point.dataset.team);
    return;
  }
  const scroll = event.target.closest("[data-scroll]");
  if (scroll) {
    event.preventDefault();
    document.getElementById(scroll.dataset.scroll)?.scrollIntoView({
      behavior: matchMedia("(prefers-reduced-motion: reduce)").matches
        ? "instant"
        : "smooth",
    });
    return;
  }
  const action = event.target.closest("[data-action]")?.dataset.action;
  if (action === "methodology") $("#method-dialog").showModal();
  if (action === "close-dialog") $("#method-dialog").close();
  if (action === "retry") render();
  if (action === "compare" && selected.length === 2)
    location.href = href("compare", { teams: selected.join(",") });
  if (action === "clear-compare") {
    selected = [];
    $$("[data-compare]").forEach((e) => (e.checked = false));
    updateTray();
  }
  if (action === "reset-lab" && labState) {
    labState.values = { ...labState.baseline };
    for (const [key, value] of Object.entries(labState.values)) {
      const input = $(`#input-${key}`);
      if (key === "attacking_spend") {
        input.max = labState.values.total_spend;
        input.disabled = labState.values.total_spend === 0;
        $("#max-attacking_spend").textContent = formatFeature(
          key,
          labState.values.total_spend,
        );
      }
      input.value = value;
      $(`#output-${key}`).textContent = formatFeature(key, value);
    }
    clearTimeout(labTimer);
    updatePrediction();
  }
});
document.addEventListener("change", (event) => {
  if (event.target.id === "season-select")
    setScope(currentScope().competition, event.target.value);
  if (event.target.dataset.compare)
    toggleComparison(Number(event.target.dataset.compare));
  if (event.target.id === "lab-club") {
    const url = new URL(location.href);
    url.searchParams.set("team", event.target.value);
    history.pushState({}, "", url);
    render();
  }
});
document.addEventListener("input", (event) => {
  if (event.target.id === "club-search") {
    tableSearch = event.target.value;
    $("#ranking-body").innerHTML = tableRows(currentData.rows);
  }
  const key = event.target.dataset.feature;
  if (key && labState) {
    const value = Number(event.target.value);
    labState.values[key] = value;
    $(`#output-${key}`).textContent = formatFeature(key, value);
    if (key === "total_spend") {
      const attack = $("#input-attacking_spend");
      attack.max = value;
      attack.disabled = value === 0;
      labState.values.attacking_spend = Math.min(
        value,
        labState.values.attacking_spend,
      );
      attack.value = labState.values.attacking_spend;
      $("#output-attacking_spend").textContent = formatFeature(
        "attacking_spend",
        labState.values.attacking_spend,
      );
      $("#max-attacking_spend").textContent = formatFeature(
        "attacking_spend",
        value,
      );
    }
    clearTimeout(labTimer);
    labTimer = setTimeout(updatePrediction, 180);
  }
});
function showTooltip(point) {
  const wrap = point.closest(".chart-wrap"),
    tip = $(".tooltip", wrap);
  if (!tip) return;
  const p = point.getBoundingClientRect(),
    box = wrap.getBoundingClientRect();
  tip.hidden = false;
  tip.innerHTML = `<strong>${escape(point.dataset.name)}</strong><span>${escape(point.dataset.season)} · Spend ${euro(Number(point.dataset.x))}<br>${point.dataset.mode === "next" ? "Next-season Δ" : "Champagne Index"} ${number(Number(point.dataset.y))}</span>`;
  tip.style.left = `${Math.max(95, Math.min(box.width - 95, p.x - box.x + p.width / 2))}px`;
  tip.style.top = `${Math.max(90, p.y - box.y - 12)}px`;
}
document.addEventListener("pointerover", (event) => {
  const point = event.target.closest(".point");
  if (point) showTooltip(point);
});
document.addEventListener("pointerout", (event) => {
  if (
    event.target.closest(".point") &&
    !event.relatedTarget?.closest?.(".point")
  )
    $$(".tooltip").forEach((t) => (t.hidden = true));
});
document.addEventListener("focusin", (event) => {
  const point = event.target.closest(".point");
  if (point) showTooltip(point);
});
document.addEventListener("focusout", (event) => {
  if (event.target.closest(".point"))
    $$(".tooltip").forEach((t) => (t.hidden = true));
});
document.addEventListener("keydown", (event) => {
  const point = event.target.closest?.(".point");
  if (point && (event.key === "Enter" || event.key === " ")) {
    event.preventDefault();
    location.href = href("club/" + point.dataset.team);
  }
});
$("#method-dialog").addEventListener("click", (event) => {
  if (event.target === $("#method-dialog")) {
    const r = event.target.getBoundingClientRect();
    if (
      event.clientX < r.left ||
      event.clientX > r.right ||
      event.clientY < r.top ||
      event.clientY > r.bottom
    )
      event.target.close();
  }
});
window.addEventListener("hashchange", () => {
  render();
  window.scrollTo(0, 0);
});
window.addEventListener("popstate", () => render());
let resizeTimer;
window.addEventListener("resize", () => {
  clearTimeout(resizeTimer);
  resizeTimer = setTimeout(() => {
    if (routeName() === "overview" && currentData) switchChart(chartMode);
  }, 200);
});
async function boot() {
  try {
    meta = await request("/api/meta");
    await render();
  } catch (error) {
    $("#app").setAttribute("aria-busy", "false");
    $("#app").innerHTML =
      `<div class="empty-state"><h2>The data room is unavailable.</h2><p>${escape(error.message)}</p><button class="button" data-action="reload" style="margin-top:20px">Reload the page ↻</button></div>`;
    document.addEventListener("click", (e) => {
      if (e.target.closest('[data-action="reload"]')) location.reload();
    });
  }
}
boot();
