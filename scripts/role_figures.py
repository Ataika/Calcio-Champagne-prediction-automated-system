# -*- coding: utf-8 -*-
"""Plain explanatory figures for the personal defense guides.

Deliberately not UML and deliberately without any measured value: these are
for speakers who need to picture their own part of the system, not to carry
numbers they did not measure. Each figure ships with a caption that says how
to read it and one sentence the speaker can say while it is on screen.
"""

FIG_STYLE = """<style>
.fig{width:100%;height:auto;margin:2mm 0 1mm;break-inside:avoid}
.fig text{font-family:Arial,Helvetica,sans-serif;fill:#252a24}
.fig .t{font-size:13px;font-weight:bold}
.fig .b{font-size:11.5px}
.fig .s{font-size:10px;fill:#6d7269}
.fig .k{font-size:10px;fill:#782e43;font-weight:bold;paint-order:stroke;stroke:#fff;stroke-width:3;stroke-linejoin:round}
.fig .box{fill:#f5f5ef;stroke:#8d9382;stroke-width:1.2}
.fig .good{fill:#eef0e7;stroke:#657251;stroke-width:1.4}
.fig .stop{fill:#f4ece9;stroke:#782e43;stroke-width:1.4}
.fig .note{fill:#f2efe4;stroke:#9b783c;stroke-width:1}
.fig .arrow{stroke:#252a24;stroke-width:1.4;fill:none}
.fig .reject{stroke:#782e43;stroke-width:1.4;fill:none;stroke-dasharray:5 3}
.figwrap{break-inside:avoid;margin:4mm 0 6mm}
.figwrap h3{margin:0 0 1mm}
.figcap{font-size:8.6pt;color:#555b52;margin:0 0 1mm}
.figsay{font-size:8.8pt;border-left:3px solid #657251;background:#eef0e7;padding:2mm 3mm;margin:1mm 0 0}
</style>"""

A = ('<defs><marker id="fa" markerWidth="10" markerHeight="10" refX="9" refY="5" orient="auto">'
     '<path d="M0,0 L9,5 L0,10 z" fill="#252a24"/></marker>'
     '<marker id="fr" markerWidth="10" markerHeight="10" refX="9" refY="5" orient="auto">'
     '<path d="M0,0 L9,5 L0,10 z" fill="#782e43"/></marker></defs>')


def _box(x, y, w, h, title, lines, kind="box"):
    out = [f'<rect class="{kind}" x="{x}" y="{y}" width="{w}" height="{h}" rx="3"/>',
           f'<text class="t" x="{x + w / 2}" y="{y + 20}" text-anchor="middle">{title}</text>']
    for i, line in enumerate(lines):
        out.append(f'<text class="b" x="{x + w / 2}" y="{y + 38 + 15 * i}" text-anchor="middle">{line}</text>')
    return "".join(out)


def _arr(x1, y1, x2, y2, label="", reject=False, dy=-6):
    cls, marker = ("reject", "fr") if reject else ("arrow", "fa")
    out = [f'<path class="{cls}" marker-end="url(#{marker})" d="M{x1},{y1} L{x2},{y2}"/>']
    if label:
        out.append(f'<text class="k" x="{(x1 + x2) / 2}" y="{(y1 + y2) / 2 + dy}" text-anchor="middle">{label}</text>')
    return "".join(out)


# ---------------------------------------------------------------- Neda
def neda_acquisition():
    s = [f'<svg class="fig" viewBox="0 0 700 250">{A}']
    s.append(_box(10, 40, 150, 72, "Public repository", ["one pinned version", "of eleven files"]))
    s.append(_box(200, 40, 150, 72, "Fingerprint check", ["does the file match", "what we wrote down?"]))
    s.append(_box(390, 10, 150, 72, "Temporary file", ["nothing is installed", "until it passes"], "box"))
    s.append(_box(390, 130, 150, 72, "Rejected", ["no half-written file", "ever reaches us"], "stop"))
    s.append(_box(560, 10, 130, 72, "Database", ["one table", "per file"], "good"))
    s.append(_arr(160, 76, 200, 76))
    s.append(_arr(352, 64, 388, 44))
    s.append('<text class="k" x="370" y="30" text-anchor="middle">match</text>')
    s.append(_arr(352, 90, 388, 162, reject=True))
    s.append('<text class="k" x="356" y="124">mismatch</text>')
    s.append(_arr(540, 46, 560, 46))
    s.append('<text class="s" x="10" y="232">The same check runs whether the file was downloaded today or months ago.</text>')
    s.append('</svg>')
    return "".join(s)


