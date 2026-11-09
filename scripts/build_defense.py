#!/usr/bin/env python3
"""Build the offline study site and print-ready HTML from defense/curriculum.json.

PDFs are rendered with the system Chrome by scripts/render_defense.mjs.
"""
from __future__ import annotations

import html
import json
import shutil
from pathlib import Path
from build_final_report import main as build_final_report

ROOT = Path(__file__).resolve().parents[1]
CURRICULUM = ROOT / "defense/curriculum.json"
SITE = ROOT / "defense/site"
MATERIALS = ROOT / "defense/materials"
DOWNLOADS = SITE / "downloads"


def esc(value: object) -> str:
    return html.escape(str(value), quote=True)


def bullet_list(values: list[str]) -> str:
    return "<ul>" + "".join(f"<li>{esc(value)}</li>" for value in values) + "</ul>"


def number_list(values: list[str]) -> str:
    return "<ol>" + "".join(f"<li>{esc(value)}</li>" for value in values) + "</ol>"


def style() -> str:
    return """<style>
@page { size: A4; margin: 17mm 17mm 18mm; }
* { box-sizing: border-box; }
body { margin: 0; color:#242923; font: 10.3pt/1.55 Arial,Helvetica,sans-serif; }
h1,h2,h3 { font-family:Georgia,'Times New Roman',serif; line-height:1.1; color:#292d27; }
h1 { font-size:28pt; margin:8mm 0 3mm; }
h2 { font-size:19pt; margin:9mm 0 3mm; border-bottom:1px solid #b9beb0; padding-bottom:2mm; break-after:avoid; }
h3 { font-size:13pt; margin:5mm 0 2mm; break-after:avoid; }
p { margin:2mm 0 4mm; }
li { margin:1.4mm 0; }
table { border-collapse:collapse; width:100%; margin:4mm 0; font-size:9pt; }
th,td { text-align:left; vertical-align:top; border-bottom:1px solid #d7d9d1; padding:2.5mm; }
th { background:#eceee5; font: bold 8pt Arial; }
.cover { min-height:235mm; display:flex; flex-direction:column; justify-content:space-between; page-break-after:always; }
.kicker,.tag { font:8pt/1.5 Menlo,Consolas,monospace; letter-spacing:1.2px; color:#782e43; text-transform:uppercase; }
.lede { font:15pt/1.5 Georgia,serif; max-width:160mm; color:#666b62; }
.cover-footer { border-top:2px solid #292d27; padding-top:4mm; color:#6d7269; font-size:9pt; }
.callout { border-left:3px solid #782e43; background:#f3eeea; padding:4mm 5mm; margin:4mm 0; break-inside:avoid; }
.warning { border-left-color:#9b783c; background:#f2efe4; }
.metric { font:23pt/1.2 Georgia,serif; color:#657251; }
.small { color:#6d7269; font-size:8.5pt; }
.figure { margin:5mm 0; break-inside:avoid; }
.figure img { max-width:100%; max-height:115mm; object-fit:contain; border:1px solid #d7d9d1; }
.figure figcaption { color:#6d7269; font-size:8pt; margin-top:1mm; }
.question { break-inside:avoid; margin:3mm 0; }
.question p { margin:1mm 0; }
.answer { color:#51574e; }
.role { break-before:page; }
.slide { page:slide; }
.notes { background:#eef0e7; padding:4mm; margin-top:5mm; font-size:9.5pt; }
.page-num:after { content: counter(page); }
@page slide { size: 13.333in 7.5in; margin: 0.5in; }
.slides-doc { font-size:18pt; }
.slides-doc h1 { font-size:34pt; }
.slides-doc ul { font-size:17pt; line-height:1.55; }
@media print { a { color:inherit; text-decoration:none; } .break { break-before:page; } }
</style>"""


def document(title: str, body: str, language: str = "en", slides: bool = False) -> str:
    cls = "slides-doc" if slides else ""
    return (f'<!doctype html><html lang="{language}"><head><meta charset="utf-8">'
            f'<meta name="viewport" content="width=device-width,initial-scale=1"><title>{esc(title)}</title>'
            f'{style()}</head><body class="{cls}">{body}</body></html>')


