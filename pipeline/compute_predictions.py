"""PROCESS step: builds the Champagne Index, joins it with transfer spend, fits a
simple linear trend, and writes everything to a `champagne_results` table the
dashboard reads from.

Champagne Index = (goals + assists) / matches for a team, in one competition, in one
season — see sql/champagne_queries.sql for exactly how it's computed from
player_performances.

Prediction = one global linear fit of "change in index next season" against
"money spent on incoming transfers this season" (scipy.stats.linregress). This is a
trend line, not a trained ML model — it's meant to answer "does spending predict a
rise in attacking output", not to be a production forecaster.
"""
import json
import os
import re
import time

import pandas as pd
import psycopg2
from psycopg2.extras import execute_values
from scipy import stats
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import r2_score
from sklearn.model_selection import train_test_split

RESULT_COLUMNS = [
    "team_id", "team_name", "season_name", "season_key", "competition_id",
    "competition_name", "matches", "total_goals", "total_assists",
    "champagne_index", "total_spend", "attacking_spend", "delta_index",
    "predicted_next_index", "is_latest_season",
]

# football-data.co.uk league code -> Transfermarkt competition_id, so match_results
# (keyed by league_code) can be joined with champagne_results (keyed by competition_id).
LEAGUE_TO_COMPETITION = {"E0": "GB1", "SP1": "ES1", "I1": "IT1", "D1": "L1", "F1": "FR1"}

STANDINGS_COLUMNS = [
    "league_code", "competition_id", "season_name", "team_id", "team_name",
    "played", "wins", "draws", "losses", "goals_for", "goals_against",
    "goal_diff", "points", "position", "champagne_index", "total_spend",
]


def connect():
    last_error = None
    for attempt in range(15):
        try:
            return psycopg2.connect(
                host=os.environ.get("POSTGRES_HOST", "db"),
                port=os.environ.get("POSTGRES_PORT", "5432"),
                dbname=os.environ["POSTGRES_DB"],
                user=os.environ["POSTGRES_USER"],
                password=os.environ["POSTGRES_PASSWORD"],
            )
        except psycopg2.OperationalError as exc:
            last_error = exc
            print(f"[pipeline] db not ready yet (attempt {attempt + 1}/15): {exc}", flush=True)
            time.sleep(2)
    raise SystemExit(f"[pipeline] could not connect to the database: {last_error}")


def season_sort_key(season_name):
    """'08/09' -> 2008, '99/00' -> 1999, '23/24' -> 2023. None if unparseable."""
    match = re.match(r"(\d{2})/(\d{2})", str(season_name))
    if not match:
        return None
    start_yy = int(match.group(1))
    return 2000 + start_yy if start_yy < 50 else 1900 + start_yy


def build_views(conn):
    with open("/sql/champagne_queries.sql") as f:
        views_sql = f.read()
    with conn.cursor() as cur:
        cur.execute(views_sql)
    conn.commit()


def load_reserve_youth_team_ids(conn):
    """team_children maps every club to its own squads, including itself (parent_team_id
    == child_team_id for the first team). Rows where they differ are reserve/youth/U-21
    squads of that parent — excluding those gives a first-team-only filter without
    guessing at club_division text."""
    df = pd.read_sql(
        "SELECT DISTINCT child_team_id FROM team_children WHERE parent_team_id <> child_team_id",
        conn,
    )
    return set(df["child_team_id"])


