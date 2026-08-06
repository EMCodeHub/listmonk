#!/bin/sh
set -eu
export LISTMONK_db__user="${POSTGRES_USER}"
export LISTMONK_db__database="${POSTGRES_LISTMONK_DB}"
export LISTMONK_db__password="$(cat /run/secrets/postgres_password)"
./listmonk --install --idempotent --yes --config /listmonk/config.toml
./listmonk --upgrade --yes --config /listmonk/config.toml
exec ./listmonk --config /listmonk/config.toml
