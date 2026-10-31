-- Calcio Champagne — SQL exploration (Issue #2)
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
