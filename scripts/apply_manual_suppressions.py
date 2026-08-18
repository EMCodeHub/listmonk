"""Remove manually suppressed recipients from active local Listmonk datasets."""
from __future__ import annotations

import csv
import json
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SUPPRESSIONS = ROOT / "listmonk_emails/manual_suppressions.json"
ACTIVE_ROOTS = [
    ROOT / "clean_emails_interior_design",
    ROOT / "clean_emails_real_estate",
    *(ROOT / "listmonk_emails").glob("clean_emails_*"),
]


def main() -> None:
    data = json.loads(SUPPRESSIONS.read_text(encoding="utf-8"))
    blocked = {email.lower(): reason for email, reason in data["emails"].items()}
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup_root = ROOT / "backups" / f"manual_suppressions_{stamp}"
    changes = []
    folders = set()
    for active_root in ACTIVE_ROOTS:
        if not active_root.exists():
            continue
        for path in active_root.rglob("*"):
            if not path.is_file() or not (path.name == "listmonk_subscribers.csv" or re.fullmatch(r"emails\(\d+\)\.txt", path.name)):
                continue
            if path.name == "listmonk_subscribers.csv":
                with path.open(encoding="utf-8-sig", newline="") as handle:
                    reader = csv.DictReader(handle); fields = reader.fieldnames; rows = list(reader)
                if not fields or "email" not in fields:
                    raise RuntimeError(f"Missing email column: {path}")
                removed = [row for row in rows if row["email"].strip().lower() in blocked]
                kept = [row for row in rows if row["email"].strip().lower() not in blocked]
                kind = "csv"
            else:
                rows = [line.strip() for line in path.read_text(encoding="utf-8-sig").splitlines() if line.strip()]
                removed = [email for email in rows if email.lower() in blocked]
                kept = [email for email in rows if email.lower() not in blocked]
                kind = "txt"
            if not removed:
                continue
            backup = backup_root / path.relative_to(ROOT)
            backup.parent.mkdir(parents=True, exist_ok=True); shutil.copy2(path, backup)
            if kind == "csv":
                with path.open("w", encoding="utf-8", newline="") as handle:
                    writer = csv.DictWriter(handle, fieldnames=fields, quoting=csv.QUOTE_ALL); writer.writeheader(); writer.writerows(kept)
                emails = [row["email"].strip().lower() for row in removed]
            else:
                path.write_text("\n".join(kept) + ("\n" if kept else ""), encoding="utf-8")
                emails = [email.lower() for email in removed]
            changes.append({"file": str(path.relative_to(ROOT)), "removed": emails, "remaining": len(kept)})
            folders.add(path.parent)
    renames = []
    for folder in sorted(folders, key=lambda p: len(p.parts), reverse=True):
        csv_path = folder / "listmonk_subscribers.csv"
        if csv_path.exists():
            with csv_path.open(encoding="utf-8-sig", newline="") as handle: count = sum(1 for _ in csv.DictReader(handle))
        else:
            txt = next(folder.glob("emails(*).txt")); count = sum(1 for line in txt.read_text(encoding="utf-8-sig").splitlines() if line.strip())
        for txt in list(folder.glob("emails(*).txt")):
            target = folder / f"emails({count}).txt"
            if txt != target: txt.rename(target); renames.append([str(txt.relative_to(ROOT)), str(target.relative_to(ROOT))])
        match = re.match(r"^(\d+ - .+?) \(\d+\)$", folder.name)
        if match:
            target_folder = folder.with_name(f"{match.group(1)} ({count})")
            if folder != target_folder: folder.rename(target_folder); renames.append([str(folder.relative_to(ROOT)), str(target_folder.relative_to(ROOT))])
    report = {"generated_at": datetime.now(timezone.utc).isoformat(), "suppressed": len(blocked), "files_changed": len(changes), "removals": sum(len(x["removed"]) for x in changes), "changes": changes, "renames": renames, "backup": str(backup_root.relative_to(ROOT))}
    backup_root.mkdir(parents=True, exist_ok=True)
    (backup_root / "audit.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({key: report[key] for key in ("suppressed", "files_changed", "removals", "backup")}, ensure_ascii=False))


if __name__ == "__main__": main()
