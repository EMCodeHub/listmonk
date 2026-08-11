#!/usr/bin/env python3
"""Create starred clean Listmonk lists on the VPS without altering old lists or bounce state."""

from __future__ import annotations

import argparse
import base64
import csv
import gzip
import json
import os
import re
import uuid
from pathlib import Path

import paramiko


COLLECTIONS = {
    "clean_emails_dermatologist": "dermatologist",
    "clean_emails_odontologist": "odontologist",
    "clean_emails_real_estate": "real estate",
    "clean_emails_renovation": "renovation",
    "clean_emails_construction": "construction",
}
FOLDER_RE = re.compile(r"^\d+ - (.+?) \((\d+)\)$")


def build_stage(root: Path, output: Path) -> dict:
    manifest, total_rows = [], 0
    with output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle); writer.writerow(["list_name", "email", "name", "attribs"])
        for folder_name, niche in COLLECTIONS.items():
            collection = root / folder_name
            for csv_path in sorted(collection.glob("*/listmonk_subscribers.csv")):
                match = FOLDER_RE.match(csv_path.parent.name)
                if not match:
                    raise RuntimeError(f"Unexpected folder name: {csv_path.parent}")
                country, expected = match.group(1), int(match.group(2))
                display = "USA" if country == "United States" else country
                list_name = f"{display} {niche} leads *"
                count = 0
                with csv_path.open(encoding="utf-8-sig", newline="") as source:
                    for row in csv.DictReader(source):
                        email = row["email"].strip().lower()
                        if not email:
                            continue
                        attribs = row.get("attributes", "{}") or "{}"
                        json.loads(attribs)
                        writer.writerow([list_name, email, row.get("name", ""), attribs])
                        count += 1; total_rows += 1
                if count != expected:
                    raise RuntimeError(f"Expected {expected} rows, got {count}: {csv_path}")
                if count == 0:
                    writer.writerow([list_name, "", "", "{}"])
                manifest.append({"name": list_name, "country": country, "niche": niche, "rows": count})
    names = [m["name"] for m in manifest]
    if len(names) != 603 or len(set(names)) != 603:
        raise RuntimeError(f"Manifest invariant failed: total={len(names)} unique={len(set(names))}")
    return {"lists": len(names), "rows": total_rows, "by_niche": {n: sum(x["rows"] for x in manifest if x["niche"] == n) for n in COLLECTIONS.values()}}


def run_ssh(client: paramiko.SSHClient, command: str, timeout: int = 600) -> str:
    _, stdout, stderr = client.exec_command(command, timeout=timeout)
    out, err = stdout.read().decode("utf-8", "replace"), stderr.read().decode("utf-8", "replace")
    if err.strip():
        raise RuntimeError(err)
    return out


