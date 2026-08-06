#!/bin/sh
set -eu

backup_dir="${BACKUP_DIR:-/backups}"
retention_days="${BACKUP_RETENTION_DAYS:-14}"
timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
mkdir -p "$backup_dir"

for database in "${POSTGRES_LISTMONK_DB:-listmonk}"; do
  target="$backup_dir/${database}_${timestamp}.sql.gz"
  pg_dump --host="${POSTGRES_HOST:-postgres}" --username="$POSTGRES_USER" --dbname="$database" --no-owner --no-acl | gzip -9 > "$target"
  test -s "$target"
  gzip -t "$target"
done

find "$backup_dir" -type f -name '*.sql.gz' -mtime "+$retention_days" -delete
