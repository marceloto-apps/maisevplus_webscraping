-- =============================================================
-- 023_retrofit_queue.sql
-- Tabelas de controle e auditoria para o processo de retrofit.
-- =============================================================

CREATE TABLE IF NOT EXISTS public.retrofit_queue (
    league_id           INTEGER PRIMARY KEY REFERENCES public.leagues(league_id) ON DELETE CASCADE,
    priority            INTEGER NOT NULL,
    status              VARCHAR(20) NOT NULL DEFAULT 'pending',
    total_matches       INTEGER NOT NULL DEFAULT 0,
    processed_matches   INTEGER NOT NULL DEFAULT 0,
    success_matches     INTEGER NOT NULL DEFAULT 0,
    attempts            INTEGER NOT NULL DEFAULT 0,
    last_attempt_at     TIMESTAMPTZ,
    error_details       TEXT,
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS public.retrofit_match_log (
    match_id            UUID PRIMARY KEY REFERENCES public.matches(match_id) ON DELETE CASCADE,
    league_id           INTEGER NOT NULL REFERENCES public.leagues(league_id) ON DELETE CASCADE,
    status              VARCHAR(20) NOT NULL DEFAULT 'pending',
    error_message       TEXT,
    processed_at        TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_retrofit_match_log_league ON public.retrofit_match_log(league_id);

-- Trigger para atualizar updated_at automaticamente na tabela retrofit_queue
CREATE OR REPLACE TRIGGER trg_retrofit_queue_updated_at
    BEFORE UPDATE ON public.retrofit_queue
    FOR EACH ROW
    EXECUTE FUNCTION fn_update_timestamp();
