# Project audit — 4 November 2026

Scope: data validity, model evaluation, application behavior, reproducibility,
course evidence and a complete editorial frontend. Work branch:
`codex/calcio-editorial-audit`.

## Findings and corrections

| Severity | Finding | Resolution |
| --- | --- | --- |
| High | Transfermarkt 25/26 has 2–4 league matches per club, but was compared with full final standings | Keep standings; exclude index/position pairs below 80% match coverage or 30 played games. Default UI to complete seasons. |
| High | `shift(-1)` treated a club's return after a missing season as next season | Require consecutive season years and adequate current/next match coverage. |
| High | Market-value lag was computed after joining competitions, comparing a club to itself within the same season | Build a unique club-season feature table, join the exact preceding year, then join competitions. |
| High | Random test split mixed historical and future seasons | Use a chronological holdout and a zero-change baseline on exactly the same test rows. |
| High | Lab real-club prefill silently used median age/value changes and sometimes another competition | Persist and query all five inputs by club, season and competition; disclose missing inputs. |
| High | Name aliases produced three duplicate club-season-competition rows | Aggregate by canonical identifiers, choose a display name separately, enforce a primary key. Output is 156,084 unique rows. |
| High | README linked a different dataset schema and required account-based manual download | Verify ten exact upstream byte matches; pin revision, LFS object checksums and headers; automatically download missing sources without login. Document the one legacy metadata normalization and unresolved licence. |
| High | Measurements were single-run, missing full startup/hardware/current per-container RAM | Three-repetition benchmark and host-side full-system measurement scripts; preserve individual runs, processor/RAM, sample counts and conditions. |
| High | Reimported data triggered a multi-minute roster DISTINCT plan | ANALYZE after load; pipeline/benchmark use 64 MB work_mem and disable JIT. Diagnostic DISTINCT: 744.7 ms, 1,014,460 rows, 90,129 kB hash memory. Aborted diagnostic excluded from means. |
| Medium | The first ranking included one-match cup outliers and mixed seasons | Top-five league filters, explicit season, minimum sample; partial seasons are identified. |
| Medium | Club trend joined different competitions into one line; predictions plotted at the input season | Explicit competition per trend; scenario result has an explicit target season. |
| Medium | Model metrics were global while visible chart filters were local | Compute descriptive correlation on the displayed sample, label global model evidence separately. |
| Medium | Historical README findings were hardcoded/stale; significance confused with practical effect | Record the rerun below; render live metrics and sample sizes. A tiny effect can have a small p-value. |
| Medium | No HTTP API existed | Add a bounded, validated read API over pipeline outputs plus model inference. |
| Medium | Docker sent raw data/models/secrets as build context | Add `.dockerignore`; retain bind mounts for runtime inputs. |
| Medium | Benchmark could leave the live index dropped after a failed run | Restore the index in `finally`; use the same deterministic team sample and alternating conditions over three repeats. |
| Medium | Source file order was assumed by positional COPY | Validate all source headers before import; atomically place only checksum-verified downloads. |
| Medium | Unplayed fixtures / two-digit years could corrupt match enrichment | Accept both date formats; load completed H/D/A results only; empty optional input is safe. |
| Medium | Shared DB connection and model-cache invalidation were fragile | Read-only pooled connections with rollback/timeouts; atomic model replacement, mtime invalidation, input validation and strict JSON nulls. |
| Medium | Fast filter changes could race with an older data response | Discard outdated route generations; scenario predictions also reject stale replies. |
| Medium | Default API docs required external CDN assets conflicting with the app's CSP/offline use | Local API reference and machine-readable OpenAPI JSON; no external runtime assets. |

## Original evidence (before corrections)

Read from the running database on 4 November 2026:

- Spend/next-index correlation: r = −0.0182459, p = 0.0000216155, n = 54,186.
  The effect is practically tiny, but the earlier “not significant” claim is false.
- Index/position: r = −0.6627481, n = 484. Excluding mismatched 25/26:
  r = −0.7932850, n = 388. This is a retrospective association, not a forecast.
- Original random-split RandomForest R² = 0.149805, n = 32,346.
  This score must not be compared directly with the corrected temporal protocol.

## Course source status

The original **CIDS Lecture 15 — Project launch & architecture design**,
Vincenzo Lomonaco, 29 October 2026, was found in Downloads and read in full
(43-page PDF). `COURSE_REQUIREMENTS.md` maps the mandatory checklist and
measurement/presentation rules to exact PDF pages. The website, ML, cloud,
Spark and Kubernetes are optional in the brief; they do not replace the core.

