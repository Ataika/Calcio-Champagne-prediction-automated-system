"""PROCESS step: what do injuries cost a season? Days and games missed are
summed per club-season from the injury log, attributed through each player's
performance row for that season. The correlation column asks one question of
every league-season: do clubs that lose more days to injury score less?
Attribution is approximate — an injury row names a season, not the exact club
on the injury date, so a mid-season mover counts for both clubs he played for.
"""
import pandas as pd
from psycopg2.extras import execute_values

REPORT = "injury burden"


def compute(conn):
    burden = pd.read_sql("""
        SELECT perf.team_id, perf.season_name, perf.competition_id,
               SUM(inj.days_missed) AS days_missed,
               SUM(inj.games_missed) AS games_missed,
               COUNT(*) AS injury_spells
        FROM player_injuries inj
        JOIN (SELECT DISTINCT player_id, team_id, season_name, competition_id
              FROM player_performances) perf
          ON perf.player_id = inj.player_id AND perf.season_name = inj.season_name
        WHERE inj.days_missed IS NOT NULL
        GROUP BY perf.team_id, perf.season_name, perf.competition_id
    """, conn)
    if burden.empty:
        return pd.DataFrame()

    index = pd.read_sql("""
        SELECT team_id, season_name, competition_id, champagne_index
        FROM champagne_index_by_team_season
    """, conn)
    merged = burden.merge(index, on=["team_id", "season_name", "competition_id"], how="inner")

    corr = (merged.groupby(["competition_id", "season_name"])
            .apply(lambda g: g["days_missed"].corr(g["champagne_index"]) if len(g) >= 8 else None,
                   include_groups=False)
            .rename("days_index_corr").reset_index())
    merged = merged.merge(corr, on=["competition_id", "season_name"], how="left")
    merged["days_missed"] = merged["days_missed"].astype(float).round(0)
    merged["days_index_corr"] = merged["days_index_corr"].astype(float).round(3)
    return merged[["team_id", "season_name", "competition_id", "days_missed",
                   "games_missed", "injury_spells", "days_index_corr"]]


COLUMNS = ["team_id", "season_name", "competition_id", "days_missed", "games_missed",
           "injury_spells", "days_index_corr"]


def write(conn, frame):
    with conn.cursor() as cur:
        cur.execute("DROP TABLE IF EXISTS injury_burden_by_team_season;")
        cur.execute("""
            CREATE TABLE injury_burden_by_team_season (
                team_id INTEGER,
                season_name TEXT,
                competition_id TEXT,
                days_missed NUMERIC,
                games_missed NUMERIC,
                injury_spells INTEGER,
                days_index_corr NUMERIC
            );
        """)
        if not frame.empty:
            values = [tuple(None if pd.isna(v) else v for v in row) for row in frame[COLUMNS].itertuples(index=False)]
            execute_values(cur, f"INSERT INTO injury_burden_by_team_season ({', '.join(COLUMNS)}) VALUES %s", values)
        cur.execute("CREATE INDEX IF NOT EXISTS idx_injury_team ON injury_burden_by_team_season (team_id, season_name);")
    conn.commit()
