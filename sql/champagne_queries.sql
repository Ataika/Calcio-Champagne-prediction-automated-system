-- Calcio Champagne — processing queries
-- Run after the bulk load (loader) and before the app starts (pipeline).
-- Two views feed the "champagne_results" table that pipeline/compute_predictions.py builds:
--
--   1. champagne_index_by_team_season
--      Attacking output per match for a team in one competition/season, plus its
--      defensive mirror (goals conceded, clean sheets) from the same source table.
--      nb_in_group is constant across all players of the same team+season+competition
--      in this dataset, so MAX() is just "read the team's match count for that row group" —
--      there is no per-match table, this is the proxy the whole project is built on.
--      goals_conceded/clean_sheets are populated only on goalkeeper rows in this source
--      (confirmed: outfield players always read 0, not null), so SUM() across the group
--      is already the correct team-season total — not double counting across outfielders.
--
--   2. transfer_spend_by_team_season
--      Money a team spent buying players ahead of a season, split four ways by
--      player_profiles.main_position (Attack/Midfield/Defender/Goalkeeper — the only
--      four clean values in that column), plus outgoing fees and the net of the two.

-- Defensive columns change the existing view's output order; drop before
-- recreation so PostgreSQL does not mistake the new column names for renames.
DROP VIEW IF EXISTS champagne_index_by_team_season;
CREATE VIEW champagne_index_by_team_season AS
SELECT
    team_id,
    MAX(team_name) AS team_name,
    season_name,
    competition_id,
    MAX(competition_name) AS competition_name,
    SUM(goals) AS total_goals,
    SUM(assists) AS total_assists,
    SUM(goals_conceded) AS total_goals_conceded,
    SUM(clean_sheets) AS total_clean_sheets,
    MAX(nb_in_group) AS matches,
    ROUND(
        (SUM(goals) + SUM(assists)) / NULLIF(MAX(nb_in_group), 0),
        2
    ) AS champagne_index,
    ROUND(SUM(goals_conceded)::numeric / NULLIF(MAX(nb_in_group), 0), 2) AS goals_conceded_per_match,
    ROUND(SUM(clean_sheets)::numeric / NULLIF(MAX(nb_in_group), 0), 3) AS clean_sheet_rate
FROM player_performances
GROUP BY team_id, season_name, competition_id;

CREATE OR REPLACE VIEW transfer_spend_by_team_season AS
WITH incoming AS (
    SELECT
        th.to_team_id AS team_id,
        th.season_name,
        SUM(th.transfer_fee) AS total_spend,
        SUM(th.transfer_fee) FILTER (WHERE pp.main_position = 'Attack') AS attacking_spend,
        SUM(th.transfer_fee) FILTER (WHERE pp.main_position = 'Midfield') AS midfield_spend,
        SUM(th.transfer_fee) FILTER (WHERE pp.main_position = 'Defender') AS defensive_spend,
        SUM(th.transfer_fee) FILTER (WHERE pp.main_position = 'Goalkeeper') AS goalkeeper_spend
    FROM transfer_history th
    LEFT JOIN player_profiles pp ON pp.player_id = th.player_id
    WHERE th.to_team_id IS NOT NULL
    GROUP BY th.to_team_id, th.season_name
),
outgoing AS (
    SELECT
        th.from_team_id AS team_id,
        th.season_name,
        SUM(th.transfer_fee) AS total_sales
    FROM transfer_history th
    WHERE th.from_team_id IS NOT NULL
    GROUP BY th.from_team_id, th.season_name
)
SELECT
    i.team_id,
    i.season_name,
    i.total_spend,
    i.attacking_spend,
    i.midfield_spend,
    i.defensive_spend,
    i.goalkeeper_spend,
    COALESCE(o.total_sales, 0) AS total_sales,
    i.total_spend - COALESCE(o.total_sales, 0) AS net_spend
FROM incoming i
LEFT JOIN outgoing o ON o.team_id = i.team_id AND o.season_name = i.season_name;
