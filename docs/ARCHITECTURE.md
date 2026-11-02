# Architecture

How the pieces fit together, and how to add a new piece without breaking the
existing ones. See `docs/GLOSSARY.md` for what each metric/table means.

## Data flow

```
Kaggle CSVs ─┐
             ├─> loader (COPY into Postgres) ─> pipeline (views + models) ─> app (Streamlit, :8502)
match CSVs ──┘                                        │
                                                        ├─> transfer_fee_model.py (manual)
                                                        └─> club_style_clustering.py (manual)
measure/benchmark.py ──> measure/results/results.json ──> app's Performance tab
```

`loader` → `pipeline` → `app` run automatically on `docker compose up`
(`service_completed_successfully` dependency chain in `docker-compose.yml`).
`measure`, `transfer_fee_model.py`, and `club_style_clustering.py` are
on-demand side analyses — not started automatically, since none of the core
dashboard tabs hard-depend on them (the dashboard checks for their tables and
shows a "not run yet" message if they're missing).

## Why each piece lives where it does

- **`sql/schema.sql`** — one table per raw Kaggle CSV, created once by the loader.
- **`sql/champagne_queries.sql`** — the two views (`champagne_index_by_team_season`,
  `transfer_spend_by_team_season`) that `compute_predictions.py` reads from.
  Kept as SQL, not inline in Python, so they're directly runnable/checkable
  with `psql` independent of the Python pipeline.
- **`sql/exploration.sql`** — hand-written business-style queries (not part of
  the automatic pipeline). This is where new one-off analytics belong unless
  they need to be *computed* (not just queried) — see below.
- **`pipeline/compute_predictions.py`** — anything that needs to **write** a
  result table the dashboard reads from `champagne_results`/`champagne_model*`.
- **`pipeline/transfer_fee_model.py`**, **`pipeline/club_style_clustering.py`**
  — self-contained side analyses, each independently runnable, each writing
  its own table. Kept out of `compute_predictions.py` on purpose: they don't
  share inputs with the champagne pipeline (transfer_fee_model doesn't touch
  `champagne_results` at all) and keeping them separate means one failing
  doesn't block the others or the core `docker compose up` flow.
- **`app/dashboard.py`** — pure read layer. Every tab does `pd.read_sql(...)`
  against a table the pipeline already wrote; the dashboard itself never
  computes a model or a derived metric beyond simple display formatting.

## Adding a new analysis

1. **Read-only SQL exploration** (no new derived table needed): add to
   `sql/exploration.sql`, verify with
   `docker compose exec -T db psql -U team -d calcio < sql/exploration.sql`.
2. **Needs Python/pandas/sklearn to compute** (a model, a clustering, a
   feature engineered from multiple tables): new standalone script in
   `pipeline/`, following the `transfer_fee_model.py` pattern — own
   `connect()`, own `main()`, writes its own table, documented at the top of
   the file with whether it's wired into `docker compose up` or manual.
   Add it to `pipeline/Dockerfile`'s `COPY` lines and to
   `pipeline/requirements.txt` if it needs a new dependency.
3. **Needs to show up in the dashboard**: add a `@st.cache_data` loader
   function (follow the `load_club_clusters()` pattern — wrap in
   `try/except` returning an empty DataFrame, so a missing table shows a
   friendly "not run yet" message instead of crashing the whole app) and a
   new tab or expander.

## Known constraints worth knowing before you extend this

- **K-Means cluster indices aren't stable across runs.** Never hardcode a
  cluster's identity to its integer index — derive names from that run's
  actual centroid values (see `club_style_clustering.py::name_clusters`).
- **`float('nan') or default` does NOT fall back to `default` in Python** —
  NaN is truthy. Use `pd.notna(x)` explicitly. (This crashed the dashboard
  once in production — see the "Fix NaN crash" commit.)
- **`transfer_fee` is 95% zero** (loans never carry a fee, most "Transfer"
  rows are free/undisclosed) — any model/query using it should filter to
  `transfer_type = 'Transfer' AND transfer_fee > 0` or explicitly reason
  about the zero-inflation.
- **Season name formats differ across tables** — `season_name` ('23/24') in
  most tables, `season_id` (just '2023') in `team_competitions_seasons`/
  `team_details`. Convert explicitly, don't assume they match.
- **`club_division` is unreliable** for filtering by league tier — use
  `team_children` for a first-team filter instead.

## Where the trained models live

Models that only need to report a metric (R², correlation, feature
importances) write that metric to a table and discard the fitted model
object — fine for a static report, but useless for live inference.

The **Lab tab** (interactive "what would this team's next season look like")
is the one place that needs the actual fitted model object, not just its
score — see `docs/LAB.md` for how that model is persisted and loaded.
