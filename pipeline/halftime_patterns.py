"""PROCESS step: what happens after half-time? For every completed match with
a recorded half-time score, classify each team's evening: led at the break and
won, led and let it slip, trailed and came back, or trailed and lost. The
club-season totals make a "comeback kings / lead bottlers" table that the
comparison page can sit next to actual GF/GA — same source, same grain.
"""
import pandas as pd
from psycopg2.extras import execute_values

REPORT = "half-time patterns"


def compute(conn):
    matches = pd.read_sql("""
        SELECT league_code, season_name, home_team_id, away_team_id,
               home_goals, away_goals, ht_home_goals, ht_away_goals
        FROM match_results
        WHERE home_goals IS NOT NULL AND away_goals IS NOT NULL
          AND ht_home_goals IS NOT NULL AND ht_away_goals IS NOT NULL
    """, conn)
    if matches.empty:
        return pd.DataFrame()

    # One row per team per match, from that team's perspective.
    home = matches.rename(columns={
        "home_team_id": "team_id", "home_goals": "goals_for", "away_goals": "goals_against",
        "ht_home_goals": "ht_for", "ht_away_goals": "ht_against"})
    away = matches.rename(columns={
        "away_team_id": "team_id", "away_goals": "goals_for", "home_goals": "goals_against",
        "ht_away_goals": "ht_for", "ht_home_goals": "ht_against"})
    cols = ["league_code", "season_name", "team_id", "goals_for", "goals_against", "ht_for", "ht_against"]
    long = pd.concat([home[cols], away[cols]], ignore_index=True)

    led = long["ht_for"] > long["ht_against"]
    trailed = long["ht_for"] < long["ht_against"]
    won = long["goals_for"] > long["goals_against"]
    lost = long["goals_for"] < long["goals_against"]

    long["led_at_ht"] = led
    long["held_lead"] = led & won
    long["blew_lead"] = led & ~won            # a draw also counts as points dropped
    long["trailed_at_ht"] = trailed
    long["comeback_win"] = trailed & won
    long["stayed_beaten"] = trailed & lost

    grouped = long.groupby(["league_code", "season_name", "team_id"]).agg(
        matches=("team_id", "size"),
        led_at_ht=("led_at_ht", "sum"), held_lead=("held_lead", "sum"), blew_lead=("blew_lead", "sum"),
        trailed_at_ht=("trailed_at_ht", "sum"), comeback_win=("comeback_win", "sum"),
        stayed_beaten=("stayed_beaten", "sum"),
    ).reset_index()
    # Share of half-time leads converted into wins; NULL when a club never led.
    grouped["lead_conversion"] = (grouped["held_lead"] / grouped["led_at_ht"]).round(3)
    grouped.loc[grouped["led_at_ht"] == 0, "lead_conversion"] = None
    return grouped


COLUMNS = ["league_code", "season_name", "team_id", "matches", "led_at_ht", "held_lead",
           "blew_lead", "trailed_at_ht", "comeback_win", "stayed_beaten", "lead_conversion"]


def write(conn, frame):
    with conn.cursor() as cur:
        cur.execute("DROP TABLE IF EXISTS halftime_patterns;")
        cur.execute("""
            CREATE TABLE halftime_patterns (
                league_code TEXT,
                season_name TEXT,
                team_id INTEGER,
                matches INTEGER,
                led_at_ht INTEGER,
                held_lead INTEGER,
                blew_lead INTEGER,
                trailed_at_ht INTEGER,
                comeback_win INTEGER,
                stayed_beaten INTEGER,
                lead_conversion NUMERIC
            );
        """)
        if not frame.empty:
            values = [tuple(None if pd.isna(v) else v for v in row) for row in frame[COLUMNS].itertuples(index=False)]
            execute_values(cur, f"INSERT INTO halftime_patterns ({', '.join(COLUMNS)}) VALUES %s", values)
        cur.execute("CREATE INDEX IF NOT EXISTS idx_halftime_team ON halftime_patterns (team_id, season_name);")
    conn.commit()
