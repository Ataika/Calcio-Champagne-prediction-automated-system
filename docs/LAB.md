# Scenario Lab and model protocol

## Prediction unit and intended use

A row is club × season × competition. The target is next consecutive season's
Champagne Index minus the current index. The UI is a retrospective educational
scenario explorer. It is not a causal transfer-spending estimator or a live
league-position forecast.

Features: current `champagne_index`, `total_spend`, `attacking_spend`,
`squad_avg_age`, `market_value_change`. Squad age is season start year minus birth
year, averaged across the distinct season roster. Market values use the latest
observed value per player in the season's starting calendar year, with equal
player weighting. Its change joins the exact preceding club-season before any
competition rows are joined. Missing inputs are not silently filled for the Lab.

Targets require consecutive years, at least 30 source matches in both top-five
league seasons, or five in other competitions. Reserve/youth squads are excluded
from model fitting using `team_children`. No target is formed across a promotion
or relegation gap in a competition or from a partial 25/26 league snapshot.

## Evaluation and baseline

The most recent seasons accounting for roughly 20% of eligible observations are
held out together, using `season_key` as the boundary. Earlier seasons train the
evaluation model; later seasons test it. Multiple competitions from one season
cannot straddle the boundary. This is one fixed chronological holdout, not nested
cross-validation or an independently verified live backtest. Hyperparameters are
fixed: 200 trees, maximum depth 6, seed 42. The earlier implementation used a
random row split; its old score is not directly comparable.

Measured on 4 November 2026: cutoff 2021, 16,074 training observations, 5,585 test
observations; R² 0.127115, MAE 0.485593. Predicting zero change on the same test
rows gives MAE 0.511364 and R² −0.000183. The improvement is modest. These numbers
are stored with sample counts and protocol in `champagne_model_ml.evaluation`.

A second RandomForest is trained on all eligible rows for Lab exploration. Its
own training fit is never reported as test performance. Some prefilled historical
club-seasons occurred in this model's training; the UI states that explicitly.
See [scikit-learn's temporal evaluation guidance](https://scikit-learn.org/stable/modules/cross_validation.html#cross-validation-of-time-series-data)
for the reason to keep future seasons out of historical training evaluation.

## Persistence and inference

`models/champagne_rf_model.joblib` contains model, ordered feature names, observed
min/median/max and percentile ranges, plus evaluation metadata. The pipeline
writes a temporary file and replaces the old model atomically. The API loads
only this local trusted artifact and invalidates its cache on file change.

`lab_team_features` stores all five real inputs by exact team, season and
competition. `/api/lab/config` reports missing fields; the UI asks the visitor to
choose another club instead of substituting dataset medians.

`POST /api/lab/predict` validates finite numbers, budget/age/index bounds and
`attacking_spend <= total_spend`; feature order follows the artifact. The browser
bounds the attack slider by the total budget, debounces requests and discards
stale responses. Baseline and modified scenario use the same deployed model.

No uncertainty band is fabricated. Observed out-of-training-range inputs are
identified. The old approximate league-position output is omitted because a
same-season association is not a calibrated next-season rank forecast.
