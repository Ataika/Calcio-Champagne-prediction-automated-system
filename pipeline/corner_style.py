"""PROCESS step: corners as a style marker. Corners per match for and against
each club-season, and the league-season correlation between corner volume and
goals scored. Corners are pressure, not quality: the correlation column shows
in the data how loosely "winning corners" and "scoring" are related.
"""
import pandas as pd
from psycopg2.extras import execute_values

REPORT = "corner style"


def compute(conn):
    matches = pd.read_sql("""
        SELECT league_code, season_name, home_team_id, away_team_id,
               home_goals, away_goals, home_corners, away_corners
        FROM match_results
        WHERE home_corners IS NOT NULL AND away_corners IS NOT NULL
          AND home_goals IS NOT NULL AND away_goals IS NOT NULL
    """, conn)
    if matches.empty:
        return pd.DataFrame()

    home = matches.rename(columns={
        "home_team_id": "team_id", "home_corners": "corners_for", "away_corners": "corners_against",
        "home_goals": "goals_for"})
    away = matches.rename(columns={
        "away_team_id": "team_id", "away_corners": "corners_for", "home_corners": "corners_against",
        "away_goals": "goals_for"})
    cols = ["league_code", "season_name", "team_id", "corners_for", "corners_against", "goals_for"]
    long = pd.concat([home[cols], away[cols]], ignore_index=True)

    grouped = long.groupby(["league_code", "season_name", "team_id"]).agg(
        matches=("team_id", "size"),
        corners_for_per_match=("corners_for", "mean"),
        corners_against_per_match=("corners_against", "mean"),
        goals_per_match=("goals_for", "mean"),
    ).reset_index()

    # One correlation per league-season: do teams that win more corners score more?
    corr = (grouped.groupby(["league_code", "season_name"])
            .apply(lambda g: g["corners_for_per_match"].corr(g["goals_per_match"]), include_groups=False)
            .rename("corners_goals_corr").reset_index())
    grouped = grouped.merge(corr, on=["league_code", "season_name"], how="left")
    for col in ("corners_for_per_match", "corners_against_per_match", "goals_per_match"):
        grouped[col] = grouped[col].round(2)
    grouped["corners_goals_corr"] = grouped["corners_goals_corr"].round(3)
    return grouped


COLUMNS = ["league_code", "season_name", "team_id", "matches", "corners_for_per_match",
           "corners_against_per_match", "goals_per_match", "corners_goals_corr"]


def write(conn, frame):
    with conn.cursor() as cur:
        cur.execute("DROP TABLE IF EXISTS corner_style_by_team_season;")
        cur.execute("""
            CREATE TABLE corner_style_by_team_season (
                league_code TEXT,
                season_name TEXT,
                team_id INTEGER,
                matches INTEGER,
                corners_for_per_match NUMERIC,
                corners_against_per_match NUMERIC,
                goals_per_match NUMERIC,
                corners_goals_corr NUMERIC
            );
        """)
        if not frame.empty:
            values = [tuple(None if pd.isna(v) else v for v in row) for row in frame[COLUMNS].itertuples(index=False)]
            execute_values(cur, f"INSERT INTO corner_style_by_team_season ({', '.join(COLUMNS)}) VALUES %s", values)
    conn.commit()
