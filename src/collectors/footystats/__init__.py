"""
Footystats Collector module
Orquestra o backfill e o tracking contínuo de Fixtures e Matches
usando o Footystats como API primária M1.
"""
from .api_client import FootyStatsClient
from .matches_collector import MatchesCollector
from .fixtures_collector import FixturesCollector
from .backfill import FootyStatsBackfill

__all__ = [
    "FootyStatsClient",
    "MatchesCollector",
    "FixturesCollector", 
    "FootyStatsBackfill"
]
