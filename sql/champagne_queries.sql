-- Calcio Champagne — processing queries
-- Run after the bulk load (loader) and before the app starts (pipeline).
-- Two views feed the "champagne_results" table that pipeline/compute_predictions.py builds:
--
--   1. champagne_index_by_team_season
--      Attacking output per match for a team in one competition/season.
--      nb_in_group is constant across all players of the same team+season+competition
--      in this dataset, so MAX() is just "read the team's match count for that row group" —
--      there is no per-match table, this is the proxy the whole project is built on.
--
--   2. transfer_spend_by_team_season
--      Money a team spent buying players ahead of a season, split into total spend and
--      spend specifically on attacking players (joined to player_profiles.main_position).

CREATE OR REPLACE VIEW champagne_index_by_team_season AS
SELECT
    team_id,
    MAX(team_name) AS team_name,
    season_name,
    competition_id,
    MAX(competition_name) AS competition_name,
    SUM(goals) AS total_goals,
    SUM(assists) AS total_assists,
    MAX(nb_in_group) AS matches,
    ROUND(
        (SUM(goals) + SUM(assists)) / NULLIF(MAX(nb_in_group), 0),
        2
    ) AS champagne_index
FROM player_performances
GROUP BY team_id, season_name, competition_id;

CREATE OR REPLACE VIEW transfer_spend_by_team_season AS
SELECT
    th.to_team_id AS team_id,
    th.season_name,
    SUM(th.transfer_fee) AS total_spend,
    SUM(th.transfer_fee) FILTER (WHERE pp.main_position = 'Attack') AS attacking_spend
FROM transfer_history th
LEFT JOIN player_profiles pp ON pp.player_id = th.player_id
WHERE th.to_team_id IS NOT NULL
GROUP BY th.to_team_id, th.season_name;