Two explicit external boundaries remain: the work is a solo portfolio exercise,
not four real team members, and the pinned public source has no explicit licence
file. The legacy metadata table's exact provenance also remains unverified;
it does not feed the core index/model. Independent second-laptop validation and
recording the recommended two-minute backup video are not fabricated as complete.

## Corrected analytical evidence

- Spend → consecutive next-season change: r = −0.003612725, p = 0.4782423,
  n = 38,531. This is now both a tiny effect and nonsignificant in this sample.
- Same-season index ↔ sufficiently covered final standings: r = −0.7932850,
  n = 388. Final 25/26 standings remain stored, but partial attacking snapshots
  are excluded from the correlation.
- Chronological RandomForest: R² = 0.1271151, MAE = 0.4855928 vs. zero-change
  baseline MAE = 0.5113644. Earlier train n = 16,074; held-out n = 5,585,
  from season-start year 2021. About 5% MAE improvement, not a claim of strong
  forecasting or a comparison on the old random-split protocol.

## Executed validation

- The corrected loader/pipeline has been executed on all 11 prepared source
  tables, with optional match enrichment. Model and output tables were rebuilt.
- Ten regression tests pass: consecutive targets, partial-season exclusion,
  competition-safe value lag, chronological split counts/baseline, zero budgets,
  finite inputs, budget consistency, bound parameters, JSON nulls, source headers.
- Browser checks cover real league/season filtering, club profiles, comparison,
  live Lab/reset, methods dialog/Escape, project evidence and 390px layouts;
  desktop/mobile screenshots are stored in ignored `artifacts/`.
- Final run: **10 regression tests, 13 live API/data checks and 12 browser
  checks passed**. Browser JavaScript exception list is empty; app/db are healthy,
  loader/pipeline exited successfully. `git diff --check` is clean.
- Real public acquisition was exercised in a temporary directory: the 0.5 MiB
  `team_children` file downloaded without login, passed SHA-256 and header
  validation, and was placed atomically. Existing prepared files were untouched.
- Three complete cached-source starts averaged **31.100 s** (loader **12.532 s**,
  pipeline **9.698 s**). Observed working-set maxima: db **250.6 MiB**, loader
  **17.93 MiB**, pipeline **500.9 MiB**, app **107.3 MiB**.
- Three index-condition pairs averaged **10.8724 s** without vs. **0.0748 s**
  with the index, **145.4×** for the deterministic 300-club sample. Three growth
  repeats for each of 25/50/100% are saved. Database **695.5 MiB** vs. local CSVs
  **356.6 MiB**, on an Apple M3 Pro / 18 GiB laptop.
- `MEASUREMENTS.md` and README contain the generated tables, individual timing
  repetitions, hardware, snapshot/caching conditions and sampling limitations.
  Screenshots and machine-readable check results are local ignored artifacts;
  source CSVs, model weights and credentials remain excluded from Git/build context.

## 5 November 2026 — comparison follow-up

The comparison now includes completed head-to-head league meetings for the
selected season: individual home/away scores, wins/draws/losses, goals for and
against, goal difference, goals per match, clean sheets and points. Aggregation
preserves each club's perspective, including away games. Missing match-source
coverage is distinct from an empty meeting list or a real 0–0 draw; match-level
assists are not inferred from season totals.

Executed validation: **16 regression tests, 16 live API/data checks and 15 browser
checks passed**. The Inter/Milan 24/25 example matches the prepared source's 1–2
and 1–1 fixtures and 2–3 aggregate goals. Checks include reversed club order,
invalid/same/out-of-scope clubs, missing enrichment and the 390px comparison.
README records the original six-commit update `6f34edb..b8d0d0a`, with two commits per persona,
their exact Git emails and the distinction between authorship and push access.

## 5 November 2026 — smaller completion tasks

Six additional work packages address match import validation, duplicate/stale
enrichment, safe acquisition, optional-data verification, application readiness
and documented acceptance checks. See [WORK_PACKAGES.md](WORK_PACKAGES.md) for
their scope and remaining external submission steps.

The full stack was rebuilt and run against the prepared sources: 5,743,186
primary rows and 8,908 completed matches were retained. App and database health
checks pass; loader and pipeline exit successfully. **37 regression tests,
16 live API/data checks and 15 browser checks passed**. Browser checks cover
desktop and 390px layouts, source-dependent meeting counts and missing coverage.
Acquisition failures are exercised with fake HTTP responses, without source
downloads or modifications to the prepared inputs.
