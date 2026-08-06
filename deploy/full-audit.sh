#!/bin/sh
set -eu
cd /opt/listmonk
echo DOCKER
docker compose config --quiet
docker compose ps
docker stats --no-stream --format '{{.Name}} cpu={{.CPUPerc}} mem={{.MemUsage}}'
docker network inspect listmonk-production_backend listmonk-production_frontend --format '{{.Name}} internal={{.Internal}} containers={{len .Containers}}'
echo POSTGRES
docker compose exec -T postgres psql -U consthruads -d listmonk -Atqc "select 'connections='||count(*) from pg_stat_activity; select 'db_size='||pg_size_pretty(pg_database_size(current_database())); select 'invalid_indexes='||count(*) from pg_index where not indisvalid; select 'dead_tuples='||coalesce(sum(n_dead_tup),0) from pg_stat_user_tables;"
docker compose exec -T postgres psql -U consthruads -d listmonk -c 'VACUUM (ANALYZE);' >/dev/null
echo RESTORE_TEST
latest="$(find backups -type f -name '*.dump' -printf '%T@ %p\n' | sort -nr | head -n1 | cut -d' ' -f2-)"
test -n "$latest"
docker compose exec -T postgres dropdb -U consthruads --if-exists listmonk_restore_test
docker compose exec -T postgres createdb -U consthruads listmonk_restore_test
docker cp "$latest" listmonk-production-postgres-1:/tmp/restore.dump
docker compose exec -T postgres pg_restore -U consthruads -d listmonk_restore_test --no-owner --no-acl --exit-on-error /tmp/restore.dump
docker compose exec -T postgres psql -U consthruads -d listmonk_restore_test -Atqc "select 'restored_tables='||count(*) from pg_tables where schemaname='public'; select 'restored_subscribers='||count(*) from subscribers;"
docker compose exec -T postgres dropdb -U consthruads listmonk_restore_test
docker compose exec -T postgres rm /tmp/restore.dump
echo NGINX
nginx -t
sed -n '1,240p' /etc/nginx/sites-available/mail.consthruads.com
echo TLS
openssl x509 -noout -enddate -issuer -subject -in /etc/letsencrypt/live/mail.consthruads.com/fullchain.pem
systemctl is-enabled certbot.timer
echo PORTS
ss -lntup
ufw status verbose
echo HTTP
curl -sS -o /dev/null -w 'https=%{http_code}\n' https://mail.consthruads.com/
curl -sS -o /dev/null -w 'http=%{http_code} redirect=%{redirect_url}\n' http://mail.consthruads.com/
curl -sS -o /dev/null -w 'health=%{http_code}\n' http://127.0.0.1:9000/health
echo LOGS
docker compose logs --since=30m postgres listmonk backup 2>&1 | grep -Ei 'error|fatal|panic|failed' | tail -n 100 || true
journalctl -u nginx --since='30 minutes ago' --no-pager | grep -Ei 'error|fatal|panic|failed' | tail -n 50 || true
