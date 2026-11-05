"""Loads the Transfermarkt CSV archive into PostgreSQL.

GET:   missing primary CSVs are fetched from the pinned public manifest into /data.
STORE: this script creates the schema (sql/schema.sql) and bulk-loads each CSV with
       Postgres's native COPY, then builds the indices the processing step needs.
"""
import csv
import os
import time
import json
import re
from pathlib import Path
from datetime import datetime, timezone

try:
    from .get_data import ensure_dataset
except ImportError:
    from get_data import ensure_dataset

import psycopg2
from psycopg2.extras import execute_values

DATA_DIR = "/data"
MATCHES_DIR = os.path.join(DATA_DIR, "matches")

# football-data.co.uk league code -> what shows up as competition_id in champagne_results.
# Only used for logging; match_results itself keys off team_id, not competition_id.
MATCH_LEAGUES = ["E0", "SP1", "I1", "D1", "F1"]

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


def run_team_name_map(conn):
    with open("/sql/team_name_map.sql") as f:
        with conn.cursor() as cur:
            cur.execute(f.read())
    conn.commit()
    print("[loader] team_name_map seeded", flush=True)


def load_table(conn, table, csv_relpath):
    path = os.path.join(DATA_DIR, csv_relpath)
    if not os.path.exists(path):
        raise SystemExit(
            f"[loader] missing {path} — run get_data.py or check the source manifest. See README."
        )
    with conn.cursor() as cur:
        cur.execute(f"TRUNCATE TABLE {table};")
        with open(path, "r", encoding="utf-8") as f:
            cur.copy_expert(
                f"COPY {table} FROM STDIN WITH (FORMAT csv, HEADER true, NULL '')",
                f,
            )
    conn.commit()


def season_folder_to_name(folder_season):
    """'2425' -> '24/25', matching champagne_results.season_name."""
    if not re.fullmatch(r"[0-9]{4}", folder_season) or (int(folder_season[:2]) + 1) % 100 != int(folder_season[2:]):
        raise ValueError("Match filenames must use consecutive season years, for example 2425.csv.")
    return f"{folder_season[:2]}/{folder_season[2:]}"


def parse_match_result(row):
    """Return a completed, internally consistent score; unplayed fixtures return None."""
    result = (row.get("FTR") or "").strip()
    if not result:
        return None
    if result not in {"H", "D", "A"}:
        raise ValueError("Unknown full-time result.")
    match_date = None
    for date_format in ("%d/%m/%Y", "%d/%m/%y"):
        try:
            match_date = datetime.strptime((row.get("Date") or "").strip(), date_format).date()
            break
        except ValueError:
            continue
    if match_date is None:
        raise ValueError("A completed match must have a valid date.")
    try:
        home_goals, away_goals = int(row.get("FTHG", "")), int(row.get("FTAG", ""))
    except (ValueError, TypeError) as error:
        raise ValueError("Completed scores must be whole numbers.") from error
    if home_goals < 0 or away_goals < 0:
        raise ValueError("Goals cannot be negative.")
    expected = "H" if home_goals > away_goals else "A" if home_goals < away_goals else "D"
    if result != expected:
        raise ValueError("Full-time result contradicts the score.")
    return match_date, home_goals, away_goals, result


