# Presentation and rehearsal notes

Source: Lecture 15, pages 37–39. This is a rehearsal guide, not a claim that a
slide deck or backup video has been recorded. The project remains a solo
portfolio exercise; it does not satisfy four real speakers/contributors.

## Fifteen-minute route

| Time | Show | Explain |
| --- | --- | --- |
| 0–3 min | Overview, Serie A 24/25; source notes | Question, dataset size/provenance, index formula and match-count proxy; unresolved upstream licence |
| 3–5 min | README Mermaid / Project → System | Each container, startup dependencies, COPY/SQL/HTTP/shared artifacts, why PostgreSQL |
| 5–8 min | Overview → two clubs → profile → Lab | Filter one complete season, distinguish same-season from next-season chart, change one input and reset |
| 8–11 min | Project → Measurements / README table | Three repeats, time/memory/disk/growth, processor/RAM, cache conditions and observed memory limits |
| 11–13 min | Project → Findings / audit | Partial season mismatch, duplicate display names, wrong market-value lag, temporal holdout, modest baseline improvement |
| 13–15 min | Git history and attribution | Real ownership, review practice, what each component does, reproducibility boundaries |

## Before presenting

```bash
docker compose up -d
curl -f http://localhost:8502/api/health
# Open http://localhost:8502/?league=IT1&season=24%2F25#overview
```

Prepare the source data and images on the presentation laptop beforehand; a
network download is not part of the cached-source measurement. Keep README,
architecture, saved measurement JSON and screenshots available locally. Record
a two-minute backup walkthrough on the actual laptop as recommended on page 39.

## Answers everyone should be able to give

- Why a database? Fixed schemas and relational joins; native bulk loading,
  indexed lookup, persistent data, clear separation from the presentation layer.
- Why not claim buying attackers causes higher output? Retrospective observational
  seasons, recorded/undisclosed fees, confounders and no causal experiment.
- What is actually predicted? Next consecutive season's change in the index;
  no calibrated rank, match outcome or xG forecast.
- How is evaluation separated? Earlier-season training vs. later-season test,
  plus a zero-change comparator on identical held-out rows. The Lab retrains on
  all eligible history and is not an additional test set.
- Why did the headline correlation change? Partial 25/26 attacking data had been
  compared with full final standings. Coverage and denominators matter.
- Does 3× as much data imply exactly 3× the time? No; COPY, indexing, caches,
  query planning and fixed startup costs have different scaling behavior.
- Is the measured RAM a guaranteed maximum? No; it is the maximum observed
  `docker stats` working-set sample, not continuous peak RSS or a fresh-laptop bound.
- What remains outside the technical audit? Four real members, contributions
  across weeks, independent second-laptop validation and source licence confirmation.
