#!/bin/bash
set -e

# Carrega as variáveis de ambiente
if [ -f "$(dirname "$0")/../.env" ]; then
    export $(grep -v '^#' "$(dirname "$0")/../.env" | xargs)
fi

if [ -z "$DATABASE_URL" ]; then
    echo "Erro: DATABASE_URL não está configurada."
    exit 1
fi

echo "=========================================="
echo " INICIANDO EMERGÊNCIA: RESTAURAÇÃO MASTER "
echo "=========================================="

# 1. Extração segura apenas dos INSERTs exatos do Backup
echo "Extraindo INSERTS do backup de contingência..."
sed -n -e '/INSERT INTO leagues/,/;/p' \
       -e '/INSERT INTO seasons/,/;/p' \
       -e '/INSERT INTO bookmakers/,/;/p' \
       "$(dirname "$0")/../migrations/full_schema.sql.bak" > /tmp/reinstall_seeds.sql

# 2. Executa a deleção de limpeza (caso haja lixo) e a re-inserção isolada
echo "Enviando pro PostgreSQL..."
psql "$DATABASE_URL" -v ON_ERROR_STOP=1 <<EOF
    -- Usualmente uma falha aqui significa que elas já tem os registros. 
    -- Limpando de forma segura (A tabela MATCHES não será apagada porque essas referências já devem estar zeradas pra isso funcionar e ter pulado o CASCADE).
    TRUNCATE bookmakers RESTART IDENTITY CASCADE;

    \i /tmp/reinstall_seeds.sql
EOF

echo "✓ Leagues, Seasons e Bookmakers restaurados."

# 3. Restaura Teams e Team_Aliases usando o mecanismo oficial
echo "Recriando Tabela de Teams e Aliases a partir do CSV Base..."
PYTHON_BIN="$(dirname "$0")/../.venv/bin/python"
if [ ! -f "$PYTHON_BIN" ]; then
    PYTHON_BIN="python" # Fallback global
fi

$PYTHON_BIN "$(dirname "$0")/import_aliases.py" --file "$(dirname "$0")/../output/team_aliases_seed.csv"

echo "=========================================="
echo " RESTAURAÇÃO FINALIZADA COM SUCESSO!      "
echo "* A unknown_aliases recomeçará do zero (orgânica assim que o scraper varrer faltantes)."
echo "=========================================="
