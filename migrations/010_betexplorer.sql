-- ============================================================
-- Migration: T09_betexplorer_integration
-- Data: 2026-04-02
-- Descrição: Adiciona suporte ao BetExplorer como fonte de odds
-- e estende a hypertable de odds_history para acomodar mercados secundários
-- ============================================================

-- 1. Expansão da Hypertable odds_history para mercados secundários (AH, OU, DC, etc)
-- A schema base tinha apenas odds_1, odds_x e odds_2.
ALTER TABLE odds_history ADD COLUMN IF NOT EXISTS opening_1 NUMERIC(8,4);
ALTER TABLE odds_history ADD COLUMN IF NOT EXISTS opening_x NUMERIC(8,4);
ALTER TABLE odds_history ADD COLUMN IF NOT EXISTS opening_2 NUMERIC(8,4);

ALTER TABLE odds_history ADD COLUMN IF NOT EXISTS odds_over NUMERIC(8,4);
ALTER TABLE odds_history ADD COLUMN IF NOT EXISTS odds_under NUMERIC(8,4);

ALTER TABLE odds_history ADD COLUMN IF NOT EXISTS odds_home NUMERIC(8,4);
ALTER TABLE odds_history ADD COLUMN IF NOT EXISTS odds_away NUMERIC(8,4);

ALTER TABLE odds_history ADD COLUMN IF NOT EXISTS odds_1x NUMERIC(8,4);
ALTER TABLE odds_history ADD COLUMN IF NOT EXISTS odds_12 NUMERIC(8,4);
ALTER TABLE odds_history ADD COLUMN IF NOT EXISTS odds_x2 NUMERIC(8,4);

ALTER TABLE odds_history ADD COLUMN IF NOT EXISTS odds_yes NUMERIC(8,4);
ALTER TABLE odds_history ADD COLUMN IF NOT EXISTS odds_no NUMERIC(8,4);

-- 2. Adiciona betexplorer_path na tabela leagues
ALTER TABLE leagues ADD COLUMN IF NOT EXISTS betexplorer_path VARCHAR(100);

-- 3. Popula os 26 paths validados pelo discovery
UPDATE leagues SET betexplorer_path = 'england/premier-league' WHERE code = 'ENG_PL';
UPDATE leagues SET betexplorer_path = 'england/championship' WHERE code = 'ENG_CH';
UPDATE leagues SET betexplorer_path = 'england/league-one' WHERE code = 'ENG_L1';
UPDATE leagues SET betexplorer_path = 'england/league-two' WHERE code = 'ENG_L2';
UPDATE leagues SET betexplorer_path = 'england/national-league' WHERE code = 'ENG_NL';
UPDATE leagues SET betexplorer_path = 'scotland/premiership' WHERE code = 'SCO_PL';
UPDATE leagues SET betexplorer_path = 'scotland/championship' WHERE code = 'SCO_CH';
UPDATE leagues SET betexplorer_path = 'scotland/league-one' WHERE code = 'SCO_L1';
UPDATE leagues SET betexplorer_path = 'scotland/league-two' WHERE code = 'SCO_L2';
UPDATE leagues SET betexplorer_path = 'germany/bundesliga' WHERE code = 'GER_BL';
UPDATE leagues SET betexplorer_path = 'germany/2-bundesliga' WHERE code = 'GER_B2';
UPDATE leagues SET betexplorer_path = 'italy/serie-a' WHERE code = 'ITA_SA';
UPDATE leagues SET betexplorer_path = 'italy/serie-b' WHERE code = 'ITA_SB';
UPDATE leagues SET betexplorer_path = 'spain/laliga' WHERE code = 'ESP_PD';
UPDATE leagues SET betexplorer_path = 'spain/laliga2' WHERE code = 'ESP_SD';
UPDATE leagues SET betexplorer_path = 'france/ligue-1' WHERE code = 'FRA_L1';
UPDATE leagues SET betexplorer_path = 'france/ligue-2' WHERE code = 'FRA_L2';
UPDATE leagues SET betexplorer_path = 'netherlands/eredivisie' WHERE code = 'NED_ED';
UPDATE leagues SET betexplorer_path = 'belgium/jupiler-pro-league' WHERE code = 'BEL_PL';
UPDATE leagues SET betexplorer_path = 'portugal/primeira-liga' WHERE code = 'POR_PL';
UPDATE leagues SET betexplorer_path = 'turkey/super-lig' WHERE code = 'TUR_SL';
UPDATE leagues SET betexplorer_path = 'greece/super-league' WHERE code = 'GRE_SL';
UPDATE leagues SET betexplorer_path = 'brazil/serie-a-betano' WHERE code = 'BRA_SA';
UPDATE leagues SET betexplorer_path = 'mexico/liga-mx' WHERE code = 'MEX_LM';
UPDATE leagues SET betexplorer_path = 'austria/bundesliga' WHERE code = 'AUT_BL';
UPDATE leagues SET betexplorer_path = 'switzerland/super-league' WHERE code = 'SWI_SL';

-- 4. Índice para queries por source + match
CREATE INDEX IF NOT EXISTS idx_odds_history_source_match
    ON odds_history (source, match_id);

-- 5. Índice para queries de CLV (closing line por bookmaker)
CREATE INDEX IF NOT EXISTS idx_odds_history_closing_bookmaker
    ON odds_history (is_closing, bookmaker_id, market_type)
    WHERE is_closing = TRUE;

-- 6. Tabela de controle de coleta (saber o que já foi coletado)
CREATE TABLE IF NOT EXISTS betexplorer_collection_log (
    id SERIAL PRIMARY KEY,
    league_code VARCHAR(10) NOT NULL,
    match_id VARCHAR(20) NOT NULL,
    market VARCHAR(20) NOT NULL,
    bookmaker_count INTEGER DEFAULT 0,
    collected_at TIMESTAMPTZ DEFAULT NOW(),
    status VARCHAR(20) DEFAULT 'success',  -- 'success', 'partial', 'failed'
    error_message TEXT,
    duration_ms INTEGER,
    UNIQUE (match_id, market, collected_at)
);

CREATE INDEX IF NOT EXISTS idx_collection_log_league_date
    ON betexplorer_collection_log (league_code, collected_at DESC);

-- 7. View auxiliar: último snapshot de odds por jogo/mercado/bookmaker
-- Traz as bookmakers pelo JOIN para bater com a visão analítica.
CREATE OR REPLACE VIEW v_latest_odds AS
SELECT DISTINCT ON (oh.match_id, oh.market_type, oh.bookmaker_id)
    oh.match_id,
    oh.source,
    oh.market_type AS market,
    b.name AS bookmaker,
    oh.odds_1, oh.odds_x, oh.odds_2,
    oh.opening_1, oh.opening_x, oh.opening_2,
    oh.line,
    oh.odds_over, oh.odds_under,
    oh.odds_home, oh.odds_away,
    oh.odds_1x, oh.odds_12, oh.odds_x2,
    oh.odds_yes, oh.odds_no,
    oh.is_closing,
    oh.time AS collected_at
FROM odds_history oh
JOIN bookmakers b ON b.bookmaker_id = oh.bookmaker_id
ORDER BY oh.match_id, oh.market_type, oh.bookmaker_id, oh.time DESC;
