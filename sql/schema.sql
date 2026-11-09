-- Calcio Champagne — database schema
-- Mirrors the 11 CSV files in the Transfermarkt dataset almost 1:1.
-- Numeric reference columns that can be NULL (coach_id, player_agent_id, ...) are typed
-- NUMERIC instead of INTEGER because the source export writes them as "123.0" when the
-- column also contains blanks elsewhere (pandas upcasts nullable int columns to float).
-- Indices are created separately, after the bulk COPY load, in loader/load_data.py —
-- that's measured as part of the performance benchmark (see measure/benchmark.py).

CREATE TABLE IF NOT EXISTS player_profiles (
    player_id INTEGER NOT NULL,
    player_slug TEXT,
    player_name TEXT,
    player_image_url TEXT,
    name_in_home_country TEXT,
    date_of_birth DATE,
    place_of_birth TEXT,
    country_of_birth TEXT,
    height NUMERIC,
    citizenship TEXT,
    is_eu BOOLEAN,
    position TEXT,
    main_position TEXT,
    foot TEXT,
    current_club_id INTEGER,
    current_club_name TEXT,
    joined DATE,
    contract_expires DATE,
    outfitter TEXT,
    social_media_url TEXT,
    player_agent_id NUMERIC,
    player_agent_name TEXT,
    contract_option TEXT,
    date_of_last_contract_extension DATE,
    on_loan_from_club_id NUMERIC,
    on_loan_from_club_name TEXT,
    contract_there_expires DATE,
    second_club_url TEXT,
    second_club_name TEXT,
    third_club_url TEXT,
    third_club_name TEXT,
    fourth_club_url TEXT,
    fourth_club_name TEXT,
    -- source format is "DD.MM.YYYY (age)", e.g. "02.07.2022 (58)" — not a clean ISO
    -- date and not used by the pipeline, so kept as text rather than parsed.
    date_of_death TEXT
);

CREATE TABLE IF NOT EXISTS player_performances (
    player_id INTEGER NOT NULL,
    season_name TEXT NOT NULL,
    competition_id TEXT NOT NULL,
    competition_name TEXT,
    team_id INTEGER NOT NULL,
    team_name TEXT,
    nb_in_group INTEGER,
    nb_on_pitch INTEGER,
    goals NUMERIC,
    assists INTEGER,
    own_goals INTEGER,
    subed_in INTEGER,
    subed_out INTEGER,
    yellow_cards INTEGER,
    second_yellow_cards INTEGER,
    direct_red_cards INTEGER,
    penalty_goals NUMERIC,
    minutes_played NUMERIC,
    goals_conceded INTEGER,
    clean_sheets INTEGER
);

CREATE TABLE IF NOT EXISTS player_market_value (
    player_id INTEGER NOT NULL,
    date_unix DATE,
    value NUMERIC
);

CREATE TABLE IF NOT EXISTS player_latest_market_value (
    player_id INTEGER NOT NULL,
    date_unix DATE,
    value NUMERIC
);

CREATE TABLE IF NOT EXISTS player_injuries (
    player_id INTEGER NOT NULL,
    season_name TEXT,
    injury_reason TEXT,
    from_date DATE,
    end_date DATE,
    days_missed NUMERIC,
    games_missed INTEGER
);

CREATE TABLE IF NOT EXISTS player_national_performances (
    player_id INTEGER NOT NULL,
    team_id INTEGER,
    matches INTEGER,
    goals INTEGER,
    shirt_number INTEGER,
    debut DATE,
    coach_id NUMERIC,
    debut_game_id NUMERIC,
    career_state TEXT
);

CREATE TABLE IF NOT EXISTS player_teammates_played_with (
    player_id INTEGER NOT NULL,
    teammate_player_id INTEGER,
    teammate_player_name TEXT,
    ppg_played_with NUMERIC,
    joint_goal_participation NUMERIC,
    minutes_played_with NUMERIC
);

CREATE TABLE IF NOT EXISTS team_details (
    club_id INTEGER NOT NULL,
    club_slug TEXT,
    club_name TEXT,
    logo_url TEXT,
    country_name TEXT,
    season_id TEXT,
    competition_id TEXT,
    competition_slug TEXT,
    competition_name TEXT,
    club_division TEXT,
    source_url TEXT,
    _last_modified_at TIMESTAMP
);

CREATE TABLE IF NOT EXISTS team_competitions_seasons (
    club_id INTEGER NOT NULL,
    team_name TEXT,
    season_id TEXT,
    competition_name TEXT,
    competition_id TEXT,
    club_division TEXT,
    _last_modified_at TIMESTAMP
);

