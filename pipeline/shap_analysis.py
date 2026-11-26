"""Analysis-only: SHAP TreeExplainer values for the attack+defense showdown
model (pipeline/compute_predictions.py's augmented RandomForest), evaluated on
its own held-out chronological test split — the same split fit_ml_model
already used to measure test R^2/MAE, so these importances describe that same
evaluation rather than a rosier in-sample fit.

Mean |SHAP value| per feature is stored alongside (not instead of) the
existing impurity-based feature_importances_ already in champagne_model_ml.
scikit-learn's Gini/impurity importance is biased toward high-cardinality
numeric features; SHAP is not — the two disagreeing is itself informative.
"""
from psycopg2.extras import execute_values


def compute(model, X_test, feature_columns):
    # Imported here, not at module level: shap is only installed in the
    # pipeline image (pipeline/requirements.txt). compute_predictions.py
    # imports this module unconditionally, and the test suite runs inside the
    # lighter app image, which never calls compute() — only write()'s DDL.
    import shap

    explainer = shap.TreeExplainer(model)
    shap_values = explainer.shap_values(X_test)
    mean_abs_shap = abs(shap_values).mean(axis=0)
    return {feature: float(value) for feature, value in zip(feature_columns, mean_abs_shap)}


def write(conn, importances, model_variant):
    with conn.cursor() as cur:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS champagne_model_shap (
                model_variant TEXT,
                feature TEXT,
                mean_abs_shap NUMERIC,
                computed_at TIMESTAMP DEFAULT now()
            );
        """)
        cur.execute("DELETE FROM champagne_model_shap WHERE model_variant = %s;", (model_variant,))
        if importances:
            execute_values(
                cur,
                "INSERT INTO champagne_model_shap (model_variant, feature, mean_abs_shap) VALUES %s",
                [(model_variant, feature, value) for feature, value in importances.items()],
            )
    conn.commit()