def neda_grain():
    s = [f'<svg class="fig" viewBox="0 0 700 250">{A}']
    s.append(_box(10, 30, 190, 96, "Many player rows", ["one row per player,", "per season,", "per competition"]))
    s.append(_box(255, 50, 170, 60, "Add them up", ["by club, season", "and competition"], "note"))
    s.append(_box(480, 30, 210, 96, "One analysis row", ["one club,", "one season,", "one competition"], "good"))
    s.append(_arr(200, 78, 255, 78))
    s.append(_arr(425, 78, 480, 78))
    s.append('<text class="s" x="10" y="160">Clubs are joined by their number, never by their name:</text>')
    s.append(_box(10, 172, 200, 56, "“Inter”", ["a label on the screen"], "box"))
    s.append(_box(255, 172, 170, 56, "club 46", ["the real identity"], "good"))
    s.append(_arr(210, 200, 255, 200))
    s.append('<text class="s" x="440" y="196">Two spellings of one club would otherwise</text>')
    s.append('<text class="s" x="440" y="210">become two different clubs in the results.</text>')
    s.append('</svg>')
    return "".join(s)


def neda_two_sources():
    s = [f'<svg class="fig" viewBox="0 0 700 230">{A}']
    s.append(_box(10, 20, 300, 80, "Player records", ["who scored and assisted,", "season by season"]))
    s.append(_box(10, 130, 300, 80, "Match results", ["the actual scoreline", "of each played game"]))
    s.append(_box(420, 20, 270, 80, "Attacking index", ["built only from", "player records"], "good"))
    s.append(_box(420, 130, 270, 80, "Goals for and against", ["built only from", "match results"], "good"))
    s.append(_arr(310, 60, 420, 60))
    s.append(_arr(310, 170, 420, 170))
    s.append('<text class="s" x="355" y="118" text-anchor="middle">the two never mix</text>')
    s.append('</svg>')
    return "".join(s)


# ---------------------------------------------------------------- Jacopo
def jacopo_request():
    s = [f'<svg class="fig" viewBox="0 0 700 220">{A}']
    s.append(_box(10, 50, 140, 80, "The page", ["someone picks", "a league and season"]))
    s.append(_box(190, 50, 150, 80, "Our server", ["checks the request,", "then asks the database"]))
    s.append(_box(380, 50, 150, 80, "Prepared table", ["already computed", "by the pipeline"]))
    s.append(_box(570, 50, 120, 80, "The chart", ["a few hundred", "rows, not millions"], "good"))
    s.append(_arr(150, 90, 190, 90))
    s.append(_arr(340, 90, 380, 90))
    s.append(_arr(530, 90, 570, 90))
    s.append('<text class="s" x="10" y="180">Nothing is calculated in the browser, and the raw player rows never leave the server.</text>')
    s.append('</svg>')
    return "".join(s)


def jacopo_states():
    s = [f'<svg class="fig" viewBox="0 0 700 250">{A}']
    s.append(_box(250, 10, 200, 56, "Two clubs selected", ["what can the page show?"], "note"))
    s.append(_box(10, 130, 200, 90, "No coverage", ["we never loaded", "this league and season"], "stop"))
    s.append(_box(250, 130, 200, 90, "No meeting", ["the season is loaded,", "they did not play"], "stop"))
    s.append(_box(490, 130, 200, 90, "A real 0–0", ["they played and", "nobody scored"], "good"))
    s.append(_arr(300, 66, 150, 130))
    s.append(_arr(350, 66, 350, 130))
    s.append(_arr(400, 66, 560, 130))
    s.append('<text class="s" x="350" y="240" text-anchor="middle">Three different messages. The page never turns a gap in the data into a score.</text>')
    s.append('</svg>')
    return "".join(s)


def jacopo_refusals():
    s = [f'<svg class="fig" viewBox="0 0 700 240">{A}']
    s.append(_box(10, 90, 150, 70, "A request", ["arrives at the API"]))
    s.append(_box(240, 10, 200, 62, "Invalid input", ["the same club twice"], "stop"))
    s.append(_box(240, 90, 200, 62, "Not in scope", ["club or season", "we do not cover"], "stop"))
    s.append(_box(240, 170, 200, 62, "Not ready yet", ["data or model", "still missing"], "stop"))
    s.append(_box(520, 10, 170, 62, "422", ["your request", "was wrong"], "note"))
    s.append(_box(520, 90, 170, 62, "404", ["we do not have", "that one"], "note"))
    s.append(_box(520, 170, 170, 62, "503", ["we are not ready,", "try again"], "note"))
    s.append(_arr(160, 110, 240, 41))
    s.append(_arr(160, 122, 240, 122))
    s.append(_arr(160, 134, 240, 200))
    for y in (41, 122, 200):
        s.append(_arr(440, y, 520, y))
    s.append('</svg>')
    return "".join(s)


# ---------------------------------------------------------------- Gabriele
def gabriele_target():
    s = [f'<svg class="fig" viewBox="0 0 700 250">{A}']
    s.append(_box(10, 20, 180, 70, "This season", ["attacking output", "of one club"]))
    s.append(_box(260, 20, 180, 70, "The next season", ["the very next year,", "same club"]))
    s.append(_box(510, 20, 180, 70, "What we predict", ["the change", "between the two"], "good"))
    s.append(_arr(190, 55, 260, 55))
    s.append(_arr(440, 55, 510, 55, "difference"))
    s.append('<text class="s" x="10" y="130">A pair is only used when the two seasons really follow each other:</text>')
    s.append(_box(10, 148, 180, 64, "2023/24 → 2024/25", ["accepted"], "good"))
    s.append(_box(260, 148, 180, 64, "2023/24 → 2025/26", ["rejected: a year is missing"], "stop"))
    s.append(_box(510, 148, 180, 64, "Thin season", ["rejected: too few matches"], "stop"))
    s.append('</svg>')
    return "".join(s)


