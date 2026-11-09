"""PROCESS step: a *proxy* for expected goals. This dataset has no real xG
field anywhere — confirmed, no xG column in any source table, Transfermarkt
or football-data.co.uk. Every output of this module is labeled "proxy xG";
never presented as Opta/StatsBomb-grade expected goals.

proxy_xg for one team in one match = that team's shots on target * a league-
season-wide shots-on-target -> goals conversion rate (pooled across both
teams, all matches in that league-season). Aggregated to team-season level as
proxy_xg_per_match (attack side) and proxy_xga_per_match (defense side, using
the *opponent's* shots on target against this team). Finishing luck = actual
goals/match minus proxy xG/match (positive: scoring more than the shot volume
alone would suggest); defensive luck mirrors it the other way.
"""
import pandas as pd

MIN_MATCHES = 10  # per team-season; drops one-off cup-tie noise

LEAGUE_TO_COMPETITION = {"E0": "GB1", "SP1": "ES1", "I1": "IT1", "D1": "L1", "F1": "FR1"}


def compute(conn):
    matches = pd.read_sql("""
        SELECT league_code, season_name, home_team_id, away_team_id,
               home_goals, away_goals, home_shots_on_target, away_shots_on_target
        FROM match_results
        WHERE home_goals IS NOT NULL AND away_goals IS NOT NULL
          AND home_shots_on_target IS NOT NULL AND away_shots_on_target IS NOT NULL
    """, conn)
    if matches.empty:
        return pd.DataFrame()

    groups = []
    for (league_code, season_name), group in matches.groupby(["league_code", "season_name"]):
        total_goals = group["home_goals"].sum() + group["away_goals"].sum()
        total_shots_on_target = group["home_shots_on_target"].sum() + group["away_shots_on_target"].sum()
        if total_shots_on_target == 0:
            continue
        conversion_rate = total_goals / total_shots_on_target

        home = group.rename(columns={
            "home_team_id": "team_id", "home_goals": "goals", "away_goals": "goals_against",
            "home_shots_on_target": "shots_on_target", "away_shots_on_target": "opponent_shots_on_target",
        })[["team_id", "goals", "goals_against", "shots_on_target", "opponent_shots_on_target"]]
        away = group.rename(columns={
            "away_team_id": "team_id", "away_goals": "goals", "home_goals": "goals_against",
            "away_shots_on_target": "shots_on_target", "home_shots_on_target": "opponent_shots_on_target",
        })[["team_id", "goals", "goals_against", "shots_on_target", "opponent_shots_on_target"]]
        long = pd.concat([home, away], ignore_index=True)

        totals = long.groupby("team_id").agg(
            matches=("goals", "size"), goals=("goals", "sum"), goals_against=("goals_against", "sum"),
            shots_on_target=("shots_on_target", "sum"), opponent_shots_on_target=("opponent_shots_on_target", "sum"),
        ).reset_index()
        totals = totals[totals["matches"] >= MIN_MATCHES].copy()
        if totals.empty:
            continue

        totals["proxy_xg_per_match"] = (totals["shots_on_target"] * conversion_rate / totals["matches"]).round(2)
        totals["proxy_xga_per_match"] = (totals["opponent_shots_on_target"] * conversion_rate / totals["matches"]).round(2)
        totals["actual_goals_per_match"] = (totals["goals"] / totals["matches"]).round(2)
        totals["actual_conceded_per_match"] = (totals["goals_against"] / totals["matches"]).round(2)
        totals["finishing_luck"] = (totals["actual_goals_per_match"] - totals["proxy_xg_per_match"]).round(2)
        totals["defensive_luck"] = (totals["proxy_xga_per_match"] - totals["actual_conceded_per_match"]).round(2)
        totals["league_code"] = league_code
        totals["season_name"] = season_name
        totals["competition_id"] = LEAGUE_TO_COMPETITION.get(league_code)
        groups.append(totals)

    return pd.concat(groups, ignore_index=True) if groups else pd.DataFrame()


PROXY_XG_COLUMNS = [
    "team_id", "league_code", "competition_id", "season_name", "matches",
    "proxy_xg_per_match", "proxy_xga_per_match", "actual_goals_per_match",
    "actual_conceded_per_match", "finishing_luck", "defensive_luck",
]


def write(conn, proxy_df):
    with conn.cursor() as cur:
        cur.execute("DROP TABLE IF EXISTS proxy_xg_by_team_season;")
        cur.execute("""
            CREATE TABLE proxy_xg_by_team_season (
                team_id INTEGER,
                league_code TEXT,
                competition_id TEXT,
                season_name TEXT,
                matches INTEGER,
                proxy_xg_per_match NUMERIC,
                proxy_xga_per_match NUMERIC,
                actual_goals_per_match NUMERIC,
                actual_conceded_per_match NUMERIC,
                finishing_luck NUMERIC,
                defensive_luck NUMERIC
            );
        """)
        if not proxy_df.empty:
            from psycopg2.extras import execute_values
            frame = proxy_df[PROXY_XG_COLUMNS].astype(object).where(pd.notnull(proxy_df[PROXY_XG_COLUMNS]), None)
            execute_values(
                cur, f"INSERT INTO proxy_xg_by_team_season ({', '.join(PROXY_XG_COLUMNS)}) VALUES %s",
                frame.values.tolist(),
            )
            cur.execute(
                "CREATE INDEX IF NOT EXISTS idx_pxg_team_season "
                "ON proxy_xg_by_team_season (team_id, season_name, competition_id);"
            )
    conn.commit()
