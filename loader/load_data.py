"""Loads the Transfermarkt CSV archive into PostgreSQL.

GET:   the CSVs are already on disk, mounted read-only at /data (see docker-compose.yml
       and the README for how to download the Kaggle archive into data/).
STORE: this script creates the schema (sql/schema.sql) and bulk-loads each CSV with
       Postgres's native COPY, then builds the indices the processing step needs.
"""
import os
import sys
import time

import psycopg2

DATA_DIR = "/data"

# (table_name, path to its CSV under /data) — one folder per table, matching the
# Kaggle archive's own layout, so "copy archive/* into data/" just works.
TABLES = [
    ("player_profiles", "player_profiles/player_profiles.csv"),
    ("player_performances", "player_performances/player_performances.csv"),
    ("player_market_value", "player_market_value/player_market_value.csv"),
    ("player_latest_market_value", "player_latest_market_value/player_latest_market_value.csv"),
    ("player_injuries", "player_injuries/player_injuries.csv"),
    ("player_national_performances", "player_national_performances/player_national_performances.csv"),
    ("player_teammates_played_with", "player_teammates_played_with/player_teammates_played_with.csv"),
    ("team_details", "team_details/team_details.csv"),
    ("team_competitions_seasons", "team_competitions_seasons/team_competitions_seasons.csv"),
    ("team_children", "team_children/team_children.csv"),
    ("transfer_history", "transfer_history/transfer_history.csv"),
]

# Created after the bulk load — building them before COPY would slow every insert down.
INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_pp_team_season_comp "
    "ON player_performances (team_id, season_name, competition_id);",
    "CREATE INDEX IF NOT EXISTS idx_pp_player ON player_performances (player_id);",
    "CREATE INDEX IF NOT EXISTS idx_th_to_team_season ON transfer_history (to_team_id, season_name);",
    "CREATE INDEX IF NOT EXISTS idx_th_player ON transfer_history (player_id);",
    "CREATE INDEX IF NOT EXISTS idx_mv_player ON player_market_value (player_id);",
    "CREATE INDEX IF NOT EXISTS idx_profiles_main_position ON player_profiles (main_position);",
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
            print(f"[loader] db not ready yet (attempt {attempt + 1}/15): {exc}", flush=True)
            time.sleep(2)
    raise SystemExit(f"[loader] could not connect to the database: {last_error}")


def run_schema(conn):
    with open("/sql/schema.sql") as f:
        schema_sql = f.read()
    with conn.cursor() as cur:
        cur.execute(schema_sql)
    conn.commit()
    print("[loader] schema created", flush=True)


def load_table(conn, table, csv_relpath):
    path = os.path.join(DATA_DIR, csv_relpath)
    if not os.path.exists(path):
        raise SystemExit(
            f"[loader] missing {path} — did you copy the Kaggle archive into data/? See README."
        )
    with conn.cursor() as cur:
        cur.execute(f"TRUNCATE TABLE {table};")
        with open(path, "r", encoding="utf-8") as f:
            cur.copy_expert(
                f"COPY {table} FROM STDIN WITH (FORMAT csv, HEADER true, NULL '')",
                f,
            )
    conn.commit()


def main():
    conn = connect()
    run_schema(conn)

    total_rows = 0
    t0 = time.perf_counter()
    for table, csv_relpath in TABLES:
        t_table = time.perf_counter()
        load_table(conn, table, csv_relpath)
        with conn.cursor() as cur:
            cur.execute(f"SELECT COUNT(*) FROM {table};")
            rows = cur.fetchone()[0]
        total_rows += rows
        print(
            f"[loader] {table}: {rows:,} rows in {time.perf_counter() - t_table:.1f}s",
            flush=True,
        )
    load_elapsed = time.perf_counter() - t0

    t_idx = time.perf_counter()
    with conn.cursor() as cur:
        for statement in INDEXES:
            cur.execute(statement)
    conn.commit()
    index_elapsed = time.perf_counter() - t_idx

    print(
        f"[loader] done: {total_rows:,} rows across {len(TABLES)} tables, "
        f"load={load_elapsed:.1f}s index={index_elapsed:.1f}s",
        flush=True,
    )
    conn.close()


if __name__ == "__main__":
    main()
