#!/usr/bin/env python3
import asyncio
import json
import logging
from pathlib import Path
from src.collectors.betexplorer.odds_collector import BetExplorerOddsCollector

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(message)s")

async def test_e2e():
    print("=" * 60)
    print("Iniciando Teste E2E Isolado - BetExplorer Odds Collector")
    print("=" * 60)
    
    # Coleta de uma liga rápida com max limit de 1 partida (apenas mercados 1x2 e over_under para não atrasar o teste)
    collector = BetExplorerOddsCollector(markets=["1x2_ft", "ou_ft"])
    
    # Executa modo 'fixtures' para Premier League
    odds_data = await collector.collect_league("ENG_PL", mode="fixtures", max_matches=1)
    
    output_dir = Path("output")
    output_dir.mkdir(exist_ok=True)
    out_file = output_dir / "e2e_betexplorer.json"
    
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(odds_data, f, indent=2, ensure_ascii=False, default=str)
        
    print(f"\nTeste finalizado. Foram extraídas {len(odds_data)} linhas normalizadas.")
    print(f"Salvo em: {out_file}")

if __name__ == "__main__":
    asyncio.run(test_e2e())
