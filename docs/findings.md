# Findings for the presentation

Measured from the corrected pipeline on 4 November 2026. Read current model
tables or the app's Project view if the dataset is recomputed.

1. **Recorded attacking output tracks same-season league finish.** r = −0.793285,
   n = 388 sufficiently covered club-seasons from the five European leagues,
   21/22–24/25. Higher index accompanies a lower-numbered finish. This is a
   descriptive association, not evidence of next-season forecasting or causation.
   The earlier r = −0.663 included a partial 25/26 Transfermarkt snapshot paired
   with a full final table; that mismatch is now excluded.

2. **Transfer spend alone has almost no relationship with next-season index
   change.** r = −0.003613, p = 0.478242, n = 38,531 eligible consecutive pairs.
   First-team squads only; top-five pairs require 30 matches in both seasons,
   other competitions five. Missing seasons and partial next seasons are not
   targets. Avoid comparing this directly with the original 54,186-row sample.

3. **The richer model adds modest predictive value under a temporal holdout.**
   Test R² = 0.127115; MAE = 0.485593 index points vs. 0.511364 for zero change.
   16,074 earlier training rows, 5,585 held-out rows from season start 2021.
   This is roughly a 5% reduction in mean absolute error, not 87% prediction
   accuracy. The interactive Lab uses a separate all-data model and makes that
   distinction explicit.

4. **A useful club-level example:** Serie A 24/25, Atalanta records index 3.50
   with €96m incoming fees, Juventus 2.74 with €164.3m, and Inter 3.84 with
   €75.55m. This is a same-season comparison, not a causal recruitment ranking.

5. **Naive “value for money” rankings are unstable.** Tiny/undisclosed fees,
   reserve teams, short cup runs and missing defensive coverage can dominate
   ratio metrics and clusters. Show an actual league/season and sample count;
   do not sell a zero-fee or sparse-data outlier as a scouting discovery.

For infrastructure evidence use the three-repeat measurements in README and
`measure/results/results.json`. Individual runs and hardware are part of the
claim. Do not reuse the original one-run timing or unobserved memory numbers.
