-- Drop de colunas obsoletas da tabela odds_history
-- Também recria a view v_latest_odds sem as colunas dropadas.
-- Rode na VPS: psql -U maisevplus -d maisevplus_db -f scripts/sql/drop_legacy_odds_columns.sql

-- 1. Deleta a view atual que depende das colunas
DROP VIEW IF EXISTS v_latest_odds;

-- 2. Deleta as colunas
ALTER TABLE odds_history
  DROP COLUMN IF EXISTS opening_x CASCADE,
  DROP COLUMN IF EXISTS opening_2 CASCADE,
  DROP COLUMN IF EXISTS odds_over CASCADE,
  DROP COLUMN IF EXISTS odds_under CASCADE,
  DROP COLUMN IF EXISTS odds_home CASCADE,
  DROP COLUMN IF EXISTS odds_away CASCADE,
  DROP COLUMN IF EXISTS odds_1x CASCADE,
  DROP COLUMN IF EXISTS odds_12 CASCADE,
  DROP COLUMN IF EXISTS odds_x2 CASCADE,
  DROP COLUMN IF EXISTS odds_yes CASCADE,
  DROP COLUMN IF EXISTS odds_no CASCADE;

-- 3. Recria a view com o modelo atual
CREATE OR REPLACE VIEW v_latest_odds AS
SELECT DISTINCT ON (oh.match_id, oh.market_type, oh.bookmaker_id)
    oh.match_id,
    oh.source,
    oh.market_type AS market,
    b.name AS bookmaker,
    oh.odds_1, oh.odds_x, oh.odds_2,
    oh.opening_1, 
    oh.line,
    oh.is_closing,
    oh.time AS collected_at
FROM odds_history oh
JOIN bookmakers b ON b.bookmaker_id = oh.bookmaker_id
ORDER BY oh.match_id, oh.market_type, oh.bookmaker_id, oh.time DESC;
