"""
FootyStats Daily Updater
Atualiza TODOS os jogos das temporadas ativas (is_current = TRUE).
Processa jogos scheduled, incomplete e finished conforme resposta da API.
Ao final, avalia encerramento automático de temporadas via check_and_close_seasons().
"""
import asyncio
from datetime import datetime, timezone
from typing import List, Dict

from ...db import get_pool
from ...db.logger import get_logger
from .api_client import FootyStatsClient
from .matches_collector import MatchesCollector
from ...normalizer.team_resolver import TeamResolver, MatchResolver

logger = get_logger(__name__)

# Mapeamento de status da FootyStats para o status interno
FOOTYSTATS_STATUS_MAP = {
    "complete":   "finished",
    "finished":   "finished",
    "incomplete": "scheduled",
    "scheduled":  "scheduled",
    "suspended":  "scheduled",
    "postponed":  "postponed",
    "cancelled":  "cancelled",
}


class FootyStatsDailyUpdater:
    """
    Processa todas as temporadas ativas diariamente.
    Idempotente: pode ser re-executado sem duplicar dados.
    """

    def __init__(self):
        self.api_client = FootyStatsClient()
        self._pool = None
        self.unresolved_teams: set = set()

    async def _init_db(self):
        if self._pool is None:
            self._pool = await get_pool()

    async def run(self) -> dict:
        """
        Ponto de entrada principal. Retorna resumo da execução.
        """
        await self._init_db()
        await TeamResolver.load_cache()

        async with self._pool.acquire() as conn:
            active_seasons = await conn.fetch(
                """
                SELECT s.season_id, s.league_id, s.footystats_season_id, l.code AS league_code
                FROM seasons s
                JOIN leagues l ON s.league_id = l.league_id
                WHERE s.is_current = TRUE
                  AND s.footystats_season_id IS NOT NULL
                ORDER BY l.code
                """
            )

        if not active_seasons:
            logger.warning("footystats_daily_no_active_seasons")
            return {"seasons_processed": 0, "matches_upserted": 0, "seasons_closed": 0}

        logger.info("footystats_daily_start", active_seasons=len(active_seasons))

        # Processamento CONCORRENTE — mesma estratégia do FootyStatsBackfill
        semaphore = asyncio.Semaphore(5)

        async def _fetch_and_process(season):
            async with semaphore:
                league_code = season["league_code"]
                fs_season_id = season["footystats_season_id"]
                logger.info("footystats_daily_season_start", league=league_code, fs_season_id=fs_season_id)
                try:
                    matches_data = await self.api_client.fetch_season_matches(fs_season_id)
                    if not matches_data:
                        logger.warning("footystats_daily_empty_response", league=league_code)
                        return 0
                    upserted = await self._process_season(matches_data, dict(season))
                    logger.info("footystats_daily_season_done", league=league_code, upserted=upserted)
                    return upserted
                except Exception as e:
                    logger.error("footystats_daily_season_error", league=league_code, error=str(e))
                    return 0

        results = await asyncio.gather(*[_fetch_and_process(s) for s in active_seasons])
        total_upserted = sum(r for r in results if isinstance(r, int))

        # Avalia encerramento automático de temporadas
        seasons_closed = await self._autoclose_seasons()

        if self.unresolved_teams:
            logger.warning(
                "footystats_daily_unresolved_teams",
                count=len(self.unresolved_teams),
                teams=sorted(self.unresolved_teams)
            )

        return {
            "seasons_processed": len(active_seasons),
            "matches_upserted": total_upserted,
            "seasons_closed": seasons_closed,
        }

    async def _process_season(self, matches_data: List[Dict], season: dict) -> int:
        """
        Itera os matches retornados pela API e faz upsert no banco.
        Processa todos os status (finished, scheduled, postponed, etc.).
        """
        league_id = season["league_id"]
        season_id = season["season_id"]
        upserted = 0

        async with self._pool.acquire() as conn:
            for raw_match in matches_data:
                home_name = str(raw_match.get("home_name", ""))
                away_name = str(raw_match.get("away_name", ""))

                home_id = await TeamResolver.resolve("footystats", home_name)
                away_id = await TeamResolver.resolve("footystats", away_name)

                if home_id is None:
                    self.unresolved_teams.add(home_name)
                if away_id is None:
                    self.unresolved_teams.add(away_name)
                if home_id is None or away_id is None:
                    continue

                fs_id = raw_match.get("id")
                parsed = MatchesCollector.parse_raw_match(raw_match)
                kickoff = parsed["matches"].get("kickoff")

                if not fs_id or not kickoff:
                    continue

                # Status bruto da FootyStats → status interno
                raw_status = raw_match.get("status", "incomplete").lower()
                internal_status = FOOTYSTATS_STATUS_MAP.get(raw_status, "scheduled")

                # Resolve match existente (por footystats_id ou nome+data)
                match_id = await MatchResolver.resolve_with_footystats(
                    league_id, home_name, away_name, kickoff.date(), fs_id
                )

                m = parsed["matches"]

                if match_id:
                    # UPDATE — atualiza status e placar independente do estado anterior
                    await conn.execute(
                        """
                        UPDATE matches SET
                            footystats_id = $1,
                            kickoff       = $2,
                            status        = $3,
                            ft_home       = $4,
                            ft_away       = $5,
                            ht_home       = $6,
                            ht_away       = $7,
                            updated_at    = NOW()
                        WHERE match_id = $8
                        """,
                        fs_id, kickoff, internal_status,
                        m.get("ft_home"), m.get("ft_away"),
                        m.get("ht_home"), m.get("ht_away"),
                        match_id,
                    )
                else:
                    # INSERT — jogo novo (ex: fixture futura recém-publicada)
                    match_id = await conn.fetchval(
                        """
                        INSERT INTO matches (
                            season_id, league_id, home_team_id, away_team_id,
                            footystats_id, kickoff, status, ft_home, ft_away,
                            ht_home, ht_away, updated_at
                        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, NOW())
                        ON CONFLICT DO NOTHING
                        RETURNING match_id
                        """,
                        season_id, league_id, home_id, away_id,
                        fs_id, kickoff, internal_status,
                        m.get("ft_home"), m.get("ft_away"),
                        m.get("ht_home"), m.get("ht_away"),
                    )

                if not match_id:
                    continue

                upserted += 1

                # Só insere/atualiza match_stats para jogos finalizados
                if internal_status == "finished":
                    s = parsed["match_stats"]
                    await self._upsert_match_stats(conn, match_id, s)

        return upserted

    async def _upsert_match_stats(self, conn, match_id, s: dict):
        """Upsert centralizado de match_stats. Idêntico ao FootyStatsBackfill."""
        await conn.execute(
            """
            INSERT INTO match_stats (
                match_id,
                xg_home, xg_away, total_goals_ft,
                goals_home_minutes, goals_away_minutes,
                corners_home_ft, corners_away_ft,
                offsides_home, offsides_away,
                yellow_cards_home_ft, yellow_cards_away_ft,
                red_cards_home_ft, red_cards_away_ft,
                shots_on_target_home, shots_on_target_away,
                shots_off_target_home, shots_off_target_away,
                shots_home, shots_away,
                fouls_home, fouls_away,
                possession_home, possession_away,
                btts_potential,
                corners_home_ht, corners_away_ht,
                corners_home_2h, corners_away_2h,
                goals_home_2h, goals_away_2h,
                cards_home_ht, cards_away_ht,
                cards_home_2h, cards_away_2h,
                dangerous_attacks_home, dangerous_attacks_away,
                attacks_home, attacks_away,
                goals_home_0_10_min, goals_away_0_10_min,
                corners_home_0_10_min, corners_away_0_10_min,
                cards_home_0_10_min, cards_away_0_10_min,
                home_ppg, away_ppg,
                pre_match_home_ppg, pre_match_away_ppg,
                pre_match_overall_ppg_home, pre_match_overall_ppg_away,
                xg_prematch_home, xg_prematch_away
            ) VALUES (
                $1,
                $2,$3,$4,$5,$6,$7,$8,$9,$10,
                $11,$12,$13,$14,$15,$16,$17,$18,$19,$20,
                $21,$22,$23,$24,$25,$26,$27,$28,$29,$30,
                $31,$32,$33,$34,$35,$36,$37,$38,$39,$40,
                $41,$42,$43,$44,$45,$46,$47,$48,$49,$50,
                $51,$52,$53
            )
            ON CONFLICT (match_id) DO UPDATE SET
                xg_home=EXCLUDED.xg_home, xg_away=EXCLUDED.xg_away,
                total_goals_ft=EXCLUDED.total_goals_ft,
                goals_home_minutes=EXCLUDED.goals_home_minutes,
                goals_away_minutes=EXCLUDED.goals_away_minutes,
                corners_home_ft=EXCLUDED.corners_home_ft, corners_away_ft=EXCLUDED.corners_away_ft,
                offsides_home=EXCLUDED.offsides_home, offsides_away=EXCLUDED.offsides_away,
                yellow_cards_home_ft=EXCLUDED.yellow_cards_home_ft,
                yellow_cards_away_ft=EXCLUDED.yellow_cards_away_ft,
                red_cards_home_ft=EXCLUDED.red_cards_home_ft,
                red_cards_away_ft=EXCLUDED.red_cards_away_ft,
                shots_on_target_home=EXCLUDED.shots_on_target_home,
                shots_on_target_away=EXCLUDED.shots_on_target_away,
                shots_off_target_home=EXCLUDED.shots_off_target_home,
                shots_off_target_away=EXCLUDED.shots_off_target_away,
                shots_home=EXCLUDED.shots_home, shots_away=EXCLUDED.shots_away,
                fouls_home=EXCLUDED.fouls_home, fouls_away=EXCLUDED.fouls_away,
                possession_home=EXCLUDED.possession_home, possession_away=EXCLUDED.possession_away,
                btts_potential=EXCLUDED.btts_potential,
                corners_home_ht=EXCLUDED.corners_home_ht, corners_away_ht=EXCLUDED.corners_away_ht,
                corners_home_2h=EXCLUDED.corners_home_2h, corners_away_2h=EXCLUDED.corners_away_2h,
                goals_home_2h=EXCLUDED.goals_home_2h, goals_away_2h=EXCLUDED.goals_away_2h,
                cards_home_ht=EXCLUDED.cards_home_ht, cards_away_ht=EXCLUDED.cards_away_ht,
                cards_home_2h=EXCLUDED.cards_home_2h, cards_away_2h=EXCLUDED.cards_away_2h,
                dangerous_attacks_home=EXCLUDED.dangerous_attacks_home,
                dangerous_attacks_away=EXCLUDED.dangerous_attacks_away,
                attacks_home=EXCLUDED.attacks_home, attacks_away=EXCLUDED.attacks_away,
                goals_home_0_10_min=EXCLUDED.goals_home_0_10_min,
                goals_away_0_10_min=EXCLUDED.goals_away_0_10_min,
                corners_home_0_10_min=EXCLUDED.corners_home_0_10_min,
                corners_away_0_10_min=EXCLUDED.corners_away_0_10_min,
                cards_home_0_10_min=EXCLUDED.cards_home_0_10_min,
                cards_away_0_10_min=EXCLUDED.cards_away_0_10_min,
                home_ppg=EXCLUDED.home_ppg, away_ppg=EXCLUDED.away_ppg,
                pre_match_home_ppg=EXCLUDED.pre_match_home_ppg,
                pre_match_away_ppg=EXCLUDED.pre_match_away_ppg,
                pre_match_overall_ppg_home=EXCLUDED.pre_match_overall_ppg_home,
                pre_match_overall_ppg_away=EXCLUDED.pre_match_overall_ppg_away,
                xg_prematch_home=EXCLUDED.xg_prematch_home,
                xg_prematch_away=EXCLUDED.xg_prematch_away
            """,
            match_id,
            s.get("xg_home"), s.get("xg_away"), s.get("total_goals_ft"),
            s.get("goals_home_minutes"), s.get("goals_away_minutes"),
            s.get("corners_home_ft"), s.get("corners_away_ft"),
            s.get("offsides_home"), s.get("offsides_away"),
            s.get("yellow_cards_home_ft"), s.get("yellow_cards_away_ft"),
            s.get("red_cards_home_ft"), s.get("red_cards_away_ft"),
            s.get("shots_on_target_home"), s.get("shots_on_target_away"),
            s.get("shots_off_target_home"), s.get("shots_off_target_away"),
            s.get("shots_home"), s.get("shots_away"),
            s.get("fouls_home"), s.get("fouls_away"),
            s.get("possession_home"), s.get("possession_away"),
            s.get("btts_potential"),
            s.get("corners_home_ht"), s.get("corners_away_ht"),
            s.get("corners_home_2h"), s.get("corners_away_2h"),
            s.get("goals_home_2h"), s.get("goals_away_2h"),
            s.get("cards_home_ht"), s.get("cards_away_ht"),
            s.get("cards_home_2h"), s.get("cards_away_2h"),
            s.get("dangerous_attacks_home"), s.get("dangerous_attacks_away"),
            s.get("attacks_home"), s.get("attacks_away"),
            s.get("goals_home_0_10_min"), s.get("goals_away_0_10_min"),
            s.get("corners_home_0_10_min"), s.get("corners_away_0_10_min"),
            s.get("cards_home_0_10_min"), s.get("cards_away_0_10_min"),
            s.get("home_ppg"), s.get("away_ppg"),
            s.get("pre_match_home_ppg"), s.get("pre_match_away_ppg"),
            s.get("pre_match_overall_ppg_home"), s.get("pre_match_overall_ppg_away"),
            s.get("xg_prematch_home"), s.get("xg_prematch_away"),
        )

    async def _autoclose_seasons(self) -> int:
        """
        Avalia e fecha automaticamente temporadas encerradas via função SQL.
        Retorna o número de temporadas efetivamente fechadas.
        """
        closed = 0
        async with self._pool.acquire() as conn:
            rows = await conn.fetch("SELECT * FROM check_and_close_seasons()")
            for row in rows:
                status = "CLOSED" if row["closed"] else "open"
                logger.info(
                    "season_autoclose_check",
                    season_id=row["season_id"],
                    league=row["league_code"],
                    status=status,
                    reason=row["reason"],
                )
                if row["closed"]:
                    closed += 1
        return closed
