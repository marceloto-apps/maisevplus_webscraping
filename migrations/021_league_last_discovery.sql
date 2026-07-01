-- Migration: 021_league_last_discovery.sql
-- Adiciona a coluna para armazenar o timestamp da última descoberta de fixtures do Flashscore

ALTER TABLE leagues ADD COLUMN IF NOT EXISTS last_fixtures_discovery_at TIMESTAMPTZ;