CREATE TABLE IF NOT EXISTS team_children (
    parent_team_id INTEGER,
    parent_team_name TEXT,
    child_team_id INTEGER,
    child_team_name TEXT,
    _last_modified_at TIMESTAMP
);

CREATE TABLE IF NOT EXISTS transfer_history (
    player_id INTEGER NOT NULL,
    season_name TEXT,
    transfer_date DATE,
    from_team_id INTEGER,
    from_team_name TEXT,
    to_team_id INTEGER,
    to_team_name TEXT,
    transfer_type TEXT,
    value_at_transfer NUMERIC,
    transfer_fee NUMERIC
);

-- Enrichment: real match results, from football-data.co.uk (not part of the Kaggle
-- archive — see data/matches/ and loader/load_matches.py). Gives the project an
-- actual outcome (goals, result, league position) to check the Champagne Index
-- against, instead of only match-count proxies from player_performances.
CREATE TABLE IF NOT EXISTS match_results (
    league_code TEXT NOT NULL,       -- football-data.co.uk code, e.g. 'E0' (Premier League)
    season_name TEXT NOT NULL,       -- Transfermarkt-style '24/25', so it joins to champagne_results
    match_date DATE,
    home_team_id INTEGER NOT NULL,   -- resolved via team_name_map
    away_team_id INTEGER NOT NULL,
    home_goals INTEGER,
    away_goals INTEGER,
    result CHAR(1),                  -- 'H', 'D', 'A' (full-time result)
    referee TEXT,
    -- Everything below is optional/nullable: present in every local source CSV
    -- (verified across all 5 leagues, 21/22-25/26) but parsed leniently by
    -- loader/load_data.py's parse_match_extras(), so an older-format match CSV
    -- missing these columns still loads the core score fields above.
    home_shots INTEGER,
    away_shots INTEGER,
    home_shots_on_target INTEGER,
    away_shots_on_target INTEGER,
    home_corners INTEGER,
    away_corners INTEGER,
    home_yellow INTEGER,
    away_yellow INTEGER,
    home_red INTEGER,
    away_red INTEGER,
    ht_home_goals INTEGER,
    ht_away_goals INTEGER,
    -- Betting-market columns: Bet365 1x2 odds and Asian handicap (see docs/GLOSSARY.md
    -- for what the Asian handicap line means) — a "wisdom of crowds" strength signal,
    -- independent of this project's own goals/spend data, not a measured outcome.
    odds_home NUMERIC,
    odds_draw NUMERIC,
    odds_away NUMERIC,
    asian_handicap_line NUMERIC,
    asian_handicap_home_odds NUMERIC,
    asian_handicap_away_odds NUMERIC
);

-- Upgrade an existing installation without dropping previously loaded scores.
-- The loader validates every incoming fixture before its transactional TRUNCATE
-- and replacement, so failed imports preserve the stored match set.
ALTER TABLE match_results ADD COLUMN IF NOT EXISTS home_shots INTEGER;
ALTER TABLE match_results ADD COLUMN IF NOT EXISTS away_shots INTEGER;
ALTER TABLE match_results ADD COLUMN IF NOT EXISTS home_shots_on_target INTEGER;
ALTER TABLE match_results ADD COLUMN IF NOT EXISTS away_shots_on_target INTEGER;
ALTER TABLE match_results ADD COLUMN IF NOT EXISTS home_corners INTEGER;
ALTER TABLE match_results ADD COLUMN IF NOT EXISTS away_corners INTEGER;
ALTER TABLE match_results ADD COLUMN IF NOT EXISTS home_yellow INTEGER;
ALTER TABLE match_results ADD COLUMN IF NOT EXISTS away_yellow INTEGER;
ALTER TABLE match_results ADD COLUMN IF NOT EXISTS home_red INTEGER;
ALTER TABLE match_results ADD COLUMN IF NOT EXISTS away_red INTEGER;
ALTER TABLE match_results ADD COLUMN IF NOT EXISTS ht_home_goals INTEGER;
ALTER TABLE match_results ADD COLUMN IF NOT EXISTS ht_away_goals INTEGER;
ALTER TABLE match_results ADD COLUMN IF NOT EXISTS odds_home NUMERIC;
ALTER TABLE match_results ADD COLUMN IF NOT EXISTS odds_draw NUMERIC;
ALTER TABLE match_results ADD COLUMN IF NOT EXISTS odds_away NUMERIC;
ALTER TABLE match_results ADD COLUMN IF NOT EXISTS asian_handicap_line NUMERIC;
ALTER TABLE match_results ADD COLUMN IF NOT EXISTS asian_handicap_home_odds NUMERIC;
ALTER TABLE match_results ADD COLUMN IF NOT EXISTS asian_handicap_away_odds NUMERIC;
