-- =============================================================
-- 004_control_tables.sql
-- Tabelas de controle: ingestion_log
-- Depende de: nenhuma FK externa
-- =============================================================

-- ------------------------------------------------------------
-- 6.1 ingestion_log
-- ------------------------------------------------------------
CREATE TABLE ingestion_log (
    log_id              SERIAL PRIMARY KEY,
    job_id              VARCHAR(50) NOT NULL,
    source              VARCHAR(20) NOT NULL,
    job_type            VARCHAR(30) NOT NULL,
    started_at          TIMESTAMPTZ NOT NULL,
    finished_at         TIMESTAMPTZ,
    status              VARCHAR(15) NOT NULL,
    records_collected   INTEGER DEFAULT 0,
    records_new         INTEGER DEFAULT 0,
    records_skipped     INTEGER DEFAULT 0,
    error_message       TEXT,
    metadata_json       JSONB,
    created_at          TIMESTAMPTZ DEFAULT NOW()
);

COMMENT ON TABLE ingestion_log IS 'Log de jobs. Critério de aceite: sem failed por 48h.';
