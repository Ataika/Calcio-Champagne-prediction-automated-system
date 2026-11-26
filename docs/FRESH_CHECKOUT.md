# Reproducing the project from a clean checkout

The course asks for a README a stranger can follow. This file is the protocol
for proving it, the record of what has been proved so far, and the template for
the part that still has to be done by another person on another laptop.

## What counts as evidence

| Level | What it proves | Status |
| --- | --- | --- |
| Re-run on the original machine with prepared data | The stack still works | Done continuously; weakest level |
| Clean clone on the original machine, empty `data/`, sources downloaded by the loader | The repository is complete and the README path works | Done — see below |
| Fresh checkout by another person on another laptop, README only | That a stranger can run it | **Not done.** Cannot be produced on this machine |

The third row is the one the course cares about. Nothing on the original laptop
can substitute for it: a machine that already has the images, the CSVs, the
Docker settings and the author's habits cannot discover what a newcomer is
missing.

## Recorded result — clean clone, original machine, 9 November 2026

Commit `301bfef` of `codex/calcio-editorial-audit` was cloned into an empty
directory, `.env` was copied from `.env.example`, and `docker compose up --build`
was run with no prepared data and no manual steps.

| Observation | Value |
| --- | --- |
| Wall clock, command to healthy app | 63 s, including the source download |
| Sources | 11 tables fetched from pinned revision `da9227e1f42b`, no login, every checksum matched |
| Rows loaded | 5,605,055 across 11 tables |
| Model | test R² 0.1271 (five features) and 0.1502 (attack+defense), SHAP top feature `champagne_index` at 0.2054 — identical to the prepared snapshot |
| Optional match data | absent, as designed: it is not redistributed |
| Health | `ready=true`, `model_available=true`, no missing tables |

Two results are worth keeping. First, the row count is 138,131 lower than the
5,743,186 of the prepared snapshot, and that gap is exactly the documented
legacy difference in `team_competitions_seasons` (196,378 rows locally against
58,247 upstream). A fresh checkout therefore reproduces the analysis but not
that one legacy table, which is why the report states the difference instead of
hiding it.

Second, without the optional match files the system degrades the way the code
claims it does: league standings were skipped, power ratings, proxy-xG and the
red-card effect came out as zero rows, and the API answered with zeros and
nulls rather than failing. The model, which does not depend on that enrichment,
was unaffected.

**What this does not prove.** The machine already had Docker configured, the
base images cached and the author present. It shows the repository is complete
and the README path works; it does not show that a stranger can follow it.

## Protocol for the second laptop

Prerequisites: Docker Desktop running, roughly 8 GB free disk, a network
connection, and nothing else bound to port 8502.

```bash
git clone https://github.com/Ataika/Calcio-Champagne-prediction-automated-system
cd Calcio-Champagne-prediction-automated-system
cp .env.example .env
docker compose up --build
```

Then, while it runs, record what you see:

1. Did the loader download the eleven source CSVs without a login, and did every
   checksum match?
2. Did the pipeline finish and print the model lines (`RandomForest`, `showdown`,
   `SHAP`, `power ratings`, `proxy-xG`, `red-card effect`)?
3. Does `http://localhost:8502/api/health` answer `ready=true`?
4. Does the Overview page open on a complete season with 20 clubs?
5. How long did the whole command take, on what hardware?

Expected reference values from the original machine (Apple M3 Pro, 18 GiB):
5,743,186 rows across 11 tables, 484 derived team-seasons, test R² 0.1271 for
the five-feature model and 0.1502 for the attack+defense variant, health
`ready=true`. A first run on another machine is slower than the measured
31.10 s, because that number excludes the download and the image build.

## Result template — fill this in, do not pre-fill it

| Field | Value |
| --- | --- |
| Who ran it | |
| Date | |
| Machine (CPU, RAM, OS) | |
| Docker Desktop version | |
| Total time for `docker compose up --build` | |
| Did it work without help from the author? | |
| Anything missing from the README | |
| Fix applied afterwards (commit) | |

An entry is only evidence if the person who ran it writes it. If a step needed
a hint from the author, record the hint: that is precisely the README gap the
exercise is meant to find.
