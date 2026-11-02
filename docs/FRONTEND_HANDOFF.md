# Frontend handoff

For whoever (human or agent — e.g. OpenAI Codex) builds a standalone
frontend for this project next. The current UI is a Streamlit dashboard
(`app/dashboard.py`) reading directly from Postgres — functional, not the
end goal if a "real" frontend (React/Next.js or similar) is wanted. This
doc is the data contract so a new frontend doesn't have to reverse-engineer
the schema from `pipeline/*.py` and six SQL files.

**Read `docs/GLOSSARY.md` first** for what each metric means, and
`docs/ARCHITECTURE.md` for how the pipeline produces these tables. This doc
only covers what a frontend needs to *consume*.

## What's missing today: an API layer

There is currently **no HTTP API** — `app/dashboard.py` connects to Postgres
directly with `psycopg2`. A new frontend needs one of:

1. **A thin read-only API** (recommended) — a FastAPI service with one
   endpoint per table below, each basically `SELECT * FROM <table> WHERE
   <filters>`. Low effort: every endpoint is a single, already-known query,
   no business logic to design (the pipeline already computed everything).
   Suggested shape: `GET /api/champagne-results?competition=...&season=...`,
   `GET /api/standings?league=...&season=...`, `GET /api/club-clusters`,
   `POST /api/lab/predict` (body = the 5 feature values, loads the same
   `/models/champagne_rf_model.joblib` the Streamlit Lab tab uses — see
   `docs/LAB.md` for exactly how).
2. **Direct Postgres access from the frontend's backend**, if it already
   has one — same tables, same columns, skip the API layer.

Either way, the tables below are the entire contract — nothing else in the
database is meant for a frontend to read directly (internal working tables
only, e.g. raw `player_performances` is 1.9M rows and not something to page
through client-side).

## Tables to expose

| Table | Primary use | Key columns |
|---|---|---|
| `champagne_results` | Ranking tab, Team trend tab | `team_id, team_name, season_name, competition_id, competition_name, matches, champagne_index, total_spend, attacking_spend, delta_index, predicted_next_index, is_latest_season, season_key` |
| `champagne_model` | "Spend vs output" headline stats | `slope, intercept, r_value, p_value, n_observations` (single row, most recent `computed_at`) |
| `champagne_model_ml` | Richer-model headline stats | `r2_score, n_observations, feature_importances` (JSON string — parse client-side) |
| `league_standings` | Standings tab | `league_code, competition_id, season_name, team_id, team_name, played, wins, draws, losses, goals_for, goals_against, goal_diff, points, position, champagne_index, total_spend` — **empty if the optional match enrichment wasn't loaded**, frontend must handle that |
| `champagne_vs_position_model` | Standings headline stats | `r_value, p_value, n_observations, slope, intercept` |
| `transfer_fee_model` | (if built) transfer-fee model stats | `r2_score, n_observations, feature_importances` |
| `club_style_clusters` | Club styles tab | `team_id, team_name, season_name, competition_name, champagne_index, spend_efficiency, discipline_index, goals_conceded_per_match, clean_sheet_rate, total_spend, cluster, cluster_name` |

## The Lab prediction endpoint

The Lab tab's "backend" is just: load `/models/champagne_rf_model.joblib`
(a dict with keys `model`, `feature_cols`, `feature_ranges`), build a
single-row input matching `feature_cols`' order, call `.predict()`. A
`POST /api/lab/predict` endpoint wrapping exactly that (see
`app/dashboard.py`'s `tab_lab` block for the reference implementation,
~40 lines) is the one place a new frontend needs backend logic beyond
"query a table" — everything else is read-only passthrough.

For the league-position estimate: invert `champagne_vs_position_model`'s
`slope`/`intercept` against the predicted index, same formula as the
Streamlit version. Always surface the uncertainty caveat (r≈-0.66, not
deterministic) — don't present it as a confident number.

## What NOT to rebuild

- Don't recompute Champagne Index, spend efficiency, cluster assignments,
  etc. client-side — they're all precomputed pipeline outputs, just display
  them.
- Don't query `player_performances`/`transfer_history`/other raw tables
  directly from a frontend — those are pipeline inputs (millions of rows),
  not frontend-shaped data. If a new view is needed, add it to the pipeline
  (see `docs/ARCHITECTURE.md`'s "Adding a new analysis" section) and expose
  *that* table instead.
