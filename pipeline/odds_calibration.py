"""PROCESS step: how often is the bookmaker's favourite actually right — and
do our own Poisson ratings agree with the market?

Two outputs from the loaded Bet365 closing odds. First, calibration: matches
are bucketed by the favourite's implied probability (1/odds, which overstates
the true probability by the bookmaker's margin — stated, not corrected), and
each bucket compares implied probability with the favourite's actual win rate.
Second, agreement: for matches where both sides have a power rating in that
league-season, how often the market favourite, and separately the higher-rated
side, went on to win. Both are descriptive scorecards on the same historical
matches — neither is a betting strategy, and nothing here feeds the model.
"""
import pandas as pd
from psycopg2.extras import execute_values

REPORT = "odds calibration"
BUCKETS = [(0.0, 0.40), (0.40, 0.50), (0.50, 0.60), (0.60, 0.70), (0.70, 1.01)]


def _load(conn):
    return pd.read_sql("""
        SELECT league_code, season_name, home_team_id, away_team_id, result,
               odds_home, odds_draw, odds_away
        FROM match_results
        WHERE result IN ('H', 'D', 'A')
          AND odds_home > 1 AND odds_draw > 1 AND odds_away > 1
    """, conn)


def compute(conn):
    matches = _load(conn)
    if matches.empty:
        return {"calibration": pd.DataFrame(), "agreement": pd.DataFrame()}

    matches["favourite"] = matches[["odds_home", "odds_away"]].idxmin(axis=1).map(
        {"odds_home": "H", "odds_away": "A"})
    fav_odds = matches[["odds_home", "odds_away"]].min(axis=1)
    matches["implied_prob"] = 1.0 / fav_odds
    matches["favourite_won"] = matches["favourite"] == matches["result"]

    rows = []
    for low, high in BUCKETS:
        bucket = matches[(matches["implied_prob"] >= low) & (matches["implied_prob"] < high)]
        if len(bucket) < 30:
            continue
        rows.append({
            "bucket": f"{low:.0%}–{min(high, 1.0):.0%}",
            "matches": int(len(bucket)),
            "implied_prob_mean": round(float(bucket["implied_prob"].mean()), 3),
            "favourite_win_rate": round(float(bucket["favourite_won"].mean()), 3),
        })
    calibration = pd.DataFrame(rows)

    # In the Maher parametrization used by power_ratings.py the away side
    # scores exp(attack_away - defense_home): a HIGHER defense rating means
    # fewer goals conceded. Overall strength is therefore attack PLUS defense.
    ratings = pd.read_sql("""
        SELECT league_code, season_name, team_id, attack_rating + defense_rating AS strength
        FROM team_power_ratings
    """, conn)
    merged = (matches
              .merge(ratings.rename(columns={"team_id": "home_team_id", "strength": "home_strength"}),
                     on=["league_code", "season_name", "home_team_id"])
              .merge(ratings.rename(columns={"team_id": "away_team_id", "strength": "away_strength"}),
                     on=["league_code", "season_name", "away_team_id"]))
    agreement = pd.DataFrame()
    if not merged.empty:
        merged["rating_pick"] = merged["home_strength"].gt(merged["away_strength"]).map({True: "H", False: "A"})
        merged["rating_right"] = merged["rating_pick"] == merged["result"]
        agreement = merged.groupby("league_code").agg(
            matches=("result", "size"),
            favourite_win_rate=("favourite_won", "mean"),
            rating_win_rate=("rating_right", "mean"),
            agreement_rate=("favourite", lambda f: float((f == merged.loc[f.index, "rating_pick"]).mean())),
        ).reset_index().round(3)

    return {"calibration": calibration, "agreement": agreement}


def write(conn, result):
    calibration, agreement = result["calibration"], result["agreement"]
    with conn.cursor() as cur:
        cur.execute("DROP TABLE IF EXISTS odds_calibration;")
        cur.execute("""
            CREATE TABLE odds_calibration (
                bucket TEXT,
                matches INTEGER,
                implied_prob_mean NUMERIC,
                favourite_win_rate NUMERIC
            );
        """)
        if not calibration.empty:
            execute_values(cur, "INSERT INTO odds_calibration (bucket, matches, implied_prob_mean, favourite_win_rate) VALUES %s",
                           list(calibration.itertuples(index=False)))
        cur.execute("DROP TABLE IF EXISTS odds_vs_ratings;")
        cur.execute("""
            CREATE TABLE odds_vs_ratings (
                league_code TEXT,
                matches INTEGER,
                favourite_win_rate NUMERIC,
                rating_win_rate NUMERIC,
                agreement_rate NUMERIC
            );
        """)
        if not agreement.empty:
            execute_values(cur, "INSERT INTO odds_vs_ratings (league_code, matches, favourite_win_rate, rating_win_rate, agreement_rate) VALUES %s",
                           list(agreement.itertuples(index=False)))
    conn.commit()
