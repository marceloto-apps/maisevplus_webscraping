-- =============================================================
-- 008_functions_triggers.sql
-- Funções e triggers utilitários
-- Depende de: 003_data_tables.sql, 002_reference_tables.sql
-- =============================================================

-- ============================================================
-- 11.1 Trigger updated_at para tabela matches
-- ============================================================
CREATE OR REPLACE FUNCTION fn_update_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_matches_updated_at
    BEFORE UPDATE ON matches
    FOR EACH ROW
    EXECUTE FUNCTION fn_update_timestamp();

-- ============================================================
-- 11.2 Reset Diário de Keys
-- ============================================================
CREATE OR REPLACE FUNCTION fn_reset_daily_api_keys()
RETURNS void AS $$
BEGIN
    UPDATE api_keys SET usage_today = 0, last_reset_at = NOW();
END;
$$ LANGUAGE plpgsql;

-- ============================================================
-- 11.3 Reset Mensal de Keys
-- ============================================================
CREATE OR REPLACE FUNCTION fn_reset_monthly_api_keys()
RETURNS void AS $$
BEGIN
    UPDATE api_keys SET usage_month = 0;
END;
$$ LANGUAGE plpgsql;
