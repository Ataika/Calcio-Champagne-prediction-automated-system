# -*- coding: utf-8 -*-
"""UML figures for the project report, drawn as inline print-safe SVG.

No external renderer and no image files: the report is printed to PDF by
headless Chrome, so the diagrams must survive as plain markup. Layout is
orthogonal on purpose — a line that crosses a box reads as a relationship
that does not exist.
"""

SVG_STYLE = """<style>
.uml{width:100%;height:auto;margin:3mm 0;break-inside:avoid}
.uml text{font-family:Arial,Helvetica,sans-serif;fill:#252a24}
.uml .n{font-size:11px;font-weight:bold}
.uml .nl{font-size:9px;font-weight:bold}
.uml .s{font-size:8.5px;fill:#782e43;font-style:italic}
.uml .a{font-size:9px}
.uml .m{font-size:8px;fill:#555b52;paint-order:stroke;stroke:#ffffff;stroke-width:3;stroke-linejoin:round}
.uml .box{fill:#f5f5ef;stroke:#8d9382;stroke-width:1}
.uml .node{fill:#fdfdfa;stroke:#252a24;stroke-width:1.2}
.uml .derived{fill:#eef0e7;stroke:#657251;stroke-width:1}
.uml .art{fill:#f2efe4;stroke:#9b783c;stroke-width:1}
.uml .life{stroke:#8d9382;stroke-width:1;stroke-dasharray:4 3}
.uml .act{fill:#d9ddcf;stroke:#657251}
.uml .sep{stroke:#8d9382;stroke-width:.8}
.uml .dep{stroke:#782e43;stroke-width:1.1;fill:none;stroke-dasharray:5 3}
.uml .flow{stroke:#252a24;stroke-width:1.1;fill:none}
</style>"""

DEFS = ('<defs>'
        '<marker id="open" markerWidth="9" markerHeight="9" refX="8" refY="4.5" orient="auto">'
        '<path d="M0,0 L8,4.5 L0,9" fill="none" stroke="#782e43" stroke-width="1.1"/></marker>'
        '<marker id="solid" markerWidth="9" markerHeight="9" refX="8" refY="4.5" orient="auto">'
        '<path d="M0,0 L8,4.5 L0,9 z" fill="#252a24"/></marker>'
        '<marker id="dot" markerWidth="7" markerHeight="7" refX="3.5" refY="3.5" orient="auto">'
        '<circle cx="3.5" cy="3.5" r="2.6" fill="#657251"/></marker>'
        '</defs>')

ROW = 13


def box(x, y, w, name, stereotype, rows, kind="box"):
    """One UML classifier: stereotype line, name, then one attribute compartment."""
    head = 32 if stereotype else 20
    h = head + ROW * len(rows) + 7
    name_class = "n" if len(name) <= 22 else "nl"
    out = [f'<g><rect class="{kind}" x="{x}" y="{y}" width="{w}" height="{h}" rx="2"/>']
    if stereotype:
        out.append(f'<text class="s" x="{x + w / 2}" y="{y + 13}" text-anchor="middle">«{stereotype}»</text>')
    out.append(f'<text class="{name_class}" x="{x + w / 2}" y="{y + head - 7}" text-anchor="middle">{name}</text>')
    if rows:
        out.append(f'<line class="sep" x1="{x}" y1="{y + head}" x2="{x + w}" y2="{y + head}"/>')
    for i, row in enumerate(rows):
        out.append(f'<text class="a" x="{x + 7}" y="{y + head + 11 + ROW * i}">{row}</text>')
    out.append('</g>')
    return "".join(out)


def _label(x, y, text, anchor="start"):
    return f'<text class="m" x="{x}" y="{y}" text-anchor="{anchor}">{text}</text>'


