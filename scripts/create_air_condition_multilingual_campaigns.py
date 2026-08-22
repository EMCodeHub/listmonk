#!/usr/bin/env python3
"""Sync clean HVAC leads into language lists and create draft campaigns."""

from __future__ import annotations

import csv
import gzip
import html
import json
import os
import re
import subprocess
import uuid
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "clean_emails_air_condition"
TRANSLATIONS = ROOT / "listmonk_emails" / "air_condition_campaign_translations.json"
FOLDER_RE = re.compile(r"^\d+ - (.+?) \((\d+)\)$")
SSH_TARGET = f"root@{os.environ.get('LISTMONK_VPS_HOST', '187.127.70.251')}"
FROM_EMAIL = "Edward <edward.hvac@consthruads.com>"

LANGUAGES = {
    "English": {"United States","United Kingdom","South Africa","Australia","Singapore","Ireland","Kenya","Bermuda","Guyana","Montserrat","Guernsey","Jersey","Malta","Gibraltar","Trinidad and Tobago","Anguilla","Belize","Cocos Islands","Falkland Islands","Papua New Guinea","Pitcairn","Barbados","British Virgin Islands","Guam","Canada","Cayman Islands","Cook Islands","Dominica","Grenada","Maldives","Niue","Northern Mariana Islands","Saint Kitts and Nevis","Saint Lucia","Saint Vincent and the Grenadines","U.S. Virgin Islands","American Samoa","Antigua and Barbuda","Bahamas","Brunei","Christmas Island","Isle of Man","New Zealand","South Georgia and the South Sandwich Islands"},
    "Spanish": {"Andorra","Argentina","Bolivia","Chile","Colombia","Costa Rica","Dominican Republic","Ecuador","El Salvador","Honduras","Mexico","Paraguay","Peru","Spain","Uruguay","Panama"},
    "Portuguese": {"Brazil","Portugal","Macao"},
    "French": {"France","Guadeloupe","Martinique","Monaco","New Caledonia","French Polynesia","Saint Martin","Saint Barthelemy","Luxembourg"},
    "German": {"Austria","Germany","Liechtenstein","Switzerland"},
    "Italian": {"Italy","San Marino","Vatican"},
    "Dutch": {"The Netherlands","Belgium","Aruba","Bonaire, Saint Eustatius and Saba","Suriname","Sint Maarten"},
    "Greek": {"Greece","Cyprus"}, "Polish": {"Poland"}, "Romanian": {"Romania","Moldova"},
    "Czech": {"Czechia"}, "Slovak": {"Slovakia"}, "Hungarian": {"Hungary"},
    "Croatian": {"Croatia","Montenegro","Serbia","Slovenia"},
    "Bulgarian": {"Bulgaria","North Macedonia"},
    "Arabic": {"Bahrain","Kuwait","Qatar","Saudi Arabia","United Arab Emirates","Oman"},
    "Russian": {"Armenia","Azerbaijan","Georgia","Mongolia"}, "Albanian": {"Albania"},
    "Norwegian": {"Norway","Svalbard and Jan Mayen"}, "Finnish": {"Finland"},
    "Danish": {"Denmark","Greenland"}, "Estonian": {"Estonia"}, "Lithuanian": {"Lithuania"},
    "Latvian": {"Latvia"}, "Icelandic": {"Iceland"}, "Swedish": {"Sweden","Aland Islands"},
}


