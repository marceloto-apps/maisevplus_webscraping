-- migrations/014_season_autoclose_function.sql
-- Cria a função que avalia e encerra temporadas automaticamente.
-- Critério: todos os matches = 'finished' e o último jogo ocorreu há mais de 3 dias.

CREATE OR REPLACE FUNCTION check_and_close_seasons()
RETURNS TABLE(season_id INTEGER, league_code TEXT, closed BOOLEAN, reason TEXT)
LANGUAGE plpgsql
AS $$
DECLARE
    rec RECORD;
    total_matches INT;
    finished_matches INT;
    last_kickoff TIMESTAMPTZ;
BEGIN
    FOR rec IN
        SELECT s.season_id, s.league_id, l.code AS league_code
        FROM seasons s
        JOIN leagues l ON s.league_id = l.league_id
        WHERE s.is_current = TRUE
    LOOP
        -- Contagem total e finalizados
        SELECT
            COUNT(*),
            COUNT(*) FILTER (WHERE m.status = 'finished'),
            MAX(m.kickoff)
        INTO total_matches, finished_matches, last_kickoff
        FROM matches m
        WHERE m.season_id = rec.season_id;

        season_id    := rec.season_id;
        league_code  := rec.league_code;

        -- Sem jogos cadastrados: não fecha ainda
        IF total_matches = 0 THEN
            closed := FALSE;
            reason := 'no_matches_yet';
            RETURN NEXT;
            CONTINUE;
        END IF;

        -- Todos finalizados e último jogo há mais de 3 dias
        IF finished_matches = total_matches
           AND last_kickoff < NOW() - INTERVAL '3 days' THEN

            UPDATE seasons
            SET
                is_current = FALSE,
                end_date   = last_kickoff::date,
                updated_at = NOW()
            WHERE seasons.season_id = rec.season_id;

            closed := TRUE;
            reason := format('all_%s_finished_last_%s', total_matches, last_kickoff::date);
        ELSE
            closed := FALSE;
            reason := format('%s/%s_finished_last_%s', finished_matches, total_matches, COALESCE(last_kickoff::date::text, 'none'));
        END IF;

        RETURN NEXT;
    END LOOP;
END;
$$;

-- Garante permissão de execução para o role da aplicação
-- GRANT EXECUTE ON FUNCTION check_and_close_seasons() TO maisev_app;
