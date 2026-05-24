-- Rollback da migration 020
-- ⚠️ Use somente em caso de falha crítica. Restaure match_stats a partir do backup depois.
BEGIN;

DROP VIEW IF EXISTS v_match_full CASCADE;

ALTER TABLE matches 
    DROP COLUMN IF EXISTS flashscore_stats_collected,
    DROP COLUMN IF EXISTS flashscore_odds_collected;

ALTER TABLE leagues DROP COLUMN IF EXISTS primary_source;

DROP TABLE IF EXISTS match_stats_fs;

COMMIT;

-- Em seguida, restaure os dados antigos:
--   psql $DATABASE_URL < backup_match_stats_pre_020.sql
-- E recrie a view v_match_full executando a versão anterior da definição
-- (verificar última migration anterior à 020 que cria v_match_full, i.e., 013_flatten_match_stats.sql).
