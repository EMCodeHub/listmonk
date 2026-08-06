import json
import smtplib
import ssl
import subprocess

raw = subprocess.run(
    ["docker", "compose", "exec", "-T", "postgres", "psql", "-U", "consthruads", "-d", "listmonk", "-Atqc", "select value->0 from settings where key='smtp'"],
    cwd="/opt/listmonk", capture_output=True, text=True, check=True,
).stdout.strip()
smtp = json.loads(raw)

with smtplib.SMTP(smtp["host"], int(smtp["port"]), timeout=20) as client:
    client.ehlo()
    if not client.has_extn("starttls"):
        raise SystemExit("STARTTLS not advertised")
    client.starttls(context=ssl.create_default_context())
    client.ehlo()
    client.login(smtp["username"], smtp["password"])
    code, response = client.mail("noreply@consthruads.com")
    if code >= 400:
        raise SystemExit(f"SES rejected sender identity: SMTP {code}")
    client.rset()
print("auth=ok starttls=ok sender_noreply_consthruads=accepted no_message_sent=true")
