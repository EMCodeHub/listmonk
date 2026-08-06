#!/bin/sh
set -eu
cd /opt/listmonk
echo COMPOSE
docker compose ps
echo DATA
docker compose exec -T postgres psql -U consthruads -d listmonk -Atqc "select 'tables=' || count(*) from pg_tables where schemaname='public'; select 'subscribers=' || count(*) from subscribers; select 'lists=' || count(*) from lists; select 'campaigns=' || count(*) from campaigns;"
echo BACKUPS
ls -lh backups
for backup in backups/*.sql.gz; do gzip -t "$backup"; done
echo PORTS
ss -lntup
echo SERVICES
systemctl is-active docker nginx certbot.timer
systemctl is-enabled docker nginx certbot.timer
echo SES_TCP
timeout 10 sh -c 'nc -z email-smtp.us-east-1.amazonaws.com 587' && echo reachable
echo NGINX_HEADERS
curl -sSI http://mail.consthruads.com | head -n 8
curl -sSI https://mail.consthruads.com | head -n 12
echo LOCAL_PROXY
curl -sSI -H 'Host: mail.consthruads.com' -H 'X-Forwarded-Proto: https' http://127.0.0.1:9000/ | head -n 8
echo LOGS
docker compose logs --tail=25 listmonk backup