def quote(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def language_for(country: str) -> str:
    matches = [language for language, countries in LANGUAGES.items() if country in countries]
    if len(matches) != 1:
        raise RuntimeError(f"Country must map to exactly one language: {country}: {matches}")
    return matches[0]


def body(values: dict[str, str], code: str, rtl: bool) -> str:
    e = lambda name: html.escape(values[name], quote=False)
    url = f"https://consthruads.com/?lang={code}"
    content = f"""<p>{e('p1')}</p>
<p>{e('p2')}</p>
<p>{e('p3a')} <strong>{e('p3b')}</strong>.</p>
<p>{e('p4')}</p>
<p>{e('p5')}</p>
<p>{e('p6')}</p>
<p>{e('p7')}</p>
<p>{e('p8')}<br>Edward</p>
<p><a href="{url}" target="_blank" rel="noopener noreferrer">{url}</a></p>"""
    return f'<div dir="rtl">{content}</div>' if rtl else content


def build_stage(path: Path) -> tuple[dict, list[tuple[str, str, str, str, str, str]]]:
    payload = json.loads(TRANSLATIONS.read_text(encoding="utf-8"))
    codes, translations = payload["codes"], payload["translations"]
    if set(codes) != set(LANGUAGES) or set(translations) != set(LANGUAGES):
        raise RuntimeError("Translation languages do not match language map")
    rows, seen, countries, counts = [], set(), set(), Counter()
    for folder in sorted(path for path in SOURCE.iterdir() if path.is_dir()):
        match = FOLDER_RE.match(folder.name)
        if not match:
            raise RuntimeError(f"Unexpected folder: {folder.name}")
        country, expected = match.group(1), int(match.group(2)); language = language_for(country)
        source = folder / "listmonk_subscribers.csv"; source_rows = 0
        with source.open(encoding="utf-8-sig", newline="") as handle:
            for row in csv.DictReader(handle):
                email = row["email"].strip().lower(); source_rows += bool(email)
                if not email:
                    continue
                if email in seen:
                    raise RuntimeError(f"Duplicate clean email across countries: {email}")
                json.loads(row.get("attributes", "{}") or "{}")
                seen.add(email); rows.append([language, email, row.get("name", ""), row.get("attributes", "{}"), country]); counts[language] += 1
        if source_rows != expected:
            raise RuntimeError(f"Folder count mismatch: {folder.name}: {source_rows} != {expected}")
        countries.add(country)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle); writer.writerow(["language","email","name","attribs","country"]); writer.writerows(rows)
    definitions = []
    for language in sorted(counts):
        code, values = codes[language], translations[language]
        definitions.append((language, code, f"air conditioning {language.lower()}", f"Air Conditioning Leads - {language}", values["subject"], body(values, code, language == "Arabic")))
    return {"countries": len(countries), "languages": len(counts), "stage_rows": len(rows), "group_counts": dict(counts)}, definitions


def ssh(command: str, timeout: int = 1800) -> str:
    result = subprocess.run(["ssh","-o","BatchMode=yes","-o","ConnectTimeout=20",SSH_TARGET,command], capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout)
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or f"ssh exited {result.returncode}")
    return result.stdout


