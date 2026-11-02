# Presentation findings

Short, spoken-out-loud findings, each backed by a real number from the dashboard or
database — not a guess.

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

3. **"Best value for money" is dominated by noise, not a real story.** The naive
   leaderboard (`sql/exploration.sql` Query 3a, `spend_efficiency` sorted DESC)
   is topped by tiny-spend outliers: Manchester City's U21 side spent a
   nominal **€1 total** and still posted a 2.9 Champagne Index, followed by a
   run of Italian lower-league cup campaigns (AC Prato, Foligno Calcio,
   Vicenza Calcio) with €50k–250k spend. There's no team here that genuinely
   "solved" attacking output cheaply at a real, competitive first-team level —
   this metric needs a minimum-spend and first-team filter (the same idea as
   Issue #3's reserve/youth exclusion) before a real "smart spenders" claim
   could be made.

4. **"Worst value for money" is mostly zero-output cup runs, not wasted
   budgets.** The bottom of the same leaderboard (Query 3b) is five single-cup
   campaigns — mostly 1. FC Kaiserslautern and 1. FC Saarbrücken in the
   DFB-Pokal and Intertoto-Cup across the 80s/90s/00s — each with a Champagne
   Index of exactly **0.0** despite real transfer spend (€150k–675k). These
   are squads that simply didn't score or assist in that one cup competition,
   not evidence that the transfer money itself was wasted.

5. **The Premier League spends more per transfer than anyone else, by a wide
   margin.** Across 13,754 paid transfers (Query 2), the Premier League's
   average fee is **€13.7M** — 55% higher than second-place LaLiga (€8.85M),
   and more than double Ligue 1, Serie A, or the Bundesliga (€5.6M–6.6M each).
   Total nominal Premier League spend across the full dataset (1960–2025) is
   also by far the largest of the top-5 leagues at **€188.6B**.
