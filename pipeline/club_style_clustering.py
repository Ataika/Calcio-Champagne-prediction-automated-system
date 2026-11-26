"""Extra analytics: K-Means clustering of team-seasons into "club style" archetypes
on five features — champagne_index, spend_efficiency, discipline_index,
goals_conceded_per_match, clean_sheet_rate.

First-team squads only (team_children filter, same as Issue #3), 15+ matches,
same card/goals_conceded pattern already flagged in sql/exploration.sql: lower
leagues often have zero tracked cards/goals_conceded, which K-Means picks up as
its own cluster — labelled honestly below as data-sparse, not a real tactical
style, rather than quietly presented as a finding.

Not part of the automatic `docker compose up` flow — run manually once the
stack is up:
    docker compose exec pipeline python club_style_clustering.py
"""
import os

import numpy as np
import pandas as pd
import psycopg2
from psycopg2.extras import execute_values
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler

FEATURE_COLUMNS = [
    "champagne_index", "spend_efficiency", "discipline_index",
    "goals_conceded_per_match", "clean_sheet_rate",
]

def name_clusters(data):
    """K-Means cluster indices aren't stable across runs (n_init picks whichever
    random start has the lowest inertia, which can flip the index numbering even
    with a fixed random_state) — so names must be derived from each run's actual
    centroid values, never hardcoded to an index number.
    """
    centroids = data.groupby("cluster")[FEATURE_COLUMNS + ["total_spend"]].mean()
    names = {}

    # The data-sparse cluster: near-zero defensive stats (cards + goals_conceded)
    # means that league simply isn't tracked, not that the team is disciplined/
    # defensively solid. Flag it before any spend-based ranking.
    sparsity_score = centroids["discipline_index"] + centroids["goals_conceded_per_match"]
    sparse_cluster = sparsity_score.idxmin()
    names[sparse_cluster] = "Lower-tier / data-sparse"

    remaining = centroids.drop(index=sparse_cluster).sort_values("total_spend")
    labels = ["Shoestring overachievers", "Mid-table grinders", "Big-spending elite"]
    for i, cluster_id in enumerate(remaining.index):
        names[cluster_id] = labels[min(i, len(labels) - 1)]
    return names


def connect():
    return psycopg2.connect(
        host=os.environ.get("POSTGRES_HOST", "db"),
        port=os.environ.get("POSTGRES_PORT", "5432"),
        dbname=os.environ["POSTGRES_DB"],
        user=os.environ["POSTGRES_USER"],
        password=os.environ["POSTGRES_PASSWORD"],
    )


def build_features(conn):
    champagne = pd.read_sql("SELECT * FROM champagne_results", conn)
    reserve_youth = set(
        pd.read_sql(
            "SELECT DISTINCT child_team_id FROM team_children WHERE parent_team_id <> child_team_id",
            conn,
        )["child_team_id"]
    )

    # goals_conceded_per_match and clean_sheet_rate now come straight from
    # champagne_results (champagne_index_by_team_season computes them too) —
    # only discipline_index still needs its own query.
    discipline = pd.read_sql(
        """
        SELECT team_id, season_name, competition_id,
               MAX(nb_in_group) AS matches,
               SUM(yellow_cards + second_yellow_cards + direct_red_cards) AS cards
        FROM player_performances
        GROUP BY team_id, season_name, competition_id
        """,
        conn,
    )
    discipline["discipline_index"] = discipline["cards"] / discipline["matches"].replace(0, np.nan)

    merged = champagne.merge(
        discipline[["team_id", "season_name", "competition_id", "discipline_index"]],
        on=["team_id", "season_name", "competition_id"], how="left",
    )
    merged = merged[~merged["team_id"].isin(reserve_youth)]
    merged = merged[merged["matches"] >= 15]

    merged["spend_efficiency"] = merged["champagne_index"] / (
        merged["total_spend"].replace(0, np.nan) / 1e6
    )
    merged["spend_efficiency"] = merged["spend_efficiency"].fillna(0)
    cap = merged["spend_efficiency"].quantile(0.99)
    merged["spend_efficiency"] = merged["spend_efficiency"].clip(upper=cap)

    return merged.dropna(subset=FEATURE_COLUMNS)


def cluster(data, n_clusters=4):
    X = StandardScaler().fit_transform(data[FEATURE_COLUMNS])
    km = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
    labels = km.fit_predict(X)
    data = data.copy()
    data["cluster"] = labels
    names = name_clusters(data)
    data["cluster_name"] = data["cluster"].map(names)
    return data


def write_results(conn, data):
    with conn.cursor() as cur:
        cur.execute("DROP TABLE IF EXISTS club_style_clusters;")
        cur.execute("""
            CREATE TABLE club_style_clusters (
                team_id INTEGER, team_name TEXT, season_name TEXT, competition_name TEXT,
                champagne_index NUMERIC, spend_efficiency NUMERIC, discipline_index NUMERIC,
                goals_conceded_per_match NUMERIC, clean_sheet_rate NUMERIC, total_spend NUMERIC,
                cluster INTEGER, cluster_name TEXT
            );
        """)
    conn.commit()

    cols = ["team_id", "team_name", "season_name", "competition_name", "champagne_index",
            "spend_efficiency", "discipline_index", "goals_conceded_per_match",
            "clean_sheet_rate", "total_spend", "cluster", "cluster_name"]
    frame = data[cols].astype(object).where(pd.notnull(data[cols]), None)
    with conn.cursor() as cur:
        execute_values(
            cur, f"INSERT INTO club_style_clusters ({', '.join(cols)}) VALUES %s",
            frame.values.tolist(),
        )
    conn.commit()


def main():
    conn = connect()
    data = build_features(conn)
    clustered = cluster(data)
    write_results(conn, clustered)
    print(f"[club_style_clustering] wrote {len(clustered):,} team-seasons across "
          f"{clustered['cluster'].nunique()} clusters", flush=True)
    print(clustered.groupby("cluster_name")[FEATURE_COLUMNS].mean().round(2).to_string(), flush=True)
    conn.close()


if __name__ == "__main__":
    main()
