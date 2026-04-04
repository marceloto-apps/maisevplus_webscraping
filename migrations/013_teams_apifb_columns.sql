-- migrations/013_teams_apifb_columns.sql
ALTER TABLE teams ADD COLUMN IF NOT EXISTS api_football_id INTEGER;
ALTER TABLE teams ADD COLUMN IF NOT EXISTS api_football_name VARCHAR(100);
