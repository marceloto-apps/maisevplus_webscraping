-- ⚠️ PRÉ-REQUISITO MANUAL:
-- Antes de executar esta migration, faça backup da tabela match_stats:
--   pg_dump -t match_stats $DATABASE_URL > backup_match_stats_pre_020.sql
-- Esta migration faz DROP de colunas (xg_fs_*, xgot_fs_*, xa_fs_*) após migrar os dados.

BEGIN;

-- 1. Criar a nova tabela match_stats_fs
CREATE TABLE IF NOT EXISTS match_stats_fs (
    id              BIGSERIAL PRIMARY KEY,
    match_id        UUID NOT NULL REFERENCES matches(match_id) ON DELETE CASCADE,
    
    -- xG (Expected Goals)
    xg_home_ft      NUMERIC(5,2),
    xg_away_ft      NUMERIC(5,2),
    xg_home_ht      NUMERIC(5,2),
    xg_away_ht      NUMERIC(5,2),
    xg_home_2h      NUMERIC(5,2),
    xg_away_2h      NUMERIC(5,2),
    
    -- xGOT (Expected Goals on Target)
    xgot_home_ft    NUMERIC(5,2),
    xgot_away_ft    NUMERIC(5,2),
    xgot_home_ht    NUMERIC(5,2),
    xgot_away_ht    NUMERIC(5,2),
    xgot_home_2h    NUMERIC(5,2),
    xgot_away_2h    NUMERIC(5,2),
    
    -- xA (Expected Assists)
    xa_home_ft      NUMERIC(5,2),
    xa_away_ft      NUMERIC(5,2),
    xa_home_ht      NUMERIC(5,2),
    xa_away_ht      NUMERIC(5,2),
    xa_home_2h      NUMERIC(5,2),
    xa_away_2h      NUMERIC(5,2),
    
    collected_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
    CONSTRAINT uq_match_stats_fs_match UNIQUE (match_id)
);

CREATE INDEX IF NOT EXISTS idx_match_stats_fs_match_id ON match_stats_fs(match_id);
CREATE INDEX IF NOT EXISTS idx_match_stats_fs_collected_at ON match_stats_fs(collected_at);

-- 2. Proteção idempotente na migração de dados
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name='match_stats' AND column_name='xg_fs_home'
    ) THEN
        INSERT INTO match_stats_fs (
            match_id, 
            xg_home_ft, xg_away_ft, 
            xgot_home_ft, xgot_away_ft, 
            xa_home_ft, xa_away_ft, 
            collected_at
        )
        SELECT 
            match_id,
            xg_fs_home, xg_fs_away,
            xgot_fs_home, xgot_fs_away,
            xa_fs_home, xa_fs_away,
            collected_at
        FROM match_stats
        WHERE xg_fs_home IS NOT NULL 
           OR xg_fs_away IS NOT NULL 
           OR xgot_fs_home IS NOT NULL 
           OR xgot_fs_away IS NOT NULL 
           OR xa_fs_home IS NOT NULL 
           OR xa_fs_away IS NOT NULL
        ON CONFLICT (match_id) DO NOTHING;
        
        RAISE NOTICE 'Migração de dados Flashscore concluída';
    ELSE
        RAISE NOTICE 'Colunas xg_fs_* já removidas, pulando migração de dados';
    END IF;
END $$;

-- 3. Deletar colunas flashscore antigas de match_stats (exceto crosses)
ALTER TABLE match_stats 
    DROP COLUMN IF EXISTS xg_fs_home,
    DROP COLUMN IF EXISTS xg_fs_away,
    DROP COLUMN IF EXISTS xgot_fs_home,
    DROP COLUMN IF EXISTS xgot_fs_away,
    DROP COLUMN IF EXISTS xa_fs_home,
    DROP COLUMN IF EXISTS xa_fs_away;

-- 4. Adicionar novas colunas em matches para controle
ALTER TABLE matches
    ADD COLUMN IF NOT EXISTS flashscore_stats_collected BOOLEAN NOT NULL DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS flashscore_odds_collected  BOOLEAN NOT NULL DEFAULT FALSE;