def gabriele_holdout():
    s = [f'<svg class="fig" viewBox="0 0 700 230">{A}']
    s.append('<rect class="good" x="10" y="40" width="380" height="60" rx="3"/>')
    s.append('<text class="t" x="200" y="66" text-anchor="middle">Earlier seasons</text>')
    s.append('<text class="b" x="200" y="86" text-anchor="middle">the model learns here</text>')
    s.append('<rect class="note" x="410" y="40" width="280" height="60" rx="3"/>')
    s.append('<text class="t" x="550" y="66" text-anchor="middle">Later seasons</text>')
    s.append('<text class="b" x="550" y="86" text-anchor="middle">it is tested here, unseen</text>')
    s.append('<path class="arrow" marker-end="url(#fa)" d="M10,120 L690,120"/>')
    s.append('<text class="s" x="10" y="138">time</text>')
    s.append(_box(10, 155, 320, 62, "Our model", ["predicts a change", "for each test season"], "box"))
    s.append(_box(370, 155, 320, 62, "The simple comparison", ["predicts no change at all"], "box"))
    s.append('<text class="k" x="350" y="192" text-anchor="middle">vs</text>')
    s.append('</svg>')
    return "".join(s)


def gabriele_claims():
    s = [f'<svg class="fig" viewBox="0 0 700 230">{A}']
    s.append(_box(10, 30, 200, 80, "Two things move together", ["spending and output,", "in the same records"]))
    s.append(_box(260, 30, 180, 80, "We can say this", ["they are associated"], "good"))
    s.append(_box(500, 30, 190, 80, "We cannot say this", ["one causes the other"], "stop"))
    s.append(_arr(210, 70, 260, 70))
    s.append(_arr(440, 70, 500, 70, "", reject=True))
    s.append('<path d="M462,60 L478,80 M478,60 L462,80" stroke="#782e43" stroke-width="2.2"/>')
    s.append(_box(10, 140, 680, 70, "Why not", ["richer clubs differ in many ways at once — squad, coach, league, luck — and we never ran an experiment",
                                                "where one club spends and an identical club does not"], "note"))
    s.append('</svg>')
    return "".join(s)


FIGURES = {
    "neda": [
        ("From a public file to a table we trust", neda_acquisition,
         "Read it left to right. A file is only installed after its fingerprint matches the one we recorded; anything else is thrown away.",
         "“We never trust a download. We compare it with a fingerprint we wrote down in advance, and a file that fails never reaches the database.”"),
        ("What one row of the analysis is", neda_grain,
         "The left side is the raw data, one row per player. The right side is the unit everything else is built on.",
         "“One row of our analysis is one club, in one season, in one competition — and clubs are joined by number, never by name.”"),
        ("Two sources that are never mixed", neda_two_sources,
         "Two separate inputs produce two separate measures. Each number on the screen comes from exactly one of them.",
         "“The attacking index comes from player records; goals for and against come from real scorelines. We never add one to the other.”"),
    ],
    "jacopo": [
        ("What happens when someone clicks", jacopo_request,
         "Four steps, left to right. The heavy work happened earlier, in the pipeline; the page only displays a prepared answer.",
         "“The browser asks our server, the server reads a prepared table and sends back a few hundred rows. Nothing heavy happens in the browser.”"),
        ("Three situations that look alike", jacopo_states,
         "One selection, three possible outcomes. The page shows a different message for each of them.",
         "“Missing data, a season where they never met, and a real goalless draw are three different answers — the page never invents a score.”"),
        ("What the server refuses, and what it replies", jacopo_refusals,
         "Each refusal has its own answer code. The numbers are labels for the kind of problem, not error levels.",
         "“If the request is wrong we say so, if the club is outside our scope we say so, and if the data is not ready we say that instead of showing something false.”"),
    ],
    "lill": [
        ("What the model is asked to predict", gabriele_target,
         "The prediction target is a change between two seasons that genuinely follow each other, not a league position and not a match result.",
         "“We predict how a club's attacking output changes in the following season — and only when both seasons are properly covered.”"),
        ("Learning on the past, tested on the future", gabriele_holdout,
         "Time runs left to right. The model never sees the seasons it is judged on, and it is compared with the simplest possible guess.",
         "“We train on earlier seasons and test on later ones, and we compare the model with simply predicting no change at all.”"),
        ("What we may and may not claim", gabriele_claims,
         "The left arrow is allowed, the crossed one is not. This is the boundary every number in our project sits behind.",
         "“These are historical records, not an experiment, so we can say two things move together — never that one causes the other.”"),
    ],
}
