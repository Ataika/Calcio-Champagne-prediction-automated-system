"""PROCESS step: a simplified Maher (1982) Poisson attack/defense rating per
team, fit independently for each league-season in match_results. Two
parameters per team (attack, defense) plus one shared home-advantage term:

    home_goals ~ Poisson(exp(attack[home] - defense[away] + home_advantage))
    away_goals ~ Poisson(exp(attack[away] - defense[home]))

This is the textbook two-parameter football rating model (the "basic" half of
Dixon-Coles 1997, without their low-score correlation correction) — not Elo,
not a commercial rating, fit from scratch on this project's own match goals.
Separate, properly identified attack and defense numbers per team, versus the
single counting-stat ratios (goals/match, goals_conceded/match) used
elsewhere. Also the basis for the comparison page's match simulator
(see simulate_scoreline below).

Needs enough matches to identify n_teams*2+1 parameters reliably — a partial
season snapshot is skipped, not reported with a meaningless fit.
"""
import numpy as np
import pandas as pd
from psycopg2.extras import execute_values
from scipy.optimize import minimize

MIN_MATCHES = 50

# Mirrors pipeline/compute_predictions.py's LEAGUE_TO_COMPETITION. Duplicated
# rather than imported to avoid a circular import between the two modules;
# both are five stable, rarely-changed entries.
LEAGUE_TO_COMPETITION = {"E0": "GB1", "SP1": "ES1", "I1": "IT1", "D1": "L1", "F1": "FR1"}


def _negative_log_likelihood(params, home_idx, away_idx, home_goals, away_goals, n_teams):
    attack = params[:n_teams]
    defense = params[n_teams:2 * n_teams]
    home_advantage = params[-1]
    home_rate = np.exp(attack[home_idx] - defense[away_idx] + home_advantage)
    away_rate = np.exp(attack[away_idx] - defense[home_idx])
    # Poisson log-likelihood up to a goals!-dependent constant that doesn't
    # affect where the optimum is.
    log_likelihood = (
        np.sum(home_goals * np.log(home_rate) - home_rate)
        + np.sum(away_goals * np.log(away_rate) - away_rate)
    )
    return -log_likelihood


def fit_group(matches):
    """`matches`: one league-season's rows (home_team_id, away_team_id,
    home_goals, away_goals). Returns (ratings_df, home_advantage) or
    (None, None) if there aren't enough matches to identify the parameters."""
    if len(matches) < MIN_MATCHES:
        return None, None
    teams = sorted(set(matches["home_team_id"]) | set(matches["away_team_id"]))
    index = {team: i for i, team in enumerate(teams)}
    n_teams = len(teams)
    home_idx = matches["home_team_id"].map(index).to_numpy()
    away_idx = matches["away_team_id"].map(index).to_numpy()
    home_goals = matches["home_goals"].to_numpy(dtype=float)
    away_goals = matches["away_goals"].to_numpy(dtype=float)

    result = minimize(
        _negative_log_likelihood, np.zeros(2 * n_teams + 1),
        args=(home_idx, away_idx, home_goals, away_goals, n_teams),
        method="L-BFGS-B", options={"maxiter": 500},
    )
    attack = result.x[:n_teams]
    defense = result.x[n_teams:2 * n_teams]
    home_advantage = float(result.x[-1])
    # attack/defense are only identified up to an additive shift (adding c to
    # every attack and subtracting c from every defense leaves every match
    # rate unchanged) — center both at zero so ratings are comparable team to
    # team and, loosely, across league-seasons.
    attack = attack - attack.mean()
    defense = defense - defense.mean()
    ratings = pd.DataFrame({
        "team_id": teams,
        "attack_rating": attack.round(3),
        "defense_rating": defense.round(3),
    })
    ratings["overall_rating"] = (ratings["attack_rating"] - ratings["defense_rating"]).round(3)
    return ratings, home_advantage


def compute(conn):
    matches = pd.read_sql("""
        SELECT league_code, season_name, home_team_id, away_team_id, home_goals, away_goals
        FROM match_results WHERE home_goals IS NOT NULL AND away_goals IS NOT NULL
    """, conn)
    if matches.empty:
        return pd.DataFrame()

    groups = []
    for (league_code, season_name), group in matches.groupby(["league_code", "season_name"]):
        ratings, home_advantage = fit_group(group)
        if ratings is None:
            continue
        ratings["league_code"] = league_code
        ratings["season_name"] = season_name
        ratings["competition_id"] = LEAGUE_TO_COMPETITION.get(league_code)
        ratings["home_advantage"] = round(home_advantage, 3)
        ratings["n_matches"] = len(group)
        groups.append(ratings)
    return pd.concat(groups, ignore_index=True) if groups else pd.DataFrame()


RATING_COLUMNS = [
    "team_id", "league_code", "competition_id", "season_name",
    "attack_rating", "defense_rating", "overall_rating", "home_advantage", "n_matches",
]


def write(conn, ratings_df):
    with conn.cursor() as cur:
        cur.execute("DROP TABLE IF EXISTS team_power_ratings;")
        cur.execute("""
            CREATE TABLE team_power_ratings (
                team_id INTEGER,
                league_code TEXT,
                competition_id TEXT,
                season_name TEXT,
                attack_rating NUMERIC,
                defense_rating NUMERIC,
                overall_rating NUMERIC,
                home_advantage NUMERIC,
                n_matches INTEGER
            );
        """)
        if not ratings_df.empty:
            frame = ratings_df[RATING_COLUMNS].astype(object).where(pd.notnull(ratings_df[RATING_COLUMNS]), None)
            execute_values(
                cur, f"INSERT INTO team_power_ratings ({', '.join(RATING_COLUMNS)}) VALUES %s",
                frame.values.tolist(),
            )
            cur.execute(
                "CREATE INDEX IF NOT EXISTS idx_tpr_team_season "
                "ON team_power_ratings (team_id, season_name, competition_id);"
            )
    conn.commit()
