"""PROCESS step: a full pairwise correlation matrix across every attack, defense,
discipline, spend and squad-value feature the pipeline computes, plus each
feature's correlation against the two things the project actually cares about —
next-season delta_index and real league position. Today's codebase only ever
computes two ad-hoc pairwise fits (spend->delta_index in compute(), index->position
in compute_standings()); this is the single place that answers "which of our
features actually relates to anything" in one pass, and flags near-duplicate
features (|r| > 0.9) so a later SHAP/importance pass isn't misled by splitting
importance across two columns that are really the same signal.

Not a model — plain Pearson correlation, same statistic already used everywhere
else in this pipeline (scipy.stats).
"""
from scipy import stats

COLLINEARITY_THRESHOLD = 0.9
MIN_PAIR_OBSERVATIONS = 20

# Every candidate feature the correlation matrix considers, if present on the
# frame passed in. Deliberately includes both attack and defense signals side
# by side — the whole point is not defaulting to attack-only comparisons.
CANDIDATE_FEATURES = [
    "champagne_index", "net_index", "goals_conceded_per_match", "clean_sheet_rate",
    "discipline_index", "total_spend", "attacking_spend", "midfield_spend",
    "defensive_spend", "goalkeeper_spend", "total_sales", "net_spend",
    "squad_avg_age", "squad_avg_value", "market_value_change",
]
TARGET_COLUMNS = ["delta_index", "position"]


def compute(frame):
    """`frame` is one row per team-season-competition with as many of
    CANDIDATE_FEATURES/TARGET_COLUMNS already merged onto it as the caller has
    available (main() merges league position in before calling this)."""
    available = [c for c in CANDIDATE_FEATURES if c in frame.columns]
    pairs = []
    for i, feature_a in enumerate(available):
        for feature_b in available[i + 1:]:
            sub = frame[[feature_a, feature_b]].dropna()
            if len(sub) < MIN_PAIR_OBSERVATIONS:
                continue
            r, _p = stats.pearsonr(sub[feature_a].astype(float), sub[feature_b].astype(float))
            r = float(r)
            if r != r:  # NaN — e.g. one column is constant in this sample
                continue
            pairs.append({
                "feature_a": feature_a, "feature_b": feature_b, "r": r, "n": len(sub),
                "collinear": bool(abs(r) > COLLINEARITY_THRESHOLD),
            })

    targets = []
    for target in TARGET_COLUMNS:
        if target not in frame.columns:
            continue
        for feature in available:
            sub = frame[[feature, target]].dropna()
            if len(sub) < MIN_PAIR_OBSERVATIONS:
                targets.append({"feature": feature, "target": target, "r": None, "p": None, "n": len(sub)})
                continue
            r, p = stats.pearsonr(sub[feature].astype(float), sub[target].astype(float))
            targets.append({
                "feature": feature, "target": target,
                "r": None if r != r else float(r), "p": None if p != p else float(p), "n": len(sub),
            })

    return pairs, targets


def write(conn, pairs, targets):
    with conn.cursor() as cur:
        cur.execute("DROP TABLE IF EXISTS feature_correlation_matrix;")
        cur.execute("""
            CREATE TABLE feature_correlation_matrix (
                feature_a TEXT,
                feature_b TEXT,
                r_value NUMERIC,
                n_observations INTEGER,
                collinear BOOLEAN,
                computed_at TIMESTAMP DEFAULT now()
            );
        """)
        cur.execute("DROP TABLE IF EXISTS feature_correlation_targets;")
        cur.execute("""
            CREATE TABLE feature_correlation_targets (
                feature TEXT,
                target TEXT,
                r_value NUMERIC,
                p_value NUMERIC,
                n_observations INTEGER,
                computed_at TIMESTAMP DEFAULT now()
            );
        """)
        for pair in pairs:
            cur.execute(
                "INSERT INTO feature_correlation_matrix (feature_a, feature_b, r_value, n_observations, collinear) "
                "VALUES (%s, %s, %s, %s, %s)",
                (pair["feature_a"], pair["feature_b"], pair["r"], int(pair["n"]), bool(pair["collinear"])),
            )
        for row in targets:
            cur.execute(
                "INSERT INTO feature_correlation_targets (feature, target, r_value, p_value, n_observations) "
                "VALUES (%s, %s, %s, %s, %s)",
                (row["feature"], row["target"], row["r"], row["p"], int(row["n"])),
            )
    conn.commit()
