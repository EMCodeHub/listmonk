#!/bin/sh
set -eu
cd /opt/listmonk
i=0
until [ "$(docker inspect -f '{{.State.Health.Status}}' listmonk-production-listmonk-1)" = healthy ] && [ "$(docker inspect -f '{{.State.Health.Status}}' listmonk-production-postgres-1)" = healthy ]; do
  i=$((i + 1)); test "$i" -lt 30; sleep 2
done
docker compose ps
printf 'https_status='; curl -sS -o /dev/null -w '%{http_code}\n' https://mail.consthruads.com/
printf 'http_redirect='; curl -sS -o /dev/null -w '%{http_code} %{redirect_url}\n' http://mail.consthruads.com/
docker compose exec -T postgres psql -U consthruads -d listmonk -Atqc "select 'root_url=' || (value#>>'{}') from settings where key='app.root_url'; select 'smtp_enabled=' || (value->0->>'enabled') || ',host=' || (value->0->>'host') || ',port=' || (value->0->>'port') || ',username_set=' || ((value->0->>'username') <> '') || ',password_set=' || ((value->0->>'password') <> '') from settings where key='smtp';"
printf 'backup_files='; find backups -type f -name '*.sql.gz' | wc -l
for backup in backups/*.sql.gz; do gzip -t "$backup"; done
printf 'certificate_expiry='; openssl x509 -enddate -noout -in /etc/letsencrypt/live/mail.consthruads.com/fullchain.pem | cut -d= -f2-
printf 'ufw='; ufw status | head -n1
printf 'public_listeners='; ss -lntH | awk '$4 ~ /:(22|80|443)$/ {print $4}' | paste -sd, -
printf 'postgres_public='; ss -lntH | grep -Eq '(^|:)(5432)[[:space:]]' && echo yes || echo no
printf 'docker_enabled='; systemctl is-enabled docker
printf 'nginx_enabled='; systemctl is-enabled nginx
printf 'certbot_timer='; systemctl is-enabled certbot.timer
