"""PROCESS step: cards per match by referee. Yellow and red cards from both
sides of every completed match a referee took, with a minimum match count so
one wild evening does not crown "the strictest referee in Europe". The rate is
descriptive: strict referees and rough fixtures are not separated here.
"""
import pandas as pd
from psycopg2.extras import execute_values

REPORT = "referee discipline"
MIN_MATCHES = 10


def compute(conn):
    matches = pd.read_sql("""
        SELECT referee, league_code,
               home_yellow, away_yellow, home_red, away_red
        FROM match_results
        WHERE referee IS NOT NULL AND referee <> ''
          AND home_yellow IS NOT NULL AND away_yellow IS NOT NULL
    """, conn)
    if matches.empty:
        return pd.DataFrame()

    matches["yellows"] = matches["home_yellow"] + matches["away_yellow"]
    matches["reds"] = matches["home_red"].fillna(0) + matches["away_red"].fillna(0)
    grouped = matches.groupby(["referee", "league_code"]).agg(
        matches=("yellows", "size"),
        yellows_per_match=("yellows", "mean"),
        reds_per_match=("reds", "mean"),
    ).reset_index()
    grouped = grouped[grouped["matches"] >= MIN_MATCHES].copy()
    grouped["yellows_per_match"] = grouped["yellows_per_match"].round(2)
    grouped["reds_per_match"] = grouped["reds_per_match"].round(3)
    return grouped.sort_values("yellows_per_match", ascending=False)


COLUMNS = ["referee", "league_code", "matches", "yellows_per_match", "reds_per_match"]


def write(conn, frame):
    with conn.cursor() as cur:
        cur.execute("DROP TABLE IF EXISTS referee_discipline;")
        cur.execute("""
            CREATE TABLE referee_discipline (
                referee TEXT,
                league_code TEXT,
                matches INTEGER,
                yellows_per_match NUMERIC,
                reds_per_match NUMERIC
            );
        """)
        if not frame.empty:
            execute_values(cur, f"INSERT INTO referee_discipline ({', '.join(COLUMNS)}) VALUES %s",
                           list(frame[COLUMNS].itertuples(index=False)))
    conn.commit()
