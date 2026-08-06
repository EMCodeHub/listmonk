import base64
import json
import os
import secrets
import sys
import urllib.request

old_password = sys.stdin.readline().rstrip("\r\n")
if not old_password:
    raise SystemExit("missing current password")

base = "http://127.0.0.1:9000/api/users/1"

def call(password, method="GET", payload=None):
    data = None if payload is None else json.dumps(payload).encode()
    request = urllib.request.Request(base, data=data, method=method)
    request.add_header("Authorization", "Basic " + base64.b64encode(f"admin:{password}".encode()).decode())
    if data is not None:
        request.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(request, timeout=15) as response:
        return json.load(response)

user = call(old_password)["data"]
new_password = secrets.token_urlsafe(36)
user["password"] = new_password
user["password_login"] = True
call(old_password, "PUT", user)
call(new_password)

path = "/root/listmonk-admin-password.txt"
fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
with os.fdopen(fd, "w") as handle:
    handle.write("username=admin\npassword=" + new_password + "\n")
os.chmod(path, 0o600)
print("admin_password_rotated=true login_verified=true credential_file=/root/listmonk-admin-password.txt mode=600")
