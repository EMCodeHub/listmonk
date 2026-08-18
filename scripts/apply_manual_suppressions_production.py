"""Audit or apply a private manual-suppression proposal to Listmonk production."""
from __future__ import annotations

import argparse
import base64
import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PROPOSAL = ROOT.parent / "emails_relevance_hostinguer" / "hostinger_mail_cleaner" / "private" / "rejection_suppression_proposal.json"
HOST = f"root@{os.environ['LISTMONK_VPS_HOST']}"


def ssh(command: str) -> str:
    result = subprocess.run(
        ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=15", HOST, command],
        text=True, capture_output=True, timeout=1200, check=False,
    )
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or f"ssh exited {result.returncode}")
    return result.stdout


def psql(sql: str) -> str:
    payload = base64.b64encode(sql.encode()).decode()
    command = f'''docker exec listmonk-production-postgres-1 sh -lc 'echo {payload} | base64 -d | psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -At' '''
    return ssh(command)


def values(emails: list[str]) -> str:
    return ",".join("('" + email.replace("'", "''") + "')" for email in emails)


def audit_sql(emails: list[str]) -> str:
    return f"""\
\\set ON_ERROR_STOP on
CREATE TEMP TABLE targets(email text);
INSERT INTO targets(email) VALUES {values(emails)};
SELECT json_build_object(
 'targets',(SELECT COUNT(*) FROM targets),
 'existing',(SELECT COUNT(*) FROM subscribers s JOIN targets t ON lower(s.email)=t.email),
 'blocklisted',(SELECT COUNT(*) FROM subscribers s JOIN targets t ON lower(s.email)=t.email WHERE s.status='blocklisted'),
 'memberships',(SELECT COUNT(*) FROM subscriber_lists sl JOIN subscribers s ON s.id=sl.subscriber_id JOIN targets t ON lower(s.email)=t.email),
 'missing',(SELECT COUNT(*) FROM targets t WHERE NOT EXISTS(SELECT 1 FROM subscribers s WHERE lower(s.email)=t.email))
);
"""


def apply_sql(emails: list[str]) -> str:
    return f"""\
\\set ON_ERROR_STOP on
BEGIN;
SELECT pg_advisory_xact_lock(82496693);
CREATE TEMP TABLE targets(email text PRIMARY KEY);
INSERT INTO targets(email) VALUES {values(emails)};
INSERT INTO subscribers(uuid,email,name,attribs,status)
SELECT gen_random_uuid(),t.email,'','{{}}'::jsonb,'blocklisted' FROM targets t
WHERE NOT EXISTS(SELECT 1 FROM subscribers s WHERE lower(s.email)=t.email);
UPDATE subscribers s SET status='blocklisted' FROM targets t WHERE lower(s.email)=t.email;
WITH removed AS (
 DELETE FROM subscriber_lists sl USING subscribers s,targets t
 WHERE sl.subscriber_id=s.id AND lower(s.email)=t.email RETURNING sl.subscriber_id
)
SELECT json_build_object(
 'targets',(SELECT COUNT(*) FROM targets),
 'blocklisted',(SELECT COUNT(*) FROM subscribers s JOIN targets t ON lower(s.email)=t.email WHERE s.status='blocklisted'),
 'memberships_removed',(SELECT COUNT(*) FROM removed),
 'memberships_remaining',(SELECT COUNT(*) FROM subscriber_lists sl JOIN subscribers s ON s.id=sl.subscriber_id JOIN targets t ON lower(s.email)=t.email)
);
COMMIT;
"""


def json_result(output: str) -> dict:
    rows = [line for line in output.splitlines() if line.startswith("{")]
    if not rows:
        raise RuntimeError("Production query returned no JSON result")
    return json.loads(rows[-1])


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--proposal", type=Path, default=DEFAULT_PROPOSAL)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    data = json.loads(args.proposal.read_text(encoding="utf-8"))
    emails = sorted({email.strip().lower() for email in data["emails"]})
    if not emails or any("@" not in email for email in emails):
        raise RuntimeError("Invalid or empty proposal")
    before = json_result(psql(audit_sql(emails)))
    result = {"before": before, "apply": args.apply}
    if args.apply:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        backup = f"/root/listmonk-backups/pre_manual_suppressions_{stamp}.dump"
        ssh(f'''mkdir -p /root/listmonk-backups && docker exec listmonk-production-postgres-1 sh -lc 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc' > {backup} && test -s {backup}''')
        backup_bytes = int(ssh(f"stat -c %s {backup}").strip())
        applied = json_result(psql(apply_sql(emails)))
        after = json_result(psql(audit_sql(emails)))
        if after["blocklisted"] != len(emails) or after["memberships"] != 0 or after["missing"] != 0:
            raise RuntimeError(f"Independent verification failed: {after}")
        result.update({"backup": backup, "backup_bytes": backup_bytes, "applied": applied, "after": after})
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
