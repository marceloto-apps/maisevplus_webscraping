#!/bin/bash
set -e

# Extrai DATABASE_URL do .env se existir
if [ -f "$(dirname "$0")/../.env" ]; then
    export $(grep -v '^#' "$(dirname "$0")/../.env" | xargs)
fi

if [ -z "$DATABASE_URL" ]; then
    echo "Erro: DATABASE_URL não está configurada."
    echo "Configure no arquivo .env ou exporte a variável de ambiente."
    exit 1
fi

echo "Iniciando execução das migrations..."

MIGRATIONS_DIR="$(dirname "$0")/../migrations"

# Executa as migrations em ordem
for file in $(ls -1 "$MIGRATIONS_DIR"/*.sql | sort); do
    echo "Executando: $(basename "$file")"
    psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f "$file"
done

echo "Todas as migrations foram aplicadas com sucesso!"
