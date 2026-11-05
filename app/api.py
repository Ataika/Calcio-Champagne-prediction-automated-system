"""Same-origin HTTP API and editorial frontend. Pipeline outputs are read-only.

Run inside Compose, or: uvicorn app.api:app --port 8502
No raw player table is exposed; every chart has a bounded league/season scope.
"""
from __future__ import annotations

import csv
import io
import json
import logging
import math
import os
import pathlib
import threading
from contextlib import contextmanager
from datetime import date, datetime
from decimal import Decimal
from functools import lru_cache

import joblib
import pandas as pd
import psycopg2
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from psycopg2.extras import RealDictCursor
from psycopg2.pool import ThreadedConnectionPool
from pydantic import BaseModel, ConfigDict, Field, model_validator
from scipy import stats

ROOT = pathlib.Path(__file__).resolve().parent
MODEL_PATH = pathlib.Path(os.getenv("LAB_MODEL_PATH", "/models/champagne_rf_model.joblib"))
RESULTS_PATH = pathlib.Path(os.getenv("RESULTS_PATH", "/results/results.json"))
LEAGUES = {
    "IT1": {"name": "Serie A", "country": "Italy", "code": "I1"},
    "GB1": {"name": "Premier League", "country": "England", "code": "E0"},
    "ES1": {"name": "LaLiga", "country": "Spain", "code": "SP1"},
    "L1": {"name": "Bundesliga", "country": "Germany", "code": "D1"},
    "FR1": {"name": "Ligue 1", "country": "France", "code": "F1"},
}
FEATURES = ["champagne_index", "total_spend", "attacking_spend", "squad_avg_age", "market_value_change"]
app = FastAPI(title="Calcio Champagne", version="2.0.0", docs_url=None, redoc_url=None,
              openapi_url="/api/openapi.json")
log = logging.getLogger("calcio")


