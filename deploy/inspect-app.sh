#!/bin/sh
set -eu
cd /opt/listmonk
sleep 10
docker compose ps
for path in / /admin /admin/ /api/health /api/health/ /api/config; do
  code="$(curl -sS -o /dev/null -w '%{http_code}' "http://127.0.0.1:9000${path}")"
  echo "$path $code"
done
docker compose exec -T postgres psql -U consthruads -d listmonk -c '\d settings'
docker compose exec -T postgres psql -U consthruads -d listmonk -c 'select key, value from settings order by key;'
