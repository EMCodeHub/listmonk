#!/usr/bin/env python3
"""Idempotently create country/niche lists and import Listmonk CSV files."""

import argparse
import http.cookiejar
import json
import os
import re
import subprocess
import time
import urllib.parse
import urllib.request
import uuid
from pathlib import Path


BASE_URL = os.environ.get("LISTMONK_BASE_URL", "http://localhost").rstrip("/")
SSH_TARGET = os.environ.get("LISTMONK_SSH_TARGET", "")
CREDENTIALS_FILE = os.environ.get(
    "LISTMONK_CREDENTIALS_FILE", "/root/listmonk-admin-password.txt"
)
NICHE_LABELS = {
    "clean_emails_dermatologist": "dermatologist",
    "clean_emails_odontologist": "odontologist",
    "clean_emails_real_estate": "real estate",
    "clean_emails_renovation": "renovation companies",
}


def get_credentials():
    if not SSH_TARGET:
        raise RuntimeError("LISTMONK_SSH_TARGET is required for remote imports")
    proc = subprocess.run(
        ["ssh", "-o", "BatchMode=yes", SSH_TARGET, "cat", CREDENTIALS_FILE],
        capture_output=True, text=True, check=True,
    )
    return dict(line.split("=", 1) for line in proc.stdout.splitlines() if "=" in line)


def login():
    creds = get_credentials()
    jar = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
    url = BASE_URL + "/admin/login"
    page = opener.open(url, timeout=30).read().decode()
    nonce = re.search(r'name="nonce" value="([^"]+)"', page).group(1)
    body = urllib.parse.urlencode({
        "nonce": nonce, "username": creds["username"],
        "password": creds["password"], "next": "/admin",
    }).encode()
    response = opener.open(url, body, timeout=30)
    if response.geturl().rstrip("/").endswith("/admin/login"):
        raise RuntimeError("Listmonk login failed")
    return opener


def api_json(opener, method, path, payload=None):
    data = None if payload is None else json.dumps(payload).encode()
    request = urllib.request.Request(BASE_URL + path, data=data, method=method)
    if data is not None:
        request.add_header("Content-Type", "application/json")
    with opener.open(request, timeout=60) as response:
        return json.load(response)


def multipart_import(opener, csv_path, list_id):
    boundary = "----listmonk-" + uuid.uuid4().hex
    params = json.dumps({
        "mode": "subscribe", "subscription_status": "confirmed",
        "overwrite": False, "delim": ",", "lists": [list_id],
    })
    chunks = []
    for name, value in (("params", params),):
        chunks.append(f"--{boundary}\r\nContent-Disposition: form-data; name=\"{name}\"\r\n\r\n{value}\r\n".encode())
    chunks.append(
        f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"listmonk_subscribers.csv\"\r\nContent-Type: text/csv\r\n\r\n".encode()
    )
    chunks.append(csv_path.read_bytes())
    chunks.append(f"\r\n--{boundary}--\r\n".encode())
    request = urllib.request.Request(
        BASE_URL + "/api/import/subscribers", data=b"".join(chunks), method="POST",
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
    )
    with opener.open(request, timeout=180) as response:
        json.load(response)

    while True:
        stats = api_json(opener, "GET", "/api/import/subscribers")["data"]
        if stats["status"] == "finished":
            return stats
        if stats["status"] == "failed":
            logs = api_json(opener, "GET", "/api/import/subscribers/logs")["data"]
            raise RuntimeError(f"Import failed for {csv_path}: {logs}")
        time.sleep(0.5)


def build_manifest(root):
    manifest = []
    for folder, niche in NICHE_LABELS.items():
        for csv_path in sorted((root / folder).glob("*/listmonk_subscribers.csv")):
            match = re.match(r"^\d+ - (.+?) \((\d+)\)$", csv_path.parent.name)
            if not match:
                raise ValueError(f"Unexpected country folder: {csv_path.parent}")
            country, expected = match.group(1), int(match.group(2))
            display_country = "USA" if country == "United States" else country
            manifest.append({
                "name": f"{display_country} {niche} lead generation",
                "country": country, "niche": niche, "expected": expected,
                "csv": csv_path,
            })
    names = [item["name"] for item in manifest]
    if len(names) != 476 or len(set(names)) != 476:
        raise RuntimeError(f"Manifest invariant failed: {len(names)} entries")
    return manifest


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--checkpoint", type=Path, required=True)
    args = parser.parse_args()
    manifest = build_manifest(args.root)
    if not args.apply:
        print(json.dumps({"lists": len(manifest), "rows": sum(x["expected"] for x in manifest)}, indent=2))
        return

    checkpoint = set()
    if args.checkpoint.exists():
        checkpoint = set(json.loads(args.checkpoint.read_text(encoding="utf-8")))
    opener = login()
    existing = api_json(opener, "GET", "/api/lists?per_page=all")["data"]["results"]
    lists_by_name = {item["name"]: item for item in existing}

    for index, item in enumerate(manifest, 1):
        name = item["name"]
        if name in checkpoint:
            print(f"[{index}/476] checkpoint skip: {name}", flush=True)
            continue
        if name not in lists_by_name:
            created = api_json(opener, "POST", "/api/lists", {
                "name": name, "type": "private", "optin": "single",
                "tags": [], "description": "",
            })["data"]
            lists_by_name[name] = created
            print(f"[{index}/476] created list {created['id']}: {name}", flush=True)
        else:
            print(f"[{index}/476] using list {lists_by_name[name]['id']}: {name}", flush=True)

        stats = multipart_import(opener, item["csv"], lists_by_name[name]["id"])
        checkpoint.add(name)
        args.checkpoint.write_text(json.dumps(sorted(checkpoint), indent=2), encoding="utf-8")
        print(f"[{index}/476] imported {stats['imported']}/{stats['total']}: {name}", flush=True)


if __name__ == "__main__":
    main()
