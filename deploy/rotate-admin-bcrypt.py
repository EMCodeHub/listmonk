import http.cookiejar
import os
import secrets
import subprocess
import urllib.parse
import urllib.request
cwd = "/opt/listmonk"
query = ["docker", "compose", "exec", "-T", "postgres", "psql", "-U", "consthruads", "-d", "listmonk", "-Atqc"]
old_hash = subprocess.run(query + ["select password from users where username='admin'"], cwd=cwd, capture_output=True, text=True, check=True).stdout.strip()
new_password = secrets.token_urlsafe(36)

def sql(statement):
    subprocess.run(query + [statement], cwd=cwd, capture_output=True, text=True, check=True)

safe_password = new_password.replace("'", "''")
sql(f"update users set password=crypt('{safe_password}', gen_salt('bf')), password_login=true, updated_at=now() where username='admin'")
try:
    jar = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
    login_page = opener.open("http://127.0.0.1:9000/admin/login", timeout=15).read().decode()
    nonce_marker = 'name="nonce" value="'
    nonce = login_page.split(nonce_marker, 1)[1].split('"', 1)[0]
    body = urllib.parse.urlencode({"nonce": nonce, "username": "admin", "password": new_password, "next": "/admin"}).encode()
    response = opener.open("http://127.0.0.1:9000/admin/login", body, timeout=15)
    if response.geturl().rstrip("/").endswith("/admin/login") or not list(jar):
        raise RuntimeError("login verification failed")
except Exception:
    safe_old = old_hash.replace("'", "''")
    sql(f"update users set password='{safe_old}', updated_at=now() where username='admin'")
    raise

path = "/root/listmonk-admin-password.txt"
fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
with os.fdopen(fd, "w") as handle:
    handle.write("username=admin\npassword=" + new_password + "\n")
os.chmod(path, 0o600)
print("admin_password_rotated=true login_verified=true credential_file=/root/listmonk-admin-password.txt mode=600")
