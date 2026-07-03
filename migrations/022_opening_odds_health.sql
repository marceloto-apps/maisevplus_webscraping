-- =============================================================
-- 022_opening_odds_health.sql
-- Adiciona a coluna opening_found às tabelas scraping_health de public e features.
-- =============================================================

ALTER TABLE public.scraping_health ADD COLUMN IF NOT EXISTS opening_found INT NOT NULL DEFAULT 0;
ALTER TABLE features.scraping_health ADD COLUMN IF NOT EXISTS opening_found INT NOT NULL DEFAULT 0;
