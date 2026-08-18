#!/usr/bin/env python3
"""Synchronize strict interior-design leads into production language lists."""

from __future__ import annotations

import base64
import csv
import gzip
import json
import os
import re
import urllib.parse
import uuid
from collections import Counter
from pathlib import Path

import paramiko


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "clean_emails_interior_design"
SUPPRESSIONS = ROOT / "listmonk_emails" / "manual_suppressions.json"
FOLDER_RE = re.compile(r"^\d+ - (.+?) \((\d+)\)$")

LANGUAGES = {
    "english": {
        "United States", "United Kingdom", "South Africa", "Australia", "Singapore", "Ireland", "Kenya",
        "Bermuda", "Guyana", "Montserrat", "Guernsey", "Jersey", "Malta", "Gibraltar", "Trinidad and Tobago",
        "Anguilla", "Belize", "Cocos Islands", "Falkland Islands", "Papua New Guinea", "Pitcairn", "Barbados",
        "British Virgin Islands", "Guam", "Canada", "Cayman Islands", "Cook Islands", "Dominica", "Grenada",
        "Maldives", "Niue", "Northern Mariana Islands", "Saint Kitts and Nevis", "Saint Lucia",
        "Saint Vincent and the Grenadines", "U.S. Virgin Islands", "American Samoa",
    },
    "spanish": {
        "Andorra", "Argentina", "Bolivia", "Chile", "Colombia", "Costa Rica", "Dominican Republic", "Ecuador",
        "El Salvador", "Honduras", "Mexico", "Paraguay", "Peru", "Spain", "Uruguay",
    },
    "portuguese": {"Brazil", "Portugal", "Macao"},
    "french": {
        "France", "Guadeloupe", "Martinique", "Monaco", "New Caledonia", "French Polynesia", "Saint Martin",
        "Saint Barthelemy",
    },
    "german": {"Austria", "Germany", "Liechtenstein", "Switzerland"},
    "italian": {"Italy", "San Marino", "Vatican"},
    "dutch": {"The Netherlands", "Belgium", "Aruba", "Bonaire, Saint Eustatius and Saba", "Suriname"},
    "greek": {"Greece", "Cyprus"},
    "polish": {"Poland"},
    "romanian": {"Romania", "Moldova"},
    "czech": {"Czechia"},
    "slovak": {"Slovakia"},
    "hungarian": {"Hungary"},
    "croatian": {"Croatia", "Montenegro", "Serbia", "Slovenia"},
    "bulgarian": {"Bulgaria", "North Macedonia"},
    "arabic": {"Bahrain", "Kuwait", "Qatar", "Saudi Arabia", "United Arab Emirates"},
    "russian": {"Armenia", "Azerbaijan", "Georgia", "Mongolia"},
    "albanian": {"Albania"},
}


def target_for(country: str) -> str:
    matches = [language for language, countries in LANGUAGES.items() if country in countries]
    if len(matches) > 1:
        raise RuntimeError(f"Country has multiple language targets: {country}: {matches}")
    return f"interior design {matches[0]}" if matches else f"interior design {country}"


def build_stage(path: Path) -> dict:
    suppressed = set()
    if SUPPRESSIONS.exists():
        suppressed = {email.lower() for email in json.loads(SUPPRESSIONS.read_text(encoding="utf-8"))["emails"]}
    email_owner: dict[str, str] = {}
    list_counts: Counter[str] = Counter()
    country_counts: dict[str, int] = {}
    rows: list[list[str]] = []
    folders = sorted(folder for folder in SOURCE.iterdir() if folder.is_dir())
    for folder in folders:
        match = FOLDER_RE.match(folder.name)
        if not match:
            raise RuntimeError(f"Unexpected folder name: {folder.name}")
        country, expected = match.group(1), int(match.group(2))
        list_name = target_for(country)
        source_file = folder / "listmonk_subscribers.csv"
        count = source_count = 0
        with source_file.open(encoding="utf-8-sig", newline="") as handle:
            for row in csv.DictReader(handle):
                email = row["email"].strip().lower()
                if not email:
                    continue
                source_count += 1
                if email in suppressed:
                    continue
                if email in email_owner:
                    raise RuntimeError(f"Global duplicate {email}: {email_owner[email]} and {country}")
                attribs = row.get("attributes", "{}") or "{}"
                json.loads(attribs)
                email_owner[email] = country
                rows.append([list_name, email, row.get("name", ""), attribs, country])
                list_counts[list_name] += 1
                count += 1
        if source_count != expected:
            raise RuntimeError(f"Expected {expected} source rows, got {source_count}: {source_file}")
        country_counts[country] = count
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["list_name", "email", "name", "attribs", "country"])
        writer.writerows(rows)
    if not email_owner:
        raise RuntimeError("Interior-design stage is empty")
    return {
        "countries": len(country_counts), "stage_rows": len(rows), "suppressed": len(suppressed), "target_lists": len(list_counts),
        "group_counts": dict(sorted(list_counts.items(), key=lambda item: (-item[1], item[0]))),
    }


