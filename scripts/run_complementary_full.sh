#!/usr/bin/env bash
# =============================================================
# Fase 3 — Rodada completa do complementary para drenar a fila
# Uso: bash scripts/run_complementary_full.sh
# =============================================================

set -euo pipefail

LIMIT=150
LOGFILE="logs/complementary_full_$(date +%Y%m%d_%H%M%S).log"

echo "=== Fase 3: Re-scraping Complementar ==="
echo "Limite: $LIMIT partidas"
echo "Log: $LOGFILE"
echo "Início: $(date)"
echo ""

# Detect virtualenv python interpreter or fallback
if [ -f ".venv/bin/python" ]; then
    PYTHON_BIN=".venv/bin/python"
elif [ -f "venv/bin/python" ]; then
    PYTHON_BIN="venv/bin/python"
else
    PYTHON_BIN="python3"
fi

# Rodar com output unbuffered (-u) e salvar log + stdout (repassando argumentos adicionais)
"$PYTHON_BIN" -u scripts/run_flashscore_complementary.py --limit "$LIMIT" "$@" 2>&1 | tee "$LOGFILE"

echo ""
echo "=== Fim: $(date) ==="
echo "Log salvo em: $LOGFILE"
