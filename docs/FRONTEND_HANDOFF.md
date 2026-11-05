# Frontend and API handoff

The primary frontend is `app/static/`, served by `app/api.py` in the same app
container. Default URL: **http://localhost:8502**. No frontend build or external
assets are required. The original Streamlit UI remains optional at :8503:

```bash
docker compose --profile legacy up -d legacy
```

## Views and state

- `#overview`: one league/season ranking, spend/output scatter, separate
  next-consecutive-season analysis with a table of every plotted observation.
- `#clubs` and `#club/<id>`: directory, exact-competition history, profile and Lab
  entry. Missing years are left as gaps; partial recent seasons are not connected.
- `#compare`: exactly two clubs, a shared season and historical competition.
- `#lab`: real five-input prefill, original/model-scenario comparison, reset and
  observed model limits. No hidden median inputs or invented prediction bands.
- `#project`: architecture, source provenance, live model evaluation, measured
  infrastructure and the verified LUISS course mapping.

League and season are URL query parameters (`league`, `season`); Lab club uses
`team`, comparison uses `teams`. Browser history/deep links work. League changes
clear a cross-league comparison. Defaults choose the latest adequately covered
source season, not a mixed “latest per club” snapshot. Partial seasons remain
visible as disabled options with a partial label.

## HTTP contract

| Endpoint | Purpose |
| --- | --- |
| `GET /api/health` | Database/output readiness and model presence |
| `GET /api/meta` | Five leagues, sorted season coverage, defaults, model summary |
| `GET /api/season?competition=IT1&season=24/25&min_matches=15` | Bounded season rows, same-sample descriptive correlations |
| `GET /api/analysis?competition=IT1&season=24/25` | Five-season input window, valid next-season deltas, fit for that displayed sample; separately labeled global model |
| `GET /api/clubs/46?competition=IT1&season=24/25` | Club history, selected-season context and optional exploratory cluster |
| `GET /api/lab/config?team_id=46&competition=IT1&season=24/25` | Exact prefill, missing inputs, ranges and evaluation |
| `POST /api/lab/predict` | Five-feature JSON body; predicted delta/index and support warnings |
| `GET /api/export?competition=IT1&season=24/25` | CSV for the displayed season, with spreadsheet-formula protection |
| `GET /api/project` | Model evidence, source table estimates and benchmark artifact |

Interactive OpenAPI docs are at `/api/docs`. Database queries bind user values;
season and league filters are validated. The connection defaults to read-only,
and raw player tables are never exposed. Numeric missing values are null.

## Design and QA

Paper / ink / burgundy / olive, serif editorial headings, tabular numeric type.
Club badges are typographic initials, not claimed official club logos. SVG
charts, controls, filters and table links are keyboard accessible; a methods
dialog explains the denominator and output proxy. Tables scroll within their
container on narrow screens. Reduced motion and print styling are supported.

Run `node scripts/browser_check.mjs` with local Chrome and Node 22+ for real
browser checks and desktop/mobile screenshots in ignored `artifacts/`. The test
uses an isolated temporary profile and cleans up only its own process/files.
