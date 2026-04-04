-- migrations/012_api_football_expansion.sql
-- Adiciona a coluna is_home em lineups para compatibilidade com os parsers
ALTER TABLE lineups ADD COLUMN IF NOT EXISTS is_home BOOLEAN;

-- Adiciona a coluna api_football_league_id nas ligas (requerida para mapeamento)
ALTER TABLE leagues ADD COLUMN IF NOT EXISTS api_football_league_id INTEGER;

-- Criação da tabela de Eventos do Jogo
CREATE TABLE IF NOT EXISTS match_events (
    event_id SERIAL PRIMARY KEY,
    match_id UUID NOT NULL REFERENCES matches(match_id) ON DELETE CASCADE,
    time_elapsed INTEGER NOT NULL,
    time_extra INTEGER,
    team_id INTEGER REFERENCES teams(team_id),
    player_id INTEGER,
    player_name VARCHAR(150),
    assist_id INTEGER,
    assist_name VARCHAR(150),
    event_type VARCHAR(50) NOT NULL,
    event_detail VARCHAR(100),
    comments TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    -- Restrição de unicidade para evitar duplicações no backfill/re-scrapes
    UNIQUE(match_id, team_id, time_elapsed, time_extra, event_type, player_name)
);

CREATE INDEX IF NOT EXISTS idx_match_events_match_id ON match_events(match_id);
CREATE INDEX IF NOT EXISTS idx_match_events_team_id ON match_events(team_id);

-- Criação da tabela de Estatísticas Individuais de Jogadores
CREATE TABLE IF NOT EXISTS match_player_stats (
    stats_id SERIAL PRIMARY KEY,
    match_id UUID NOT NULL REFERENCES matches(match_id) ON DELETE CASCADE,
    team_id INTEGER NOT NULL REFERENCES teams(team_id),
    player_id INTEGER NOT NULL,
    player_name VARCHAR(150) NOT NULL,
    minutes_played INTEGER,
    rating NUMERIC(4,2),
    
    -- Ataque
    goals INTEGER,
    assists INTEGER,
    shots_total INTEGER,
    shots_on INTEGER,
    
    -- Passes
    passes_total INTEGER,
    passes_key INTEGER,
    passes_accuracy NUMERIC(5,2),
    
    -- Defesa
    tackles INTEGER,
    blocks INTEGER,
    interceptions INTEGER,
    
    -- Duelos
    duels_total INTEGER,
    duels_won INTEGER,
    
    -- Dribles
    dribbles_attempts INTEGER,
    dribbles_success INTEGER,
    
    -- Faltas/Cartões
    fouls_drawn INTEGER,
    fouls_committed INTEGER,
    cards_yellow INTEGER,
    cards_red INTEGER,
    offsides INTEGER,
    saves INTEGER,
    
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(match_id, player_id)
);

CREATE INDEX IF NOT EXISTS idx_match_player_stats_match_id ON match_player_stats(match_id);
CREATE INDEX IF NOT EXISTS idx_match_player_stats_team_id ON match_player_stats(team_id);

-- View para facilitar a identificação dos matches de ontem (D-1) aptos à coleta
CREATE OR REPLACE VIEW v_today_matches_apifb AS
SELECT 
    m.match_id,
    m.api_football_id,
    l.api_football_league_id,
    s.label as season_label,
    m.kickoff
FROM matches m
JOIN leagues l ON m.league_id = l.league_id
JOIN seasons s ON m.season_id = s.season_id
WHERE m.status IN ('finished', 'FT', 'AET', 'PEN')
  AND m.api_football_id IS NOT NULL 
  AND l.api_football_league_id IS NOT NULL
  AND m.kickoff::date >= current_date - interval '2 days';
