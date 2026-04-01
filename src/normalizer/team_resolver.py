"""
T03 — src/normalizer/team_resolver.py + MatchResolver
"""

from typing import Optional
from uuid import UUID
from datetime import date
from ..db import get_pool
from ..db.logger import get_logger

logger = get_logger(__name__)


class TeamResolver:
    """
    Resolve nomes de times (raw, de qualquer fonte) para o team_id canônico.

    O cache em memória é carregado uma única vez no startup (~3.480 aliases).
    Todos os lookups subsequentes são O(1) sem round-trip ao banco.
    aliases não encontrados são registrados em unknown_aliases para revisão manual.
    """

    def __init__(self, pool):
        self._pool = pool
        # { (source, alias_name_lower): team_id }
        self._cache: dict[tuple[str, str], int] = {}

    async def load_cache(self) -> None:
        """Carrega todos os aliases conhecidos para o cache em memória."""
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT source, alias_name, team_id FROM team_aliases"
            )
        self._cache = {
            (row["source"], row["alias_name"].lower()): row["team_id"]
            for row in rows
        }
        logger.info("team_resolver_cache_loaded", aliases=len(self._cache))

    async def resolve(self, source: str, raw_name: str) -> Optional[int]:
        """
        Retorna o team_id se o alias for conhecido.
        Se não encontrar → registra em unknown_aliases e retorna None.
        """
        key = (source, raw_name.lower().strip())
        if key in self._cache:
            return self._cache[key]

        # Não encontrado — registrar para revisão manual
        async with self._pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO unknown_aliases (source, raw_name, first_seen)
                VALUES ($1, $2, NOW())
                ON CONFLICT (source, raw_name) DO NOTHING
                """,
                source, raw_name,
            )
        logger.warning(
            "unknown_alias",
            source=source,
            raw_name=raw_name,
        )
        return None

    def add_to_cache(self, source: str, alias_name: str, team_id: int) -> None:
        """Adiciona um alias ao cache em memória após resolução manual."""
        self._cache[(source, alias_name.lower())] = team_id


class MatchResolver:
    """
    Resolve a match_id (UUID) a partir de liga + times + data, cruzando fontes.
    Usa TeamResolver internamente para mapear nomes para IDs.
    """

    def __init__(self, pool, team_resolver: TeamResolver):
        self._pool = pool
        self._team_resolver = team_resolver

    async def resolve(
        self,
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
        home_id = await self._team_resolver.resolve(source, home_name)
        away_id = await self._team_resolver.resolve(source, away_name)

        if home_id is None or away_id is None:
            return None

        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT match_id
                FROM matches
                WHERE league_id    = $1
                  AND home_team_id = $2
                  AND away_team_id = $3
                  AND kickoff::date = $4
                LIMIT 1
                """,
                league_id, home_id, away_id, kickoff_date,
            )
        if row:
            return row["match_id"]

        logger.warning(
            "match_not_found",
            league_id=league_id,
            home=home_name,
            away=away_name,
            date=str(kickoff_date),
            source=source,
        )
        return None
