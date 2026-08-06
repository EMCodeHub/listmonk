#!/bin/sh
set -eu
cd /opt/listmonk
echo SERVICES
docker compose config --quiet
docker compose ps
systemctl is-active docker nginx certbot.timer
systemctl is-enabled docker nginx certbot.timer
echo APP_SETTINGS
docker compose exec -T postgres psql -U consthruads -d listmonk -Atqc "select key||'='||value::text from settings where key in ('app.root_url','app.from_email','app.message_rate','bounce.enabled','bounce.webhooks_enabled','bounce.ses_enabled') order by key; select 'smtp_safe='||jsonb_build_object('host',value->0->>'host','port',value->0->>'port','enabled',value->0->>'enabled','tls_type',value->0->>'tls_type','config_header',value->0->'email_headers','username_set',(value->0->>'username')<>'','password_set',(value->0->>'password')<>'')::text from settings where key='smtp';"
echo DATABASE
docker compose exec -T postgres pg_isready -U consthruads -d listmonk
docker compose exec -T postgres psql -U consthruads -d listmonk -Atqc "select 'tables='||count(*) from pg_tables where schemaname='public'; select 'invalid_indexes='||count(*) from pg_index where not indisvalid;"
echo BACKUPS
find backups -maxdepth 1 -type f -printf '%m %s %f\n' | sort
latest="$(find backups -type f -name '*.dump' -printf '%T@ %p\n' | sort -nr | head -n1 | cut -d' ' -f2-)"
pg_restore_check="$(docker run --rm -i postgres:17-alpine pg_restore --list < "$latest" | grep -c '^')"
echo "latest_backup_toc_lines=$pg_restore_check"
echo PERMISSIONS
stat -c '%a %U:%G %n' .env secrets/postgres_password config.toml docker-compose.yml backups/*.dump /root/listmonk-admin-password.txt
echo SECRET_LOCATIONS
docker inspect listmonk-production-listmonk-1 --format '{{range .Config.Env}}{{println .}}{{end}}' | awk -F= '/password|secret|username/i {print $1"=<redacted>"}'
grep -Elri 'AKIA[0-9A-Z]{16}|smtp_password|SMTP password' --exclude='.env' --exclude='*.dump' --exclude='*.sql.gz*' --exclude='configure-ses.py' /opt/listmonk 2>/dev/null || true
echo NETWORK
ss -lntH | awk '{print $4}' | sort -u
ufw status | head -n 12
echo HTTP
curl -sS -o /dev/null -w 'https=%{http_code}\n' https://mail.consthruads.com/
curl -sS -o /dev/null -w 'http=%{http_code} redirect=%{redirect_url}\n' http://mail.consthruads.com/
curl -sS -o /dev/null -w 'health=%{http_code}\n' http://127.0.0.1:9000/health
echo TLS
openssl x509 -noout -enddate -subject -issuer -in /etc/letsencrypt/live/mail.consthruads.com/fullchain.pem
echo NGINX
nginx -t
curl -sS -D - -o /dev/null https://mail.consthruads.com/ | grep -Ei 'HTTP/|strict-transport|x-content|x-frame|referrer|permissions'
echo RECENT_ERRORS
docker compose logs --since=10m postgres listmonk backup 2>&1 | grep -Ei 'error|fatal|panic|failed' | tail -n 30 || true
