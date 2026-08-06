#!/bin/sh
set -eu
if [ "$#" -ne 2 ]; then
  echo "Usage: restore.sh DATABASE BACKUP.sql.gz" >&2
  exit 2
fi
database="$1"
backup="$2"
test -s "$backup"
gzip -t "$backup"
gunzip -c "$backup" | psql --host="${POSTGRES_HOST:-postgres}" --username="$POSTGRES_USER" --dbname="$database" --single-transaction
