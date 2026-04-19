-- =============================================================
-- 019_odds_quality_flags.sql
-- Adiciona flags para qualificação de coerência de odds na tabela match_data_quality
-- =============================================================

ALTER TABLE match_data_quality
    ADD COLUMN suspicious_1x2_odds BOOLEAN DEFAULT FALSE,
    ADD COLUMN suspicious_ah_odds  BOOLEAN DEFAULT FALSE,
    ADD COLUMN suspicious_ou_odds  BOOLEAN DEFAULT FALSE;

CREATE INDEX idx_mdq_suspicious ON match_data_quality (match_id)
WHERE suspicious_1x2_odds OR suspicious_ah_odds OR suspicious_ou_odds;

COMMENT ON COLUMN match_data_quality.suspicious_1x2_odds IS 'Odds 1x2 fora de range, ou com soma de probabilidade implicita bizarra (margins), ou valores identicos.';
COMMENT ON COLUMN match_data_quality.suspicious_ah_odds IS 'Asian Handicap com progressão invertida de odd x line, fora de range ou linhas genéricas.';
COMMENT ON COLUMN match_data_quality.suspicious_ou_odds IS 'Over/Under com progressão invertida, fora de range ou flat lines (lixo).';
