-- Migração para recriar o índice de dedup com a estratégia de placeholder
BEGIN;

DROP INDEX IF EXISTS idx_odds_dedup;

CREATE UNIQUE INDEX idx_odds_dedup ON odds_history (
    match_id, bookmaker_id, market_type,
    COALESCE(line, -9999), period, content_hash, time
);

COMMIT;
