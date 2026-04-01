"""
T07 — Understat Collector
Scraping de xG e Shot Data focado em 6 ligas TOP Tier europeias.
"""
from .scraper import UnderstatScraper
from .shot_collector import ShotCollector
from .backfill import UnderstatBackfill

__all__ = [
    "UnderstatScraper",
    "ShotCollector",
    "UnderstatBackfill"
]
