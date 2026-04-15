-- =============================================================
-- 017_prematch_odds.sql
-- Tabela e infraestrutura analítica para odds pré-live
-- =============================================================

-- 1. Garante que qualquer criação subsequente seja obrigatoriamente no schema public.
SET search_path TO public;

-- 2. Limpa qualquer criação acidental anterior no schema features se ocorreu via run-away search paths.
DROP VIEW IF EXISTS features.v_prematch_evolution CASCADE;
DROP TABLE IF EXISTS features.prematch_odds CASCADE;
DROP FUNCTION IF EXISTS features.mark_closing_prematch(UUID) CASCADE;

CREATE TABLE public.prematch_odds (
    id                  BIGSERIAL,
    time                TIMESTAMPTZ NOT NULL,
    match_id            UUID NOT NULL REFERENCES matches(match_id) ON DELETE CASCADE,
    bookmaker_id        INTEGER NOT NULL REFERENCES bookmakers(bookmaker_id),
    market_type         VARCHAR(10) NOT NULL,
    line                NUMERIC(5,2),
    period              VARCHAR(5) DEFAULT 'ft',
    
    odds_1              NUMERIC(8,4),
    odds_x              NUMERIC(8,4),
    odds_2              NUMERIC(8,4),
    overround           NUMERIC(6,4),
    
    odd_period          VARCHAR(15) NOT NULL,
    odd_moment          VARCHAR(10) NOT NULL,
    source              VARCHAR(20) NOT NULL,
    collect_job_id      VARCHAR(50),
    
    PRIMARY KEY (id, time)
);

COMMENT ON TABLE prematch_odds IS 'Hypertable TimescaleDB para snapshots frequentes de odds pré-jogo sem dedup rígido.';
COMMENT ON COLUMN prematch_odds.odd_period IS 'Tempo até o kickoff na coleta (e.g. 74h26m)';
COMMENT ON COLUMN prematch_odds.odd_moment IS 'opening | mid | closing (closing será setado iterativamente no fim)';

SELECT create_hypertable('public.prematch_odds', 'time', chunk_time_interval => INTERVAL '1 month', if_not_exists => TRUE);

-- =============================================================
-- Indexes
-- =============================================================
-- 1. Timeline de um jogo
CREATE INDEX IF NOT EXISTS idx_prematch_evolution ON public.prematch_odds(match_id, bookmaker_id, market_type, time DESC);

-- 2. Busca por momento
CREATE INDEX IF NOT EXISTS idx_prematch_moment ON public.prematch_odds(odd_moment, time DESC);

-- 3. Último snapshot
CREATE INDEX IF NOT EXISTS idx_prematch_last_snapshot ON public.prematch_odds(match_id, time DESC);

-- 4. Rastreio de jobs
CREATE INDEX IF NOT EXISTS idx_prematch_job ON public.prematch_odds(source, collect_job_id);

-- Index auxiliar em matches
CREATE INDEX IF NOT EXISTS idx_matches_scheduled_flashscore ON public.matches(kickoff, league_id) 
WHERE status = 'scheduled' AND flashscore_id IS NOT NULL;


-- =============================================================
-- Views Analíticas
-- =============================================================
CREATE OR REPLACE VIEW public.v_prematch_evolution AS
SELECT
    m.league_id,
    l.tier,
    m.home_team_id,
    m.away_team_id,
    m.kickoff,
    po.match_id,
    po.bookmaker_id,
    b.display_name AS bookmaker_name,
    po.market_type,
    po.line,
    po.period,
    po.odds_1,
    po.odds_x,
    po.odds_2,
    po.overround,
    po.odd_period,
    po.odd_moment,
    po.time,
    po.odds_1 - LAG(po.odds_1) OVER w_snapshot AS delta_1,
    po.odds_x - LAG(po.odds_x) OVER w_snapshot AS delta_x,
    po.odds_2 - LAG(po.odds_2) OVER w_snapshot AS delta_2,
    po.overround - LAG(po.overround) OVER w_snapshot AS delta_overround,
    ROW_NUMBER() OVER w_snapshot AS snapshot_num,
    COUNT(*) OVER w_combination AS total_snapshots,
    FIRST_VALUE(po.odds_1) OVER w_snapshot AS opening_odds_1,
    FIRST_VALUE(po.odds_x) OVER w_snapshot AS opening_odds_x,
    FIRST_VALUE(po.odds_2) OVER w_snapshot AS opening_odds_2
FROM prematch_odds po
JOIN matches m ON po.match_id = m.match_id
JOIN leagues l ON m.league_id = l.league_id
JOIN bookmakers b ON po.bookmaker_id = b.bookmaker_id
WINDOW 
    w_combination AS (PARTITION BY po.match_id, po.bookmaker_id, po.market_type, COALESCE(po.line, 0), po.period),
    w_snapshot AS (PARTITION BY po.match_id, po.bookmaker_id, po.market_type, COALESCE(po.line, 0), po.period ORDER BY po.time);


-- =============================================================
-- Functions
-- =============================================================
CREATE OR REPLACE FUNCTION public.mark_closing_prematch(p_match_id UUID)
RETURNS void AS $$
BEGIN
    WITH last_snapshots AS (
        SELECT id, time
        FROM (
            SELECT id, time,
                   ROW_NUMBER() OVER (
                       PARTITION BY bookmaker_id, market_type, COALESCE(line, 0), period
                       ORDER BY time DESC
                   ) as rn
            FROM prematch_odds
            WHERE match_id = p_match_id
        ) sub
        WHERE rn = 1
    )
    UPDATE prematch_odds
    SET odd_moment = 'closing'
    FROM last_snapshots ls
    WHERE prematch_odds.id = ls.id AND prematch_odds.time = ls.time;
END;
$$ LANGUAGE plpgsql;
