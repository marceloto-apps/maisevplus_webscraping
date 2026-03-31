-- =============================================================
-- 001_extensions.sql
-- Extensions necessárias para o banco maisevplus (M1)
-- Pré-requisito: PostgreSQL 16+ com TimescaleDB 2.13+
-- =============================================================

CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE;
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- Verificação pós-instalação
-- SELECT extname, extversion FROM pg_extension WHERE extname IN ('timescaledb', 'pgcrypto');
