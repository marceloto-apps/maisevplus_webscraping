"""
T03 — src/normalizer/team_resolver.py + MatchResolver
"""

from typing import Optional
from uuid import UUID
from datetime import date
from ..db.logger import get_logger
from src.alerts.telegram_mini import TelegramAlert

logger = get_logger(__name__)


class TeamResolver:
    """
    Resolve nomes de times (raw, de qualquer fonte) para o team_id canônico.

    O cache em memória é carregado uma única vez no startup (~3.480 aliases).
    Todos os lookups subsequentes são O(1) sem round-trip ao banco.
    aliases não encontrados são registrados em unknown_aliases para revisão manual.
    """

    _cache: dict[tuple[str, str], int] = {}
    _pending_unknowns: set[tuple[str, str]] = set()

    @classmethod
    async def load_cache(cls) -> None:
        """Carrega todos os aliases conhecidos para o cache em memória."""
        from src.db.pool import get_pool
        pool = await get_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT source, alias_name, team_id FROM team_aliases"
            )
        cls._cache = {
            (row["source"], row["alias_name"].lower()): row["team_id"]
            for row in rows
        }
        logger.info("team_resolver_cache_loaded", aliases=len(cls._cache))

    @classmethod
    async def resolve(cls, source: str, raw_name: str) -> Optional[int]:
        """
        Retorna o team_id se o alias for conhecido.
        Se não encontrar → registra em unknown_aliases e retorna None.
        """
        key = (source, raw_name.lower().strip())
        if key in cls._cache:
            return cls._cache[key]

        # Não encontrado — registrar para revisão manual
        cls._pending_unknowns.add((source, raw_name))
        logger.warning(
            "unknown_alias",
            source=source,
            raw_name=raw_name,
        )
        return None

    @classmethod
    async def flush_unknowns(cls) -> int:
        """Persiste aliases desconhecidos em batch. Chamar ao final da coleta."""
        if not cls._pending_unknowns:
            return 0
        from src.db.pool import get_pool
        pool = await get_pool()
        async with pool.acquire() as conn:
            await conn.executemany(
                """
                INSERT INTO unknown_aliases (source, raw_name, first_seen)
                VALUES ($1, $2, NOW())
                ON CONFLICT (source, raw_name) DO NOTHING
                """,
                list(cls._pending_unknowns),
            )
        count = len(cls._pending_unknowns)
        
        TelegramAlert.fire(
            "warning", 
            f"🏷️ *{count}* aliases desconhecidos salvos para revisão manual."
        )
        
        cls._pending_unknowns.clear()
        return count

    @classmethod
    def add_to_cache(cls, source: str, alias_name: str, team_id: int) -> None:
        """Adiciona um alias ao cache em memória após resolução manual."""
        cls._cache[(source, alias_name.lower())] = team_id


class MatchResolver:
    """
    Resolve a match_id (UUID) a partir de liga + times + data, cruzando fontes.
    Usa TeamResolver internamente para mapear nomes para IDs.
    """

    @classmethod
    async def resolve(
        cls,
        league_id: int,
        home_name: str,
        away_name: str,
        kickoff_date: date,
        source: str,
    ) -> Optional[UUID]:
        """
        Retorna o match_id UUID preexistente na base.
        Retorna None se o jogo não existir ou se algum time não for reconhecido.
        """
        home_id = await TeamResolver.resolve(source, home_name)
        away_id = await TeamResolver.resolve(source, away_name)

        if home_id is None or away_id is None:
            return None

        from src.db.pool import get_pool
        pool = await get_pool()
        async with pool.acquire() as conn:
            match_id = await cls._composite_match(conn, league_id, home_id, away_id, kickoff_date)
            
        if match_id:
            return match_id

        logger.warning(
            "match_not_found",
            league_id=league_id,
            home=home_name,
            away=away_name,
            date=str(kickoff_date),
            source=source,
        )
        return None

    @classmethod
    async def _composite_match(cls, conn, league_id, home_id, away_id, kickoff_date) -> Optional[UUID]:
        row = await conn.fetchrow(
            """
            SELECT match_id FROM matches
            WHERE league_id = $1
              AND home_team_id = $2
              AND away_team_id = $3
              AND kickoff >= $4::date
              AND kickoff < ($4::date + INTERVAL '1 day')
            LIMIT 1
            """,
            league_id, home_id, away_id, kickoff_date,
        )
        return row["match_id"] if row else None

    @classmethod
    async def resolve_with_footystats(
        cls,
        league_id: int,
        home_name: str,
        away_name: str,
        kickoff_date: date,
        footystats_id: int
    ) -> Optional[UUID]:
        """
        Solução hierárquica baseada nos specs M1 Footystats.
        Prioridade 1: ID exato gravado na DB.
        Prioridade 2: Match Natural (Date).
        Prioridade 3: Fuzzy (+-1 dia), obrigatoriamente resultando em 1 unica row.
        """
        home_id = await TeamResolver.resolve("footystats", home_name)
        away_id = await TeamResolver.resolve("footystats", away_name)

        if home_id is None or away_id is None:
            return None

        from src.db.pool import get_pool
        pool = await get_pool()
        async with pool.acquire() as conn:
            # 1. Hard Match
            row = await conn.fetchrow("SELECT match_id FROM matches WHERE footystats_id = $1", footystats_id)
            if row:
                return row["match_id"]

            # 2. Composite Match
            match_id = await cls._composite_match(conn, league_id, home_id, away_id, kickoff_date)
            if match_id:
                await conn.execute(
                    "UPDATE matches SET footystats_id = $1 WHERE match_id = $2 AND footystats_id IS NULL",
                    footystats_id, match_id,
                )
                return match_id

            # 3. Fuzzy match (+- 1 day lock)
            rows = await conn.fetch(
                """
                SELECT match_id FROM matches
                WHERE league_id = $1
                  AND home_team_id = $2
                  AND away_team_id = $3
                  AND ABS(kickoff::date - $4::date) <= 1
                """,
                league_id, home_id, away_id, kickoff_date,
            )
            if len(rows) == 1:
                match_id = rows[0]["match_id"]
                await conn.execute(
                    "UPDATE matches SET footystats_id = $1 WHERE match_id = $2 AND footystats_id IS NULL",
                    footystats_id, match_id,
                )
                return match_id
            elif len(rows) > 1:
                logger.warning(
                    "fuzzy_match_ambiguous",
                    count=len(rows),
                    league_id=league_id,
                    home=home_id,
                    away=away_id,
                    date=str(kickoff_date)
                )

        return None
