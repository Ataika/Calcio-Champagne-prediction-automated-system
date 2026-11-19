"""PROCESS step: how big is home advantage, league by league and season by
season? Counted directly from completed scorelines: share of home wins, draws
and away wins, plus mean goals for each side. Descriptive — it says how often
the home side won here, not why.
"""
import pandas as pd
from psycopg2.extras import execute_values

REPORT = "home advantage"


def compute(conn):
    matches = pd.read_sql("""
        SELECT league_code, season_name, result, home_goals, away_goals
        FROM match_results
        WHERE result IN ('H', 'D', 'A')
          AND home_goals IS NOT NULL AND away_goals IS NOT NULL
    """, conn)
    if matches.empty:
        return pd.DataFrame()

    grouped = matches.groupby(["league_code", "season_name"]).agg(
        matches=("result", "size"),
        home_wins=("result", lambda r: int((r == "H").sum())),
        draws=("result", lambda r: int((r == "D").sum())),
        away_wins=("result", lambda r: int((r == "A").sum())),
        home_goals_avg=("home_goals", "mean"),
        away_goals_avg=("away_goals", "mean"),
    ).reset_index()
    grouped["home_win_share"] = (grouped["home_wins"] / grouped["matches"]).round(3)
    grouped["away_win_share"] = (grouped["away_wins"] / grouped["matches"]).round(3)
    grouped["home_goals_avg"] = grouped["home_goals_avg"].round(2)
    grouped["away_goals_avg"] = grouped["away_goals_avg"].round(2)
    return grouped


COLUMNS = ["league_code", "season_name", "matches", "home_wins", "draws", "away_wins",
           "home_win_share", "away_win_share", "home_goals_avg", "away_goals_avg"]


def write(conn, frame):
    with conn.cursor() as cur:
        cur.execute("DROP TABLE IF EXISTS home_advantage_by_league_season;")
        cur.execute("""
            CREATE TABLE home_advantage_by_league_season (
                league_code TEXT,
                season_name TEXT,
                matches INTEGER,
                home_wins INTEGER,
                draws INTEGER,
                away_wins INTEGER,
                home_win_share NUMERIC,
                away_win_share NUMERIC,
                home_goals_avg NUMERIC,
                away_goals_avg NUMERIC
            );
        """)
        if not frame.empty:
            execute_values(cur, f"INSERT INTO home_advantage_by_league_season ({', '.join(COLUMNS)}) VALUES %s",
                           list(frame[COLUMNS].itertuples(index=False)))
    conn.commit()
