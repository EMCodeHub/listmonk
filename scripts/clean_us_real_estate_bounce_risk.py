#!/usr/bin/env python3
"""Aggressively remove high-risk bounce candidates from the US real-estate list.

The rules are deliberately evidence-led: known campaign bounces, morphology with
high observed bounce lift, one empirically high-risk domain, placeholder data,
and domains whose prior DNS validation did not confirm an MX record.
"""

from __future__ import annotations

import csv
import json
import re
import shutil
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "listmonk_emails" / "clean_emails_real_estate" / "001 - United States (57670)"
EMAILS_FILE = DATA_DIR / "emails(57670).txt"
SUBSCRIBERS_FILE = DATA_DIR / "listmonk_subscribers.csv"
BOUNCES_FILE = ROOT / "bounces_real_estate_usa.csv"
DNS_CACHE_FILE = ROOT / "listmonk_emails" / "clean_emails_real_estate" / "domain_validation_cache.csv"
AUDIT_FILE = DATA_DIR / "removed_bounce_risk.csv"
SUMMARY_FILE = DATA_DIR / "bounce_risk_cleanup_summary.json"
REPORT_FILE = DATA_DIR / "BOUNCE_RISK_CLEANUP_REPORT.md"
EMAILS_BACKUP = DATA_DIR / "emails.before_bounce_risk_cleanup.57670.txt"
SUBSCRIBERS_BACKUP = DATA_DIR / "listmonk_subscribers.before_bounce_risk_cleanup.csv"

PLACEHOLDER_DOMAINS = {
    "correo.com", "email.com", "example.com", "info.com", "mysite.com",
    "webdev.com", "website.com", "yourmail.com",
}
HIGH_RISK_DOMAINS = {"loanfactory.com"}
PHONEISH = re.compile(r"[0-9]{3,}[-.]?[0-9]{3,}")
TEST_TOKEN = re.compile(r"(^|[._-])(test|testing|example|sample|dummy|fake)([._-]|$)")
HEX_TOKEN = re.compile(r"[0-9a-f]{20,}")
EMAIL_SYNTAX = re.compile(r"^[a-z0-9.!#$%&'*+/=?^_`{|}~-]+@[a-z0-9.-]+\.[a-z]{2,}$")


def load_bounces() -> dict[str, str]:
    with BOUNCES_FILE.open(encoding="utf-8-sig", newline="") as handle:
        return {
            row["email"].strip().lower(): row["type"].strip().lower()
            for row in csv.DictReader(handle)
        }


def load_dns_status() -> dict[str, str]:
    with DNS_CACHE_FILE.open(encoding="utf-8-sig", newline="") as handle:
        return {
            row["domain"].strip().lower(): row["status"].strip().lower()
            for row in csv.DictReader(handle)
        }


def classify(email: str, bounces: dict[str, str], dns: dict[str, str]) -> list[str]:
    reasons: list[str] = []
    if email in bounces:
        reasons.append(f"known_{bounces[email]}_bounce")
    if not EMAIL_SYNTAX.fullmatch(email) or email.count("@") != 1:
        reasons.append("invalid_syntax")
        return reasons

    local, domain = email.rsplit("@", 1)
    digits = sum(ch.isdigit() for ch in local)
    if len(local) == 1:
        reasons.append("single_character_local")
    if re.match(r"^\d{3,}", local):
        reasons.append("numeric_prefix")
    if digits >= 7:
        reasons.append("digit_heavy_local")
    if PHONEISH.search(local):
        reasons.append("phone_or_id_contamination")
    if HEX_TOKEN.fullmatch(local):
        reasons.append("machine_generated_token")
    if TEST_TOKEN.search(local):
        reasons.append("test_or_placeholder_local")
    if domain in PLACEHOLDER_DOMAINS:
        reasons.append("placeholder_domain")
    if domain in HIGH_RISK_DOMAINS:
        reasons.append("observed_high_bounce_domain")
    if dns.get(domain) != "valid_mx":
        reasons.append("mx_not_confirmed")
    return reasons


