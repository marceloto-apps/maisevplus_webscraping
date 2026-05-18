#!/bin/bash
set -e

echo "============================================="
echo "  VALIDAÇÃO DE DEPLOY — MaisEVPlus Scraping"
echo "============================================="
echo ""

cd "$(dirname "$0")/.."

if [ -d "venv" ]; then
    echo "Ativando ambiente virtual (venv)..."
    source venv/bin/activate
elif [ -d ".venv" ]; then
    echo "Ativando ambiente virtual (.venv)..."
    source .venv/bin/activate
fi

echo "--- 1/6: Verificando que COALESCE -9999 sumiu ---"
if grep -rn "COALESCE.*9999" src/ --include="*.py"; then
    echo "❌ FALHA: Ainda existe -9999 no código!"
    exit 1
else
    echo "✅ OK"
fi
echo ""

echo "--- 2/6: Verificando que Odds API sumiu ---"
if grep -rn "odds_api\|ODDS_API" src/collectors/ src/scheduler/ --include="*.py" 2>/dev/null; then
    echo "❌ FALHA: Referências à Odds API encontradas!"
    exit 1
else
    echo "✅ OK"
fi
echo ""

echo "--- 3/6: Testando resolve_bookmaker case-insensitive ---"
python3 -c "
from src.collectors.flashscore.config import resolve_bookmaker
assert resolve_bookmaker('bet365') is not None
assert resolve_bookmaker('BET365') is not None
assert resolve_bookmaker('Bet365') is not None
assert resolve_bookmaker('Pinnacle') is not None
print('✅ OK')
"
echo ""

echo "--- 4/6: Verificando colunas scraping_health ---"
python3 -c "
import asyncio, asyncpg, os
from dotenv import load_dotenv
load_dotenv()
async def run():
    conn = await asyncpg.connect(os.getenv('DATABASE_URL'))
    cols = await conn.fetch('''
        SELECT column_name FROM information_schema.columns 
        WHERE table_name = 'scraping_health' ORDER BY ordinal_position
    ''')
    names = [c['column_name'] for c in cols]
    required = ['bet365_found', 'pinnacle_found', 'avg_bookmakers', 'unidentified_rows', 
                'unknown_bookmakers', 'parse_errors', 'success_rate', 'alert_level']
    missing = [r for r in required if r not in names]
    if missing:
        print(f'❌ FALHA: Colunas faltando: {missing}')
        exit(1)
    print(f'✅ OK ({len(names)} colunas)')
    await conn.close()
asyncio.run(run())
"
echo ""

echo "--- 5/6: Rodando backfill de 2 jogos (teste E2E) ---"
xvfb-run -a python3 scripts/run_flashscore_backfill.py --league ENG_PL --limit 2
echo ""

echo "--- 6/6: Verificando Bet365 1x2 FT no banco ---"
python3 -c "
import asyncio, asyncpg, os
from dotenv import load_dotenv
load_dotenv()
async def run():
    conn = await asyncpg.connect(os.getenv('DATABASE_URL'))
    rows = await conn.fetch('''
        SELECT oh.market_type, oh.period, oh.odds_1, oh.odds_x, oh.odds_2, oh.time
        FROM odds_history oh
        WHERE oh.bookmaker_id = 3 AND oh.market_type = '1x2' AND oh.period = 'ft'
        ORDER BY oh.time DESC LIMIT 5
    ''')
    for r in rows:
        print(dict(r))
    if not rows:
        print('❌ ALERTA: NENHUMA odd da Bet365 encontrada após backfill!')
        exit(1)
    print(f'✅ OK ({len(rows)} registros encontrados)')
    
    # Verificar scraping_health
    health = await conn.fetch('SELECT * FROM scraping_health ORDER BY run_ts DESC LIMIT 1')
    if health:
        h = dict(health[0])
        print(f'Health: alert_level={h.get(\"alert_level\")}, bet365={h.get(\"bet365_found\")}, rate={h.get(\"success_rate\")}')
    else:
        print('⚠️ scraping_health vazia (pode ser normal se é o primeiro run)')
    await conn.close()
asyncio.run(run())
"
echo ""

echo "============================================="
echo "  ✅ VALIDAÇÃO COMPLETA"
echo "============================================="
