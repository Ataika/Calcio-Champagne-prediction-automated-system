"""MEASURE step (required #5): query time with vs. without an index, database size
on disk, and a 25% / 50% / 100% data-growth test on the biggest table
(player_performances, ~150 MB / 1.9M rows) — does time double when data doubles?

Run with: docker compose run measure
Writes:   measure/results/results.json (bind-mounted into the app container too, so
          the dashboard's Performance tab reads it live).

Peak memory per container isn't measured here — reading another container's memory
from inside this one needs the Docker socket mounted in, which is more privilege
than this benchmark needs. Run `docker stats` once while `docker compose up` is
running instead (see README) and fill the two numbers into results.json or the
README table by hand.
"""
import io
import json
import os
import pathlib
import platform
import time

import psycopg2

DATA_DIR = "/data"
RESULTS_PATH = pathlib.Path("/results/results.json")
BIG_TABLE_CSV = os.path.join(DATA_DIR, "player_performances/player_performances.csv")

CHAMPAGNE_QUERY = """
    SELECT team_id, team_name, season_name, competition_id,
           (SUM(goals) + SUM(assists)) / NULLIF(MAX(nb_in_group), 0) AS champagne_index
    FROM {table}
    GROUP BY team_id, team_name, season_name, competition_id;
"""

# The dashboard's "Team trend" tab filters champagne_results by one team_id — that's
# the lookup an index on (team_id, season_name, competition_id) actually speeds up.
# The full GROUP BY above scans the whole table either way, so it wouldn't show the
# difference (the index-vs-no-index comparison below uses this instead).
TEAM_LOOKUP_QUERY = """
    SELECT team_id, team_name, season_name, competition_id,
           (SUM(goals) + SUM(assists)) / NULLIF(MAX(nb_in_group), 0) AS champagne_index
    FROM player_performances
    WHERE team_id = %s
    GROUP BY team_id, team_name, season_name, competition_id;
"""
N_LOOKUP_TEAMS = 300  # repeat the lookup for this many distinct teams to get a stable timing


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
            print(f"[measure] db not ready yet (attempt {attempt + 1}/15): {exc}", flush=True)
            time.sleep(2)
    raise SystemExit(f"[measure] could not connect to the database: {last_error}")


def time_query(conn, table):
    t0 = time.perf_counter()
    with conn.cursor() as cur:
        cur.execute(CHAMPAGNE_QUERY.format(table=table))
        cur.fetchall()
    return time.perf_counter() - t0


def sample_team_ids(conn, n):
    with conn.cursor() as cur:
        cur.execute(
            "SELECT team_id FROM (SELECT DISTINCT team_id FROM player_performances) t "
            "ORDER BY random() LIMIT %s;",
            (n,),
        )
        return [row[0] for row in cur.fetchall()]


def time_team_lookups(conn, team_ids):
    t0 = time.perf_counter()
    with conn.cursor() as cur:
        for team_id in team_ids:
            cur.execute(TEAM_LOOKUP_QUERY, (team_id,))
            cur.fetchall()
    return time.perf_counter() - t0


def query_with_without_index(conn):
    team_ids = sample_team_ids(conn, N_LOOKUP_TEAMS)

    with conn.cursor() as cur:
        cur.execute("DROP INDEX IF EXISTS idx_pp_team_season_comp;")
    conn.commit()
    without = time_team_lookups(conn, team_ids)

    with conn.cursor() as cur:
        cur.execute(
            "CREATE INDEX IF NOT EXISTS idx_pp_team_season_comp "
            "ON player_performances (team_id, season_name, competition_id);"
        )
    conn.commit()
    with_index = time_team_lookups(conn, team_ids)
    return without, with_index


def db_size_mb(conn):
    with conn.cursor() as cur:
        cur.execute("SELECT pg_database_size(current_database());")
        size_bytes = cur.fetchone()[0]
    return round(size_bytes / (1024 * 1024), 1)


def count_csv_rows(path):
    with open(path, "r", encoding="utf-8") as f:
        return sum(1 for _ in f) - 1  # minus header


def growth_test(conn):
    total_rows = count_csv_rows(BIG_TABLE_CSV)
    results = []

    with conn.cursor() as cur:
        cur.execute(
            "CREATE TABLE IF NOT EXISTS player_performances_bench "
            "(LIKE player_performances INCLUDING ALL);"
        )
    conn.commit()

    for pct in (0.25, 0.5, 1.0):
        n_rows = int(total_rows * pct)
        with conn.cursor() as cur:
            cur.execute("TRUNCATE player_performances_bench;")
        conn.commit()

        t0 = time.perf_counter()
        with open(BIG_TABLE_CSV, "r", encoding="utf-8") as f:
            buf = io.StringIO()
            buf.write(f.readline())  # header
            for i, line in enumerate(f):
                if i >= n_rows:
                    break
                buf.write(line)
        buf.seek(0)
        with conn.cursor() as cur:
            cur.copy_expert(
                "COPY player_performances_bench FROM STDIN WITH (FORMAT csv, HEADER true, NULL '')",
                buf,
            )
        conn.commit()
        load_seconds = time.perf_counter() - t0

        query_seconds = time_query(conn, "player_performances_bench")
        results.append(
            {
                "pct": int(pct * 100),
                "rows": n_rows,
                "load_seconds": round(load_seconds, 2),
                "query_seconds": round(query_seconds, 4),
            }
        )
        print(
            f"[measure] growth {int(pct * 100)}%: {n_rows:,} rows "
            f"load={load_seconds:.2f}s query={query_seconds:.4f}s",
            flush=True,
        )

    with conn.cursor() as cur:
        cur.execute("DROP TABLE IF EXISTS player_performances_bench;")
    conn.commit()
    return results


def main():
    conn = connect()

    without_idx, with_idx = query_with_without_index(conn)
    disk_mb = db_size_mb(conn)
    growth = growth_test(conn)

    data = {
        "query_without_index_seconds": round(without_idx, 4),
        "query_with_index_seconds": round(with_idx, 4),
        "db_size_mb": disk_mb,
        "growth_test": growth,
        "machine": platform.platform(),
        "peak_memory_mb": {"db": None, "loader": None, "pipeline": None, "app": None},
        "note": (
            "peak_memory_mb is filled in by hand from `docker stats` while "
            "`docker compose up` runs — see README."
        ),
    }

    RESULTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    RESULTS_PATH.write_text(json.dumps(data, indent=2))
    print(f"[measure] wrote {RESULTS_PATH}", flush=True)
    print(
        f"[measure] without index={without_idx:.4f}s with index={with_idx:.4f}s "
        f"({without_idx / with_idx if with_idx else float('inf'):.1f}x faster) disk={disk_mb} MB",
        flush=True,
    )
    conn.close()


if __name__ == "__main__":
    main()
