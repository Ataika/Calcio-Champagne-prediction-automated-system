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
from datetime import datetime, timezone
from statistics import mean

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
N_LOOKUP_TEAMS = 300
REPEATS = 3


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
                application_name="calcio_measure",
                options="-c work_mem=64MB -c jit=off",
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
            "ORDER BY md5(team_id::text || '42') LIMIT %s;",
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
    without, with_index = [], []
    try:
        for _ in range(REPEATS):
            with conn.cursor() as cur:
                cur.execute("DROP INDEX IF EXISTS idx_pp_team_season_comp;")
            conn.commit()
            without.append(time_team_lookups(conn, team_ids))
            with conn.cursor() as cur:
                cur.execute("CREATE INDEX idx_pp_team_season_comp ON player_performances (team_id, season_name, competition_id);")
            conn.commit()
            with_index.append(time_team_lookups(conn, team_ids))
    finally:
        # A failed benchmark must not leave the application without its index.
        conn.rollback()
        with conn.cursor() as cur:
            cur.execute("CREATE INDEX IF NOT EXISTS idx_pp_team_season_comp ON player_performances (team_id, season_name, competition_id);")
        conn.commit()
    return mean(without), mean(with_index), {"without_index": without, "with_index": with_index}


def db_size_mb(conn):
    with conn.cursor() as cur:
        cur.execute("SELECT pg_database_size(current_database());")
        size_bytes = cur.fetchone()[0]
    return round(size_bytes / (1024 * 1024), 1)


def count_csv_rows(path):
    with open(path, "r", encoding="utf-8") as f:
        return sum(1 for _ in f) - 1  # minus header


def growth_test_once(conn):
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


def growth_test(conn):
    runs = [growth_test_once(conn) for _ in range(REPEATS)]
    return [dict(
        pct=runs[0][i]["pct"], rows=runs[0][i]["rows"],
        load_seconds=round(mean(run[i]["load_seconds"] for run in runs), 4),
        query_seconds=round(mean(run[i]["query_seconds"] for run in runs), 4),
        load_runs=[run[i]["load_seconds"] for run in runs],
        query_runs=[run[i]["query_seconds"] for run in runs],
    ) for i in range(3)]


def main():
    conn = connect()

    without_idx, with_idx, lookup_runs = query_with_without_index(conn)
    disk_mb = db_size_mb(conn)
    growth = growth_test(conn)

    data = {
        "query_without_index_seconds": round(without_idx, 4),
        "query_with_index_seconds": round(with_idx, 4),
        "db_size_mb": disk_mb,
        "growth_test": growth,
        "machine": platform.platform(),
        "measured_at": datetime.now(timezone.utc).isoformat(),
        "repeats": REPEATS,
        "lookup_runs": lookup_runs,
        "lookup_team_sample": "300 distinct teams ordered by md5(team_id || '42')",
        "postgres_settings": {"work_mem": "64MB", "jit": "off"},
        "raw_csv_mb": round(sum(p.stat().st_size for p in pathlib.Path(DATA_DIR).rglob("*.csv")) / (1024 ** 2), 1),
        "peak_memory_mb": {"db": None, "loader": None, "pipeline": None, "app": None},
        "note": (
            "Three alternating index conditions; three growth repeats. Warm OS/database caches are not flushed. "
            "Use scripts/measure_system.py for full-run, laptop hardware and per-container memory evidence."
        ),
    }

    RESULTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    # Preserve independently sampled full-system evidence when rerunning queries.
    if RESULTS_PATH.exists():
        previous = json.loads(RESULTS_PATH.read_text())
        for key in ("peak_memory_mb", "system_runs", "system_run_seconds", "hardware", "memory_method", "system_measured_at"):
            if key in previous:
                data[key] = previous[key]
    temporary = RESULTS_PATH.with_suffix(".tmp")
    temporary.write_text(json.dumps(data, indent=2))
    temporary.replace(RESULTS_PATH)
    print(f"[measure] wrote {RESULTS_PATH}", flush=True)
    print(
        f"[measure] without index={without_idx:.4f}s with index={with_idx:.4f}s "
        f"({without_idx / with_idx if with_idx else float('inf'):.1f}x faster) disk={disk_mb} MB",
        flush=True,
    )
    conn.close()


if __name__ == "__main__":
    main()