def cover(title: str, kicker: str, summary: str, footer: str) -> str:
    return (f'<section class="cover"><div><div class="kicker">{esc(kicker)}</div>'
            f'<h1>{title}</h1><p class="lede">{esc(summary)}</p></div>'
            f'<div class="cover-footer">{esc(footer)}</div></section>')


def report(d: dict) -> str:
    m = d["measurements"]
    body = [cover("Calcio Champagne", "LUISS · Computational Infrastructures · Project report",
                  "A reproducible football data system: source acquisition, relational processing, temporal evaluation, web interface, and measured runtime behaviour.",
                  f"Prepared {d['prepared']} · Evidence branch {d['branch']} · Local, dated evidence snapshot")]
    body.append(f'<h2>Executive summary</h2><p>{esc(d["summary_en"])}</p>')
    body.append('<div class="callout"><b>What the evidence says.</b> Recorded transfer spending has a practically zero linear association with next-season index change in the eligible sample (r = −0.003613, p = 0.478, n = 38,531). The same-season index-position association is stronger (r = −0.793, n = 388), but it is descriptive and the direction is inverse because a lower league-position number is better. A chronological RandomForest improves on a zero-change MAE baseline by about 5%; the test R² is 0.127.</div>')
    body.append('<h2>1. Research questions and measures</h2>')
    body.append('<h3>Primary attacking index</h3><p><b>Champagne Index = (recorded player goals + assists) / source matches.</b> The observation is club × season × competition. The main source is Transfermarkt player-level seasonal data; its group match count is a proxy, not a verified fixture count. The index is neither expected goals nor a match-event model.</p>')
    body.append('<h3>Actual season scoring context</h3><p>The optional football-data.co.uk match enrichment supplies completed home/away scores for five leagues and five seasons (21/22–25/26): 25 league-season files and 8,908 completed matches in this snapshot. For each club, <b>GF</b> is goals scored, <b>GA</b> is goals conceded and <b>GD = GF − GA</b>. The attacking rank orders GF per played match descending; the defensive rank orders GA per match ascending. Both use SQL RANK within a league-season, so tied rates share a rank. The comparison keeps these whole-season totals separate from the selected clubs’ direct head-to-head results.</p>')
    body.append('<p>Serie A 24/25 makes the distinction concrete: Inter recorded 79 GF, 35 GA and +44 GD (attack rank 1, defense rank 2); Milan recorded 61, 43 and +18 (attack rank 3, defense rank 7). These ranks summarize scorelines, not tactics or chance quality. <b>xG is not in the loaded match schema or checked source fields and is therefore not reported.</b> Player-level `goals_conceded` and `clean_sheets` exist in the primary source, but coverage is uneven; they are not substituted for complete club match totals.</p>')
    body.append('<p>We also checked those goalkeeper totals against actual scores on 388 adequately covered top-five club-seasons: conceded totals agree exactly in 366 cases (94.3%), while clean-sheet counts agree in 269 (69.3%). This supports using the player aggregate as a qualified cross-check, not as the comparison source. Defensive transfer spending also has no useful linear association with next-season change in that conceded-goal rate (r = 0.004047, p = 0.426997, n = 38,531). This secondary relationship is descriptive and uses the broader, uneven-coverage player dataset.</p>')
    body.append('<h2>2. Data sources and acquisition</h2>')
    body.append('<p>The primary input consists of eleven pinned CSV tables (5,743,186 local rows in the audited snapshot). The loader verifies exact headers and hashes, normalizes the documented metadata exception, uses atomic downloads, bulk COPY and post-load indices. Team aliases are mapped before match scores join to canonical club identifiers. Raw datasets and model artifacts are excluded from the Git repository and Docker build context.</p>')
    body.append('<p>The optional match data is manually prepared and has a verified team-name map. Unplayed fixtures are excluded; dates, score ranges, result consistency and duplicate/conflicting fixtures are validated. Removing the optional source clears stale matches. The enrichment adds standings and head-to-head scores; the core Transfermarkt pipeline remains usable without it.</p>')
    body.append('<div class="callout warning"><b>Licence boundary.</b> The primary upstream snapshot is pinned and reproducible, but an explicit licence was not confirmed at that revision. Public download availability is not treated as a reuse licence. That course requirement remains open until the source owner or a replacement dataset resolves it.</div>')
    body.append('<h2>3. Architecture and data flow</h2>')
    body.append('<table><thead><tr><th>Stage</th><th>Component</th><th>Responsibility</th></tr></thead><tbody><tr><td>GET</td><td>Python loader</td><td>Verify/acquire CSVs and optional matches; normalize and validate.</td></tr><tr><td>STORE</td><td>PostgreSQL 16</td><td>Persist source tables, canonical identifiers, indices and prepared outputs.</td></tr><tr><td>PROCESS</td><td>Python pipeline</td><td>Aggregate features, build targets, train/evaluate models, calculate standings.</td></tr><tr><td>SHOW</td><td>FastAPI + static browser app</td><td>Bounded read-only API, club views, comparisons, Lab and methods.</td></tr></tbody></table>')
    body.append('<p>Docker Compose gates downstream work on database health and successful completion of loading and processing. Measurements are a separate opt-in service. A legacy Streamlit dashboard is optional. Read-only API queries bind parameters and expose bounded prepared tables, not raw player records.</p>')
    body.append('<h2>4. Statistical methods and evaluation</h2>')
    body.append('<h3>Association analysis</h3><p>Incoming recorded transfer fees are compared with the next consecutive season’s change in Champagne Index. Only actual consecutive season pairs are included. On 38,531 eligible observations the Pearson correlation is −0.003612725 (p = 0.4782423): no useful linear spending association is supported. In 388 adequately covered top-five club-seasons, the same-season correlation between index and final position is −0.793285. The position sign is negative because lower numerical positions represent better finishes. It does not establish a spending or scoring intervention.</p>')
    body.append('<h3>Temporal prediction</h3><p>The prediction target is next consecutive season index minus current index. Five features are evaluated with earlier seasons for training and later seasons for a held-out test: 16,074 train rows and 5,585 test rows, with test seasons starting in 2021. RandomForest test R² is 0.127115 and MAE 0.485593; the zero-change baseline MAE is 0.511364 on the same test rows, about a 5% MAE reduction. This is a modest improvement, not an accuracy percentage. A separate all-data model powers the retrospective Lab and is not the temporal test model.</p>')
    body.append('<p>The first-team filter excludes reserve/youth clubs. Market values and fees contain structural missingness and undisclosed amounts. Seasonal rows are retrospective, not a pre-window causal forecast. A partial Transfermarkt season is not paired with full final standings: comparisons require at least 30 games and 80% match coverage.</p>')
    body.append('<h2>5. Comparison and user-facing evidence</h2>')
    body.append('<p>The club comparison reports spending, player-level index components, actual league GF/GA/GD, attack/defense ranks, league finish, points and a distinct direct-meeting block with scorelines, wins/draws/losses, clean sheets and points. Missing optional match coverage is identified instead of shown as zero goals. CSV export and the Lab carry method notes and validation constraints.</p>')
    for filename, caption in [("comparison-desktop.png", "Two-club comparison after score-derived season metrics were added."), ("overview-desktop.png", "Overview with league scope, historical context and model evidence."), ("lab-desktop.png", "Retrospective scenario Lab using the saved five-feature model.")]:
        source = ROOT / "artifacts" / filename
        if source.exists():
            target = SITE / "assets" / filename
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
            body.append(f'<figure class="figure"><img src="../site/assets/{esc(filename)}"><figcaption>{esc(caption)}</figcaption></figure>')
    body.append('<h2>6. Infrastructure measurement</h2>')
    body.append(f'<p><b>Machine.</b> {esc(m["machine"])}. Three-run means. Sources and built images retained; containers recreated, source rows reimported and the model retrained. OS/database caches were not flushed and other workloads were uncontrolled. Download and image build are excluded from the 31.10-second cached-source startup.</p>')
    body.append('<table><thead><tr><th>Measurement</th><th>Observed value</th><th>Scope</th></tr></thead><tbody>')
    body.append(f'<tr><td>Complete cached-source startup</td><td>31.10 s</td><td>Mean of 3 runs</td></tr><tr><td>Loader / pipeline mean</td><td>{m["loader"]:.2f} s / {m["pipeline"]:.2f} s</td><td>Separate timed stages</td></tr><tr><td>Database / CSV footprint</td><td>{m["db_mib"]:.1f} / {m["csv_mib"]:.1f} MiB</td><td>Measured snapshot</td></tr><tr><td>300 selective lookups</td><td>{m["lookup_without"]:.4f} s → {m["lookup_with"]:.4f} s</td><td>One query, before/after index</td></tr></tbody></table>')
    body.append('<table><thead><tr><th>Largest-table share</th><th>Rows</th><th>Load</th><th>Query</th></tr></thead><tbody>')
    for share, rows, load, query in m["growth"]:
        body.append(f'<tr><td>{share}%</td><td>{rows:,}</td><td>{load:.2f} s</td><td>{query:.3f} s</td></tr>')
    body.append('</tbody></table><p>Memory values are sampled docker stats working sets, not guaranteed peaks. Growth timings are local observations, not a universal scaling law. The 145.4× lookup change is specific to the measured selective query.</p>')
    body.append('<h2>7. Validation, ownership and limitations</h2>')
    body.append('<p>The repository snapshot has 38 unit/regression checks, 16 live API/data checks and 15 real-browser checks. The checks cover source verification, match consistency, target construction, model evaluation, endpoint contracts and core UI interaction. They do not prove that all failure modes are absent or establish independent work by each participant. Four study tracks in the companion guide map responsibilities to code paths; every participant should be able to explain the full pipeline and name only work they personally performed.</p>')
    body.append('<ul><li>Primary-data licence remains unconfirmed.</li><li>Transfermarkt match count is a proxy; undisclosed transfer fees appear as zero.</li><li>Champagne Index is a seasonal attacking proxy; no match-level xG is present.</li><li>League rankings are score-based and do not apply every official tie-break or deduction.</li><li>Historical correlations are descriptive; the model is modest and retrospective.</li><li>Independent fresh-checkout validation and a backup presentation recording remain to be completed by the team.</li></ul>')
    body.append('<h2>Reproduction</h2><p>See README for the Docker Compose startup, loader options, optional match-data location and API. The report records the tested evidence and date; rebuilds can differ if upstream files or local metadata inputs change.</p>')
    body.append(f'<p class="small">Prepared from {esc(d["repository"])} on branch {esc(d["branch"])}. Source attribution and implementation notes are maintained in docs/SOURCES.md and docs/AUDIT.md.</p>')
    return document("Calcio Champagne — Project Report", "".join(body))


