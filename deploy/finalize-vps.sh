#!/bin/sh
set -eu
cd /opt/listmonk
docker compose exec -T postgres psql -U consthruads -d listmonk <<'SQL'
UPDATE settings SET value = '"https://mail.consthruads.com"'::jsonb WHERE key = 'app.root_url';
UPDATE settings
SET value = jsonb_build_array(
  (value->0) || jsonb_build_object(
    'host', 'email-smtp.us-east-1.amazonaws.com',
    'port', 587,
    'enabled', false,
    'username', '',
    'password', '',
    'tls_type', 'STARTTLS',
    'auth_protocol', 'login'
  )
)
WHERE key = 'smtp';
SQL
docker compose restart listmonk
i=0
until curl -fsS http://127.0.0.1:9000/ >/dev/null; do
  i=$((i + 1))
  test "$i" -lt 30
  sleep 2
done
certbot renew --dry-run
curl -fsSI https://mail.consthruads.com/ | head -n 12
docker compose ps
