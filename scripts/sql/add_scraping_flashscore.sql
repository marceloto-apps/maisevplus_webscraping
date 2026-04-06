-- Adiciona coluna de controle de backfill na tabela matches
ALTER TABLE matches ADD COLUMN IF NOT EXISTS scraping_flashscore boolean DEFAULT false;
