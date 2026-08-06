#!/bin/sh
set -eu
cd /opt/listmonk
stamp="$(date -u +%Y%m%dT%H%M%SZ)"
dest="/opt/listmonk/prechange/${stamp}"
install -d -m 700 "$dest"
docker compose exec -T postgres pg_dump -U consthruads -d listmonk --format=custom --no-owner --no-acl > "$dest/listmonk.dump"
test -s "$dest/listmonk.dump"
docker run --rm -i postgres:17-alpine pg_restore --list < "$dest/listmonk.dump" >/dev/null
cp -a docker-compose.yml config.toml .env nginx.conf ./*.sh ./*.py "$dest/" 2>/dev/null || true
cp -a /etc/nginx/sites-available/mail.consthruads.com "$dest/nginx-site.conf"
chmod -R go-rwx "$dest"
sha256sum "$dest/listmonk.dump" > "$dest/SHA256SUMS"
echo "$dest"
du -sh "$dest"
