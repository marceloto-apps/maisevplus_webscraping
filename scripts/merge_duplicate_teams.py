import asyncio
import os
import sys
from dotenv import load_dotenv

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.db.pool import get_pool

load_dotenv()

SQL_MERGE = """
DO $$
DECLARE
    r RECORD;
    m RECORD;
    target_match_id UUID;
    new_home_id INTEGER;
    new_away_id INTEGER;
    cnt_teams INTEGER := 0;
    cnt_matches INTEGER := 0;
BEGIN
    RAISE NOTICE '=== INICIANDO MESCLA DE TIMES DUPLICADOS ===';

    FOR r IN (
        WITH duplicates AS (
            SELECT 
                LOWER(name_canonical) AS clean_name, 
                country,
                MIN(team_id) AS keep_id
            FROM public.teams
            GROUP BY LOWER(name_canonical), country
            HAVING COUNT(*) > 1
        )
        SELECT 
            t.team_id AS delete_id,
            d.keep_id,
            t.name_canonical,
            t.country
        FROM public.teams t
        JOIN duplicates d ON LOWER(t.name_canonical) = d.clean_name AND t.country = d.country
        WHERE t.team_id <> d.keep_id
        ORDER BY d.keep_id ASC, t.team_id ASC
    ) LOOP
        cnt_teams := cnt_teams + 1;
        RAISE NOTICE 'Mesclando Time "%" (%) -> (%) no país "%"', r.name_canonical, r.delete_id, r.keep_id, r.country;

        -- 1. Resolver conflitos de partidas associadas ao time duplicado
        FOR m IN (
            SELECT match_id, league_id, home_team_id, away_team_id, kickoff
            FROM public.matches
            WHERE home_team_id = r.delete_id OR away_team_id = r.delete_id
        ) LOOP
            new_home_id := CASE WHEN m.home_team_id = r.delete_id THEN r.keep_id ELSE m.home_team_id END;
            new_away_id := CASE WHEN m.away_team_id = r.delete_id THEN r.keep_id ELSE m.away_team_id END;

            -- Verificar se já existe uma partida com a mesma chave única (league_id, home, away, data)
            SELECT match_id INTO target_match_id
            FROM public.matches
            WHERE league_id = m.league_id
              AND home_team_id = new_home_id
              AND away_team_id = new_away_id
              AND kickoff::date = m.kickoff::date
              AND match_id <> m.match_id
            LIMIT 1;

            IF target_match_id IS NOT NULL THEN
                cnt_matches := cnt_matches + 1;
                RAISE NOTICE '  -> Partida duplicada encontrada: % conflitando com %. Mesclando estatísticas e removendo.', m.match_id, target_match_id;
                
                -- Mesclar tabelas associadas antes de deletar a partida duplicada
                
                -- match_stats
                DELETE FROM public.match_stats 
                WHERE match_id = m.match_id 
                  AND EXISTS (SELECT 1 FROM public.match_stats WHERE match_id = target_match_id);
                UPDATE public.match_stats SET match_id = target_match_id WHERE match_id = m.match_id;

                -- match_stats_fs
                DELETE FROM public.match_stats_fs 
                WHERE match_id = m.match_id 
                  AND EXISTS (SELECT 1 FROM public.match_stats_fs WHERE match_id = target_match_id);
                UPDATE public.match_stats_fs SET match_id = target_match_id WHERE match_id = m.match_id;

                -- odds_history
                UPDATE public.odds_history SET match_id = target_match_id WHERE match_id = m.match_id;

                -- prematch_odds
                UPDATE public.prematch_odds SET match_id = target_match_id WHERE match_id = m.match_id;

                -- lineups
                DELETE FROM public.lineups 
                WHERE match_id = m.match_id 
                  AND EXISTS (
                      SELECT 1 FROM public.lineups 
                      WHERE match_id = target_match_id 
                        AND team_id = lineups.team_id 
                        AND source = lineups.source
                  );
                UPDATE public.lineups SET match_id = target_match_id WHERE match_id = m.match_id;

                -- match_events
                DELETE FROM public.match_events 
                WHERE match_id = m.match_id 
                  AND EXISTS (
                      SELECT 1 FROM public.match_events 
                      WHERE match_id = target_match_id 
                        AND COALESCE(team_id, 0) = COALESCE(match_events.team_id, 0) 
                        AND time_elapsed = match_events.time_elapsed 
                        AND COALESCE(time_extra, 0) = COALESCE(match_events.time_extra, 0) 
                        AND event_type = match_events.event_type 
                        AND player_name = match_events.player_name
                  );
                UPDATE public.match_events SET match_id = target_match_id WHERE match_id = m.match_id;

                -- match_player_stats
                DELETE FROM public.match_player_stats 
                WHERE match_id = m.match_id 
                  AND EXISTS (
                      SELECT 1 FROM public.match_player_stats 
                      WHERE match_id = target_match_id 
                        AND player_id = match_player_stats.player_id
                  );
                UPDATE public.match_player_stats SET match_id = target_match_id WHERE match_id = m.match_id;

                -- Deletar a partida duplicada
                DELETE FROM public.matches WHERE match_id = m.match_id;
            ELSE
                UPDATE public.matches 
                SET home_team_id = new_home_id, 
                    away_team_id = new_away_id,
                    updated_at = NOW()
                WHERE match_id = m.match_id;
            END IF;
        END LOOP;

        -- 2. Atualizar as referências de times nas demais tabelas
        BEGIN
            UPDATE public.lineups SET team_id = r.keep_id WHERE team_id = r.delete_id;
        EXCEPTION WHEN unique_violation THEN
            DELETE FROM public.lineups WHERE team_id = r.delete_id;
        END;

        BEGIN
            UPDATE public.match_events SET team_id = r.keep_id WHERE team_id = r.delete_id;
        EXCEPTION WHEN unique_violation THEN
            DELETE FROM public.match_events WHERE team_id = r.delete_id;
        END;

        BEGIN
            UPDATE public.match_player_stats SET team_id = r.keep_id WHERE team_id = r.delete_id;
        EXCEPTION WHEN unique_violation THEN
            DELETE FROM public.match_player_stats WHERE team_id = r.delete_id;
        END;

        BEGIN
            UPDATE public.team_aliases SET team_id = r.keep_id WHERE team_id = r.delete_id;
        EXCEPTION WHEN unique_violation THEN
            DELETE FROM public.team_aliases WHERE team_id = r.delete_id;
        END;

        BEGIN
            UPDATE public.unknown_aliases SET resolved_team_id = r.keep_id WHERE resolved_team_id = r.delete_id;
        EXCEPTION WHEN unique_violation THEN
            DELETE FROM public.unknown_aliases WHERE resolved_team_id = r.delete_id;
        END;

        -- 3. Deletar o time duplicado
        DELETE FROM public.teams WHERE team_id = r.delete_id;
    END LOOP;

    RAISE NOTICE '=== PROCESSO CONCLUÍDO ===';
    RAISE NOTICE 'Times duplicados removidos: %', cnt_teams;
    RAISE NOTICE 'Partidas duplicadas mescladas: %', cnt_matches;
END $$;
"""

async def main():
    pool = await get_pool()
    async with pool.acquire() as conn:
        # Adiciona listener para capturar avisos e notices do PostgreSQL
        def show_notice(connection, message):
            print(message.message)

        conn.add_log_listener(show_notice)
        
        # Executa o script de mescla dentro de uma transação
        async with conn.transaction():
            await conn.execute("SET search_path TO public;")
            await conn.execute(SQL_MERGE)
            
    await pool.close()

if __name__ == "__main__":
    asyncio.run(main())
