"""
T03 — src/normalizer/match_resolver.py
Re-exporta MatchResolver de team_resolver.py para manter a estrutura de
arquivos alinhada com o TASKS.md (que lista ambos como entregáveis separados).
"""

from .team_resolver import MatchResolver

__all__ = ["MatchResolver"]
