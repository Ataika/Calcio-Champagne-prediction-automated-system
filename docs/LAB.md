# The Lab tab

An interactive "what would this team-season look like" playground in the
dashboard — drag sliders for a hypothetical (or real) team, get a live
prediction. Built to make the model tangible rather than just a number in a
README, so a non-technical visitor has something to click and learn from.

## How it works

1. **Training** (`pipeline/compute_predictions.py::fit_ml_model`) fits the
   same `RandomForestRegressor` as Issue #3's richer model, on the five
   features in `ML_FEATURE_COLUMNS` (`champagne_index`, `total_spend`,
   `attacking_spend`, `squad_avg_age`, `market_value_change`), predicting
   `delta_index` (next season's Champagne Index minus this season's).

2. **Two models get fit, not one**: the first is trained on an 80/20 split
   specifically so its score on the held-out 20% is an honest R² (currently
   ≈0.15 — a real but modest signal, reported in `champagne_model_ml`). The
   second is retrained on **all** available rows — a better model for actual
   predictions, but its score can't be honestly reported (it already saw
   that data), so its R² is never quoted, only the held-out one is.
   See `save_lab_model` / `fit_ml_model` in `compute_predictions.py`.

3. **Persistence**: the all-data model is pickled with `joblib` to
   `/models/champagne_rf_model.joblib`, a bind-mounted directory shared
   between the `pipeline` and `app` containers (`./models` on the host —
   gitignored, regenerated every pipeline run, same pattern as
   `measure/results/results.json`). The bundle also stores the exact
   feature column order and each feature's observed min/median/max, so the
   dashboard can build sensible slider ranges without a second DB query.

4. **Inference** (`app/dashboard.py`, `tab_lab`): loads the joblib bundle
   with `@st.cache_resource`, builds a one-row DataFrame from the slider
   values (column order must match `lab["feature_cols"]` — the bundle
   carries this on purpose so a future refactor of the feature list can't
   silently misalign model input), and calls `.predict()`.

5. **League position estimate**: a second, much rougher step. The
   `champagne_vs_position_model` table stores the slope/intercept of the
   linear fit between Champagne Index and real league position (not just
   r/p like before — Issue #3 only needed the correlation strength, the Lab
   tab needed the actual fitted line, so `slope`/`intercept` columns were
   added to that table too). The Lab tab inverts that line:
   `position ≈ slope * predicted_next_index + intercept`, clamped to ≥1.
   This is explicitly labelled as "a vibe, not a prediction" in the UI — r
   = -0.663 means real position depends on plenty the model doesn't see
   (fixtures, injuries, luck).

## Why two separate concerns stayed separate

It would be tempting to fold "train" and "predict" into one function, but
keeping evaluation (held-out R²) and deployment (all-data model) as
genuinely different model objects is what makes the R²≈0.15 claim honest —
a model's own training data is not evidence of how well it generalizes.

## Extending it

To add a feature to the Lab: add it to `ML_FEATURE_COLUMNS` in
`compute_predictions.py`, make sure `build_ml_features` computes it, add a
matching `st.slider` in `tab_lab` (pull its range from
`lab["feature_ranges"][your_new_column]`), and re-run the pipeline — the
`feature_cols` list in the saved bundle keeps the dashboard's input order in
sync with the model automatically, nothing else to wire up.