def guide(d: dict) -> str:
    body = [cover("Team Defense Guide", "Four study tracks · one complete system",
                  "Русское пособие с проверяемыми фактами, английскими репликами, упражнениями, вопросами экзаменатора и репетицией на 15 минут.",
                  f"Calcio Champagne · Prepared {d['prepared']} · English phrases are practice material, not claims about individual authorship.")]
    body.append(f'<h2>Проект за одну минуту</h2><p>{esc(d["summary_ru"])}</p>')
    body.append('<div class="callout"><b>Новые показатели сравнения.</b> GF — забитые голы; GA — пропущенные; GD = GF−GA. Атакующий ранг строится по голам за матч (чем больше, тем выше место), защитный — по пропущенным за матч (чем меньше, тем выше место). Ранг считается отдельно внутри выбранных лиги и сезона; ничьи делят место. xG отсутствует в загруженной схеме, его нельзя выводить из счёта.</div>')
    body.append('<h2>План подготовки команды</h2><ol><li>Каждый изучает свою карточку, проходит упражнения и показывает, где подтверждение в репозитории.</li><li>Вместе проследите CSV → PostgreSQL → pipeline → API → экран.</li><li>Проведите 15-минутную репетицию с таймером; не превышайте время своей части.</li><li>Каждый отвечает минимум на два вопроса вне своего направления.</li><li>Проверьте приложение на другом ноутбуке и подготовьте резервное видео.</li></ol>')
    body.append('<div class="callout warning"><b>Распределение в пособии — план изучения и выступления.</b> Оно само по себе не доказывает, кто писал конкретный код. На защите описывайте фактическую работу, которую вы можете показать.</div>')
    for r in d["roles"]:
        body.append(f'<section class="role"><div class="kicker">{esc(r["account"])} · {esc(r["minutes"])} recommended speaking time</div><h2>{esc(r["name"])}</h2><p><b>Область:</b> {esc(r["scope"])}</p><h3>Что знать</h3>{bullet_list(r["must_know"])}<h3>Что показать</h3>{number_list(r["show"])}<h3>Английская реплика для репетиции</h3><div class="callout"><i>{esc(r["script_en"])}</i></div><p><b>Передача слова:</b> “{esc(r["handoff_en"])}”</p><h3>Практика</h3>{number_list(r["exercises"])}<h3>Избегай</h3>{bullet_list(r["avoid"])}</section>')
    body.append('<section class="break"><h2>Вопросы экзаменатора</h2><p>Сначала ответь вслух коротко, затем объясни основание и ограничение.</p>')
    for q in d["questions"]:
        who = "Все" if q["role"] == "all" else next((r["account"] for r in d["roles"] if r["id"] == q["role"]), "Команда")
        body.append(f'<div class="question"><div class="tag">{esc(who)}</div><p><b lang="en">{esc(q["question"])}</b></p><p class="small" lang="ru">{esc(q["ru"])}</p><p class="answer" lang="en">{esc(q["answer"])}</p></div>')
    body.append('</section><h2>Порядок 15-минутного выступления</h2><table><thead><tr><th>Slide</th><th>Owner</th><th>Time</th><th>What to show</th></tr></thead><tbody>')
    clock = 0
    for i, s in enumerate(d["slides"], 1):
        start = f"{clock // 60:02d}:{clock % 60:02d}"; clock += s["seconds"]; end = f"{clock // 60:02d}:{clock % 60:02d}"
        owner = next(r["account"] for r in d["roles"] if r["id"] == s["owner"])
        body.append(f'<tr><td>{i}. {esc(s["title"])}</td><td>{esc(owner)}</td><td>{start}–{end}</td><td>{esc("; ".join(s["bullets"]))}</td></tr>')
    body.append('</tbody></table><h2>Демо и готовность</h2>')
    body.append('<table><thead><tr><th>Time</th><th>Action</th><th>Expected / fallback</th></tr></thead><tbody>')
    for item in d["demo"]:
        body.append(f'<tr><td>{esc(item["time"])}</td><td>{esc(item["action"])}</td><td>{esc(item["expected"])}<br><span class="small">{esc(item["fallback"])}</span></td></tr>')
    body.append('</tbody></table>')
    body.append('<h3>До сдачи</h3>' + bullet_list([c["label"] for c in d["checklist"]]))
    body.append('<h2>Проверенные факты и ограничения</h2><table><thead><tr><th>Measure</th><th>Value</th><th>Explanation</th></tr></thead><tbody>')
    for m in d["metrics"]:
        body.append(f'<tr><td>{esc(m["label"])}</td><td>{esc(m["value"])}</td><td>{esc(m["note"])}</td></tr>')
    body.append('</tbody></table><p>Первичный источник закреплён по версии, но лицензия не подтверждена. Это открытый пункт, который нельзя закрыть одной ссылкой на публичную загрузку.</p>')
    return document("Team Defense Guide", "".join(body), "ru")