def clean(value):
    """Strict JSON: missing numeric values are null, never NaN or Infinity."""
    if isinstance(value, dict):
        return {k: clean(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [clean(v) for v in value]
    if isinstance(value, Decimal):
        value = float(value)
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return value


@lru_cache(maxsize=1)
def pool():
    return ThreadedConnectionPool(
        1, 8, host=os.getenv("POSTGRES_HOST", "db"), port=os.getenv("POSTGRES_PORT", "5432"),
        dbname=os.environ["POSTGRES_DB"], user=os.environ["POSTGRES_USER"],
        password=os.environ["POSTGRES_PASSWORD"], connect_timeout=5,
        options="-c default_transaction_read_only=on -c statement_timeout=15000",
    )


@contextmanager
def connection():
    conn = pool().getconn()
    try:
        yield conn
    finally:
        conn.rollback()
        pool().putconn(conn)


def read(sql, params=()):
    with connection() as conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(sql, params)
        return clean(cur.fetchall())


def exists(table):
    return bool(read("SELECT to_regclass(%s) AS name", ("public." + table,))[0]["name"])


def latest(table):
    # Callers supply only internal constant names, never request parameters.
    if table not in {"champagne_model", "champagne_model_ml", "champagne_vs_position_model", "transfer_fee_model"}:
        raise ValueError("Unknown model table")
    if not exists(table):
        return None
    rows = read(f"SELECT * FROM {table} ORDER BY computed_at DESC LIMIT 1")
    if not rows:
        return None
    row = rows[0]
    for key in ("feature_importances", "evaluation"):
        if isinstance(row.get(key), str):
            row[key] = json.loads(row[key])
    return row


def scope(competition, season):
    if competition not in LEAGUES:
        raise HTTPException(422, "Choose one of the five supported leagues.")
    import re
    match = re.fullmatch(r"(\d{2})/(\d{2})", season)
    if not match or (int(match[1]) + 1) % 100 != int(match[2]):
        raise HTTPException(422, "Season must be consecutive years, for example 24/25.")


def regression(rows, x, y):
    pairs = [(r[x], r[y]) for r in rows if r.get(x) is not None and r.get(y) is not None]
    if len(pairs) < 3 or len({p[0] for p in pairs}) < 2 or len({p[1] for p in pairs}) < 2:
        return {"n": len(pairs), "r": None, "slope": None, "intercept": None, "p": None}
    fit = stats.linregress(*zip(*pairs))
    return clean({"n": len(pairs), "r": fit.rvalue, "p": fit.pvalue,
                  "slope": fit.slope, "intercept": fit.intercept})


@app.middleware("http")
async def response_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data:; connect-src 'self'; font-src 'self'; object-src 'none'; "
        "base-uri 'self'; frame-ancestors 'none'"
    )
    if request.url.path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-store"
    return response


@app.exception_handler(psycopg2.Error)
async def database_error(request, exc):
    log.exception("Database request failed", exc_info=exc)
    return JSONResponse(status_code=503, content={"detail": "Data is temporarily unavailable. Please retry."})


@app.get("/api/health")
def health():
    read("SELECT 1")
    ready = exists("champagne_results")
    return JSONResponse(status_code=200 if ready else 503, content={"ready": ready, "model_available": MODEL_PATH.exists()})


@app.get("/api/meta")
def metadata():
    seasons = read("""
        SELECT competition_id, season_name, season_key, COUNT(*) AS clubs,
               MIN(matches) AS min_matches, MAX(matches) AS max_matches,
               ROUND(AVG(matches), 1) AS average_matches
        FROM champagne_results WHERE competition_id = ANY(%s)
        GROUP BY competition_id, season_name, season_key ORDER BY season_key DESC
    """, (list(LEAGUES),))
    leagues = []
    for key, info in LEAGUES.items():
        available = [dict(s, complete=s["average_matches"] >= 30) for s in seasons if s["competition_id"] == key]
        complete = [s for s in available if s["complete"]]
        leagues.append(dict(info, id=key, seasons=available, default_season=complete[0]["season_name"] if complete else None))
    return {"leagues": leagues, "default_competition": "IT1", "model": latest("champagne_model_ml")}


def season_rows(competition, season, min_matches=15):
    return read("""
        SELECT cr.*, ls.position, ls.points, ls.played, ls.wins, ls.draws, ls.losses,
               ls.goals_for, ls.goals_against, ls.goal_diff,
               prev.champagne_index AS previous_index,
               cr.champagne_index - prev.champagne_index AS change_from_previous
        FROM champagne_results cr
        LEFT JOIN league_standings ls ON ls.team_id=cr.team_id
            AND ls.competition_id=cr.competition_id AND ls.season_name=cr.season_name
        LEFT JOIN champagne_results prev ON prev.team_id=cr.team_id
            AND prev.competition_id=cr.competition_id AND prev.season_key=cr.season_key-1
        WHERE cr.competition_id=%s AND cr.season_name=%s AND cr.matches >= %s
        ORDER BY cr.champagne_index DESC, cr.team_name
    """, (competition, season, min_matches))


@app.get("/api/season")
def season_data(competition: str = "IT1", season: str = "24/25", min_matches: int = Query(15, ge=5, le=38)):
    scope(competition, season)
    rows = season_rows(competition, season, min_matches)
    # Correlation with final position uses only comparable season snapshots.
    comparable = [r for r in rows if r.get("played", 0) and r["played"] >= 30 and r["matches"] >= 0.8 * r["played"]]
    return {"rows": rows, "spend_correlation": regression(rows, "total_spend", "champagne_index"),
            "position_correlation": regression(comparable, "champagne_index", "position"),
            "min_matches": min_matches, "league": LEAGUES[competition]}


@app.get("/api/analysis")
def analysis(competition: str = "IT1", season: str = "24/25"):
    scope(competition, season)
    key = 2000 + int(season[:2]) if int(season[:2]) < 50 else 1900 + int(season[:2])
    rows = read("""
        SELECT team_id, team_name, season_name, season_key, total_spend, attacking_spend,
               champagne_index, delta_index, matches
        FROM champagne_results WHERE competition_id=%s AND season_key BETWEEN %s AND %s
            AND delta_index IS NOT NULL AND matches>=30
        ORDER BY season_key, team_name
    """, (competition, key - 4, key))
    return {"rows": rows, "correlation": regression(rows, "total_spend", "delta_index"),
            "from_year": key - 4, "to_year": key, "global_model": latest("champagne_model")}


@app.get("/api/clubs/{team_id}")
def club(team_id: int, competition: str = "IT1", season: str = "24/25"):
    scope(competition, season)
    if team_id <= 0:
        raise HTTPException(422, "Invalid club.")
    rows = read("""
        SELECT cr.*, ls.position, ls.points FROM champagne_results cr
        LEFT JOIN league_standings ls ON cr.team_id=ls.team_id
            AND cr.competition_id=ls.competition_id AND cr.season_name=ls.season_name
        WHERE cr.team_id=%s AND cr.competition_id=%s ORDER BY cr.season_key
    """, (team_id, competition))
    if not rows:
        raise HTTPException(404, "This club has no data in the selected league.")
    current = next((r for r in rows if r["season_name"] == season), None)
    clusters = read("SELECT * FROM club_style_clusters WHERE team_id=%s AND season_name=%s AND competition_name=%s",
                    (team_id, season, LEAGUES[competition]["name"])) if exists("club_style_clusters") else []
    return {"team_name": rows[-1]["team_name"], "history": rows, "current": current,
            "style": clusters[0] if clusters else None}


_model_lock = threading.Lock()
_model_cache = {"stamp": None, "bundle": None}


def lab_model():
    if not MODEL_PATH.exists():
        raise HTTPException(503, "The scenario model is not available yet. Run the pipeline first.")
    stamp = MODEL_PATH.stat().st_mtime_ns
    with _model_lock:
        if _model_cache["stamp"] != stamp:
            _model_cache.update(stamp=stamp, bundle=joblib.load(MODEL_PATH))
    return _model_cache["bundle"]


@app.get("/api/lab/config")
def lab_config(team_id: int = Query(..., gt=0), competition: str = "IT1", season: str = "24/25"):
    scope(competition, season)
    bundle = lab_model()
    if not exists("lab_team_features"):
        raise HTTPException(503, "Club scenario inputs have not been computed. Run the updated pipeline.")
    rows = read("""SELECT f.*, cr.team_name FROM lab_team_features f
                   JOIN champagne_results cr USING (team_id, competition_id, season_name)
                   WHERE f.team_id=%s AND f.competition_id=%s AND f.season_name=%s""",
                (team_id, competition, season))
    if not rows:
        raise HTTPException(404, "No scenario inputs for this club-season.")
    row = rows[0]
    missing = [f for f in FEATURES if row[f] is None]
    return {"features": {f: row[f] for f in FEATURES}, "missing": missing,
            "ranges": bundle["feature_ranges"], "evaluation": bundle.get("evaluation"), "team_name": row["team_name"]}


class Scenario(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    champagne_index: float = Field(ge=0, le=40)
    total_spend: float = Field(ge=0, le=2_000_000_000)
    attacking_spend: float = Field(ge=0, le=2_000_000_000)
    squad_avg_age: float = Field(ge=14, le=45)
    market_value_change: float = Field(ge=-1_000_000_000, le=1_000_000_000)

    @model_validator(mode="after")
    def attacking_budget(self):
        if self.attacking_spend > self.total_spend:
            raise ValueError("Attacking spend cannot exceed total spend.")
        return self


@app.post("/api/lab/predict")
def predict(scenario: Scenario):
    bundle = lab_model()
    values = scenario.model_dump()
    frame = pd.DataFrame([values], columns=bundle["feature_cols"])
    delta = float(bundle["model"].predict(frame)[0])
    outside = [f for f in FEATURES if values[f] < bundle["feature_ranges"][f]["min"] or values[f] > bundle["feature_ranges"][f]["max"]]
    return clean({"delta": delta, "next_index": values["champagne_index"] + delta,
                  "outside_training_range": outside, "evaluation": bundle.get("evaluation")})


@app.get("/api/export")
def export(competition: str = "IT1", season: str = "24/25"):
    scope(competition, season)
    rows = season_rows(competition, season)
    cols = ["team_name", "season_name", "competition_name", "matches", "champagne_index", "total_spend", "attacking_spend", "position", "points"]
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=cols, extrasaction="ignore")
    writer.writeheader()
    for row in rows:
        # Spreadsheet formula injection protection for externally supplied names.
        writer.writerow({k: "'" + v if isinstance(v, str) and v.startswith(("=", "+", "-", "@")) else v for k, v in row.items()})
    return Response(output.getvalue(), media_type="text/csv", headers={
        "Content-Disposition": f'attachment; filename="calcio-{competition}-{season.replace("/", "-")}.csv"'})


@app.get("/api/project")
def project():
    counts = read("""SELECT relname AS name, n_live_tup AS rows FROM pg_stat_user_tables
        WHERE relname=ANY(%s) ORDER BY n_live_tup DESC""", ([
        "player_profiles", "player_performances", "player_market_value", "player_latest_market_value",
        "player_injuries", "player_national_performances", "player_teammates_played_with", "team_details",
        "team_competitions_seasons", "team_children", "transfer_history", "match_results"],))
    coverage = read("SELECT COUNT(*) AS team_seasons, COUNT(DISTINCT team_id) AS clubs, MIN(season_key) AS from_year, MAX(season_key) AS to_year FROM champagne_results")[0]
    benchmark = json.loads(RESULTS_PATH.read_text()) if RESULTS_PATH.exists() else None
    model = latest("champagne_model_ml")
    return clean({"tables": counts, "coverage": coverage, "benchmark": benchmark,
                  "linear": latest("champagne_model"), "ml": model,
                  "position": latest("champagne_vs_position_model"),
                  "transfer": latest("transfer_fee_model"),
                  "course_source_verified": True})


app.mount("/static", StaticFiles(directory=ROOT / "static"), name="static")


@app.get("/api/docs", include_in_schema=False)
def api_docs():
    return FileResponse(ROOT / "static" / "api-docs.html")


@app.get("/", include_in_schema=False)
def index():
    return FileResponse(ROOT / "static" / "index.html", headers={"Cache-Control": "no-cache"})