def run(client: paramiko.SSHClient, command: str, timeout: int = 1200) -> str:
    _, stdout, stderr = client.exec_command(command, timeout=timeout)
    output = stdout.read().decode("utf-8", "replace")
    error = stderr.read().decode("utf-8", "replace")
    if error.strip():
        raise RuntimeError(error)
    return output


def http_request(transport, method: str, path: str, body: bytes = b"", headers: dict | None = None):
    channel = transport.open_channel("direct-tcpip", ("127.0.0.1", 9000), ("127.0.0.1", 0))
    all_headers = {"Host": "127.0.0.1", "Connection": "close", **(headers or {})}
    if body:
        all_headers["Content-Length"] = str(len(body))
    request = (f"{method} {path} HTTP/1.1\r\n" + "".join(f"{key}: {value}\r\n" for key, value in all_headers.items()) + "\r\n").encode() + body
    channel.sendall(request)
    data = b""
    while True:
        chunk = channel.recv(65536)
        if not chunk:
            break
        data += chunk
    channel.close()
    head, _, payload = data.partition(b"\r\n\r\n")
    return head.decode("utf-8", "replace"), payload


def refresh_list_cache(client: paramiko.SSHClient, lists: list[dict], admin_password: str) -> list[dict]:
    transport = client.get_transport()
    form = urllib.parse.urlencode({"username": "admin", "password": admin_password, "next": "/admin"}).encode()
    head, _ = http_request(transport, "POST", "/admin/login", form, {"Content-Type": "application/x-www-form-urlencoded"})
    cookies = [line.split(":", 1)[1].strip().split(";", 1)[0] for line in head.splitlines()[1:] if line.lower().startswith("set-cookie:")]
    cookie = "; ".join(cookies)
    if "302" not in head.splitlines()[0] or not any(value.startswith("session=") for value in cookies):
        raise RuntimeError("Listmonk admin login failed while refreshing list cache")
    results = []
    for item in lists:
        body = json.dumps({
            "name": item["name"], "type": "private", "optin": "single", "tags": [],
            "description": "Strict interior-design audience grouped by shared language; production bounces excluded.",
        }).encode()
        response_head, _ = http_request(transport, "PUT", f"/api/lists/{item['id']}", body, {"Cookie": cookie, "Content-Type": "application/json"})
        results.append({"id": item["id"], "name": item["name"], "http": response_head.splitlines()[0]})
    if any("200" not in item["http"] for item in results):
        raise RuntimeError(f"List cache refresh failed: {results}")
    return results


