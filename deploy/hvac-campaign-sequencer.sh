#!/usr/bin/env bash
set -euo pipefail

LOCK=/run/lock/listmonk-hvac-campaign-sequencer.lock
CONTAINER=listmonk-production-postgres-1
APP_CONTAINER=listmonk-production-listmonk-1
PREFIX='Air Conditioning Leads - %'

exec 9>"$LOCK"
flock -n 9 || exit 0

psqlq() {
  docker exec "$CONTAINER" psql -U consthruads -d listmonk -Atqc "$1"
}

running_hvac=$(psqlq "SELECT count(*) FROM campaigns WHERE name LIKE '$PREFIX' AND status='running'")
running_other=$(psqlq "SELECT count(*) FROM campaigns WHERE name NOT LIKE '$PREFIX' AND status='running'")
paused_hvac=$(psqlq "SELECT count(*) FROM campaigns WHERE name LIKE '$PREFIX' AND status='paused'")

if (( running_hvac > 1 )); then
  echo "hold: multiple HVAC campaigns running ($running_hvac)"
  exit 1
fi
if (( running_hvac == 1 )); then
  psqlq "SELECT 'waiting: '||name||' sent='||sent||'/'||to_send FROM campaigns WHERE name LIKE '$PREFIX' AND status='running'"
  exit 0
fi
if (( running_other > 0 )); then
  echo "waiting: another non-HVAC campaign is running"
  exit 0
fi
if (( paused_hvac > 0 )); then
  echo "hold: an HVAC campaign is paused; manual review required"
  exit 0
fi

next_id=$(psqlq "SELECT id FROM campaigns WHERE name LIKE '$PREFIX' AND status='draft' AND sent=0 ORDER BY to_send ASC,id ASC LIMIT 1")
if [[ -z "$next_id" ]]; then
  echo "complete: no untouched HVAC drafts remain"
  exit 0
fi

unsafe=$(psqlq "SELECT count(*) FROM campaign_lists cl JOIN subscriber_lists sl ON sl.list_id=cl.list_id AND sl.status='confirmed' JOIN subscribers s ON s.id=sl.subscriber_id WHERE cl.campaign_id=$next_id AND (s.status<>'enabled' OR EXISTS(SELECT 1 FROM bounces b WHERE b.subscriber_id=s.id) OR EXISTS(SELECT 1 FROM subscriber_lists u WHERE u.subscriber_id=s.id AND u.status='unsubscribed'))")
if (( unsafe > 0 )); then
  echo "hold: next HVAC campaign id=$next_id has unsafe recipients ($unsafe)"
  exit 1
fi

started=$(psqlq "BEGIN; SELECT pg_advisory_xact_lock(82496703); UPDATE campaigns SET status='running',created_at=now(),updated_at=now() WHERE id=$next_id AND name LIKE '$PREFIX' AND status='draft' AND sent=0 AND NOT EXISTS(SELECT 1 FROM campaigns WHERE status='running') RETURNING id; COMMIT;" | grep -E '^[0-9]+$' | tail -n1 || true)
if [[ -z "$started" ]]; then
  echo "waiting: start precondition changed"
  exit 0
fi

docker restart "$APP_CONTAINER" >/dev/null
for _ in $(seq 1 30); do
  health=$(docker inspect -f '{{if .State.Health}}{{.State.Health.Status}}{{else}}running{{end}}' "$APP_CONTAINER")
  [[ "$health" == healthy ]] && break
  sleep 1
done

psqlq "SELECT 'started: '||name||' id='||id||' targets='||to_send||' status='||status FROM campaigns WHERE id=$started"

