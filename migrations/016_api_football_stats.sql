-- migrations/016_api_football_stats.sql
-- Extraindo stats relevantes da api-football que complementam a footystats

-- Shots off Goal (substituindo ou adicionando como coluna clara da apifootball)
ALTER TABLE match_stats
  ADD COLUMN IF NOT EXISTS shots_off_goal_home SMALLINT,
  ADD COLUMN IF NOT EXISTS shots_off_goal_away SMALLINT,
  
-- Blocked Shots
  ADD COLUMN IF NOT EXISTS blocked_shots_home SMALLINT,
  ADD COLUMN IF NOT EXISTS blocked_shots_away SMALLINT,

-- Shots insidebox
  ADD COLUMN IF NOT EXISTS shots_insidebox_home SMALLINT,
  ADD COLUMN IF NOT EXISTS shots_insidebox_away SMALLINT,

-- Shots outsidebox
  ADD COLUMN IF NOT EXISTS shots_outsidebox_home SMALLINT,
  ADD COLUMN IF NOT EXISTS shots_outsidebox_away SMALLINT,

-- Goalkeeper Saves
  ADD COLUMN IF NOT EXISTS goalkeeper_saves_home SMALLINT,
  ADD COLUMN IF NOT EXISTS goalkeeper_saves_away SMALLINT,

-- Total passes e Passes accurate (Valores grandes, INT)
  ADD COLUMN IF NOT EXISTS total_passes_home INTEGER,
  ADD COLUMN IF NOT EXISTS total_passes_away INTEGER,
  ADD COLUMN IF NOT EXISTS passes_accurate_home INTEGER,
  ADD COLUMN IF NOT EXISTS passes_accurate_away INTEGER,

-- Passes %
  ADD COLUMN IF NOT EXISTS passes_pct_home NUMERIC(5,2),
  ADD COLUMN IF NOT EXISTS passes_pct_away NUMERIC(5,2),

-- Expected Goals (xG) da API Football
  ADD COLUMN IF NOT EXISTS expected_goals_home NUMERIC(5,2),
  ADD COLUMN IF NOT EXISTS expected_goals_away NUMERIC(5,2);
