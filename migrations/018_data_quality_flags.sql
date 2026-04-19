-- =============================================================
-- 018_data_quality_flags.sql
-- Tabela para rastrear a cobertura de dados e identificar
-- jogos que faltam alguma parte de odds ou estatísticas.
-- =============================================================

CREATE TABLE match_data_quality (
    match_id                    UUID PRIMARY KEY REFERENCES matches(match_id) ON DELETE CASCADE,
    
    -- Flags verdadeiras se estiver FALTANDO o dado esperado
    missing_footystats_stats    BOOLEAN DEFAULT FALSE,
    missing_apifb_stats         BOOLEAN DEFAULT FALSE,
    missing_flashscore_stats    BOOLEAN DEFAULT FALSE,
    missing_fd_odds             BOOLEAN DEFAULT FALSE,
    missing_fs_odds             BOOLEAN DEFAULT FALSE,
    
    updated_at                  TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_mdq_missing_stats ON match_data_quality (match_id)
WHERE missing_footystats_stats OR missing_apifb_stats OR missing_flashscore_stats;

CREATE INDEX idx_mdq_missing_odds ON match_data_quality (match_id)
WHERE missing_fd_odds OR missing_fs_odds;

COMMENT ON TABLE match_data_quality IS 'Tabela alimentada via job diário (data_quality_routine) para classificar gaps de cobertura nas partidas finalizadas.';