def component_diagram() -> str:
    """Deployment and component view: what runs where, and who may depend on whom."""
    p = [f'<svg class="uml" viewBox="0 0 700 476" role="img" aria-label="UML component and deployment diagram">{DEFS}']
    p.append('<rect class="node" x="6" y="18" width="688" height="392" rx="3"/>')
    p.append('<text class="s" x="18" y="34">«device» MacBook · Apple M3 Pro · 18 GiB · macOS</text>')
    p.append('<rect class="node" x="18" y="42" width="664" height="356" rx="3" fill="#ffffff"/>')
    p.append('<text class="s" x="30" y="58">«execution environment» Docker Engine · one compose project</text>')

    p.append(box(40, 70, 180, "loader", "container", ["python 3.12", "runs once, must exit 0", "GET · VALIDATE · COPY"]))
    p.append(box(255, 70, 180, "pipeline", "container", ["python + scikit-learn", "runs once, must exit 0", "SQL · model · SHAP"]))
    p.append(box(470, 70, 180, "app", "container", ["fastapi + uvicorn", "port 8502 → host", "read-only queries"]))
    p.append(box(255, 196, 180, "db", "container", ["image postgres:16", "healthcheck pg_isready", "source + derived tables"]))
    p.append(box(40, 320, 180, "pgdata", "named volume", ["survives image rebuilds"], kind="art"))
    p.append(box(255, 320, 180, "./data (host)", "artifact", ["pinned CSV sources"], kind="art"))
    p.append(box(470, 320, 180, "./models (host)", "artifact", ["trained model file"], kind="art"))

    # writers and the reader, routed around the boxes
    p.append('<path class="dep" marker-end="url(#open)" d="M130,149 V222 H255"/>')
    p.append(_label(136, 166, "COPY · bulk insert"))
    p.append('<path class="dep" marker-end="url(#open)" d="M345,149 V196"/>')
    p.append(_label(351, 172, "SQL read / write"))
    p.append('<path class="dep" marker-end="url(#open)" d="M560,149 V240 H435"/>')
    p.append(_label(554, 166, "SELECT only", "end"))

    # where state is kept
    p.append('<path class="dep" marker-end="url(#open)" d="M300,275 V304 H130 V320"/>')
    p.append(_label(136, 316, "stores rows"))
    p.append('<path class="dep" marker-end="url(#open)" d="M90,149 V282 H345 V320"/>')
    p.append(_label(96, 278, "reads validated CSV"))
    p.append('<path class="dep" marker-end="url(#open)" d="M400,149 V175 H452 V352 H470"/>')
    p.append(_label(448, 348, "writes", "end"))
    p.append('<path class="dep" marker-end="url(#open)" d="M520,149 V320"/>')
    p.append(_label(526, 300, "loads model"))

    # the user's browser lives outside the engine
    p.append(box(470, 424, 180, "Chrome / Safari", "device", []))
    p.append('<path class="flow" marker-end="url(#solid)" d="M620,424 V149"/>')
    p.append(_label(614, 420, "HTTP · JSON and HTML", "end"))
    p.append('</svg>')
    return "".join(p)


