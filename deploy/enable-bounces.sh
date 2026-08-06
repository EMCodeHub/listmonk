#!/bin/sh
set -eu
cd /opt/listmonk
docker compose exec -T postgres psql -U consthruads -d listmonk -v ON_ERROR_STOP=1 <<'SQL'
UPDATE settings SET value='true'::jsonb WHERE key IN ('bounce.enabled','bounce.webhooks_enabled','bounce.ses_enabled');
SQL
docker compose restart listmonk
sleep 5
docker compose ps listmonk
docker compose exec -T postgres psql -U consthruads -d listmonk -Atqc "select key || '=' || value::text from settings where key in ('bounce.enabled','bounce.webhooks_enabled','bounce.ses_enabled') order by key"
