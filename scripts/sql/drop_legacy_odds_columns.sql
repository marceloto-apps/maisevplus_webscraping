-- Drop de colunas obsoletas da tabela odds_history
-- Rode na VPS: psql -U maisevplus -d maisevplus_db -f scripts/sql/drop_legacy_odds_columns.sql

ALTER TABLE odds_history
  DROP COLUMN IF EXISTS opening_x,
  DROP COLUMN IF EXISTS opening_2,
  DROP COLUMN IF EXISTS odds_over,
  DROP COLUMN IF EXISTS odds_under,
  DROP COLUMN IF EXISTS odds_home,
  DROP COLUMN IF EXISTS odds_away,
  DROP COLUMN IF EXISTS odds_1x,
  DROP COLUMN IF EXISTS odds_12,
  DROP COLUMN IF EXISTS odds_x2,
  DROP COLUMN IF EXISTS odds_yes,
  DROP COLUMN IF EXISTS odds_no;
