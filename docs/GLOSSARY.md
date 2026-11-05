# Glossary

Every metric, table, and term used across this project, in one place — so
nobody has to go spelunking through SQL/Python to know what a column means.

## Core metrics

**Champagne Index** — `(goals + assists) / matches`, per team, per season, per
competition. "Attacking output per match." The project's central metric —
everything else is checked against it. Built in `sql/champagne_queries.sql`
(view `champagne_index_by_team_season`).

**Discipline Index** — `(yellow_cards + second_yellow_cards + direct_red_cards)
/ matches`, same grouping as Champagne Index. Lower = more disciplined. ⚠️
Lower leagues often don't track cards at all, so a near-zero value can mean
either "very disciplined" or "no data" — see **data-sparse** below.

**Transfermarkt goalkeeper defensive totals** — `goals_conceded` and
`clean_sheets` aggregated from the primary player-season table. Their per-match
rate uses the Transfermarkt group match proxy. This is a separate source from
the completed-match league table and should be labeled as such. In 388 adequately
covered top-five club-seasons, goalkeeper conceded totals exactly match the
scoreline totals in 366 (94.3%); clean-sheet totals match in 269 (69.3%). The
latter is not used as a league ranking.

**Spend efficiency** — `champagne_index / (total_spend / 1,000,000)`. "Index
points per €1M spent on incoming transfers." High = getting a lot of
attacking output for relatively little money.

**Delta index** (`delta_index`) — `next_season_champagne_index -
this_season_champagne_index` for the same team+competition. The thing the
prediction model is actually trying to predict (not the raw index itself).

**Predicted next index** — this season's Champagne Index plus the model's
predicted `delta_index`. What the dashboard's "Team trend" tab plots as the
diamond marker.

**matches** — not real match count; it's `MAX(nb_in_group)`, a Transfermarkt
column that happens to be constant across all of a team's players in the same
team+season+competition group. The closest available proxy, since the main
dataset has no match-by-match table.

**Goals for / goals against (`GF` / `GA`)** — season totals computed from
completed home/away scores in the optional football-data.co.uk match source.
**Goal difference (`GD`)** is `GF − GA`. These are actual league score totals,
separate from Transfermarkt's player goal/assist totals used in the Champagne
Index.

**Attacking rank** — `RANK()` within the same league and season by goals scored
per completed match, descending. **Defensive rank** uses goals conceded per
completed match, ascending (fewest conceded is rank 1). Per-match rates make
the ordering comparable when a season is incomplete; tied rates share a rank.
These are score-based league rankings, not xG, tactical ratings or measures of
chance quality. The available match source has no xG field.

**Net index** (`net_index`) — `(player goals + assists − Transfermarkt goalkeeper
goals conceded) / Transfermarkt source matches`. This optional pipeline measure
combines two event types from the same seasonal source. It is exploratory and is
not substituted for actual league GD.

**Defensive-spend trend** — Pearson correlation between incoming defender fees
and the next consecutive season's change in Transfermarkt goalkeeper goals
conceded per source match. Current snapshot: `r = 0.004047`, `p = 0.426997`,
`n = 38,531`; this shows no useful linear association in this sample.

## Filters and gotchas

**First-team filter** — excludes reserve/youth squads (e.g. "Real Madrid
Castilla") from model training, using `team_children` (`child_team_id` where
`parent_team_id <> child_team_id`). Not based on `team_details.club_division`
— that column is free text and too inconsistent to filter on.

**data-sparse** — shorthand for "this league doesn't track cards/goals
conceded in the source data," not a real finding. Confirmed by spot-checking:
Real Madrid's LaLiga rows are fully populated; most 4th-6th tier regional
leagues are not. ~63% of all team-seasons have `discipline_index = 0` for
this reason — don't present that as "most disciplined team" without
filtering to top divisions first.

**season_key** — `season_name` ('23/24') converted to an integer start year
(2023), for sorting/joining across tables that use different season formats.
`team_competitions_seasons.season_id` uses the bare year ('2023') directly
instead of the '23/24' format — the two need explicit conversion to join
(see `sql/exploration.sql` Query 2).

**is_latest_season** — boolean flag per team-row: is this that team's most
recent season in the dataset. Used by the dashboard's Ranking tab default view.

## Tables this project writes (not in the raw source data)

| Table | Written by | What's in it |
|---|---|---|
| `champagne_results` | `pipeline/compute_predictions.py` | Champagne Index + spend + the linear model's prediction, one row per team-season-competition |
| `champagne_model` | same | the single fitted linear trend (slope/intercept/r/p) spend→delta_index |
| `champagne_model_ml` | same | Chronological holdout R², feature importances, MAE / zero-change baseline and split metadata |
| `lab_team_features` | same | Five real model inputs by exact club-season-competition for scenario prefill |
| `league_standings` | same | real league table built from `match_results`, only populated if the optional match enrichment was loaded |
| `champagne_vs_position_model` | same | r/p/n for Champagne Index vs. real league position |
| `transfer_fee_model` | `pipeline/transfer_fee_model.py` | GradientBoosting test R² + feature importances for predicting `transfer_fee` |
| `club_style_clusters` | `pipeline/club_style_clustering.py` | K-Means cluster assignment + name per team-season |

## Club style archetypes (K-Means, k=4)

Names are assigned **dynamically from each run's actual centroid values**, not
hardcoded — cluster index numbers (0-3) aren't stable across KMeans runs, so
never assume "cluster 2 is always the big spenders."

- **Shoestring overachievers** — lowest average spend, surprisingly decent index
- **Lower-tier / data-sparse** — not a real style, see above
- **Mid-table grinders** — moderate spend, moderate everything
- **Big-spending elite** — highest spend, highest index, real match data

## Raw dataset tables (pinned Transfermarkt snapshot)

| Table | Grain | Notable columns |
|---|---|---|
| `player_profiles` | one row per player | `main_position`, `date_of_birth`, `is_eu`, `foot`, club history |
| `player_performances` | player × season × competition × team | `goals`, `assists`, cards, `nb_in_group` (matches proxy), `goals_conceded`, `clean_sheets` |
| `transfer_history` | one row per transfer | `transfer_type` (Transfer/Loan/Return from loan/Draft), `transfer_fee`, `value_at_transfer` — **95% of rows have fee=0** (loans never carry a fee in this data; most "Transfer" rows are free/undisclosed too) |
| `player_market_value` | player × date snapshot | time series of `value` |
| `player_injuries` | one row per injury | `injury_reason` (messy free text), `days_missed`, `games_missed` |
| `player_national_performances` | player × national team | caps, goals, `career_state` |
| `player_teammates_played_with` | player × teammate pair | `ppg_played_with`, `joint_goal_participation` — a pre-computed "chemistry" metric |
| `team_details`, `team_competitions_seasons` | club × season | `club_division` is messy/unreliable, don't filter on it |
| `team_children` | parent↔child | self-referencing (parent=child for the first team itself); used for the first-team filter |
| `match_results` | one row per match | optional football-data.co.uk enrichment, top-5 leagues only |

## Enrichment data

**football-data.co.uk enrichment** — optional CSVs with real match results
(home/away goals, result, referee) for the top-5 European leagues, 2021-2026.
Not part of the main Transfermarkt snapshot. Unlocks `league_standings`, the
Standings dashboard tab, and the home-advantage/injury-burden SQL queries.
See README's **Data** section for the download/folder layout.
