"""PROCESS step: the biggest wins of each league-season — the five largest
margins, with date and scoreline. Pure showmanship with a serious footnote:
extreme scorelines are exactly the rows where a mean-based rating moves most,
so the demo can point at a real match when asked what drives an outlier.
"""
import pandas as pd
from psycopg2.extras import execute_values

REPORT = "biggest wins"
TOP_N = 5


def compute(conn):
    matches = pd.read_sql("""
        SELECT league_code, season_name, match_date, home_team_id, away_team_id,
               home_goals, away_goals
        FROM match_results
        WHERE home_goals IS NOT NULL AND away_goals IS NOT NULL
          AND home_goals <> away_goals
    """, conn)
    if matches.empty:
        return pd.DataFrame()

    matches["margin"] = (matches["home_goals"] - matches["away_goals"]).abs()
    matches["winner_id"] = matches["home_team_id"].where(
        matches["home_goals"] > matches["away_goals"], matches["away_team_id"])
    matches["loser_id"] = matches["away_team_id"].where(
        matches["home_goals"] > matches["away_goals"], matches["home_team_id"])
    matches["scoreline"] = matches["home_goals"].astype(int).astype(str) + "–" + matches["away_goals"].astype(int).astype(str)

    top = (matches.sort_values(["margin", "match_date"], ascending=[False, True])
           .groupby(["league_code", "season_name"]).head(TOP_N))
    return top[["league_code", "season_name", "match_date", "winner_id", "loser_id", "scoreline", "margin"]]


COLUMNS = ["league_code", "season_name", "match_date", "winner_id", "loser_id", "scoreline", "margin"]


def write(conn, frame):
    with conn.cursor() as cur:
        cur.execute("DROP TABLE IF EXISTS biggest_wins;")
        cur.execute("""
            CREATE TABLE biggest_wins (
                league_code TEXT,
                season_name TEXT,
                match_date DATE,
                winner_id INTEGER,
                loser_id INTEGER,
                scoreline TEXT,
                margin INTEGER
            );
        """)
        if not frame.empty:
            execute_values(cur, f"INSERT INTO biggest_wins ({', '.join(COLUMNS)}) VALUES %s",
                           list(frame[COLUMNS].itertuples(index=False)))
    conn.commit()
