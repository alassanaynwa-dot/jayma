#!/bin/bash
# ============================================================
# JAYMA — backup Postgres quotidien (à appeler via cron)
# Exemple crontab :
#   0 3 * * * /opt/jayma/deploy/backup.sh >> /var/log/jayma-backup.log 2>&1
# ============================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR/.."

BACKUP_DIR="./deploy/backups"
mkdir -p "$BACKUP_DIR"

STAMP=$(date +%Y%m%d_%H%M)
FILE="$BACKUP_DIR/jayma_$STAMP.sql.gz"

docker compose -f deploy/docker-compose.prod.yml --env-file .env.production \
    exec -T db pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB" | gzip > "$FILE"

# Garder les 14 derniers jours de backup
find "$BACKUP_DIR" -name "jayma_*.sql.gz" -mtime +14 -delete

echo "[$(date -Iseconds)] Backup OK : $FILE ($(du -h "$FILE" | cut -f1))"
