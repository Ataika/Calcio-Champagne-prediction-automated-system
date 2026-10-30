"""PROCESS step: builds the Champagne Index, joins it with transfer spend, fits a
simple linear trend, and writes everything to a `champagne_results` table the
dashboard reads from.

Champagne Index = (goals + assists) / matches for a team, in one competition, in one
season — see sql/champagne_queries.sql for exactly how it's computed from
player_performances.

Prediction = one global linear fit of "change in index next season" against
"money spent on incoming transfers this season" (scipy.stats.linregress). This is a
trend line, not a trained ML model — it's meant to answer "does spending predict a
rise in attacking output", not to be a production forecaster.
"""
import os
import re
import time

import pandas as pd
import psycopg2
from psycopg2.extras import execute_values
from scipy import stats

RESULT_COLUMNS = [
    "team_id", "team_name", "season_name", "season_key", "competition_id",
    "competition_name", "matches", "total_goals", "total_assists",
    "champagne_index", "total_spend", "attacking_spend", "delta_index",
    "predicted_next_index", "is_latest_season",
]


def connect():
    last_error = None
    for attempt in range(15):
        try:
            return psycopg2.connect(
                host=os.environ.get("POSTGRES_HOST", "db"),
                port=os.environ.get("POSTGRES_PORT", "5432"),
                dbname=os.environ["POSTGRES_DB"],
                user=os.environ["POSTGRES_USER"],
                password=os.environ["POSTGRES_PASSWORD"],
            )
        except psycopg2.OperationalError as exc:
            last_error = exc
            print(f"[pipeline] db not ready yet (attempt {attempt + 1}/15): {exc}", flush=True)
            time.sleep(2)
    raise SystemExit(f"[pipeline] could not connect to the database: {last_error}")


def season_sort_key(season_name):
    """'08/09' -> 2008, '99/00' -> 1999, '23/24' -> 2023. None if unparseable."""
    match = re.match(r"(\d{2})/(\d{2})", str(season_name))
    if not match:
        return None
    start_yy = int(match.group(1))
    return 2000 + start_yy if start_yy < 50 else 1900 + start_yy


def build_views(conn):
    with open("/sql/champagne_queries.sql") as f:
        views_sql = f.read()
    with conn.cursor() as cur:
        cur.execute(views_sql)
    conn.commit()


def compute(conn):
    index_df = pd.read_sql("SELECT * FROM champagne_index_by_team_season", conn)
    spend_df = pd.read_sql("SELECT * FROM transfer_spend_by_team_season", conn)

    index_df["season_key"] = index_df["season_name"].apply(season_sort_key)
    index_df = index_df.dropna(subset=["season_key", "champagne_index"]).copy()
    index_df["season_key"] = index_df["season_key"].astype(int)

    merged = index_df.merge(spend_df, on=["team_id", "season_name"], how="left")
    merged[["total_spend", "attacking_spend"]] = merged[["total_spend", "attacking_spend"]].fillna(0)

    merged = merged.sort_values(["team_id", "competition_id", "season_key"])
    group = merged.groupby(["team_id", "competition_id"])
    merged["next_champagne_index"] = group["champagne_index"].shift(-1)
    merged["delta_index"] = merged["next_champagne_index"] - merged["champagne_index"]
    merged["is_latest_season"] = group["season_key"].transform("max") == merged["season_key"]

    # Fit the trend only on rows with a real next season and a reasonable sample of
    # matches (drops teams that only appear for a one-off cup tie).
    train = merged.dropna(subset=["delta_index"])
    train = train[train["matches"].fillna(0) >= 5]

    if len(train) >= 20:
        slope, intercept, r_value, p_value, _std_err = stats.linregress(
            train["total_spend"].astype(float), train["delta_index"].astype(float)
        )
    else:
        slope, intercept, r_value, p_value = 0.0, 0.0, 0.0, 1.0

    merged["predicted_next_index"] = (
        merged["champagne_index"].astype(float)
        + slope * merged["total_spend"].astype(float)
        + intercept
    ).round(2)

    return merged, (float(slope), float(intercept), float(r_value), float(p_value), len(train))


def write_results(conn, merged, model_stats):
    with conn.cursor() as cur:
        cur.execute("DROP TABLE IF EXISTS champagne_results;")
        cur.execute("""
            CREATE TABLE champagne_results (
                team_id INTEGER,
                team_name TEXT,
                season_name TEXT,
                season_key INTEGER,
                competition_id TEXT,
                competition_name TEXT,
                matches INTEGER,
                total_goals NUMERIC,
                total_assists INTEGER,
                champagne_index NUMERIC,
                total_spend NUMERIC,
                attacking_spend NUMERIC,
                delta_index NUMERIC,
                predicted_next_index NUMERIC,
                is_latest_season BOOLEAN
            );
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS champagne_model (
                slope NUMERIC,
                intercept NUMERIC,
                r_value NUMERIC,
                p_value NUMERIC,
                n_observations INTEGER,
                computed_at TIMESTAMP DEFAULT now()
            );
        """)
    conn.commit()

    frame = merged[RESULT_COLUMNS].astype(object).where(pd.notnull(merged[RESULT_COLUMNS]), None)
    records = frame.values.tolist()

    with conn.cursor() as cur:
        execute_values(
            cur,
            f"INSERT INTO champagne_results ({', '.join(RESULT_COLUMNS)}) VALUES %s",
            records,
        )
        cur.execute("DELETE FROM champagne_model;")
        slope, intercept, r_value, p_value, n = model_stats
        cur.execute(
            "INSERT INTO champagne_model (slope, intercept, r_value, p_value, n_observations) "
            "VALUES (%s, %s, %s, %s, %s)",
            (slope, intercept, r_value, p_value, n),
        )
        cur.execute(
            "CREATE INDEX IF NOT EXISTS idx_cr_team_season ON champagne_results (team_id, season_name);"
        )
    conn.commit()


def main():
    conn = connect()
    build_views(conn)
    merged, model_stats = compute(conn)
    write_results(conn, merged, model_stats)
    slope, intercept, r_value, p_value, n = model_stats
    print(
        f"[pipeline] wrote {len(merged):,} rows to champagne_results; "
        f"trend: slope={slope:.6g} intercept={intercept:.3f} r={r_value:.3f} n={n}",
        flush=True,
    )
    conn.close()


if __name__ == "__main__":
    main()
