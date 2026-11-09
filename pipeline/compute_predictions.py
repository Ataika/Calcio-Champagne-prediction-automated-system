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
from datetime import datetime, timezone
from pathlib import Path

import joblib
import pandas as pd
import psycopg2
from psycopg2.extras import execute_values
from scipy import stats
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error, r2_score

try:
    from . import discipline_effect, feature_correlations, power_ratings, proxy_xg, shap_analysis
except ImportError:
    import discipline_effect
    import feature_correlations
    import power_ratings
    import proxy_xg
    import shap_analysis

MODELS_DIR = "/models"

RESULT_COLUMNS = [
    "team_id", "team_name", "season_name", "season_key", "competition_id",
    "competition_name", "matches", "total_goals", "total_assists",
    "total_goals_conceded", "total_clean_sheets", "goals_conceded_per_match",
    "clean_sheet_rate", "net_index",
    "champagne_index", "total_spend", "attacking_spend", "midfield_spend",
    "defensive_spend", "goalkeeper_spend", "total_sales", "net_spend",
    "delta_index", "predicted_next_index", "is_latest_season",
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
                application_name="calcio_pipeline",
                options="-c work_mem=64MB -c jit=off",
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
    spend_cols = ["total_spend", "attacking_spend", "midfield_spend", "defensive_spend",
                  "goalkeeper_spend", "total_sales", "net_spend"]
    merged[spend_cols] = merged[spend_cols].fillna(0)
    merged[["total_goals_conceded", "total_clean_sheets", "goals_conceded_per_match",
            "clean_sheet_rate"]] = merged[["total_goals_conceded", "total_clean_sheets",
            "goals_conceded_per_match", "clean_sheet_rate"]].fillna(0)
    # Computed from raw totals rather than the two already-rounded view columns
    # (champagne_index, goals_conceded_per_match), so net_index isn't a difference
    # of two independently rounded numbers.
    match_count = merged["matches"].astype(float)
    net_raw = (
        merged["total_goals"] + merged["total_assists"] - merged["total_goals_conceded"]
    ) / match_count
    merged["net_index"] = net_raw.where(match_count > 0).round(2)

    merged = merged.sort_values(["team_id", "competition_id", "season_key"])
    group = merged.groupby(["team_id", "competition_id"])
    merged["next_champagne_index"] = group["champagne_index"].shift(-1)
    merged["next_goals_conceded_per_match"] = group["goals_conceded_per_match"].shift(-1)
    merged["next_season_key"] = group["season_key"].shift(-1)
    merged["next_matches"] = group["matches"].shift(-1)
    # A return after relegation is not "next season". Partial snapshots must not
    # become targets for a full-season model (25/26 has only 2–4 league matches).
    minimum = merged["competition_id"].isin(LEAGUE_TO_COMPETITION.values()).map({True: 30, False: 5})
    valid_pair = (
        (merged["next_season_key"] == merged["season_key"] + 1)
        & (merged["matches"].fillna(0) >= minimum)
        & (merged["next_matches"].fillna(0) >= minimum)
    )
    merged["delta_index"] = (merged["next_champagne_index"] - merged["champagne_index"]).where(valid_pair)
    # Defensive mirror of delta_index: does this season's conceded-goals rate
    # improve or worsen next season? Lower is better, so this is the quantity
    # defensive_spend is tested against below (the sign is flipped from delta_index).
    merged["delta_goals_conceded_per_match"] = (
        merged["next_goals_conceded_per_match"] - merged["goals_conceded_per_match"]
    ).where(valid_pair)
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

    # Defensive mirror of the spend->delta_index trend above: does spending on
    # defenders predict a *drop* in next-season goals conceded per match? Same
    # eligibility filter (train), different target column.
    defense_train = train.dropna(subset=["delta_goals_conceded_per_match"])
    if len(defense_train) >= 20:
        d_slope, d_intercept, d_r, d_p, _ = stats.linregress(
            defense_train["defensive_spend"].astype(float),
            defense_train["delta_goals_conceded_per_match"].astype(float),
        )
    else:
        d_slope, d_intercept, d_r, d_p = 0.0, 0.0, 0.0, 1.0
    defense_spend_model = (float(d_slope), float(d_intercept), float(d_r), float(d_p), len(defense_train))

    return merged, (float(slope), float(intercept), float(r_value), float(p_value), len(train)), defense_spend_model


ML_FEATURE_COLUMNS = ["champagne_index", "total_spend", "attacking_spend", "squad_avg_age", "market_value_change"]
# Attack-only (above) vs. attack+defense: same five inputs plus goals conceded,
# discipline and net spend. Evaluation-only — the Lab still serves the deployed
# ML_FEATURE_COLUMNS model so its documented contract (docs/LAB.md) is unchanged.
ML_FEATURE_COLUMNS_AUGMENTED = ML_FEATURE_COLUMNS + ["goals_conceded_per_match", "discipline_index", "net_spend"]


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

    # One latest observation per player/calendar year. Otherwise players with
    # more valuation snapshots receive more weight in a team's squad average.
    market_values = pd.read_sql("""
        SELECT DISTINCT ON (player_id, EXTRACT(YEAR FROM date_unix))
               player_id, EXTRACT(YEAR FROM date_unix)::integer AS season_key, value
        FROM player_market_value
        WHERE value IS NOT NULL
        ORDER BY player_id, EXTRACT(YEAR FROM date_unix), date_unix DESC
    """, conn)
    roster_mv = roster[["team_id", "season_name", "player_id", "season_key"]].merge(
        market_values, on=["player_id", "season_key"], how="left"
    )
    mv_by_team_season = (
        roster_mv.groupby(["team_id", "season_name"])["value"].mean()
        .reset_index().rename(columns={"value": "squad_avg_value"})
    )

    # Compute lag BEFORE joining competition rows. Shifting after the join used
    # another competition in the same season as the "previous season".
    squad = age_by_team_season.merge(mv_by_team_season, on=["team_id", "season_name"], how="left")
    squad["season_key"] = squad["season_name"].apply(season_sort_key)
    previous = squad[["team_id", "season_key", "squad_avg_value"]].copy()
    previous["season_key"] += 1
    previous = previous.rename(columns={"squad_avg_value": "prev_squad_avg_value"})
    squad = squad.merge(previous, on=["team_id", "season_key"], how="left", validate="one_to_one")
    squad["market_value_change"] = squad["squad_avg_value"] - squad["prev_squad_avg_value"]
    return merged.merge(squad.drop(columns="season_key"), on=["team_id", "season_name"], how="left", validate="many_to_one")


def build_discipline_index(conn):
    """Cards per match, per team-season-competition — the same query
    club_style_clustering.py uses, pulled out here so compute_predictions.py
    can also feed discipline_index into the augmented model (fit_ml_model)
    and the feature correlation matrix without a third copy of this SQL."""
    discipline = pd.read_sql("""
        SELECT team_id, season_name, competition_id,
               MAX(nb_in_group) AS matches,
               SUM(yellow_cards + second_yellow_cards + direct_red_cards) AS cards
        FROM player_performances
        GROUP BY team_id, season_name, competition_id
    """, conn)
    discipline["discipline_index"] = discipline["cards"] / discipline["matches"].replace(0, float("nan"))
    return discipline[["team_id", "season_name", "competition_id", "discipline_index"]]


def fit_ml_model(features, reserve_youth_ids, feature_columns=ML_FEATURE_COLUMNS):
    """RandomForestRegressor predicting next-season champagne_index change from
    `feature_columns`, vs. the single-feature linear baseline in compute().
    Called twice from main(): once with the deployed 5-feature set
    (ML_FEATURE_COLUMNS, unchanged — this is the model the Lab serves), once
    with ML_FEATURE_COLUMNS_AUGMENTED to test whether adding defense/discipline
    features actually helps (the attack-only vs. attack+defense showdown)."""
    train = features.dropna(subset=["delta_index"])
    train = train[train["matches"].fillna(0) >= 5]
    train = train[~train["team_id"].isin(reserve_youth_ids)]
    train = train.dropna(subset=feature_columns)

    if len(train) < 50:
        return None

    X = train[feature_columns].astype(float)
    y = train["delta_index"].astype(float)
    # Hold out recent seasons together; never randomly mix future and past.
    cutoff = int(train["season_key"].quantile(0.8))
    earlier = train["season_key"] < cutoff
    if earlier.sum() < 30 or (~earlier).sum() < 10:
        return None
    X_train, X_test, y_train, y_test = X[earlier], X[~earlier], y[earlier], y[~earlier]
    model = RandomForestRegressor(n_estimators=200, max_depth=6, random_state=42, n_jobs=-1)
    model.fit(X_train, y_train)
    predictions = model.predict(X_test)
    r2 = float(r2_score(y_test, predictions))
    importances = dict(zip(feature_columns, model.feature_importances_.astype(float)))

    # Separate model trained on ALL available rows (not just the train split) for
    # the Lab tab's live predictions — the R^2 above is still measured on the
    # held-out test split, this one is just for best real-world inference.
    deploy_model = RandomForestRegressor(n_estimators=200, max_depth=6, random_state=42, n_jobs=-1)
    deploy_model.fit(X, y)
    feature_ranges = {
        col: {"min": float(X[col].min()), "median": float(X[col].median()), "max": float(X[col].max()),
              "p01": float(X[col].quantile(0.01)), "p99": float(X[col].quantile(0.99))}
        for col in feature_columns
    }
    evaluation = {
        "split": "chronological season holdout", "test_from_season": cutoff,
        "train_rows": int(earlier.sum()), "test_rows": int((~earlier).sum()),
        "mae": float(mean_absolute_error(y_test, predictions)),
        "baseline_mae": float(mean_absolute_error(y_test, [0.0] * len(y_test))),
        "baseline_r2": float(r2_score(y_test, [0.0] * len(y_test))),
        "target": "next consecutive season index minus current index",
        "seed": 42, "n_estimators": 200, "max_depth": 6,
    }
    # model/X_test appended at the end (not inserted) so existing positional
    # unpacks of the first six elements, and tests indexing by position
    # (e.g. evaluation == result[5]), keep working unchanged.
    return r2, len(train), importances, deploy_model, feature_ranges, evaluation, model, X_test


def save_lab_model(model, feature_ranges, evaluation):
    """Persists the fitted RandomForest (not just its score) to a shared volume
    so the dashboard's Lab tab can load it and predict on arbitrary user input
    without the app container needing its own copy of the training pipeline."""
    os.makedirs(MODELS_DIR, exist_ok=True)
    temporary = os.path.join(MODELS_DIR, "champagne_rf_model.joblib.tmp")
    joblib.dump(
        {"model": model, "feature_cols": ML_FEATURE_COLUMNS, "feature_ranges": feature_ranges,
         "evaluation": evaluation},
        temporary,
    )
    os.replace(temporary, os.path.join(MODELS_DIR, "champagne_rf_model.joblib"))


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
        return pd.DataFrame(columns=STANDINGS_COLUMNS), None, [], pd.DataFrame()

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

    # Home/away split (Issue: home advantage isn't broken out anywhere else) —
    # same home/away frames as the combined table below, grouped before they're
    # concatenated together.
    home_split = home.groupby(["league_code", "season_name", "team_id"]).agg(
        home_played=("win", "size"), home_goals_for=("goals_for", "sum"), home_goals_against=("goals_against", "sum"),
    ).reset_index()
    away_split = away.groupby(["league_code", "season_name", "team_id"]).agg(
        away_played=("win", "size"), away_goals_for=("goals_for", "sum"), away_goals_against=("goals_against", "sum"),
    ).reset_index()
    home_away = home_split.merge(away_split, on=["league_code", "season_name", "team_id"], how="outer")
    home_away["competition_id"] = home_away["league_code"].map(LEAGUE_TO_COMPETITION)
    for venue in ("home", "away"):
        played = home_away[f"{venue}_played"].replace(0, float("nan"))
        home_away[f"{venue}_goals_for_per_match"] = (home_away[f"{venue}_goals_for"] / played).round(2)
        home_away[f"{venue}_goals_against_per_match"] = (home_away[f"{venue}_goals_against"] / played).round(2)

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

    # Do not correlate a partial Transfermarkt season with a final league table.
    coverage = champagne_results[["team_id", "season_name", "competition_id", "matches"]]
    enriched = enriched.merge(coverage, on=["team_id", "season_name", "competition_id"], how="left")
    comparable = (enriched["played"] >= 30) & (enriched["matches"] >= 0.8 * enriched["played"])
    enriched.loc[~comparable, "champagne_index"] = float("nan")
    corr_stats = None
    sample = enriched.dropna(subset=["champagne_index", "position"]).copy()
    if len(sample) >= 20:
        slope, intercept, r_value, p_value, _ = stats.linregress(
            sample["champagne_index"].astype(float), sample["position"].astype(float)
        )
        corr_stats = (float(r_value), float(p_value), len(sample), float(slope), float(intercept))

    # Horserace (Issue: which single number actually predicts final position
    # best — the attacking-only index, real goal difference, or points?). Same
    # `sample` rows for all three, so n is directly comparable across metrics.
    sample["goal_diff_per_match"] = sample["goal_diff"] / sample["played"].replace(0, float("nan"))
    sample["points_per_match"] = sample["points"] / sample["played"].replace(0, float("nan"))
    predictor_comparison = []
    for metric in ("champagne_index", "goal_diff_per_match", "points_per_match"):
        sub = sample.dropna(subset=[metric, "position"])
        if len(sub) >= 20:
            _, _, r, p, _ = stats.linregress(sub[metric].astype(float), sub["position"].astype(float))
            predictor_comparison.append({"metric": metric, "r": float(r), "p": float(p), "n": len(sub)})
        else:
            predictor_comparison.append({"metric": metric, "r": None, "p": None, "n": len(sub)})

    return enriched[STANDINGS_COLUMNS], corr_stats, predictor_comparison, home_away


HOME_AWAY_COLUMNS = [
    "league_code", "competition_id", "season_name", "team_id",
    "home_played", "home_goals_for_per_match", "home_goals_against_per_match",
    "away_played", "away_goals_for_per_match", "away_goals_against_per_match",
]


def write_standings(conn, standings_df, corr_stats, predictor_comparison, home_away_df):
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
        cur.execute("DROP TABLE IF EXISTS champagne_vs_position_model;")
        cur.execute("""
            CREATE TABLE champagne_vs_position_model (
                r_value NUMERIC,
                p_value NUMERIC,
                n_observations INTEGER,
                slope NUMERIC,
                intercept NUMERIC,
                computed_at TIMESTAMP DEFAULT now()
            );
        """)
        cur.execute("DROP TABLE IF EXISTS position_predictor_comparison;")
        cur.execute("""
            CREATE TABLE position_predictor_comparison (
                metric TEXT,
                r_value NUMERIC,
                p_value NUMERIC,
                n_observations INTEGER,
                computed_at TIMESTAMP DEFAULT now()
            );
        """)
        cur.execute("DROP TABLE IF EXISTS home_away_splits;")
        cur.execute("""
            CREATE TABLE home_away_splits (
                league_code TEXT,
                competition_id TEXT,
                season_name TEXT,
                team_id INTEGER,
                home_played INTEGER,
                home_goals_for_per_match NUMERIC,
                home_goals_against_per_match NUMERIC,
                away_played INTEGER,
                away_goals_for_per_match NUMERIC,
                away_goals_against_per_match NUMERIC
            );
        """)
        for metric, r_value, p_value, n in (
            (m["metric"], m["r"], m["p"], m["n"]) for m in predictor_comparison
        ):
            cur.execute(
                "INSERT INTO position_predictor_comparison (metric, r_value, p_value, n_observations) "
                "VALUES (%s, %s, %s, %s)",
                (metric, r_value, p_value, n),
            )
        if not home_away_df.empty:
            home_away_frame = home_away_df[HOME_AWAY_COLUMNS].astype(object).where(
                pd.notnull(home_away_df[HOME_AWAY_COLUMNS]), None
            )
            execute_values(
                cur,
                f"INSERT INTO home_away_splits ({', '.join(HOME_AWAY_COLUMNS)}) VALUES %s",
                home_away_frame.values.tolist(),
            )
            cur.execute(
                "CREATE INDEX IF NOT EXISTS idx_has_team_season "
                "ON home_away_splits (team_id, season_name, competition_id);"
            )
    if standings_df.empty:
        conn.commit()
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
            r_value, p_value, n, slope, intercept = corr_stats
            cur.execute(
                "INSERT INTO champagne_vs_position_model "
                "(r_value, p_value, n_observations, slope, intercept) VALUES (%s, %s, %s, %s, %s)",
                (r_value, p_value, n, slope, intercept),
            )
        cur.execute(
            "CREATE INDEX IF NOT EXISTS idx_ls_league_season "
            "ON league_standings (league_code, season_name);"
        )
    conn.commit()
    print(f"[pipeline] wrote {len(standings_df):,} rows to league_standings", flush=True)


def write_results(conn, merged, model_stats, defense_spend_model_stats):
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
                total_goals_conceded NUMERIC,
                total_clean_sheets NUMERIC,
                goals_conceded_per_match NUMERIC,
                clean_sheet_rate NUMERIC,
                net_index NUMERIC,
                champagne_index NUMERIC,
                total_spend NUMERIC,
                attacking_spend NUMERIC,
                midfield_spend NUMERIC,
                defensive_spend NUMERIC,
                goalkeeper_spend NUMERIC,
                total_sales NUMERIC,
                net_spend NUMERIC,
                delta_index NUMERIC,
                predicted_next_index NUMERIC,
                is_latest_season BOOLEAN,
                PRIMARY KEY (team_id, season_name, competition_id)
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
        cur.execute("""
            CREATE TABLE IF NOT EXISTS defense_spend_model (
                slope NUMERIC,
                intercept NUMERIC,
                r_value NUMERIC,
                p_value NUMERIC,
                n_observations INTEGER,
                computed_at TIMESTAMP DEFAULT now()
            );
        """)
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
        cur.execute("DELETE FROM defense_spend_model;")
        d_slope, d_intercept, d_r, d_p, d_n = defense_spend_model_stats
        cur.execute(
            "INSERT INTO defense_spend_model (slope, intercept, r_value, p_value, n_observations) "
            "VALUES (%s, %s, %s, %s, %s)",
            (d_slope, d_intercept, d_r, d_p, d_n),
        )
        cur.execute(
            "CREATE INDEX IF NOT EXISTS idx_cr_team_season ON champagne_results (team_id, season_name);"
        )
    conn.commit()


def write_ml_model(conn, ml_result, augmented_result=None):
    """Writes the deployed attack-only model (unchanged row shape/behavior —
    the Lab and docs/LAB.md's documented numbers read this), plus, when given,
    a second row for the attack+defense showdown model under
    model_variant='attack_defense'. Never both NULL/omitted at once so a
    caller that only ever asks for `model_variant='attack_only'` keeps
    working exactly as before."""
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
        cur.execute("ALTER TABLE champagne_model_ml ADD COLUMN IF NOT EXISTS evaluation TEXT;")
        cur.execute("ALTER TABLE champagne_model_ml ADD COLUMN IF NOT EXISTS model_variant TEXT DEFAULT 'attack_only';")
        if ml_result:
            r2, n, importances, _model, _ranges, evaluation, *_eval = ml_result
            cur.execute(
                "INSERT INTO champagne_model_ml (r2_score, n_observations, feature_importances, evaluation, model_variant) "
                "VALUES (%s, %s, %s, %s, 'attack_only')",
                (r2, n, json.dumps(importances), json.dumps(evaluation)),
            )
        if augmented_result:
            r2, n, importances, _model, _ranges, evaluation, *_eval = augmented_result
            cur.execute(
                "INSERT INTO champagne_model_ml (r2_score, n_observations, feature_importances, evaluation, model_variant) "
                "VALUES (%s, %s, %s, %s, 'attack_defense')",
                (r2, n, json.dumps(importances), json.dumps(evaluation)),
            )
    conn.commit()


def write_lab_features(conn, features):
    """Persist real club/season inputs so the UI never silently substitutes medians."""
    cols = ["team_id", "season_name", "competition_id"] + ML_FEATURE_COLUMNS
    with conn.cursor() as cur:
        cur.execute("DROP TABLE IF EXISTS lab_team_features;")
        cur.execute("""CREATE TABLE lab_team_features (
            team_id INTEGER, season_name TEXT, competition_id TEXT,
            champagne_index NUMERIC, total_spend NUMERIC, attacking_spend NUMERIC,
            squad_avg_age NUMERIC, market_value_change NUMERIC,
            PRIMARY KEY (team_id, season_name, competition_id)
        );""")
        frame = features[cols].astype(object).where(pd.notnull(features[cols]), None)
        execute_values(cur, f"INSERT INTO lab_team_features ({', '.join(cols)}) VALUES %s", frame.values.tolist())
    conn.commit()


def main():
    started = time.perf_counter()
    conn = connect()
    build_views(conn)
    reserve_youth_ids = load_reserve_youth_team_ids(conn)
    merged, model_stats, defense_spend_model_stats = compute(conn, reserve_youth_ids)
    aggregation_elapsed = time.perf_counter() - started
    write_results(conn, merged, model_stats, defense_spend_model_stats)
    slope, intercept, r_value, p_value, n = model_stats
    d_slope, d_intercept, d_r, d_p, d_n = defense_spend_model_stats
    print(
        f"[pipeline] wrote {len(merged):,} rows to champagne_results; "
        f"trend (first-team only): slope={slope:.6g} intercept={intercept:.3f} "
        f"r={r_value:.3f} n={n}; "
        f"defensive-spend trend: slope={d_slope:.6g} r={d_r:.3f} n={d_n}",
        flush=True,
    )

    ml_started = time.perf_counter()
    ml_features = build_ml_features(conn, merged)
    discipline = build_discipline_index(conn)
    ml_features = ml_features.merge(discipline, on=["team_id", "season_name", "competition_id"], how="left")
    write_lab_features(conn, ml_features)
    ml_result = fit_ml_model(ml_features, reserve_youth_ids)
    # Evaluation-only showdown: does adding defense/discipline/net-spend features
    # to the exact same inputs actually improve the test R^2? The deployed Lab
    # model above (ml_result) is unaffected either way.
    augmented_result = fit_ml_model(ml_features, reserve_youth_ids, feature_columns=ML_FEATURE_COLUMNS_AUGMENTED)
    write_ml_model(conn, ml_result, augmented_result)
    if ml_result:
        r2, n_ml, importances, deploy_model, feature_ranges, evaluation, *_eval = ml_result
        top_feature = max(importances, key=importances.get)
        print(
            f"[pipeline] RandomForest richer-feature model: test R^2={r2:.3f} n={n_ml} "
            f"top feature={top_feature} ({importances[top_feature]:.3f})",
            flush=True,
        )
        save_lab_model(deploy_model, feature_ranges, evaluation)
        print(f"[pipeline] saved Lab model to {MODELS_DIR}/champagne_rf_model.joblib", flush=True)
    else:
        print("[pipeline] not enough complete rows to fit the RandomForest model, skipping", flush=True)
    if augmented_result:
        aug_r2, aug_n, _imp, _m, _r, _e, aug_eval_model, aug_X_test = augmented_result
        base_r2 = ml_result[0] if ml_result else float("nan")
        print(
            f"[pipeline] attack-only vs. attack+defense showdown: "
            f"attack-only R^2={base_r2:.3f} attack+defense R^2={aug_r2:.3f} n={aug_n}",
            flush=True,
        )
        # SHAP on the exact held-out test split already used for the R^2 above —
        # same evaluation, not a rosier in-sample explanation (Issue: SHAP pass).
        shap_importances = shap_analysis.compute(aug_eval_model, aug_X_test, ML_FEATURE_COLUMNS_AUGMENTED)
        shap_analysis.write(conn, shap_importances, "attack_defense")
        top_shap = max(shap_importances, key=shap_importances.get)
        print(f"[pipeline] SHAP on attack+defense model: top feature={top_shap} "
              f"(mean|SHAP|={shap_importances[top_shap]:.4f})", flush=True)

    ml_elapsed = time.perf_counter() - ml_started
    standings_started = time.perf_counter()
    standings_df, corr_stats, predictor_comparison, home_away_df = compute_standings(conn, merged)
    write_standings(conn, standings_df, corr_stats, predictor_comparison, home_away_df)
    if corr_stats:
        r_value, p_value, n, _slope, _intercept = corr_stats
        print(
            f"[pipeline] champagne_index vs. league position: r={r_value:.3f} "
            f"p={p_value:.4f} n={n}",
            flush=True,
        )

    # Full feature correlation matrix + collinearity flags (Issue: 20 ideas —
    # correlation/SHAP/importance analysis "to our features in all dataset").
    # Needs real league position, which only exists once standings are computed.
    correlation_frame = ml_features
    if not standings_df.empty:
        correlation_frame = ml_features.merge(
            standings_df[["team_id", "season_name", "competition_id", "position"]],
            on=["team_id", "season_name", "competition_id"], how="left",
        )
    pairs, targets = feature_correlations.compute(correlation_frame)
    feature_correlations.write(conn, pairs, targets)
    dropped = [p for p in pairs if p["collinear"]]
    print(f"[pipeline] feature correlation matrix: {len(pairs)} pairs, "
          f"{len(dropped)} flagged collinear (|r|>{feature_correlations.COLLINEARITY_THRESHOLD})", flush=True)

    # Attack/defense power ratings (Issue #1), proxy-xG/finishing luck (#3/#4)
    # and the red-card-vs-conceded-goals effect (#11) — all built from real
    # match_results, all optional/skip-quietly if the enrichment isn't loaded.
    ratings_df = power_ratings.compute(conn)
    power_ratings.write(conn, ratings_df)
    print(f"[pipeline] power ratings: {ratings_df['team_id'].nunique() if not ratings_df.empty else 0} "
          f"team-seasons across {ratings_df[['league_code', 'season_name']].drop_duplicates().shape[0] if not ratings_df.empty else 0} league-seasons",
          flush=True)

    proxy_xg_df = proxy_xg.compute(conn)
    proxy_xg.write(conn, proxy_xg_df)
    print(f"[pipeline] proxy-xG: {len(proxy_xg_df):,} team-seasons", flush=True)

    discipline_rows = discipline_effect.compute(conn)
    discipline_effect.write(conn, discipline_rows)
    print(f"[pipeline] red-card effect: {len(discipline_rows)} league groups", flush=True)

    conn.close()
    output = Path(os.getenv("RESULTS_DIR", "/results"))
    if output.is_dir():
        payload = {"measured_at": datetime.now(timezone.utc).isoformat(),
                   "aggregation_seconds": aggregation_elapsed, "ml_seconds": ml_elapsed,
                   "standings_seconds": time.perf_counter() - standings_started,
                   "full_seconds": time.perf_counter() - started}
        (output / "pipeline.json").write_text(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
