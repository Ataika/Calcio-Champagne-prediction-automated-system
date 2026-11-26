"""PROCESS step: does a red card in a match measurably raise that match's
conceded-goal rate for the team that was sent off? Uses real match-level red
cards (home_red/away_red in match_results), not the player_performances
season-aggregate discipline_index used elsewhere — a genuine within-match
"man down" test, globally and per league, via a two-sample comparison
(scipy.stats.ttest_ind, the same statistic already used throughout this
pipeline's other pairwise tests).
"""
import pandas as pd
from psycopg2.extras import execute_values
from scipy import stats

MIN_GROUP_SIZE = 20


def compute(conn):
    matches = pd.read_sql("""
        SELECT league_code, home_goals, away_goals, home_red, away_red
        FROM match_results
        WHERE home_goals IS NOT NULL AND away_goals IS NOT NULL
          AND home_red IS NOT NULL AND away_red IS NOT NULL
    """, conn)
    if matches.empty:
        return []

    home = matches.rename(columns={"away_goals": "conceded", "home_red": "red_cards"})[
        ["league_code", "conceded", "red_cards"]]
    away = matches.rename(columns={"home_goals": "conceded", "away_red": "red_cards"})[
        ["league_code", "conceded", "red_cards"]]
    long = pd.concat([home, away], ignore_index=True)
    long["sent_off"] = long["red_cards"] > 0

    rows = []
    for league_code, group in [("ALL", long)] + list(long.groupby("league_code")):
        with_red = group.loc[group["sent_off"], "conceded"]
        without_red = group.loc[~group["sent_off"], "conceded"]
        if len(with_red) < MIN_GROUP_SIZE or len(without_red) < MIN_GROUP_SIZE:
            continue
        t_stat, p_value = stats.ttest_ind(with_red, without_red, equal_var=False)
        rows.append({
            "league_code": league_code,
            "mean_conceded_with_red": round(float(with_red.mean()), 3),
            "mean_conceded_without_red": round(float(without_red.mean()), 3),
            "difference": round(float(with_red.mean() - without_red.mean()), 3),
            "n_with_red": int(len(with_red)), "n_without_red": int(len(without_red)),
            "t_statistic": round(float(t_stat), 3), "p_value": float(p_value),
        })
    return rows


def write(conn, rows):
    with conn.cursor() as cur:
        cur.execute("DROP TABLE IF EXISTS discipline_match_effect;")
        cur.execute("""
            CREATE TABLE discipline_match_effect (
                league_code TEXT,
                mean_conceded_with_red NUMERIC,
                mean_conceded_without_red NUMERIC,
                difference NUMERIC,
                n_with_red INTEGER,
                n_without_red INTEGER,
                t_statistic NUMERIC,
                p_value NUMERIC
            );
        """)
        if rows:
            execute_values(
                cur,
                "INSERT INTO discipline_match_effect (league_code, mean_conceded_with_red, "
                "mean_conceded_without_red, difference, n_with_red, n_without_red, t_statistic, p_value) VALUES %s",
                [(r["league_code"], r["mean_conceded_with_red"], r["mean_conceded_without_red"], r["difference"],
                  r["n_with_red"], r["n_without_red"], r["t_statistic"], r["p_value"]) for r in rows],
            )
    conn.commit()