def compute(conn, reserve_youth_ids):
    index_df = pd.read_sql("SELECT * FROM champagne_index_by_team_season", conn)
    spend_df = pd.read_sql("SELECT * FROM transfer_spend_by_team_season", conn)

    index_df["season_key"] = index_df["season_name"].apply(season_sort_key)
    index_df = index_df.dropna(subset=["season_key", "champagne_index"]).copy()
    index_df["season_key"] = index_df["season_key"].astype(int)

    merged = index_df.merge(spend_df, on=["team_id", "season_name"], how="left")
    merged[["total_spend", "attacking_spend"]] = merged[["total_spend", "attacking_spend"]].fillna(0)

    merged = merged.sort_values(["team_id", "competition_id", "season_key"])
    group = merged.groupby(["team_id", "competition_id"])
    merged["next_champagne_index"] = group["champagne_index"].shift(-1)
    merged["delta_index"] = merged["next_champagne_index"] - merged["champagne_index"]
    merged["is_latest_season"] = group["season_key"].transform("max") == merged["season_key"]

    # Fit the trend only on rows with a real next season, a reasonable sample of
    # matches (drops teams that only appear for a one-off cup tie), and excluding
    # reserve/youth squads (see load_reserve_youth_team_ids) — mixing e.g. "Real
    # Madrid Castilla" in with "Real Madrid" dilutes any real spend->output signal.
    train = merged.dropna(subset=["delta_index"])
    train = train[train["matches"].fillna(0) >= 5]
    train = train[~train["team_id"].isin(reserve_youth_ids)]

    if len(train) >= 20:
        slope, intercept, r_value, p_value, _std_err = stats.linregress(
            train["total_spend"].astype(float), train["delta_index"].astype(float)
        )
    else:
        slope, intercept, r_value, p_value = 0.0, 0.0, 0.0, 1.0

    merged["predicted_next_index"] = (
        merged["champagne_index"].astype(float)
        + slope * merged["total_spend"].astype(float)
        + intercept
    ).round(2)

    return merged, (float(slope), float(intercept), float(r_value), float(p_value), len(train))


ML_FEATURE_COLUMNS = ["champagne_index", "total_spend", "attacking_spend", "squad_avg_age", "market_value_change"]


def build_ml_features(conn, merged):
    """Richer feature set per team-season, joined onto the same rows `compute()`
    already built: squad average age (player_profiles.date_of_birth) and the
    change in the squad's average market value vs. the previous season
    (player_market_value, read at the player's value within that season's year)."""
    roster = pd.read_sql(
        "SELECT DISTINCT team_id, season_name, player_id FROM player_performances", conn
    )
    profiles = pd.read_sql(
        "SELECT player_id, EXTRACT(YEAR FROM date_of_birth) AS birth_year FROM player_profiles", conn
    )
    roster = roster.merge(profiles, on="player_id", how="left")
    roster["season_key"] = roster["season_name"].apply(season_sort_key)
    roster = roster.dropna(subset=["season_key", "birth_year"])
    roster["age"] = roster["season_key"] - roster["birth_year"]
    roster = roster[(roster["age"] >= 14) & (roster["age"] <= 45)]

    age_by_team_season = (
        roster.groupby(["team_id", "season_name"])["age"].mean()
        .reset_index().rename(columns={"age": "squad_avg_age"})
    )

    market_values = pd.read_sql(
        "SELECT player_id, EXTRACT(YEAR FROM date_unix) AS year, value FROM player_market_value", conn
    )
    roster_mv = roster[["team_id", "season_name", "player_id", "season_key"]].merge(
        market_values, on="player_id", how="left"
    )
    roster_mv = roster_mv[roster_mv["year"] == roster_mv["season_key"]]
    mv_by_team_season = (
        roster_mv.groupby(["team_id", "season_name"])["value"].mean()
        .reset_index().rename(columns={"value": "squad_avg_value"})
    )

    features = merged.merge(age_by_team_season, on=["team_id", "season_name"], how="left")
    features = features.merge(mv_by_team_season, on=["team_id", "season_name"], how="left")
    features = features.sort_values(["team_id", "season_key"])
    features["prev_squad_avg_value"] = features.groupby("team_id")["squad_avg_value"].shift(1)
    features["market_value_change"] = features["squad_avg_value"] - features["prev_squad_avg_value"]
    return features


def fit_ml_model(features, reserve_youth_ids):
    """RandomForestRegressor predicting next-season champagne_index change from the
    richer feature set, vs. the single-feature linear baseline in compute()."""
    train = features.dropna(subset=["delta_index"])
    train = train[train["matches"].fillna(0) >= 5]
    train = train[~train["team_id"].isin(reserve_youth_ids)]
    train = train.dropna(subset=ML_FEATURE_COLUMNS)

    if len(train) < 50:
        return None

    X = train[ML_FEATURE_COLUMNS].astype(float)
    y = train["delta_index"].astype(float)
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
    model = RandomForestRegressor(n_estimators=200, max_depth=6, random_state=42, n_jobs=-1)
    model.fit(X_train, y_train)
    r2 = float(r2_score(y_test, model.predict(X_test)))
    importances = dict(zip(ML_FEATURE_COLUMNS, model.feature_importances_.astype(float)))
    return r2, len(train), importances


