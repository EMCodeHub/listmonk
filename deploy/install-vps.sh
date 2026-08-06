#!/bin/sh
set -eu
cd /opt/listmonk
chmod 700 entrypoint.sh backup-loop.sh
chmod 600 .env secrets/postgres_password listmonk.dump

apt-get update -qq
DEBIAN_FRONTEND=noninteractive apt-get install -y -qq nginx certbot python3-certbot-nginx ufw
systemctl enable nginx

docker compose config --quiet
docker compose up -d postgres
i=0
until docker compose exec -T postgres pg_isready -U consthruads -d listmonk; do
  i=$((i + 1))
  test "$i" -lt 30
  sleep 2
done

table_count="$(docker compose exec -T postgres psql -U consthruads -d listmonk -Atqc "select count(*) from pg_tables where schemaname='public'")"
if [ "$table_count" = "0" ]; then
  docker cp listmonk.dump listmonk-production-postgres-1:/tmp/listmonk.dump
  docker compose exec -T postgres pg_restore -U consthruads -d listmonk --no-owner --no-acl --exit-on-error /tmp/listmonk.dump
  docker compose exec -T postgres rm /tmp/listmonk.dump
else
  echo "Refusing restore: database already contains $table_count public tables" >&2
  exit 3
fi

docker compose up -d listmonk backup
i=0
until docker compose exec -T listmonk wget -qO- http://127.0.0.1:9000/ >/dev/null; do
  i=$((i + 1))
  test "$i" -lt 60
  sleep 2
done

install -m 644 nginx.conf /etc/nginx/sites-available/mail.consthruads.com
ln -sfn /etc/nginx/sites-available/mail.consthruads.com /etc/nginx/sites-enabled/mail.consthruads.com
rm -f /etc/nginx/sites-enabled/default
nginx -t
systemctl restart nginx

ufw default deny incoming
ufw default allow outgoing
ufw allow 22/tcp
ufw allow 80/tcp
ufw allow 443/tcp
ufw --force enable

certbot --nginx --non-interactive --agree-tos --redirect --hsts --staple-ocsp \
  --email admin@consthruads.com -d mail.consthruads.com
systemctl enable --now certbot.timer

docker compose ps
nginx -t
ufw status verbose
certbot certificates
