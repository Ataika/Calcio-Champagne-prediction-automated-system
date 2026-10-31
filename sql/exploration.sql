-- Calcio Champagne — SQL exploration (Issue #2, Issue #6)
-- Business-style questions against the live database. Run after `docker compose up`
-- has finished (loader + pipeline done), e.g.:
--   docker compose exec db psql -U team -d calcio -f /dev/stdin < sql/exploration.sql
-- or paste individual queries into a GUI client (TablePlus/DBeaver), host localhost,
-- port 5432, credentials from .env.

-- ============================================================================
-- Query 1: Top 10 most expensive transfers in the dataset.
-- Answers: "who are the biggest-money signings ever in this data?"
-- ============================================================================
SELECT
    pp.player_name,
    th.season_name,
    th.from_team_name,
    th.to_team_name,
    th.transfer_fee
FROM transfer_history th
LEFT JOIN player_profiles pp ON pp.player_id = th.player_id
WHERE th.transfer_fee IS NOT NULL
ORDER BY th.transfer_fee DESC
LIMIT 10;

-- ============================================================================
-- Query 2: Average transfer spend per competition.
-- Answers: "which competitions spend the most money on incoming transfers?"
--
-- transfer_history.season_name is Transfermarkt-style ('23/24'); joining to
-- team_competitions_seasons needs its season_id (the season's start year,
-- e.g. '2023'), so the CASE below converts one to the other — same logic as
-- pipeline/compute_predictions.py's season_sort_key(). A team can appear in
-- more than one competition in the same season (e.g. league + continental cup),
-- so a transfer can be counted once per competition the buying club played
-- in that season — fine for an exploration query, not for a final metric.
-- ============================================================================
SELECT
    tcs.competition_name,
    tcs.competition_id,
    COUNT(*) AS n_transfers,
    ROUND(AVG(th.transfer_fee), 0) AS avg_transfer_fee,
    ROUND(SUM(th.transfer_fee), 0) AS total_spend
FROM transfer_history th
JOIN team_competitions_seasons tcs
    ON tcs.club_id = th.to_team_id
   AND tcs.season_id = (
        CASE WHEN LEFT(th.season_name, 2)::int < 50
             THEN (2000 + LEFT(th.season_name, 2)::int)::text
             ELSE (1900 + LEFT(th.season_name, 2)::int)::text
        END
    )
WHERE th.transfer_fee IS NOT NULL AND th.transfer_fee > 0
GROUP BY tcs.competition_name, tcs.competition_id
ORDER BY avg_transfer_fee DESC;

-- ============================================================================
-- Query 3a: Spend efficiency — best value, i.e. which team-seasons got the
-- most Champagne Index per million spent on incoming transfers.
-- Answers: "who are the smart spenders?"
-- ============================================================================
SELECT
    team_name,
    season_name,
    competition_name,
    champagne_index,
    total_spend,
    ROUND(champagne_index / NULLIF(total_spend / 1e6, 0), 3) AS spend_efficiency
FROM champagne_results
WHERE total_spend > 0
ORDER BY spend_efficiency DESC
LIMIT 20;

-- ============================================================================
-- Query 3b: Spend efficiency — worst value, same metric, opposite sort.
-- Answers: "who spent big and got the least attacking output for it?"
-- ============================================================================
SELECT
    team_name,
    season_name,
    competition_name,
    champagne_index,
    total_spend,
    ROUND(champagne_index / NULLIF(total_spend / 1e6, 0), 3) AS spend_efficiency
FROM champagne_results
WHERE total_spend > 0
ORDER BY spend_efficiency ASC
LIMIT 20;

-- ============================================================================
-- Issue #6 (stretch): two more metrics, same GROUP BY pattern as
-- champagne_index_by_team_season in sql/champagne_queries.sql.
-- ============================================================================

-- Discipline Index: cards per match, per team-season. Lower = more disciplined.
CREATE OR REPLACE VIEW discipline_index_by_team_season AS
SELECT
    team_id,
    team_name,
    season_name,
    competition_id,
    competition_name,
    MAX(nb_in_group) AS matches,
    SUM(yellow_cards) AS total_yellow_cards,
    SUM(second_yellow_cards) AS total_second_yellows,
    SUM(direct_red_cards) AS total_direct_reds,
    ROUND(
        (SUM(yellow_cards) + SUM(second_yellow_cards) + SUM(direct_red_cards))
        / NULLIF(MAX(nb_in_group), 0),
        2
    ) AS discipline_index
FROM player_performances
GROUP BY team_id, team_name, season_name, competition_id, competition_name;

-- Defensive Solidity Index: the defensive mirror of Champagne Index.
-- goals_conceded_per_match: lower is better. clean_sheet_rate: higher is better.
CREATE OR REPLACE VIEW defensive_solidity_by_team_season AS
SELECT
    team_id,
    team_name,
    season_name,
    competition_id,
    competition_name,
    MAX(nb_in_group) AS matches,
    ROUND(SUM(goals_conceded) / NULLIF(MAX(nb_in_group), 0), 2) AS goals_conceded_per_match,
    ROUND(SUM(clean_sheets)::numeric / NULLIF(MAX(nb_in_group), 0), 3) AS clean_sheet_rate
FROM player_performances
GROUP BY team_id, team_name, season_name, competition_id, competition_name;

-- Most disciplined team-seasons (min 15 matches, to drop small-sample noise).
SELECT team_name, season_name, competition_name, matches, discipline_index
FROM discipline_index_by_team_season
WHERE matches >= 15
ORDER BY discipline_index ASC
LIMIT 10;

-- Best defense relative to spend: join defensive solidity to transfer spend.
SELECT
    d.team_name,
    d.season_name,
    d.competition_name,
    d.goals_conceded_per_match,
    d.clean_sheet_rate,
    s.total_spend
FROM defensive_solidity_by_team_season d
JOIN transfer_spend_by_team_season s
    ON s.team_id = d.team_id AND s.season_name = d.season_name
WHERE d.matches >= 15 AND s.total_spend > 0
ORDER BY d.goals_conceded_per_match ASC
LIMIT 10;