def role_doc(d: dict, r: dict) -> str:
    body = [cover(esc(r["name"]), f"Personal study card · {esc(r['account'])} · {esc(r['minutes'])}",
                  r["scope"], f"Calcio Champagne · Role track {r['id']} · Confirm personal work truthfully")]
    body.append('<h2>Что нужно знать</h2>' + bullet_list(r["must_know"]))
    body.append('<h2>Что показать</h2>' + number_list(r["show"]))
    body.append('<h2>Короткая речь на английском</h2><div class="callout"><i>' + esc(r["script_en"]) + '</i></div>')
    body.append('<p><b>Переход:</b> “' + esc(r["handoff_en"]) + '”</p>')
    body.append('<h2>Практические задания</h2>' + number_list(r["exercises"]))
    body.append('<h2>Вопросы по направлению</h2>')
    qs = [q for q in d["questions"] if q["role"] in (r["id"], "all")]
    for q in qs:
        body.append(f'<div class="question"><p><b lang="en">{esc(q["question"])}</b></p><p class="small">{esc(q["ru"])}</p><p class="answer">{esc(q["answer"])}</p></div>')
    body.append('<h2>Какие фразы не использовать</h2>' + bullet_list(r["avoid"]))
    body.append('<div class="callout warning">Роль — учебная ответственность. Не заявляй личное авторство или самостоятельную проверку, если этого не было. Покажи ровно те изменения и команды, которые выполнял(а) лично.</div>')
    return document(f"Role guide — {r['account']}", "".join(body), "ru")


