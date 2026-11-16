#!/usr/bin/env python3
"""Data-quality scorecard: how complete is what we loaded?

The database is not published on a host port, so run this inside the app
container, exactly like the test suite (stack must be up):

    docker compose run --rm --no-deps -v "$PWD:/source:ro" -w /source app \
        python scripts/data_quality.py

For every loaded table it reports the row count; for the columns our analysis
leans on, the share of missing values; and for transfer fees, the share of
zeros — the single most important honesty number in the project, because a
zero fee is usually an undisclosed or free move, not a measured price.
"""
import os

import psycopg2

CHECKS = [
    # (table, column, what a gap means)
    ("player_performances", "goals", "a performance row without a goal count"),
    ("player_performances", "nb_in_group", "no match-count proxy, the index denominator"),
    ("player_profiles", "date_of_birth", "age features cannot be built"),
    ("player_profiles", "citizenship", "nationality analysis loses the player"),
    ("transfer_history", "transfer_date", "the transfer cannot be assigned to a window"),
    ("player_injuries", "days_missed", "the injury spell has no measurable length"),
    ("match_results", "ht_home_goals", "no half-time story for this match"),
    ("match_results", "odds_home", "no bookmaker view of this match"),
    ("match_results", "referee", "the match has no named referee"),
]


def main() -> None:
    conn = psycopg2.connect(
        host=os.getenv("POSTGRES_HOST", "localhost"), port=os.getenv("POSTGRES_PORT", "5432"),
        dbname=os.getenv("POSTGRES_DB", "calcio"), user=os.getenv("POSTGRES_USER", "team"),
        password=os.getenv("POSTGRES_PASSWORD", "changeme"),
    )
    cur = conn.cursor()

    cur.execute("""
        SELECT relname, n_live_tup FROM pg_stat_user_tables ORDER BY n_live_tup DESC
    """)
    print(f"{'table':<36}{'rows':>12}")
    for name, rows in cur.fetchall():
        print(f"{name:<36}{rows:>12,}")

    print(f"\n{'column':<44}{'missing':>10}  meaning of a gap")
    for table, column, meaning in CHECKS:
        cur.execute(f"SELECT COUNT(*), COUNT({column}) FROM {table}")
        total, present = cur.fetchone()
        share = (total - present) / total if total else 0.0
        print(f"{table + '.' + column:<44}{share:>9.1%}  {meaning}")

    cur.execute("""
        SELECT COUNT(*) FILTER (WHERE transfer_fee = 0 OR transfer_fee IS NULL), COUNT(*)
        FROM transfer_history
    """)
    zeros, total = cur.fetchone()
    print(f"\nTransfer fees recorded as zero or missing: {zeros:,} of {total:,} "
          f"({zeros / total:.1%}). A zero is usually undisclosed or free, not a price.")
    conn.close()


if __name__ == "__main__":
    main()
