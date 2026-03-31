from typing import Optional
from uuid import UUID
from datetime import date

class TeamResolver:
    """
    Resolve nomes de times de diferentes fontes para o team_id canônico.
    Mantém cache em memória para performance.
    """
    def __init__(self, db):
        self.db = db
        self._cache = {}  # {(source, alias): team_id}

    async def load_cache(self):
        """Carrega todos os aliases conhecidos para o cache"""
        pass

    async def resolve(self, source: str, raw_name: str) -> Optional[int]:
        """
        Retorna o team_id se encontrado.
        Se não, registra na tabela unknown_aliases e retorna None.
        """
        pass

class MatchResolver:
    """
    Resolve jogos baseados em liga, times e data, independente da fonte.
    Essencial para fazer o merge/dedup de dados de fontes diferentes.
    """
    def __init__(self, db, team_resolver: TeamResolver):
        self.db = db
        self.team_resolver = team_resolver

    async def resolve(self, league_id: int, home_name: str, away_name: str,
                      kickoff_date: date, source: str) -> Optional[UUID]:
        """
        Retorna o match_id (UUID) preexistente na base.
        Usa o TeamResolver internamente.
        """
        pass