def main() -> None:
    token = uuid.uuid4().hex; stage = ROOT / f".air_condition_stage_{token}.csv"; archive = stage.with_suffix(".csv.gz")
    manifest, definitions = build_stage(stage)
    with stage.open("rb") as source, gzip.open(archive, "wb", compresslevel=6) as target:
        target.write(source.read())
    sql_file = ROOT / f".air_condition_campaigns_{token}.sql"; sql_archive = sql_file.with_suffix(".sql.gz")
    remote_gz, remote_csv, container_csv = f"/root/{archive.name}", f"/root/{stage.name}", f"/tmp/{stage.name}"
    remote_sql_gz, remote_sql = f"/root/{sql_archive.name}", f"/root/{sql_file.name}"
    defs = ",".join("(" + ",".join(quote(value) for value in row) + ")" for row in definitions)
    sql = f"""\\set ON_ERROR_STOP on
BEGIN;
SELECT pg_advisory_xact_lock(82496692);
CREATE TEMP TABLE hvac_stage(language text,email text,name text,attribs text,country text);
\\copy hvac_stage(language,email,name,attribs,country) FROM '{container_csv}' WITH (FORMAT csv,HEADER true)
CREATE TEMP TABLE defs(language text,code text,list_name text,campaign_name text,subject text,body text);
INSERT INTO defs VALUES {defs};
DO $$ BEGIN
 IF (SELECT COUNT(*) FROM hvac_stage)<>{manifest['stage_rows']} THEN RAISE EXCEPTION 'Stage count mismatch'; END IF;
 IF (SELECT COUNT(*) FROM hvac_stage)<>(SELECT COUNT(DISTINCT lower(email)) FROM hvac_stage) THEN RAISE EXCEPTION 'Duplicate stage email'; END IF;
 IF (SELECT COUNT(DISTINCT language) FROM hvac_stage)<>(SELECT COUNT(*) FROM defs) THEN RAISE EXCEPTION 'Language mismatch'; END IF;
END $$;
INSERT INTO lists(uuid,name,type,optin,tags,description)
SELECT gen_random_uuid(),d.list_name,'private','single',ARRAY[]::varchar[],'Strict bounce-filtered HVAC audience grouped by language: '||d.language FROM defs d WHERE NOT EXISTS(SELECT 1 FROM lists l WHERE l.name=d.list_name);
CREATE TEMP TABLE target_lists AS SELECT l.id,l.name,d.language FROM lists l JOIN defs d ON d.list_name=l.name;
INSERT INTO subscribers(uuid,email,name,attribs,status)
SELECT gen_random_uuid(),lower(s.email),COALESCE(s.name,''),s.attribs::jsonb,'enabled' FROM hvac_stage s WHERE NOT EXISTS(SELECT 1 FROM subscribers x WHERE lower(x.email)=lower(s.email));
DELETE FROM subscriber_lists sl USING target_lists t
WHERE sl.list_id=t.id AND sl.status='confirmed' AND NOT EXISTS(SELECT 1 FROM hvac_stage h JOIN subscribers s ON lower(s.email)=lower(h.email) WHERE h.language=t.language AND s.id=sl.subscriber_id);
INSERT INTO subscriber_lists(subscriber_id,list_id,status)
SELECT s.id,t.id,'confirmed'::subscription_status FROM hvac_stage h JOIN subscribers s ON lower(s.email)=lower(h.email) JOIN target_lists t ON t.language=h.language
WHERE s.status='enabled' AND NOT EXISTS(SELECT 1 FROM bounces b WHERE b.subscriber_id=s.id) AND NOT EXISTS(SELECT 1 FROM subscriber_lists u WHERE u.subscriber_id=s.id AND u.status='unsubscribed')
ON CONFLICT(subscriber_id,list_id) DO UPDATE SET status='confirmed'::subscription_status;
INSERT INTO campaigns(uuid,name,subject,from_email,body,content_type,status,type,messenger,template_id)
SELECT gen_random_uuid(),d.campaign_name,d.subject,{quote(FROM_EMAIL)},d.body,'html','draft','regular','email',1 FROM defs d WHERE NOT EXISTS(SELECT 1 FROM campaigns c WHERE c.name=d.campaign_name);
DO $$ BEGIN IF EXISTS(SELECT 1 FROM campaigns c JOIN defs d ON d.campaign_name=c.name WHERE c.status<>'draft' OR c.sent<>0) THEN RAISE EXCEPTION 'Campaign collision with non-draft'; END IF; END $$;
UPDATE campaigns c SET subject=d.subject,from_email={quote(FROM_EMAIL)},body=d.body,content_type='html',messenger='email',template_id=1,updated_at=now() FROM defs d WHERE c.name=d.campaign_name AND c.status='draft' AND c.sent=0;
DELETE FROM campaign_lists cl USING campaigns c,defs d WHERE cl.campaign_id=c.id AND c.name=d.campaign_name;
INSERT INTO campaign_lists(campaign_id,list_id,list_name) SELECT c.id,t.id,t.name FROM campaigns c JOIN defs d ON d.campaign_name=c.name JOIN target_lists t ON t.language=d.language;
WITH stats AS (SELECT c.id,COUNT(DISTINCT s.id)::integer n,COALESCE(MAX(s.id),0)::integer max_id FROM campaigns c JOIN defs d ON d.campaign_name=c.name JOIN target_lists t ON t.language=d.language LEFT JOIN subscriber_lists sl ON sl.list_id=t.id AND sl.status='confirmed' LEFT JOIN subscribers s ON s.id=sl.subscriber_id AND s.status='enabled' AND NOT EXISTS(SELECT 1 FROM bounces b WHERE b.subscriber_id=s.id) GROUP BY c.id) UPDATE campaigns c SET to_send=stats.n,max_subscriber_id=stats.max_id,last_subscriber_id=0 FROM stats WHERE c.id=stats.id;
SELECT json_build_object(
 'stage_rows',(SELECT COUNT(*) FROM hvac_stage),'languages',(SELECT COUNT(*) FROM defs),'target_lists',(SELECT COUNT(*) FROM target_lists),
 'confirmed_members',(SELECT COUNT(*) FROM subscriber_lists sl JOIN target_lists t ON t.id=sl.list_id WHERE sl.status='confirmed'),
 'excluded_by_production_state',{manifest['stage_rows']}-(SELECT COUNT(*) FROM subscriber_lists sl JOIN target_lists t ON t.id=sl.list_id WHERE sl.status='confirmed'),
 'unsafe',(SELECT COUNT(*) FROM subscriber_lists sl JOIN target_lists t ON t.id=sl.list_id JOIN subscribers s ON s.id=sl.subscriber_id WHERE sl.status='confirmed' AND (s.status<>'enabled' OR EXISTS(SELECT 1 FROM bounces b WHERE b.subscriber_id=s.id))),
 'cross_language_overlap',(SELECT COUNT(*) FROM (SELECT sl.subscriber_id FROM subscriber_lists sl JOIN target_lists t ON t.id=sl.list_id WHERE sl.status='confirmed' GROUP BY sl.subscriber_id HAVING COUNT(*)>1)x),
 'campaigns_not_draft',(SELECT COUNT(*) FROM campaigns c JOIN defs d ON d.campaign_name=c.name WHERE c.status<>'draft' OR c.sent<>0),
 'bad_links',(SELECT COUNT(*) FROM campaigns c JOIN defs d ON d.campaign_name=c.name WHERE position('consthruads.com/?lang='||d.code in c.body)=0),
 'bad_senders',(SELECT COUNT(*) FROM campaigns c JOIN defs d ON d.campaign_name=c.name WHERE c.from_email<>{quote(FROM_EMAIL)}),
 'campaigns',(SELECT json_agg(json_build_object('id',c.id,'language',d.language,'targets',c.to_send,'status',c.status,'sent',c.sent) ORDER BY d.language) FROM campaigns c JOIN defs d ON d.campaign_name=c.name));
COMMIT;"""
    try:
        stamp = ssh("date -u +%Y%m%d_%H%M%S").strip(); backup = f"/root/listmonk-backups/pre_air_condition_campaigns_{stamp}.dump"
        ssh(f'''mkdir -p /root/listmonk-backups && docker exec listmonk-production-postgres-1 sh -lc 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc' > {backup} && test -s {backup}''')
        sql_file.write_text(sql, encoding="utf-8")
        with sql_file.open("rb") as source, gzip.open(sql_archive, "wb", compresslevel=6) as target:
            target.write(source.read())
        subprocess.run(["scp","-q",str(archive),str(sql_archive),f"{SSH_TARGET}:/root/"],check=True,timeout=300)
        ssh(f"gzip -dc {remote_gz} > {remote_csv} && docker cp {remote_csv} listmonk-production-postgres-1:{container_csv}")
        output = ssh(f'''gzip -dc {remote_sql_gz} > {remote_sql} && docker exec -i listmonk-production-postgres-1 sh -lc 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -At' < {remote_sql}''')
        rows = [line for line in output.splitlines() if line.startswith("{")]
        if not rows: raise RuntimeError(f"No JSON result: {output[-2000:]}")
        result = json.loads(rows[-1]); result.update({"backup": backup,"backup_bytes": int(ssh(f"stat -c %s {backup}").strip()),"manifest": manifest})
        if any(result[name] for name in ("unsafe","cross_language_overlap","campaigns_not_draft","bad_links","bad_senders")):
            raise RuntimeError(f"Postcondition failed: {result}")
        print(json.dumps(result,ensure_ascii=False,indent=2))
    finally:
        try: ssh(f"docker exec listmonk-production-postgres-1 rm -f {container_csv}; rm -f {remote_gz} {remote_csv} {remote_sql_gz} {remote_sql}",60)
        except Exception: pass
        stage.unlink(missing_ok=True); archive.unlink(missing_ok=True); sql_file.unlink(missing_ok=True); sql_archive.unlink(missing_ok=True)


if __name__ == "__main__": main()
