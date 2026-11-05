# Small work packages and acceptance checks

The follow-up after `b8d0d0a` is split into six tasks. Each task has its own
commit and an observable acceptance result. Account allocation describes Git
attribution for the personas documented in README; it does not establish that
different people independently implemented the changes.

| ID | Assigned account | Finished work | Acceptance result |
| --- | --- | --- | --- |
| D1 | nedalozanovska | Parse completed matches before import; validate dates, nonnegative integer scores, result consistency and consecutive season filenames | Valid 0–0 draws and two/four-digit dates accepted; malformed and unplayed fixtures cannot become recorded results |
| D2 | nedalozanovska | Replace optional match enrichment safely | Missing sources clear stale rows; identical fixtures load once; conflicting scores stop replacement before stored matches change |
| V1 | lilllaz | Exercise source acquisition without real network calls | Bad hashes/headers and interrupted transfers leave no installed partial CSV; normalized metadata is checked; verified files work offline |
| V2 | lilllaz | Verify the app with optional enrichment | Five-league API checks and browser comparisons follow available match coverage instead of requiring one prepared derby snapshot |
| A1 | jacoposcaccianoce | Check application readiness against the pipeline contract | Missing required tables or empty result output return HTTP 503; model availability is a separate field |
| A2 | jacoposcaccianoce | Record the task split and reproducible acceptance route | README links this task list and reports the exact commit ranges; remaining external requirements stay explicit |

## Run the acceptance checks

From the repository root, with Docker Desktop running and `.env` prepared:

```bash
docker compose up --build -d
docker compose run --rm --no-deps -v "$PWD:/source:ro" -w /source app \
  python -m unittest discover -s tests -v
python3 scripts/check_live.py
node scripts/browser_check.mjs
```

The last command needs local Chrome and Node 22+. Screenshots and JSON reports
are written to ignored `artifacts/`. Tests do not require optional match CSVs:
where enrichment exists they check actual score totals; where it does not they
check the explicit missing-coverage state. Benchmarks are separate experiments,
not invented from the browser checks. See [measurements](MEASUREMENTS.md).

To reproduce the prepared-data example, compare Inter and Milan in Serie A
24/25: recorded league scores 1–2 and 1–1, total goals 2–3. A primary-only setup
instead reports that match results have not been loaded.

## What remains before a group submission

The application is runnable, but technical checks do not complete these steps:

- Confirm the actual team membership and record each person's real contribution
  and review. Each person should understand the whole pipeline, make a meaningful
  change or experiment, and present their own part. Git email counts alone do
  not demonstrate independent participation.
- Run a fresh checkout on another member's laptop using README only. Record
  that machine, any setup issue and the resulting fix. This is not claimed as
  completed by a rerun on the original laptop.
- Resolve the primary source's licence before claiming the course's clear-licence
  condition is met; see [source provenance](SOURCES.md).
- Prepare the actual slides, rehearse the 15-minute presentation and questions,
  and record the recommended two-minute backup demo. The rehearsal route in
  [DEFENSE.md](DEFENSE.md) is a guide, not an existing recording or slide deck.

Historical commits and benchmark results are preserved. No dates, independent
contributors, second-machine checks or licence confirmations are fabricated.