def compute_standings(conn, champagne_results):
    """Optional: real league tables built from match_results (football-data.co.uk
    enrichment, see loader/load_data.py). Lets the dashboard check whether a high
    Champagne Index actually correlates with finishing higher in the table — the
    one thing player_performances alone can't answer, since it has no match-level
    results. Returns an empty DataFrame (and the pipeline skips this table) if the
    enrichment wasn't loaded.
    """
    matches = pd.read_sql("SELECT * FROM match_results", conn)
    if matches.empty:
        return pd.DataFrame(columns=STANDINGS_COLUMNS), None

    home = matches.rename(columns={
        "home_team_id": "team_id", "away_team_id": "opponent_id",
        "home_goals": "goals_for", "away_goals": "goals_against",
    }).copy()
    home["win"] = home["result"] == "H"
    home["draw"] = home["result"] == "D"
    home["loss"] = home["result"] == "A"

    away = matches.rename(columns={
        "away_team_id": "team_id", "home_team_id": "opponent_id",
        "away_goals": "goals_for", "home_goals": "goals_against",
    }).copy()
    away["win"] = away["result"] == "A"
    away["draw"] = away["result"] == "D"
    away["loss"] = away["result"] == "H"

    cols = ["league_code", "season_name", "team_id", "goals_for", "goals_against", "win", "draw", "loss"]
    long = pd.concat([home[cols], away[cols]], ignore_index=True)

    table = long.groupby(["league_code", "season_name", "team_id"]).agg(
        played=("win", "size"),
        wins=("win", "sum"),
        draws=("draw", "sum"),
        losses=("loss", "sum"),
        goals_for=("goals_for", "sum"),
        goals_against=("goals_against", "sum"),
    ).reset_index()
    table["goal_diff"] = table["goals_for"] - table["goals_against"]
    table["points"] = table["wins"] * 3 + table["draws"]
    table["competition_id"] = table["league_code"].map(LEAGUE_TO_COMPETITION)

    table = table.sort_values(
        ["league_code", "season_name", "points", "goal_diff"], ascending=[True, True, False, False]
    )
    table["position"] = table.groupby(["league_code", "season_name"]).cumcount() + 1

    enriched = table.merge(
        champagne_results[["team_id", "team_name", "season_name", "competition_id", "champagne_index", "total_spend"]],
        on=["team_id", "season_name", "competition_id"],
        how="left",
    )

    corr_stats = None
    sample = enriched.dropna(subset=["champagne_index", "position"])
    if len(sample) >= 20:
        slope, intercept, r_value, p_value, _ = stats.linregress(
            sample["champagne_index"].astype(float), sample["position"].astype(float)
        )
        corr_stats = (float(r_value), float(p_value), len(sample))

    return enriched[STANDINGS_COLUMNS], corr_stats


def write_standings(conn, standings_df, corr_stats):
    with conn.cursor() as cur:
        cur.execute("DROP TABLE IF EXISTS league_standings;")
        cur.execute("""
            CREATE TABLE league_standings (
                league_code TEXT,
                competition_id TEXT,
                season_name TEXT,
                team_id INTEGER,
                team_name TEXT,
                played INTEGER,
                wins INTEGER,
                draws INTEGER,
                losses INTEGER,
                goals_for INTEGER,
                goals_against INTEGER,
                goal_diff INTEGER,
                points INTEGER,
                position INTEGER,
                champagne_index NUMERIC,
                total_spend NUMERIC
            );
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS champagne_vs_position_model (
                r_value NUMERIC,
                p_value NUMERIC,
                n_observations INTEGER,
                computed_at TIMESTAMP DEFAULT now()
            );
        """)
        cur.execute("DELETE FROM champagne_vs_position_model;")
    conn.commit()

    if standings_df.empty:
        print("[pipeline] no match_results found, skipping league_standings", flush=True)
        return

    frame = standings_df.astype(object).where(pd.notnull(standings_df), None)
    records = frame.values.tolist()
    with conn.cursor() as cur:
        execute_values(
            cur,
            f"INSERT INTO league_standings ({', '.join(STANDINGS_COLUMNS)}) VALUES %s",
            records,
        )
        if corr_stats:
            r_value, p_value, n = corr_stats
            cur.execute(
                "INSERT INTO champagne_vs_position_model (r_value, p_value, n_observations) "
                "VALUES (%s, %s, %s)",
                (r_value, p_value, n),
            )
        cur.execute(
            "CREATE INDEX IF NOT EXISTS idx_ls_league_season "
            "ON league_standings (league_code, season_name);"
        )
    conn.commit()
    print(f"[pipeline] wrote {len(standings_df):,} rows to league_standings", flush=True)


