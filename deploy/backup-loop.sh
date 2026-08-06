#!/bin/sh
set -eu
while :; do
  export PGPASSWORD="$(cat /run/secrets/postgres_password)"
  stamp="$(date -u +%Y%m%dT%H%M%SZ)"
  target="/backups/listmonk_${stamp}.dump"
  tmp="${target}.tmp"
  until pg_isready -h postgres -U "$POSTGRES_USER" -d "$POSTGRES_LISTMONK_DB" >/dev/null 2>&1; do sleep 5; done
  pg_dump -h postgres -U "$POSTGRES_USER" -d "$POSTGRES_LISTMONK_DB" --format=custom --compress=9 --no-owner --no-acl --file="$tmp"
  test -s "$tmp"
  pg_restore --list "$tmp" >/dev/null
  mv "$tmp" "$target"
  chmod 600 "$target"
  find /backups -type f \( -name 'listmonk_*.sql.gz' -o -name 'listmonk_*.dump' \) -mtime +14 -delete
  sleep 86400
done
