"""Extra analytics: predicts transfer_fee from player age, position, market value
at the time of transfer, and that season's output (goals+assists per match).

Only fit on transfer_history rows where transfer_type='Transfer' and fee > 0 —
loans and free transfers never carry a fee in this dataset (see sql/exploration.sql),
so including them would just be zero-inflation noise, not signal.

Not part of the automatic `docker compose up` flow (it's a side analysis, not
something champagne_results/the dashboard depends on) — run manually once the
stack is up:
    docker compose exec pipeline python transfer_fee_model.py
"""
import json
import os

import numpy as np
import pandas as pd
import psycopg2
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.metrics import r2_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder

NUMERIC_FEATURES = ["age", "log_value", "output_per_match", "is_eu"]
CATEGORICAL_FEATURES = ["main_position"]


def connect():
    return psycopg2.connect(
        host=os.environ.get("POSTGRES_HOST", "db"),
        port=os.environ.get("POSTGRES_PORT", "5432"),
        dbname=os.environ["POSTGRES_DB"],
        user=os.environ["POSTGRES_USER"],
        password=os.environ["POSTGRES_PASSWORD"],
    )


def build_features(conn):
    transfers = pd.read_sql(
        """
        SELECT player_id, season_name, transfer_date, transfer_fee, value_at_transfer
        FROM transfer_history
        WHERE transfer_type = 'Transfer' AND transfer_fee > 0
        """,
        conn,
    )

    profiles = pd.read_sql(
        "SELECT player_id, date_of_birth, main_position, is_eu FROM player_profiles", conn
    )
    transfers = transfers.merge(profiles, on="player_id", how="left")
    transfers["age"] = (
        pd.to_datetime(transfers["transfer_date"], errors="coerce").dt.year
        - pd.to_datetime(transfers["date_of_birth"], errors="coerce").dt.year
    )

    performances = pd.read_sql(
        """
        SELECT player_id, season_name, SUM(goals) AS goals, SUM(assists) AS assists,
               MAX(nb_in_group) AS matches
        FROM player_performances GROUP BY player_id, season_name
        """,
        conn,
    )
    transfers = transfers.merge(performances, on=["player_id", "season_name"], how="left")
    transfers["output_per_match"] = (
        (transfers["goals"].fillna(0) + transfers["assists"].fillna(0))
        / transfers["matches"].replace(0, np.nan)
    ).fillna(0)

    transfers = transfers.dropna(subset=["age", "main_position", "value_at_transfer"])
    transfers = transfers[(transfers["age"] >= 15) & (transfers["age"] <= 42)]
    transfers["log_fee"] = np.log1p(transfers["transfer_fee"])
    transfers["log_value"] = np.log1p(transfers["value_at_transfer"])
    transfers["is_eu"] = transfers["is_eu"].fillna(False).astype(int)
    return transfers


def fit(transfers):
    X = transfers[NUMERIC_FEATURES + CATEGORICAL_FEATURES]
    y = transfers["log_fee"]
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

    pre = ColumnTransformer(
        [("cat", OneHotEncoder(handle_unknown="ignore"), CATEGORICAL_FEATURES)],
        remainder="passthrough",
    )
    model = Pipeline([
        ("pre", pre),
        ("gbm", GradientBoostingRegressor(n_estimators=300, max_depth=3, random_state=42)),
    ])
    model.fit(X_train, y_train)
    r2 = float(r2_score(y_test, model.predict(X_test)))

    gbm = model.named_steps["gbm"]
    cat_names = list(
        model.named_steps["pre"].named_transformers_["cat"].get_feature_names_out(CATEGORICAL_FEATURES)
    )
    all_names = cat_names + NUMERIC_FEATURES
    importances = dict(zip(all_names, gbm.feature_importances_.astype(float)))
    return r2, len(transfers), importances


def write_results(conn, r2, n, importances):
    with conn.cursor() as cur:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS transfer_fee_model (
                r2_score NUMERIC,
                n_observations INTEGER,
                feature_importances TEXT,
                computed_at TIMESTAMP DEFAULT now()
            );
        """)
        cur.execute("DELETE FROM transfer_fee_model;")
        cur.execute(
            "INSERT INTO transfer_fee_model (r2_score, n_observations, feature_importances) "
            "VALUES (%s, %s, %s)",
            (r2, n, json.dumps(importances)),
        )
    conn.commit()


def main():
    conn = connect()
    transfers = build_features(conn)
    r2, n, importances = fit(transfers)
    write_results(conn, r2, n, importances)
    top_feature = max(importances, key=importances.get)
    print(
        f"[transfer_fee_model] test R^2 (log-fee)={r2:.3f} n={n} "
        f"top feature={top_feature} ({importances[top_feature]:.3f})",
        flush=True,
    )
    conn.close()


if __name__ == "__main__":
    main()
