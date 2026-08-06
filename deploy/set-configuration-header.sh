#!/bin/sh
set -eu
cd /opt/listmonk
docker compose exec -T postgres psql -U consthruads -d listmonk -v ON_ERROR_STOP=1 <<'SQL'
UPDATE settings
SET value=jsonb_set(value, '{0,email_headers}', '[{"X-SES-CONFIGURATION-SET":"listmonk-production"}]'::jsonb)
WHERE key='smtp';
SQL
docker compose restart listmonk
sleep 5
docker compose ps listmonk
docker compose exec -T postgres psql -U consthruads -d listmonk -Atqc "select value->0->'email_headers' from settings where key='smtp'"
