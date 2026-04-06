-- Migration 013: Flatten match_stats (One row per match)
-- Removes the 'source' column and constraints, making the table have exactly one row per match.

BEGIN;

-- 1. Dropar dependências Temporárias
DROP VIEW IF EXISTS v_match_full CASCADE;

-- 2. Consolidação e Limpeza (Remover dados de flashscore soltos ou lidar com duplicatas)
-- Vamos deletar as linhas secundárias que inserimos apenas para garantir que só sobrarão as primárias de footystats.
-- Alternativamente, poderíamos usar um UPSERT para merge, mas como o footystats tem a maior parte das infos e o flashscore tem os fs_stats,
-- o flashscore já não preencheu muito do arquivo local, então é mais leve deletar e reconsolidar tudo a longo prazo no mesmo row_id ou apagar duplicatas.
-- Como só testamos recentemente flashscore e few api_football, a forma mais segura de ter unique é:
WITH duplicates AS (
    SELECT stat_id,
           ROW_NUMBER() OVER(PARTITION BY match_id ORDER BY CASE WHEN source = 'footystats' THEN 1 ELSE 2 END, collected_at DESC) as rn
    FROM match_stats
)
DELETE FROM match_stats WHERE stat_id IN (SELECT stat_id FROM duplicates WHERE rn > 1);

-- 3. Remover constraints antigas (nome gerado ou explícito)
ALTER TABLE match_stats DROP CONSTRAINT IF EXISTS match_stats_match_id_source_key;
ALTER TABLE match_stats DROP CONSTRAINT IF EXISTS uq_match_stats_match_source;

-- 4. Dropar a coluna source
ALTER TABLE match_stats DROP COLUMN IF EXISTS source;

-- 5. Adicionar a constraint UNIQUE para match_id
ALTER TABLE match_stats ADD CONSTRAINT uq_match_stats_match_id UNIQUE (match_id);


-- 6. Recriar View v_match_full (AGORA MAIS SIMPLES, APENAS UM LEFT JOIN DIRETO)
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
    ms.xg_fs_home,
    ms.xg_fs_away,
    ms.xgot_fs_home,
    ms.xgot_fs_away,
    ms.xa_fs_home,
    ms.xa_fs_away,

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
    ms.crosses_fs_home,
    ms.crosses_fs_away,

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
LEFT JOIN match_stats ms ON m.match_id = ms.match_id;

COMMIT;
