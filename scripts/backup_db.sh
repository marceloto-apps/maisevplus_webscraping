#!/usr/bin/env bash
# =============================================================================
# backup_db.sh — Backup diário do PostgreSQL para o OneDrive via rclone
#
# Uso:
#   bash scripts/backup_db.sh
#
# Variáveis de ambiente esperadas (via .env ou exportadas):
#   DATABASE_URL  — URI completa do PostgreSQL (ex: postgres://user:pass@host:5432/db)
#   RCLONE_REMOTE — Nome do remote configurado no rclone (default: onedrive)
#   BACKUP_ONEDRIVE_PATH — Pasta no OneDrive (default: maisevplus_backups)
#   BACKUP_LOCAL_RETENTION_DAYS — Dias de retenção local (default: 2)
#   BACKUP_ONEDRIVE_RETENTION_COUNT — Qtd. de backups a manter no OneDrive (default: 5)
# =============================================================================

set -euo pipefail

# ---------------------------------------------------------------------------
# 1. Configuração — valores com fallback para defaults seguros
# ---------------------------------------------------------------------------

# Carrega .env se existir (para execução manual fora do orchestrator)
ENV_FILE="$(dirname "$(realpath "$0")")/../.env"
if [[ -f "$ENV_FILE" ]]; then
    # Exporta apenas variáveis válidas, ignorando comentários e linhas em branco
    set -a
    # shellcheck disable=SC1090
    source <(grep -E '^[A-Z_]+=.*' "$ENV_FILE" | sed 's/\r//')
    set +a
fi

RCLONE_REMOTE="${RCLONE_REMOTE:-onedrive}"
BACKUP_ONEDRIVE_PATH="${BACKUP_ONEDRIVE_PATH:-maisevplus_backups}"
LOCAL_RETENTION_DAYS="${BACKUP_LOCAL_RETENTION_DAYS:-2}"
ONEDRIVE_RETENTION_COUNT="${BACKUP_ONEDRIVE_RETENTION_COUNT:-5}"

# Diretório local de backup (dentro do projeto, ignorado pelo .gitignore)
BACKUP_DIR="$(dirname "$(realpath "$0")")/../data/backups"
mkdir -p "$BACKUP_DIR"

# Nome do arquivo de backup com timestamp
TIMESTAMP=$(date +"%Y-%m-%d_%H%M")
BACKUP_FILENAME="maisevplus_db_${TIMESTAMP}.sql.gz"
BACKUP_PATH="${BACKUP_DIR}/${BACKUP_FILENAME}"

# ---------------------------------------------------------------------------
# 2. Extrai credenciais do DATABASE_URL
#    Formato: postgres://user:pass@host:port/dbname
# ---------------------------------------------------------------------------
if [[ -z "${DATABASE_URL:-}" ]]; then
    echo "ERROR: DATABASE_URL não definida." >&2
    exit 1
fi

# Remove prefixo postgres:// ou postgresql://
DB_URL_STRIPPED="${DATABASE_URL#postgres*://}"

# Extrai user:pass@host:port/dbname
DB_USERPASS="${DB_URL_STRIPPED%%@*}"
DB_HOSTPATH="${DB_URL_STRIPPED#*@}"

DB_USER="${DB_USERPASS%%:*}"
DB_PASS="${DB_USERPASS#*:}"
DB_HOST="${DB_HOSTPATH%%:*}"
DB_PORT_DB="${DB_HOSTPATH#*:}"
DB_PORT="${DB_PORT_DB%%/*}"
DB_NAME="${DB_PORT_DB#*/}"
# Remove parâmetros extras (ex: ?sslmode=disable)
DB_NAME="${DB_NAME%%\?*}"

# ---------------------------------------------------------------------------
# 3. Executa o pg_dump comprimido
# ---------------------------------------------------------------------------
echo "INFO: Iniciando pg_dump de '${DB_NAME}' em ${DB_HOST}:${DB_PORT}..."

PGPASSWORD="$DB_PASS" pg_dump \
    --host="$DB_HOST" \
    --port="$DB_PORT" \
    --username="$DB_USER" \
    --dbname="$DB_NAME" \
    --format=plain \
    --no-password \
    | gzip -9 > "$BACKUP_PATH"

# Valida que o arquivo foi criado e tem tamanho > 0
if [[ ! -s "$BACKUP_PATH" ]]; then
    echo "ERROR: Arquivo de backup vazio ou não criado: ${BACKUP_PATH}" >&2
    exit 1
fi

BACKUP_SIZE=$(du -sh "$BACKUP_PATH" | cut -f1)
echo "INFO: Backup criado com sucesso. SIZE: ${BACKUP_SIZE} → ${BACKUP_PATH}"

# ---------------------------------------------------------------------------
# 4. Upload para o OneDrive via rclone
# ---------------------------------------------------------------------------
RCLONE_DEST="${RCLONE_REMOTE}:${BACKUP_ONEDRIVE_PATH}"
echo "INFO: Enviando para ${RCLONE_DEST}/${BACKUP_FILENAME}..."

rclone copy \
    "$BACKUP_PATH" \
    "$RCLONE_DEST" \
    --progress \
    --stats-one-line

echo "INFO: Upload concluído para ${RCLONE_DEST}."

# ---------------------------------------------------------------------------
# 5. Retenção no OneDrive: mantém apenas os N backups mais recentes
# ---------------------------------------------------------------------------
echo "INFO: Aplicando retenção no OneDrive (mantendo ${ONEDRIVE_RETENTION_COUNT} mais recentes)..."

# Lista arquivos ordenados do mais antigo para o mais novo
REMOTE_FILES=$(rclone lsf "${RCLONE_DEST}" --include "maisevplus_db_*.sql.gz" | sort)
TOTAL_REMOTE=$(echo "$REMOTE_FILES" | grep -c "." || true)

if [[ "$TOTAL_REMOTE" -gt "$ONEDRIVE_RETENTION_COUNT" ]]; then
    DELETE_COUNT=$(( TOTAL_REMOTE - ONEDRIVE_RETENTION_COUNT ))
    TO_DELETE=$(echo "$REMOTE_FILES" | head -n "$DELETE_COUNT")

    echo "INFO: Removendo ${DELETE_COUNT} backup(s) antigo(s) do OneDrive..."
    while IFS= read -r filename; do
        if [[ -n "$filename" ]]; then
            echo "  → Deletando: ${filename}"
            rclone deletefile "${RCLONE_DEST}/${filename}"
        fi
    done <<< "$TO_DELETE"
fi

echo "INFO: Retenção OneDrive aplicada. Total atual: $(( TOTAL_REMOTE <= ONEDRIVE_RETENTION_COUNT ? TOTAL_REMOTE : ONEDRIVE_RETENTION_COUNT )) backup(s)."

# ---------------------------------------------------------------------------
# 6. Retenção local: remove backups locais mais antigos que N dias
# ---------------------------------------------------------------------------
echo "INFO: Limpando backups locais mais antigos que ${LOCAL_RETENTION_DAYS} dias..."
find "$BACKUP_DIR" -name "maisevplus_db_*.sql.gz" -mtime "+${LOCAL_RETENTION_DAYS}" -delete
echo "INFO: Limpeza local concluída."

echo "INFO: ✅ Backup finalizado com sucesso. SIZE: ${BACKUP_SIZE}"
exit 0
