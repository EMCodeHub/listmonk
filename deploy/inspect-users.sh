#!/bin/sh
set -eu
cd /opt/listmonk
docker compose exec -T postgres psql -U consthruads -d listmonk -c '\d users'
docker compose exec -T postgres psql -U consthruads -d listmonk -c 'select id, username, type, status from users order by id;'
docker compose exec -T listmonk ./listmonk --help 2>&1 | sed -n '1,180p'