def main() -> None:
    required = [EMAILS_FILE, SUBSCRIBERS_FILE, BOUNCES_FILE, DNS_CACHE_FILE]
    missing = [str(path) for path in required if not path.exists()]
    if missing:
        raise SystemExit(f"Missing required files: {missing}")

    bounces = load_bounces()
    dns = load_dns_status()
    emails = [line.strip().lower() for line in EMAILS_FILE.read_text(encoding="utf-8-sig").splitlines() if line.strip()]
    if len(emails) != 57670:
        raise SystemExit(f"Safety check failed: expected 57670 emails, found {len(emails)}")
    if len(set(emails)) != len(emails):
        raise SystemExit("Safety check failed: source email list contains duplicates")

    decisions = {email: classify(email, bounces, dns) for email in emails}
    removed = {email: reasons for email, reasons in decisions.items() if reasons}
    kept = [email for email in emails if email not in removed]

    with SUBSCRIBERS_FILE.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        fieldnames = reader.fieldnames
        subscriber_rows = list(reader)
    if not fieldnames or "email" not in fieldnames:
        raise SystemExit("Safety check failed: subscriber CSV has no email column")
    csv_emails = [row["email"].strip().lower() for row in subscriber_rows]
    if set(csv_emails) != set(emails):
        raise SystemExit("Safety check failed: TXT and subscriber CSV email sets differ")
    kept_rows = [row for row in subscriber_rows if row["email"].strip().lower() not in removed]

    if not EMAILS_BACKUP.exists():
        shutil.copy2(EMAILS_FILE, EMAILS_BACKUP)
    if not SUBSCRIBERS_BACKUP.exists():
        shutil.copy2(SUBSCRIBERS_FILE, SUBSCRIBERS_BACKUP)

    EMAILS_FILE.write_text("\n".join(kept) + "\n", encoding="utf-8")
    with SUBSCRIBERS_FILE.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, quoting=csv.QUOTE_ALL)
        writer.writeheader()
        writer.writerows(kept_rows)

    with AUDIT_FILE.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["email", "reasons", "observed_bounce_type"])
        for email in emails:
            if email in removed:
                writer.writerow([email, ";".join(removed[email]), bounces.get(email, "")])

    reason_counts = Counter(reason for reasons in removed.values() for reason in reasons)
    summary = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_count": len(emails),
        "removed_count": len(removed),
        "remaining_count": len(kept),
        "known_bounces_in_source": len(set(emails) & set(bounces)),
        "known_bounces_remaining": len(set(kept) & set(bounces)),
        "hard_bounces_removed": sum(bounces.get(email) == "hard" for email in removed),
        "soft_bounces_removed": sum(bounces.get(email) == "soft" for email in removed),
        "reason_counts": dict(sorted(reason_counts.items())),
        "high_risk_domains": sorted(HIGH_RISK_DOMAINS),
    }
    SUMMARY_FILE.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")

    reason_rows = "\n".join(f"| `{reason}` | {count:,} |" for reason, count in reason_counts.most_common())
    REPORT_FILE.write_text(
        "# US real-estate bounce-risk cleanup\n\n"
        f"Generated: {summary['generated_at']}\n\n"
        f"- Before: **{len(emails):,}**\n"
        f"- Removed: **{len(removed):,}**\n"
        f"- Remaining: **{len(kept):,}**\n"
        f"- Known hard bounces removed: **{summary['hard_bounces_removed']:,}**\n"
        f"- Known soft bounces removed: **{summary['soft_bounces_removed']:,}**\n"
        f"- Known bounces remaining: **{summary['known_bounces_remaining']}**\n\n"
        "## Evidence and policy\n\n"
        "The campaign sample showed that consumer providers such as Gmail were not themselves a reliable failure signal, so provider-wide deletion was avoided. Single-character local parts and phone/ID-contaminated local parts showed strong bounce lift. `loanfactory.com` was removed because 2 of 4 observed attempted recipients bounced. Addresses without a previously confirmed MX result were removed under the requested zero-tolerance policy. Exact observed bounces and unmistakable test/placeholder records were also removed.\n\n"
        "Generic role inboxes (`info@`, `admin@`, etc.) were retained: their observed bounce rate was lower than the campaign average and therefore did not justify deletion.\n\n"
        "## Removal signals\n\n| Signal | Rows matched |\n|---|---:|\n"
        f"{reason_rows}\n\n"
        "The audit CSV may contain multiple signals per removed address, so signal counts do not sum to the unique removed total. Original files are preserved beside the cleaned files with the `before_bounce_risk_cleanup` name.\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