def load_matches(conn):
    """Optional enrichment (requirement: 'where the system got richer than the
    minimum'). If data/matches/ wasn't downloaded, skip quietly — the rest of the
    system works fine without it, this only unlocks the 'Champagne vs. league
    position' comparison in the dashboard."""
    if not os.path.isdir(MATCHES_DIR):
        print(f"[loader] {MATCHES_DIR} not found, clearing stored match enrichment (optional)", flush=True)

    with conn.cursor() as cur:
        cur.execute("SELECT league_code, source_name, team_id FROM team_name_map;")
        name_to_id = {(lc, name): tid for lc, name, tid in cur.fetchall()}

    rows = []
    unmapped = set()
    invalid = 0
    fixtures = {}
    duplicates = 0
    for league_code in MATCH_LEAGUES:
        league_dir = os.path.join(MATCHES_DIR, league_code)
        if not os.path.isdir(league_dir):
            continue
        for filename in sorted(os.listdir(league_dir)):
            if not filename.endswith(".csv"):
                continue
            try:
                season_name = season_folder_to_name(filename.removesuffix(".csv"))
            except ValueError:
                print(f"[loader] skipping unexpected match filename: {league_code}/{filename}", flush=True)
                continue
            path = os.path.join(league_dir, filename)
            with open(path, newline="", encoding="utf-8-sig") as f:
                for row in csv.DictReader(f):
                    home = row.get("HomeTeam", "").strip()
                    away = row.get("AwayTeam", "").strip()
                    home_id = name_to_id.get((league_code, home))
                    away_id = name_to_id.get((league_code, away))
                    if home_id is None:
                        unmapped.add((league_code, home))
                        continue
                    if away_id is None:
                        unmapped.add((league_code, away))
                        continue
                    try:
                        parsed = parse_match_result(row)
                        if home_id == away_id:
                            raise ValueError("A club cannot play itself.")
                    except ValueError:
                        invalid += 1
                        continue
                    if parsed is None:
                        continue
                    match_date, home_goals, away_goals, result = parsed
                    fixture = (league_code, season_name, match_date, home_id, away_id)
                    score = (home_goals, away_goals, result)
                    if fixture in fixtures:
                        if fixtures[fixture] != score:
                            raise ValueError(f"Conflicting scores for {fixture}; existing match data was not replaced.")
                        duplicates += 1
                        continue
                    fixtures[fixture] = score
                    rows.append((
                        league_code, season_name, match_date, home_id, away_id,
                        home_goals, away_goals, result, row.get("Referee") or None,
                    ))

    if unmapped:
        print(f"[loader] WARNING: {len(unmapped)} unmapped team names skipped: "
              f"{sorted(unmapped)[:10]}", flush=True)
    if invalid:
        print(f"[loader] WARNING: {invalid} invalid completed-match rows skipped", flush=True)
    if duplicates:
        print(f"[loader] {duplicates} duplicate match rows ignored", flush=True)

    with conn.cursor() as cur:
        cur.execute("TRUNCATE TABLE match_results;")
        if rows:
            execute_values(
                cur,
                "INSERT INTO match_results "
                "(league_code, season_name, match_date, home_team_id, away_team_id, "
                " home_goals, away_goals, result, referee) VALUES %s",
                rows,
            )
        cur.execute(
            "CREATE INDEX IF NOT EXISTS idx_mr_season "
            "ON match_results (league_code, season_name);"
        )
        cur.execute("CREATE INDEX IF NOT EXISTS idx_mr_home ON match_results (home_team_id);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_mr_away ON match_results (away_team_id);")
    conn.commit()
    return len(rows)


def main():
    started = time.perf_counter()
    ensure_dataset(DATA_DIR)
    download_elapsed = time.perf_counter() - started
    conn = connect()
    run_schema(conn)
    run_team_name_map(conn)

    total_rows = 0
    table_times = []
    t0 = time.perf_counter()
    for table, csv_relpath in TABLES:
        t_table = time.perf_counter()
        load_table(conn, table, csv_relpath)
        with conn.cursor() as cur:
            cur.execute(f"SELECT COUNT(*) FROM {table};")
            rows = cur.fetchone()[0]
        total_rows += rows
        table_times.append({"table": table, "rows": rows, "seconds": time.perf_counter() - t_table})
        print(
            f"[loader] {table}: {rows:,} rows in {time.perf_counter() - t_table:.1f}s",
            flush=True,
        )
    load_elapsed = time.perf_counter() - t0

    t_idx = time.perf_counter()
    with conn.cursor() as cur:
        for statement in INDEXES:
            cur.execute(statement)
        # COPY/TRUNCATE changes distributions; do not wait for autovacuum before
        # the immediately following aggregation pipeline chooses its plans.
        cur.execute("ANALYZE;")
    conn.commit()
    index_elapsed = time.perf_counter() - t_idx

    t_matches = time.perf_counter()
    n_matches = load_matches(conn)
    matches_elapsed = time.perf_counter() - t_matches
    if n_matches:
        print(
            f"[loader] match_results: {n_matches:,} rows in "
            f"{time.perf_counter() - t_matches:.1f}s",
            flush=True,
        )

    print(
        f"[loader] done: {total_rows:,} rows across {len(TABLES)} tables, "
        f"load={load_elapsed:.1f}s index={index_elapsed:.1f}s",
        flush=True,
    )
    conn.close()
    results = Path(os.getenv("RESULTS_DIR", "/results"))
    if results.is_dir():
        payload = {"measured_at": datetime.now(timezone.utc).isoformat(), "download_seconds": download_elapsed,
                   "load_seconds": load_elapsed, "index_seconds": index_elapsed,
                   "matches_seconds": matches_elapsed, "full_seconds": time.perf_counter() - started,
                   "tables": table_times, "total_rows": total_rows}
        (results / "loader.json").write_text(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
