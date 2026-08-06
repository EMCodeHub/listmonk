#!/bin/sh
set -eu
cd /opt/listmonk
docker compose ps
docker compose exec -T postgres psql -U consthruads -d listmonk -Atqc "
select 'root_url=' || (value#>>'{}') from settings where key='app.root_url';
select 'from_email=' || (value#>>'{}') from settings where key='app.from_email';
select 'message_rate=' || value::text from settings where key='app.message_rate';
select 'smtp=' || jsonb_build_object(
  'host',value->0->>'host', 'port',value->0->>'port',
  'enabled',value->0->>'enabled', 'tls_type',value->0->>'tls_type',
  'auth_protocol',value->0->>'auth_protocol',
  'username_set',(value->0->>'username')<>'',
  'password_set',(value->0->>'password')<>'',
  'tls_skip_verify',value->0->>'tls_skip_verify',
  'max_conns',value->0->>'max_conns')::text
from settings where key='smtp';
select key || '=' || value::text from settings
where key in ('bounce.enabled','bounce.ses_enabled','bounce.webhooks_enabled') order by key;
"
echo LOG_FINDINGS
docker compose logs --since=24h listmonk 2>&1 | grep -Ei 'error|smtp|bounce|complaint|fail' | tail -n 50 || true
echo TLS_ENDPOINT
timeout 15 openssl s_client -starttls smtp -connect email-smtp.us-east-1.amazonaws.com:587 -servername email-smtp.us-east-1.amazonaws.com </dev/null 2>/dev/null | openssl x509 -noout -subject -issuer -dates