def main() -> None:
    password = os.environ.get("LISTMONK_VPS_PASSWORD")
    admin_password = os.environ.get("LISTMONK_ADMIN_PASSWORD")
    host = os.environ.get("LISTMONK_VPS_HOST")
    if not password or not admin_password or not host:
        raise SystemExit("LISTMONK_VPS_PASSWORD, LISTMONK_ADMIN_PASSWORD and LISTMONK_VPS_HOST are required")
    token = uuid.uuid4().hex
    stage = ROOT / f".interior_design_stage_{token}.csv"
    archive = stage.with_suffix(".csv.gz")
    manifest = build_stage(stage)
    with stage.open("rb") as source, gzip.open(archive, "wb", compresslevel=6) as target:
        target.write(source.read())
    remote_archive = f"/root/.interior_design_stage_{token}.csv.gz"
    remote_csv = f"/root/.interior_design_stage_{token}.csv"
    container_csv = f"/tmp/interior_design_stage_{token}.csv"
    client = paramiko.SSHClient(); client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        client.connect(host, username="root", password=password, timeout=20)
        stamp = run(client, "date -u +%Y%m%d_%H%M%S").strip()
        backup = f"/root/listmonk-backups/pre_interior_design_language_sync_{stamp}.dump"
        run(client, f'''mkdir -p /root/listmonk-backups && docker exec listmonk-production-postgres-1 sh -lc 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc' > {backup} && test -s {backup}''')
        backup_bytes = int(run(client, f"stat -c %s {backup}").strip())
        sftp = client.open_sftp(); sftp.put(str(archive), remote_archive); sftp.close()
        run(client, f"gzip -dc {remote_archive} > {remote_csv} && docker cp {remote_csv} listmonk-production-postgres-1:{container_csv}")
        sql = f'''\\set ON_ERROR_STOP on
BEGIN;
SELECT pg_advisory_xact_lock(82496680);
CREATE TEMP TABLE interior_stage(list_name text,email text,name text,attribs text,country text);
\\copy interior_stage(list_name,email,name,attribs,country) FROM '{container_csv}' WITH (FORMAT csv,HEADER true)
CREATE TEMP TABLE target_names AS SELECT list_name,COUNT(*) stage_count FROM interior_stage GROUP BY list_name;
DO $$ BEGIN
 IF (SELECT COUNT(*) FROM interior_stage)<>{manifest['stage_rows']} THEN RAISE EXCEPTION 'Unexpected stage count'; END IF;
 IF (SELECT COUNT(*) FROM interior_stage)<>(SELECT COUNT(DISTINCT lower(email)) FROM interior_stage) THEN RAISE EXCEPTION 'Duplicate stage email'; END IF;
END $$;
INSERT INTO lists(uuid,name,type,optin,tags,description)
SELECT gen_random_uuid(),t.list_name,'private','single',ARRAY[]::varchar[],'Strict interior-design audience grouped by shared language; production bounces excluded.'
FROM target_names t WHERE NOT EXISTS(SELECT 1 FROM lists l WHERE l.name=t.list_name);
INSERT INTO subscribers(uuid,email,name,attribs,status)
SELECT gen_random_uuid(),lower(s.email),COALESCE(s.name,''),s.attribs::jsonb,'enabled'
FROM interior_stage s WHERE NOT EXISTS(SELECT 1 FROM subscribers x WHERE lower(x.email)=lower(s.email));
DELETE FROM subscriber_lists sl USING lists l,target_names t
WHERE sl.list_id=l.id AND l.name=t.list_name AND sl.status='confirmed'
  AND NOT EXISTS(SELECT 1 FROM interior_stage st WHERE st.list_name=t.list_name AND lower(st.email)=(SELECT lower(email) FROM subscribers WHERE id=sl.subscriber_id));
INSERT INTO subscriber_lists(subscriber_id,list_id,status)
SELECT sub.id,l.id,'confirmed'::subscription_status
FROM interior_stage st JOIN lists l ON l.name=st.list_name JOIN subscribers sub ON lower(sub.email)=lower(st.email)
WHERE sub.status='enabled'
  AND NOT EXISTS(SELECT 1 FROM bounces b WHERE b.subscriber_id=sub.id)
  AND NOT EXISTS(SELECT 1 FROM subscriber_lists u WHERE u.subscriber_id=sub.id AND u.status='unsubscribed')
ON CONFLICT(subscriber_id,list_id) DO UPDATE SET status='confirmed'::subscription_status;
CREATE TEMP TABLE result_lists AS
SELECT l.id,l.name,t.stage_count,
 (SELECT COUNT(*) FROM subscriber_lists sl WHERE sl.list_id=l.id AND sl.status='confirmed') confirmed_count
FROM lists l JOIN target_names t ON t.list_name=l.name;
SELECT json_build_object(
 'stage_rows',(SELECT COUNT(*) FROM interior_stage),
 'target_lists',(SELECT COUNT(*) FROM result_lists),
 'confirmed_members',(SELECT SUM(confirmed_count) FROM result_lists),
 'excluded_by_production_state',(SELECT SUM(stage_count-confirmed_count) FROM result_lists),
 'unsafe_members',(SELECT COUNT(*) FROM subscriber_lists sl JOIN result_lists r ON r.id=sl.list_id JOIN subscribers s ON s.id=sl.subscriber_id WHERE sl.status='confirmed' AND (s.status<>'enabled' OR EXISTS(SELECT 1 FROM bounces b WHERE b.subscriber_id=s.id))),
 'duplicate_members_across_targets',(SELECT COUNT(*) FROM (SELECT sl.subscriber_id FROM subscriber_lists sl JOIN result_lists r ON r.id=sl.list_id WHERE sl.status='confirmed' GROUP BY sl.subscriber_id HAVING COUNT(*)>1) d),
 'lists',(SELECT json_agg(json_build_object('id',id,'name',name,'stage',stage_count,'confirmed',confirmed_count) ORDER BY name) FROM result_lists)
);
COMMIT;'''
        encoded = base64.b64encode(sql.encode()).decode()
        output = run(client, f'''docker exec listmonk-production-postgres-1 sh -lc 'echo {encoded} | base64 -d | psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -At' ''')
        json_rows = [line for line in output.splitlines() if line.startswith("{")]
        if not json_rows:
            raise RuntimeError(f"No JSON result: {output[-2000:]}")
        result = json.loads(json_rows[-1])
        cache_results = refresh_list_cache(client, result["lists"], admin_password)
        result.update({"backup": backup, "backup_bytes": backup_bytes, "manifest": manifest, "cache_updates": len(cache_results)})
        print(json.dumps(result, ensure_ascii=False, indent=2))
    finally:
        if client.get_transport() and client.get_transport().is_active():
            for command in (f"docker exec listmonk-production-postgres-1 rm -f {container_csv}", f"rm -f {remote_archive} {remote_csv}"):
                try:
                    run(client, command, timeout=30)
                except Exception:
                    pass
            client.close()
        stage.unlink(missing_ok=True); archive.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