def class_diagram() -> str:
    """The data model: source tables, the analytical grain, derived outputs."""
    p = [f'<svg class="uml" viewBox="0 0 700 440" role="img" aria-label="UML class diagram of the data model">{DEFS}']
    p.append(box(10, 20, 150, "players", "source table", ["player_id : PK", "name, position", "date_of_birth"]))
    p.append(box(10, 160, 150, "team_details", "source table", ["team_id : PK", "name, league", "squad size"]))
    p.append(box(10, 300, 150, "transfer_history", "source table", ["player_id : FK", "to_team_id : FK", "season, fee"]))
    p.append(box(250, 20, 180, "player_performances", "source table",
                 ["player_id : FK", "team_id : FK", "season, competition_id", "goals, assists, matches", "cards, conceded"]))
    p.append(box(250, 196, 180, "match_results", "source table",
                 ["league_code, season_name", "home_team_id : FK", "away_team_id : FK", "goals, shots, cards"]))
    p.append(box(500, 20, 190, "champagne_index_by_team_season", "derived",
                 ["club × season × competition", "index = (goals+assists)/matches", "delta_next_season"]))
    p.append(box(500, 160, 190, "champagne_model_ml", "derived", ["model_variant", "r2_score, evaluation", "feature_importances"]))
    p.append(box(500, 300, 190, "team_power_ratings", "derived", ["attack_rating", "defense_rating", "home_advantage"]))

    # associations, orthogonal, with multiplicities at the ends
    p.append('<path class="flow" marker-start="url(#dot)" marker-end="url(#dot)" d="M160,60 H250"/>')
    p.append(_label(166, 55, "1")); p.append(_label(244, 55, "0..*", "end"))
    p.append(_label(205, 72, "plays in", "middle"))

    p.append('<path class="flow" marker-start="url(#dot)" marker-end="url(#dot)" d="M160,192 H205 V110 H250"/>')
    p.append(_label(166, 187, "1")); p.append(_label(244, 105, "0..*", "end"))
    p.append(_label(211, 150, "fields"))

    p.append('<path class="flow" marker-start="url(#dot)" marker-end="url(#dot)" d="M160,210 H190 V236 H250"/>')
    p.append(_label(166, 205, "1")); p.append(_label(244, 231, "0..*", "end"))
    p.append(_label(196, 228, "home / away"))

    p.append('<path class="flow" marker-start="url(#dot)" marker-end="url(#dot)" d="M85,300 V232"/>')
    p.append(_label(91, 296, "0..*")); p.append(_label(91, 243, "1"))
    p.append(_label(96, 272, "arrives at"))

    # derivations
    p.append('<path class="dep" marker-end="url(#open)" d="M430,70 H500"/>')
    p.append(_label(465, 64, "aggregate", "middle"))
    p.append('<path class="dep" marker-end="url(#open)" d="M595,128 V160"/>')
    p.append(_label(601, 150, "fit · evaluate"))
    p.append('<path class="dep" marker-end="url(#open)" d="M430,255 H465 V340 H500"/>')
    p.append(_label(471, 332, "Poisson fit"))

    p.append(box(250, 330, 180, "target rule", "constraint", ["two consecutive seasons", "≥30 matches (top five)"], kind="art"))
    p.append('<path class="dep" marker-end="url(#open)" d="M340,330 V300 H470 V112 H500"/>')
    p.append('</svg>')
    return "".join(p)


def sequence_diagram() -> str:
    """Startup: Compose gates every stage on the previous one finishing."""
    lifelines = [("Operator", 48, 76), ("Compose", 150, 76), ("db", 252, 60), ("loader", 352, 70),
                 ("pipeline", 452, 76), ("app", 552, 60), ("browser", 648, 76)]
    p = [f'<svg class="uml" viewBox="0 0 700 440" role="img" aria-label="UML sequence diagram of system startup">{DEFS}']
    for name, x, w in lifelines:
        p.append(f'<rect class="box" x="{x - w / 2}" y="8" width="{w}" height="24" rx="2"/>')
        p.append(f'<text class="n" x="{x}" y="24" text-anchor="middle">{name}</text>')
        p.append(f'<line class="life" x1="{x}" y1="32" x2="{x}" y2="376"/>')

    for x, y, h in [(252, 72, 268), (352, 124, 48), (452, 200, 48), (552, 276, 100)]:
        p.append(f'<rect class="act" x="{x - 5}" y="{y}" width="10" height="{h}"/>')

    msgs = [
        (48, 150, 56, "docker compose up --build", False),
        (150, 252, 80, "1 start, wait for healthcheck", False),
        (252, 150, 104, "healthy", True),
        (150, 352, 128, "2 start loader", False),
        (352, 252, 152, "verify hashes, COPY 5.74M rows", False),
        (352, 150, 176, "exit 0", True),
        (150, 452, 204, "3 start pipeline", False),
        (452, 252, 228, "aggregate, fit model, write results", False),
        (452, 150, 252, "exit 0", True),
        (150, 552, 280, "4 start app", False),
        (552, 252, 304, "SELECT prepared tables", False),
        (648, 552, 332, "GET /api/analysis", False),
        (552, 648, 356, "JSON, a few hundred rows", True),
    ]
    for x1, x2, y, label, dashed in msgs:
        cls, marker = ("dep", "open") if dashed else ("flow", "solid")
        p.append(f'<path class="{cls}" marker-end="url(#{marker})" d="M{x1},{y} H{x2}"/>')
        p.append(_label((x1 + x2) / 2, y - 5, label, "middle"))
    p.append(box(40, 380, 420, "", "", ["A non-zero exit from loader or pipeline stops the sequence:",
                                        "the app never starts on half-loaded data."], kind="art"))
    p.append('</svg>')
    return "".join(p)
