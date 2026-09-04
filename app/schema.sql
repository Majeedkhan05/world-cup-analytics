-- Normalised schema for the World Cup analytics database.
DROP TABLE IF EXISTS draw_calibration;
DROP TABLE IF EXISTS model_metrics;
DROP TABLE IF EXISTS goals;
DROP TABLE IF EXISTS shootouts;
DROP TABLE IF EXISTS elo_history;
DROP TABLE IF EXISTS elo_ratings;
DROP TABLE IF EXISTS tournaments;
DROP TABLE IF EXISTS matches;
DROP TABLE IF EXISTS teams;

CREATE TABLE teams (
    id   INTEGER PRIMARY KEY,
    name TEXT NOT NULL UNIQUE
);

CREATE TABLE matches (
    id            INTEGER PRIMARY KEY,
    date          TEXT    NOT NULL,
    year          INTEGER NOT NULL,
    tournament    TEXT    NOT NULL,
    home_team_id  INTEGER NOT NULL REFERENCES teams(id),
    away_team_id  INTEGER NOT NULL REFERENCES teams(id),
    home_score    INTEGER NOT NULL,
    away_score    INTEGER NOT NULL,
    city          TEXT,
    country       TEXT,
    neutral       INTEGER NOT NULL DEFAULT 0,
    is_world_cup  INTEGER NOT NULL DEFAULT 0,
    home_elo      REAL,   -- rating BEFORE kick-off, so predictions stay honest
    away_elo      REAL
);

CREATE TABLE goals (
    id        INTEGER PRIMARY KEY,
    match_id  INTEGER NOT NULL REFERENCES matches(id),
    team_id   INTEGER NOT NULL REFERENCES teams(id),
    scorer    TEXT,
    minute    REAL,
    own_goal  INTEGER NOT NULL DEFAULT 0,
    penalty   INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE shootouts (
    match_id  INTEGER PRIMARY KEY REFERENCES matches(id),
    winner_id INTEGER REFERENCES teams(id)
);

CREATE TABLE tournaments (
    year          INTEGER PRIMARY KEY,
    host          TEXT,
    champion_id   INTEGER REFERENCES teams(id),
    runner_up_id  INTEGER REFERENCES teams(id),
    matches       INTEGER,
    goals         INTEGER,
    teams_count   INTEGER,
    final_date    TEXT
);

CREATE TABLE elo_ratings (
    team_id     INTEGER PRIMARY KEY REFERENCES teams(id),
    rating      REAL    NOT NULL,
    matches     INTEGER NOT NULL,
    peak_rating REAL,
    peak_date   TEXT
);

CREATE TABLE elo_history (
    team_id INTEGER NOT NULL REFERENCES teams(id),
    date    TEXT    NOT NULL,
    rating  REAL    NOT NULL
);

-- Empirical draw rate per Elo-gap bucket, measured from the full history.
CREATE TABLE draw_calibration (
    bucket    INTEGER PRIMARY KEY,
    gap_lo    INTEGER,
    gap_hi    INTEGER,
    matches   INTEGER,
    draws     INTEGER,
    draw_rate REAL
);

-- Scores describing how well the predictor performs on historical matches.
CREATE TABLE model_metrics (
    name  TEXT PRIMARY KEY,
    value REAL
);

CREATE INDEX idx_matches_wc     ON matches(is_world_cup, year);
CREATE INDEX idx_matches_home   ON matches(home_team_id);
CREATE INDEX idx_matches_away   ON matches(away_team_id);
CREATE INDEX idx_goals_match    ON goals(match_id);
CREATE INDEX idx_elo_hist_team  ON elo_history(team_id, date);

-- Each match written twice, once from each team's point of view. Turns every
-- "how did team X do" question into a simple WHERE team_id = ?.
DROP VIEW IF EXISTS team_matches;
CREATE VIEW team_matches AS
    SELECT id AS match_id, date, year, tournament, is_world_cup, neutral, city, country,
           home_team_id AS team_id, away_team_id AS opponent_id,
           home_score AS gf, away_score AS ga, 1 AS was_home
    FROM matches
    UNION ALL
    SELECT id, date, year, tournament, is_world_cup, neutral, city, country,
           away_team_id, home_team_id, away_score, home_score, 0
    FROM matches;
