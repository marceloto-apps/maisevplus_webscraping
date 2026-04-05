-- migrations/015_lineups_normalize.sql
-- Normaliza a tabela lineups: de 1 row/team (players_json blob)
-- para N rows/time, uma por jogador / técnico.
--
-- Colunas novas:
--   fixture_position  VARCHAR  'coach' | 'startXI' | 'substitutes'
--   player_id         INTEGER  id do jogador na API-Football (coach incluso)
--   player_name       VARCHAR  nome do jogador / técnico
--   player_number     INTEGER  número da camisa (NULL para coach)
--   player_pos        VARCHAR  posição ('G','D','M','F','coach')
--   player_grid       VARCHAR  grade de campo ('1:1', '2:3', NULL para subs/coach)

-- 1. Apaga dados legacy (piloto — não há dados de produção ainda)
TRUNCATE TABLE lineups;

-- 2. Remove coluna antiga
ALTER TABLE lineups DROP COLUMN IF EXISTS players_json;

-- 3. Remove constraint antiga (nome pode variar)
DO $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM pg_constraint
    WHERE conrelid = 'lineups'::regclass
      AND conname LIKE '%match_id%team_id%source%'
  ) THEN
    ALTER TABLE lineups DROP CONSTRAINT lineups_match_id_team_id_source_key;
  END IF;
EXCEPTION WHEN OTHERS THEN NULL;
END $$;

-- 4. Adiciona novas colunas
ALTER TABLE lineups
  ADD COLUMN IF NOT EXISTS fixture_position VARCHAR(20),
  ADD COLUMN IF NOT EXISTS player_id        INTEGER,
  ADD COLUMN IF NOT EXISTS player_name      VARCHAR(200),
  ADD COLUMN IF NOT EXISTS player_number    INTEGER,
  ADD COLUMN IF NOT EXISTS player_pos       VARCHAR(20),
  ADD COLUMN IF NOT EXISTS player_grid      VARCHAR(20);

-- 5. Constraint única nomeada (necessária para ON CONFLICT ON CONSTRAINT)
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname = 'lineups_unique_player_key'
  ) THEN
    ALTER TABLE lineups
      ADD CONSTRAINT lineups_unique_player_key
      UNIQUE(match_id, team_id, source, fixture_position, player_id);
  END IF;
END $$;

-- 6. Índices de busca
CREATE INDEX IF NOT EXISTS idx_lineups_player_id        ON lineups(player_id)        WHERE player_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_lineups_fixture_position ON lineups(fixture_position);
