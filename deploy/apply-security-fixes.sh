#!/bin/sh
set -eu
cd /opt/listmonk
chmod 700 backup-loop.sh rotate-admin-bcrypt.py
apt-get update -qq
DEBIAN_FRONTEND=noninteractive apt-get install -y -qq python3-bcrypt
python3 rotate-admin-bcrypt.py
for file in backups/*.sql.gz; do
  test -e "$file" || continue
  size="$(stat -c %s "$file")"
  if ! gzip -t "$file" 2>/dev/null || [ "$size" -lt 1000 ]; then
    mv "$file" "$file.invalid"
  fi
done
docker compose up -d --force-recreate backup
sleep 8
docker compose ps backup
ls -lh backups
