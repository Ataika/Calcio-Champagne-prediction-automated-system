# Presentation findings

Short, spoken-out-loud findings, each backed by a real number from the dashboard or
database — not a guess. Two are filled in from numbers already computed by the
pipeline/benchmark; the rest need one `docker compose up` to pull the actual team
names out of `sql/exploration.sql` (Issue #2/#6) before the presentation.

1. **The Champagne Index actually means something.** Across the top-5 European
   leagues, 2021–2026 (484 team-seasons with real match data), a team's Champagne
   Index correlates with **r = -0.663** (p < 0.0001) against its final league
   position — a higher index tracks with finishing higher (lower-numbered) in the
   table. That's the headline: "goals + assists per match" isn't an arbitrary stat,
   it tracks real results.

2. **Money alone doesn't buy more attacking output.** Across the whole dataset
   (all competitions, 1960–2025), transfer spend against next season's change in
   Champagne Index comes out at **r ≈ -0.01** — essentially no relationship. Simply
   spending more on transfers doesn't predict a more attacking team the following
   season (see Issue #3 — this might change once reserve/youth competitions are
   filtered out of the fit).

3. **TODO — best value for money.** Run `sql/exploration.sql` Query 3a
   (`spend_efficiency` sorted DESC) once the stack is up and name the actual
   top team-season, with its champagne_index and total_spend.

4. **TODO — worst value for money.** Same query, Query 3b (sorted ASC) — the
   team-season that spent the most for the least extra attacking output.

5. **TODO — league-level spend pattern.** Run Query 2 (`avg_transfer_fee` per
   competition) and note whether any one league's spend-per-transfer average
   stands out from the rest.

## How to fill in the TODOs

```
docker compose up
docker compose exec -T db psql -U team -d calcio < sql/exploration.sql
```

Or open each query in a GUI client (TablePlus/DBeaver, `localhost:5432`, credentials
in `.env`) and read the actual rows back.