CREATE INDEX IF NOT EXISTS idx_matches_fs_stats_collected ON matches(flashscore_stats_collected) WHERE flashscore_stats_collected = FALSE;
CREATE INDEX IF NOT EXISTS idx_matches_fs_odds_collected  ON matches(flashscore_odds_collected)  WHERE flashscore_odds_collected = FALSE;

-- 5. Adicionar a coluna primary_source em leagues
ALTER TABLE leagues ADD COLUMN IF NOT EXISTS primary_source VARCHAR(20) DEFAULT 'footystats';

-- Atualiza as 26 ligas atuais
UPDATE leagues SET primary_source = 'footystats' WHERE primary_source IS NULL;

-- 6. Recriar View v_match_full apontando para match_stats_fs (sem crosses)
DROP VIEW IF EXISTS v_match_full CASCADE;

CREATE OR REPLACE VIEW v_match_full AS
SELECT
    m.match_id,
    m.season_id,
    m.kickoff,
    m.status,
    l.code AS league_code,
    l.name AS league_name,
    l.tier,
    l.xg_source AS xg_primary_source,
    s.label AS season_label,
    th.name_canonical AS home_team,
    ta.name_canonical AS away_team,
    m.ft_home,
    m.ft_away,
    m.ht_home,
    m.ht_away,
    ms.goals_home_minutes,
    ms.goals_away_minutes,

    -- xG nativos
    ms.xg_home AS footystats_xg_home,
    ms.xg_away AS footystats_xg_away,
    ms_fs.xg_home_ft AS xg_fs_home,
    ms_fs.xg_away_ft AS xg_fs_away,
    ms_fs.xgot_home_ft AS xgot_fs_home,
    ms_fs.xgot_away_ft AS xgot_fs_away,
    ms_fs.xa_home_ft AS xa_fs_home,
    ms_fs.xa_away_ft AS xa_fs_away,

    -- xGA nativos da pipeline do pbref
    ms.xga_home,
    ms.xga_away,
    
    -- Ataques / perigos
    ms.dangerous_attacks_home,
    ms.dangerous_attacks_away,
    ms.attacks_home,
    ms.attacks_away,
    
    -- Gols Totais
    ms.total_goals_ft,

    -- Posse
    ms.possession_home,
    ms.possession_away,

    -- Corners FT
    ms.corners_home_ft,
    ms.corners_away_ft,
    ms.total_corners_ft,

    -- Impedimentos / Faltas
    ms.offsides_home,
    ms.offsides_away,
    ms.fouls_home,
    ms.fouls_away,
    
    -- Cartões FT
    ms.yellow_cards_home_ft,
    ms.yellow_cards_away_ft,
    ms.red_cards_home_ft,
    ms.red_cards_away_ft,
    
    -- Finalizações
    ms.shots_on_target_home,
    ms.shots_on_target_away,
    ms.shots_off_target_home,
    ms.shots_off_target_away,
    ms.shots_home,
    ms.shots_away,
    
    -- BTTS
    ms.btts_potential,
    
    -- Stats HT / 2H
    ms.corners_home_ht,
    ms.corners_away_ht,
    ms.total_corners_ht,
    ms.corners_home_2h,
    ms.corners_away_2h,
    ms.goals_home_2h,
    ms.goals_away_2h,
    ms.cards_home_ht,
    ms.cards_away_ht,
    ms.cards_home_2h,
    ms.cards_away_2h,
    
    -- 0-10 min stats
    ms.goals_home_0_10_min,
    ms.goals_away_0_10_min,
    ms.corners_home_0_10_min,
    ms.corners_away_0_10_min,
    ms.cards_home_0_10_min,
    ms.cards_away_0_10_min,

    -- PPG Pre-match
    ms.home_ppg,
    ms.away_ppg,
    ms.pre_match_home_ppg,
    ms.pre_match_away_ppg,
    ms.pre_match_overall_ppg_home,
    ms.pre_match_overall_ppg_away,
    ms.xg_prematch_home,
    ms.xg_prematch_away

FROM matches m
JOIN leagues l ON m.league_id = l.league_id
JOIN seasons s ON m.season_id = s.season_id
JOIN teams th ON m.home_team_id = th.team_id
JOIN teams ta ON m.away_team_id = ta.team_id
LEFT JOIN match_stats ms ON m.match_id = ms.match_id
LEFT JOIN match_stats_fs ms_fs ON m.match_id = ms_fs.match_id;

COMMIT;
