# LUISS requirements and evidence

Verified against **Vincenzo Lomonaco, CIDS Lecture 15 — Project launch &
architecture design**, dated 29 October 2026. Original local source:
`/Users/ataika/Downloads/CIDS_Lecture_15_projects_intro.pdf` (43 pages).
Page numbers below are 1-based PDF pages. The original copyrighted slides are
not redistributed in this repository.

## Mandatory checklist (page 9)

| Requirement | Project evidence | Status / boundary |
| --- | --- | --- |
| One GitHub repository, four contributors, commits spread across weeks | Existing repository, branches and review practice; author/account attribution in README | **Solo portfolio exercise.** Four accounts owned by one person do not satisfy a real four-person team requirement. Do not rewrite or fabricate history. |
| README a stranger can follow | Exact setup/start/test/benchmark commands and source layout | Locally validated; running on another person's laptop still requires an independent human check. |
| SQL or NoSQL database, with a reason | PostgreSQL 16, relational schema, COPY, indices, named volume | Implemented. Fixed columns and player/club/season joins justify SQL. |
| One command starts the system | `docker compose up` after preparing `.env` / source data | Ordered health/success dependencies retained. |
| Performance in numbers, explained | Benchmark artifact plus README measurements; UI Project page | Executed three-repeat timings, four core-container memory observations and database/CSV footprint comparison; conditions in MEASUREMENTS.md. |

## Measurement protocol (pages 10–11)

- Time: loading, each main query, and complete start-to-end run.
- Memory: highest observed RAM for **each** container during its heaviest step.
- Disk: database footprint compared with original source files.
- Growth: 25%, 50% and 100% of the same data; interpret the change.
- Repeat each test **three** times and report the average. Keep individual runs.
- Record laptop processor and RAM; Docker's VM platform alone is insufficient.
- Change one experimental factor at a time. Timings depend on caches and host load.
- Results belong in the README and presentation, with interpretation.

## Data acquisition and scope (pages 5, 13, 34–35)

The suggested complete system downloads public data with a script, without a
login, and uses a source with a clear licence. The earlier README required a
Kaggle account and linked a different Transfermarkt schema. Audit the exact
11-file source, pin its revision, validate headers/checksums and disclose the
upstream licence status. Existing manual football-data.co.uk enrichment remains
manual: do not introduce a scraper contrary to the stated source terms.

ML, a website/app, cloud deployment, Spark, Kubernetes and very large data are
**not mandatory** (page 9). The new interface is an optional presentation layer;
the simple loader/database/pipeline/measurement system remains central.

## Explanation and architecture (pages 7, 14, 33–34)

README answers: the question, source/licence/size/download, database rationale,
processing, final output, and measurement plan. Diagram boxes represent
containers; arrows identify files, rows, SQL queries and HTTP pages. Every real
team member should understand the whole system and be ready to answer questions.

## Demo and presentation (pages 37–39)

- **12 November checkpoint:** five-minute end-to-end demo, one result visible,
  first complete-run timing. A beautiful interface is not required.
- **20/26 November final:** 15-minute presentation and five minutes of questions.
- Suggested timing (not a mandatory section order): question/data 3 min,
  architecture 2, live demo 3, measurements/results 3, problems 2, contributions 2.
- A two-minute backup demo video is recommended. No video is claimed to exist
  merely because the UI works or screenshots were captured.
- All real team members speak. MyLuiss team assignment and repository submission
  are human/course actions; this repository does not claim to perform them.