def presentation(d: dict) -> str:
    slides = []
    total = sum(s["seconds"] for s in d["slides"])
    elapsed = 0
    for i, s in enumerate(d["slides"], 1):
        start = f"{elapsed // 60:02d}:{elapsed % 60:02d}"; elapsed += s["seconds"]; end = f"{elapsed // 60:02d}:{elapsed % 60:02d}"
        owner = next(r["account"] for r in d["roles"] if r["id"] == s["owner"])
        slides.append(f'<section class="slide" data-seconds="{s["seconds"]}"><div class="kicker">{esc(s["kicker"])} · {start}–{end} · {esc(owner)}</div><h1>{esc(s["title"])}</h1>{bullet_list(s["bullets"])}<aside class="speaker-notes" hidden><b>Заметки выступающего / RU</b><p>{esc(s["notes"])}</p></aside><footer><span>CALCIO CHAMPAGNE · DEFENSE ACADEMY</span><span>{i:02d} / {len(d["slides"]):02d}</span></footer></section>')
    body = f'''<div id="deck">{"".join(slides)}</div><div id="controls"><button id="prev" aria-label="Previous slide">←</button><span id="counter">1 / {len(d['slides'])}</span><button id="next" aria-label="Next slide">→</button><button id="notes">Notes · N</button><button id="full">Fullscreen · F</button><span id="clock">15:00</span></div>
<script>
const cards=[...document.querySelectorAll('.slide')];let current=0,started=null,elapsed=0;const $=s=>document.querySelector(s);function show(n){{current=(n+cards.length)%cards.length;const notes=document.body.classList.contains('show-notes');cards.forEach((s,i)=>{{s.classList.toggle('active',i===current);s.querySelector('.speaker-notes').hidden=!(notes&&i===current);}});$('#counter').textContent=`${{current+1}} / ${{cards.length}}`;}}function toggleNotes(){{const active=!document.body.classList.contains('show-notes');document.body.classList.toggle('show-notes',active);cards.forEach((s,i)=>s.querySelector('.speaker-notes').hidden=!(active&&i===current));}}
$('#prev').onclick=()=>show(current-1);$('#next').onclick=()=>show(current+1);$('#notes').onclick=toggleNotes;$('#full').onclick=()=>document.fullscreenElement?document.exitFullscreen():document.documentElement.requestFullscreen();document.addEventListener('keydown',e=>{{if(['ArrowRight','PageDown',' '].includes(e.key))show(current+1);if(['ArrowLeft','PageUp'].includes(e.key))show(current-1);if(e.key.toLowerCase()==='n')toggleNotes();if(e.key.toLowerCase()==='f')document.documentElement.requestFullscreen?.();}});setInterval(()=>{{const s=Math.max(0,900-(elapsed+(started?Date.now()-started:0))/1000);$('#clock').textContent=`${{String(Math.floor(s/60)).padStart(2,'0')}}:${{String(Math.floor(s%60)).padStart(2,'0')}}`; }},250);show(0);
</script>'''
    slide_css = '''<style>
@page { size:13.333in 7.5in; margin:.48in; }
*{box-sizing:border-box}body{margin:0;background:#252a24;color:#f5f2e9;font:20pt/1.5 Arial,Helvetica,sans-serif}.slide{display:none;position:relative;height:6.54in;padding:.4in .55in}.slide.active{display:block}.kicker{color:#b8c49f;font:10pt Menlo,Consolas,monospace;letter-spacing:1.5px;text-transform:uppercase}.slide h1{font:36pt/1.1 Georgia,serif;max-width:11.5in;margin:.35in 0 .28in}.slide ul{padding-left:.35in;max-width:11.5in}.slide li{margin:.12in 0}.slide footer{position:absolute;bottom:0;left:.55in;right:.55in;border-top:1px solid #697061;padding-top:.12in;display:flex;justify-content:space-between;color:#b9beb0;font:8pt Menlo,Consolas,monospace;letter-spacing:1px}.speaker-notes{display:none}.show-notes .speaker-notes{display:block;position:absolute;left:.55in;right:.55in;bottom:.5in;background:#ede9da;color:#252a24;padding:12px;font:11pt/1.4 Arial;z-index:2}.speaker-notes p{margin:5px 0 0}#controls{position:fixed;bottom:12px;left:50%;transform:translateX(-50%);display:flex;gap:10px;align-items:center;padding:8px 12px;background:#121612;border:1px solid #586052;border-radius:6px;color:#f5f2e9;font:12px Arial}button{background:#394039;color:white;border:1px solid #72796a;padding:8px 12px;cursor:pointer}#clock{font-family:Menlo,monospace;margin:0 8px}@media print{body{background:white;color:#252a24}.slide,.slide.active{display:block;page-break-after:always;height:6.54in;break-after:page}.slide:last-child{page-break-after:auto}.slide footer{color:#657251;border-color:#c4c8bb}.kicker{color:#782e43}#controls{display:none!important}.speaker-notes{display:none!important}}
</style>'''
    return f'<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Calcio Champagne · Presentation</title>{slide_css}</head><body>{body}</body></html>'