def apply(root: Path, host: str, user: str, password: str) -> dict:
    token = uuid.uuid4().hex
    csv_path = root / f".clean_vps_sync_{token}.csv"
    gz_path = csv_path.with_suffix(".csv.gz")
    manifest = build_stage(root, csv_path)
    with csv_path.open("rb") as source, gzip.open(gz_path, "wb", compresslevel=6) as dest:
        dest.write(source.read())

    remote_gz = f"/root/.clean_vps_sync_{token}.csv.gz"
    remote_csv = f"/root/.clean_vps_sync_{token}.csv"
    container_csv = f"/tmp/clean_vps_sync_{token}.csv"
    sql = f"""\
\\set ON_ERROR_STOP on
BEGIN;
SELECT pg_advisory_xact_lock(82496621);
CREATE TEMP TABLE clean_stage(list_name text, email text, name text, attribs text);
\\copy clean_stage(list_name,email,name,attribs) FROM '{container_csv}' WITH (FORMAT csv, HEADER true)

CREATE TEMP TABLE target_names AS SELECT DISTINCT list_name FROM clean_stage;

INSERT INTO lists(uuid,name,type,optin,tags,description)
SELECT gen_random_uuid(), t.list_name, 'private', 'single', ARRAY[]::varchar[],
       'Strict bounce-filtered list synchronized from local clean_emails dataset.'
FROM target_names t
WHERE NOT EXISTS (SELECT 1 FROM lists l WHERE l.name=t.list_name);

INSERT INTO subscribers(uuid,email,name,attribs,status)
SELECT DISTINCT ON (lower(s.email)) gen_random_uuid(), lower(s.email), coalesce(s.name,''), s.attribs::jsonb, 'enabled'
FROM clean_stage s
WHERE s.email<>'' AND NOT EXISTS (SELECT 1 FROM subscribers x WHERE lower(x.email)=lower(s.email))
ORDER BY lower(s.email), s.list_name;

INSERT INTO subscriber_lists(subscriber_id,list_id,status)
SELECT DISTINCT sub.id,l.id,'confirmed'::subscription_status
FROM clean_stage st
JOIN lists l ON l.name=st.list_name
JOIN subscribers sub ON lower(sub.email)=lower(st.email)
WHERE st.email<>''
  AND sub.status='enabled'
  AND NOT EXISTS (SELECT 1 FROM bounces b WHERE b.subscriber_id=sub.id)
  AND NOT EXISTS (SELECT 1 FROM subscriber_lists oldsl WHERE oldsl.subscriber_id=sub.id AND oldsl.status='unsubscribed')
ON CONFLICT (subscriber_id,list_id) DO NOTHING;

SELECT json_build_object(
 'target_lists',(SELECT COUNT(*) FROM lists l JOIN target_names t ON t.list_name=l.name),
 'stage_rows',(SELECT COUNT(*) FROM clean_stage WHERE email<>''),
 'confirmed_memberships',(SELECT COUNT(*) FROM subscriber_lists sl JOIN lists l ON l.id=sl.list_id JOIN target_names t ON t.list_name=l.name WHERE sl.status='confirmed'),
 'unsafe_memberships',(SELECT COUNT(*) FROM subscriber_lists sl JOIN lists l ON l.id=sl.list_id JOIN target_names t ON t.list_name=l.name JOIN subscribers s ON s.id=sl.subscriber_id WHERE s.status<>'enabled' OR EXISTS(SELECT 1 FROM bounces b WHERE b.subscriber_id=s.id)),
 'bounced_records_preserved',(SELECT COUNT(*) FROM bounces),
 'blocklisted_records_preserved',(SELECT COUNT(*) FROM subscribers WHERE status='blocklisted'),
 'unsubscribed_records_preserved',(SELECT COUNT(*) FROM subscriber_lists WHERE status='unsubscribed')
);
COMMIT;
"""
    client = paramiko.SSHClient(); client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        client.connect(host, username=user, password=password, timeout=20)
        sftp = client.open_sftp(); sftp.put(str(gz_path), remote_gz); sftp.close()
        run_ssh(client, f"gzip -dc {remote_gz} > {remote_csv} && docker cp {remote_csv} listmonk-production-postgres-1:{container_csv}")
        encoded = base64.b64encode(sql.encode()).decode()
        command = f'''docker exec listmonk-production-postgres-1 sh -lc 'echo {encoded} | base64 -d | psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -At' '''
        output = run_ssh(client, command, timeout=1200)
        lines = [line for line in output.splitlines() if line.startswith("{")]
        if not lines:
            raise RuntimeError(f"No JSON result from psql: {output[-2000:]}")
        result = json.loads(lines[-1]); result["local_manifest"] = manifest
        return result
    finally:
        if client.get_transport() and client.get_transport().is_active():
            try:
                run_ssh(client, f"docker exec listmonk-production-postgres-1 rm -f {container_csv}", timeout=30)
            except Exception:
                pass
            try:
                run_ssh(client, f"rm -f {remote_gz} {remote_csv}", timeout=30)
            except Exception:
                pass
            client.close()
        csv_path.unlink(missing_ok=True); gz_path.unlink(missing_ok=True)


def main() -> None:
    parser = argparse.ArgumentParser(); parser.add_argument("--root", type=Path, required=True); parser.add_argument("--apply", action="store_true")
    parser.add_argument("--host", default="187.127.70.251"); parser.add_argument("--user", default="root")
    args = parser.parse_args(); stage = args.root / ".clean_vps_sync_dry_run.csv"
    if not args.apply:
        result = build_stage(args.root, stage); stage.unlink(missing_ok=True); print(json.dumps(result, indent=2)); return
    password = os.environ.get("LISTMONK_VPS_PASSWORD")
    if not password:
        raise SystemExit("LISTMONK_VPS_PASSWORD is required")
    print(json.dumps(apply(args.root, args.host, args.user, password), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
