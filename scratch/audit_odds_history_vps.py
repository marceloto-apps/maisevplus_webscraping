"""
scratch/audit_odds_history_vps.py

Script para auditoria detalhada das odds gravadas no banco de dados PostgreSQL
para as partidas processadas no teste de backfill/retrofit.
"""
import asyncio
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.db.pool import get_pool

FS_IDS = ["4ADQOZ24", "86M18EIN", "E3uvsQPP", "4jNW2hto"]

async def audit_matches():
    pool = await get_pool()
    async with pool.acquire() as conn:
        for fs_id in FS_IDS:
            m = await conn.fetchrow("""
                SELECT m.match_id, m.flashscore_id, m.kickoff, m.scraping_flashscore,
                       ht.name as home_team, at.name as away_team
                FROM matches m
                JOIN teams ht ON m.home_team_id = ht.team_id
                JOIN teams at ON m.away_team_id = at.team_id
                WHERE m.flashscore_id = $1
            """, fs_id)

            if not m:
                continue

            match_uuid = m["match_id"]
            print("\n" + "="*90)
            print(f"📌 MATCH: {m['home_team']} vs {m['away_team']} | FS ID: {fs_id} | UUID: {match_uuid}")
            print(f"   Kickoff: {m['kickoff']} | Scraping Status: {m['scraping_flashscore']}")
            print("="*90)

            # 1. Total de odds na tabela odds_history
            total_oh = await conn.fetchval("SELECT count(*) FROM odds_history WHERE match_id = $1", match_uuid)
            total_opening = await conn.fetchval("SELECT count(*) FROM odds_history WHERE match_id = $1 AND is_opening = true", match_uuid)
            total_closing = await conn.fetchval("SELECT count(*) FROM odds_history WHERE match_id = $1 AND is_closing = true", match_uuid)
            
            print(f"📊 RESUMO ODDS_HISTORY: Total = {total_oh} | Abertura (is_opening=true) = {total_opening} | Fechamento (is_closing=true) = {total_closing}")

            # 2. Resumo por Mercado
            markets = await conn.fetch("""
                SELECT market_type, period, count(*) as count,
                       count(*) FILTER (WHERE is_opening = true) as opening_cnt
                FROM odds_history
                WHERE match_id = $1
                GROUP BY market_type, period
                ORDER BY market_type, period
            """, match_uuid)
            print("\n   Mercados Coletados:")
            for mk in markets:
                print(f"     - Mercado: {mk['market_type']:<6} | Período: {mk['period']:<3} | Total Rows: {mk['count']:<4} | Com Abertura: {mk['opening_cnt']}")

            # 3. Resumo por Casa de Apostas
            bms = await conn.fetch("""
                SELECT b.name as bookmaker, count(*) as count,
                       count(*) FILTER (WHERE oh.is_opening = true) as opening_cnt
                FROM odds_history oh
                JOIN bookmakers b ON oh.bookmaker_id = b.bookmaker_id
                WHERE oh.match_id = $1
                GROUP BY b.name
                ORDER BY count DESC
            """, match_uuid)
            print("\n   Casas de Apostas Persistidas no Banco:")
            for b in bms:
                print(f"     - {b['bookmaker']:<16} | Total Odds: {b['count']:<4} | Odds com Abertura: {b['opening_cnt']}")

            # 4. Amostra de Odds 1x2_ft da bet365 (Opening vs Closing)
            sample = await conn.fetch("""
                SELECT b.name as bookmaker, oh.market_type, oh.period, oh.odds_1, oh.odds_x, oh.odds_2, oh.is_opening, oh.is_closing, oh.time
                FROM odds_history oh
                JOIN bookmakers b ON oh.bookmaker_id = b.bookmaker_id
                WHERE oh.match_id = $1 AND oh.market_type = '1x2' AND oh.period = 'ft'
                ORDER BY b.name, oh.is_opening DESC
            """, match_uuid)

            if sample:
                print("\n   Amostra de Odds 1x2 FT no Banco:")
                for s in sample[:10]:
                    tipo = "ABERTURA" if s["is_opening"] else ("FECHAMENTO" if s["is_closing"] else "SNAPSHOT")
                    print(f"     [{tipo:<10}] Casa: {s['bookmaker']:<12} | 1: {s['odds_1']} | X: {s['odds_x']} | 2: {s['odds_2']}")

    await pool.close()

if __name__ == "__main__":
    asyncio.run(audit_matches())
