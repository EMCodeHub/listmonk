#!/bin/sh
set -eu
cd /opt/listmonk
echo DOCKER
docker compose config --quiet
docker compose ps
docker inspect listmonk-production-listmonk-1 listmonk-production-postgres-1 listmonk-production-backup-1 --format '{{.Name}} restart={{.HostConfig.RestartPolicy.Name}} health={{if .State.Health}}{{.State.Health.Status}}{{else}}n/a{{end}}'
docker stats --no-stream --format '{{.Name}} cpu={{.CPUPerc}} mem={{.MemUsage}}'
echo DATABASE_AND_QUEUE
docker compose exec -T postgres pg_isready -U consthruads -d listmonk
docker compose exec -T postgres psql -U consthruads -d listmonk -Atqc "select 'tables='||count(*) from pg_tables where schemaname='public'; select 'subscribers='||count(*) from subscribers; select 'lists='||count(*) from lists; select 'campaigns='||count(*) from campaigns; select 'campaign_status='||status||':'||count(*) from campaigns group by status order by status; select 'invalid_indexes='||count(*) from pg_index where not indisvalid;"
echo RESTORE_TEST
latest="$(find backups -type f -name '*.dump' -printf '%T@ %p\n' | sort -nr | head -n1 | cut -d' ' -f2-)"
docker compose exec -T postgres dropdb -U consthruads --if-exists listmonk_restore_audit
docker compose exec -T postgres createdb -U consthruads listmonk_restore_audit
docker cp "$latest" listmonk-production-postgres-1:/tmp/audit.dump >/dev/null
docker compose exec -T postgres pg_restore -U consthruads -d listmonk_restore_audit --no-owner --no-acl --exit-on-error /tmp/audit.dump
docker compose exec -T postgres psql -U consthruads -d listmonk_restore_audit -Atqc "select 'restored_tables='||count(*) from pg_tables where schemaname='public'"
docker compose exec -T postgres dropdb -U consthruads listmonk_restore_audit
docker compose exec -T postgres rm /tmp/audit.dump
echo APP
curl -sS -o /dev/null -w 'health=%{http_code}\n' http://127.0.0.1:9000/health
docker compose exec -T postgres psql -U consthruads -d listmonk -Atqc "select key||'='||value::text from settings where key in ('app.root_url','app.from_email','app.message_rate','privacy.unsubscribe_header','privacy.individual_tracking','bounce.enabled','bounce.webhooks_enabled','bounce.ses_enabled') order by key"
echo FILES
stat -c '%a %U:%G %n' .env secrets/postgres_password config.toml docker-compose.yml backups/*.dump
find /opt/listmonk -type f -iname '*credential*.csv' -print
echo NGINX_TLS
nginx -t
curl -sS -o /dev/null -w 'https=%{http_code}\n' https://mail.consthruads.com/
curl -sS -o /dev/null -w 'http=%{http_code} redirect=%{redirect_url}\n' http://mail.consthruads.com/
curl -sS -D - -o /dev/null https://mail.consthruads.com/ | grep -Ei 'strict-transport|x-content|x-frame|referrer|permissions'
openssl x509 -noout -enddate -subject -issuer -in /etc/letsencrypt/live/mail.consthruads.com/fullchain.pem
systemctl is-enabled certbot.timer
echo NETWORK
ufw status | head -n 12
ss -lntH | grep -E ':(22|80|443|9000|5432)[[:space:]]' || true
echo LOGS
docker compose logs --since=30m listmonk postgres backup 2>&1 | grep -Ei 'error|fatal|panic|credential|password' | tail -n 30 || true