def write_results(conn, merged, model_stats):
    with conn.cursor() as cur:
        cur.execute("DROP TABLE IF EXISTS champagne_results;")
        cur.execute("""
            CREATE TABLE champagne_results (
                team_id INTEGER,
                team_name TEXT,
                season_name TEXT,
                season_key INTEGER,
                competition_id TEXT,
                competition_name TEXT,
                matches INTEGER,
                total_goals NUMERIC,
                total_assists INTEGER,
                champagne_index NUMERIC,
                total_spend NUMERIC,
                attacking_spend NUMERIC,
                delta_index NUMERIC,
                predicted_next_index NUMERIC,
                is_latest_season BOOLEAN
            );
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS champagne_model (
                slope NUMERIC,
                intercept NUMERIC,
                r_value NUMERIC,
                p_value NUMERIC,
                n_observations INTEGER,
                computed_at TIMESTAMP DEFAULT now()
            );
        """)
    conn.commit()

    frame = merged[RESULT_COLUMNS].astype(object).where(pd.notnull(merged[RESULT_COLUMNS]), None)
    records = frame.values.tolist()

    with conn.cursor() as cur:
        execute_values(
            cur,
            f"INSERT INTO champagne_results ({', '.join(RESULT_COLUMNS)}) VALUES %s",
            records,
        )
        cur.execute("DELETE FROM champagne_model;")
        slope, intercept, r_value, p_value, n = model_stats
        cur.execute(
            "INSERT INTO champagne_model (slope, intercept, r_value, p_value, n_observations) "
            "VALUES (%s, %s, %s, %s, %s)",
            (slope, intercept, r_value, p_value, n),
        )
        cur.execute(
            "CREATE INDEX IF NOT EXISTS idx_cr_team_season ON champagne_results (team_id, season_name);"
        )
    conn.commit()


def write_ml_model(conn, ml_result):
    with conn.cursor() as cur:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS champagne_model_ml (
                r2_score NUMERIC,
                n_observations INTEGER,
                feature_importances TEXT,
                computed_at TIMESTAMP DEFAULT now()
            );
        """)
        cur.execute("DELETE FROM champagne_model_ml;")
        if ml_result:
            r2, n, importances = ml_result
            cur.execute(
                "INSERT INTO champagne_model_ml (r2_score, n_observations, feature_importances) "
                "VALUES (%s, %s, %s)",
                (r2, n, json.dumps(importances)),
            )
    conn.commit()


def main():
    conn = connect()
    build_views(conn)
    reserve_youth_ids = load_reserve_youth_team_ids(conn)
    merged, model_stats = compute(conn, reserve_youth_ids)
    write_results(conn, merged, model_stats)
    slope, intercept, r_value, p_value, n = model_stats
    print(
        f"[pipeline] wrote {len(merged):,} rows to champagne_results; "
        f"trend (first-team only): slope={slope:.6g} intercept={intercept:.3f} "
        f"r={r_value:.3f} n={n}",
        flush=True,
    )

    ml_features = build_ml_features(conn, merged)
    ml_result = fit_ml_model(ml_features, reserve_youth_ids)
    write_ml_model(conn, ml_result)
    if ml_result:
        r2, n_ml, importances = ml_result
        top_feature = max(importances, key=importances.get)
        print(
            f"[pipeline] RandomForest richer-feature model: test R^2={r2:.3f} n={n_ml} "
            f"top feature={top_feature} ({importances[top_feature]:.3f})",
            flush=True,
        )
    else:
        print("[pipeline] not enough complete rows to fit the RandomForest model, skipping", flush=True)

    standings_df, corr_stats = compute_standings(conn, merged)
    write_standings(conn, standings_df, corr_stats)
    if corr_stats:
        r_value, p_value, n = corr_stats
        print(
            f"[pipeline] champagne_index vs. league position: r={r_value:.3f} "
            f"p={p_value:.4f} n={n}",
            flush=True,
        )

    conn.close()


if __name__ == "__main__":
    main()
