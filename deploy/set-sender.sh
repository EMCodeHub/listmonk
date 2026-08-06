#!/bin/sh
set -eu
cd /opt/listmonk
docker compose exec -T postgres psql -U consthruads -d listmonk -v ON_ERROR_STOP=1 -c \
  "UPDATE settings SET value='\"Consthruads <noreply@consthruads.com>\"'::jsonb WHERE key='app.from_email';"
docker compose restart listmonk
sleep 5
docker compose ps listmonk
docker compose exec -T postgres psql -U consthruads -d listmonk -Atqc \
  "select value#>>'{}' from settings where key='app.from_email';"
