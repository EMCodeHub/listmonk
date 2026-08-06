import csv
import json
import smtplib
import ssl
import subprocess
from pathlib import Path

credential_file = Path("/opt/listmonk/ses-credentials.csv")
with credential_file.open(newline="", encoding="utf-8-sig") as handle:
    row = next(csv.DictReader(handle))

username = row["SMTP user name"].strip()
password = row["SMTP password"].strip()
if not username or not password:
    raise SystemExit("SES credential CSV is incomplete")

host = "email-smtp.us-east-1.amazonaws.com"
port = 587

with smtplib.SMTP(host, port, timeout=20) as client:
    client.ehlo()
    client.starttls(context=ssl.create_default_context())
    client.ehlo()
    client.login(username, password)

mailer = [{
    "host": host,
    "port": port,
    "enabled": True,
    "password": password,
    "tls_type": "STARTTLS",
    "username": username,
    "max_conns": 10,
    "idle_timeout": "15s",
    "wait_timeout": "5s",
    "auth_protocol": "login",
    "email_headers": [],
    "hello_hostname": "mail.consthruads.com",
    "max_msg_retries": 2,
    "tls_skip_verify": False,
}]
payload = json.dumps(mailer, separators=(",", ":")).replace("'", "''")
sql = "UPDATE settings SET value = '%s'::jsonb WHERE key = 'smtp';\n" % payload
subprocess.run(
    ["docker", "compose", "exec", "-T", "postgres", "psql", "-U", "consthruads", "-d", "listmonk", "-v", "ON_ERROR_STOP=1"],
    cwd="/opt/listmonk",
    input=sql,
    text=True,
    check=True,
)
credential_file.unlink()
print("SES SMTP authentication and Listmonk configuration succeeded")
