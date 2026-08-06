#!/bin/sh
set -eu
site=/etc/nginx/sites-available/mail.consthruads.com
backup="${site}.pre-hardening-$(date -u +%Y%m%dT%H%M%SZ)"
cp -a "$site" "$backup"
python3 - "$site" <<'PY'
from pathlib import Path
import sys
p = Path(sys.argv[1])
s = p.read_text()
s = s.replace('    ssl_stapling on; # managed by Certbot', '    ssl_stapling off; # certificate has no OCSP responder')
s = s.replace('    ssl_stapling_verify on; # managed by Certbot', '    ssl_stapling_verify off; # certificate has no OCSP responder')
marker = '    add_header Strict-Transport-Security "max-age=31536000" always; # managed by Certbot\n'
headers = marker + '''    add_header X-Content-Type-Options "nosniff" always;
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header Referrer-Policy "strict-origin-when-cross-origin" always;
    add_header Permissions-Policy "camera=(), microphone=(), geolocation=()" always;
'''
if 'X-Content-Type-Options' not in s:
    s = s.replace(marker, headers)
p.write_text(s)
PY
if ! nginx -t; then
  cp -a "$backup" "$site"
  nginx -t
  exit 1
fi
systemctl reload nginx
curl -sSI https://mail.consthruads.com/ | grep -Ei 'HTTP/|strict-transport|x-content|x-frame|referrer|permissions'