def main() -> None:
    d = json.loads(CURRICULUM.read_text(encoding="utf-8"))
    MATERIALS.mkdir(parents=True, exist_ok=True)
    DOWNLOADS.mkdir(parents=True, exist_ok=True)
    (SITE / "data.js").write_text("window.DEFENSE_DATA = " + json.dumps(d, ensure_ascii=False, separators=(",", ":")) + ";\n", encoding="utf-8")
    (MATERIALS / "Project-Report.html").write_text(report(d), encoding="utf-8")
    build_final_report()
    (MATERIALS / "Team-Defense-Guide.html").write_text(guide(d), encoding="utf-8")
    for r in d["roles"]:
        (MATERIALS / f"Role-{r['id']}.html").write_text(role_doc(d, r), encoding="utf-8")
    (SITE / "presentation.html").write_text(presentation(d), encoding="utf-8")
    total = sum(s["seconds"] for s in d["slides"])
    if total != 900:
        raise SystemExit(f"Expected a 15-minute presentation, got {total}s")
    speaking = {r["id"]: sum(s["seconds"] for s in d["slides"] if s["owner"] == r["id"]) for r in d["roles"]}
    if set(speaking.values()) != {225}:
        raise SystemExit(f"Speaking time must stay balanced at 225 seconds each: {speaking}")
    print(f"Built offline site data, report, guide, four role cards and {len(d['slides'])} slides ({total // 60} minutes).")


if __name__ == "__main__":
    main()
