#!/usr/bin/env python3
"""Create a strict, auditable local interior-design email collection."""

from __future__ import annotations

import csv
import json
import math
import re
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

import dns.exception
import dns.resolver
from email_validator import EmailNotValidError, validate_email


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "leads-big-scrap-interior-design-copy"
OUTPUT = ROOT / "clean_emails_interior_design"
BOUNCES = ROOT / "listmonk_emails" / ".strict_vps_bounces.csv"
DOMAIN_EVIDENCE = ROOT / "listmonk_emails" / ".strict_vps_domains.csv"
CHECKPOINT = ROOT / "listmonk_emails" / ".interior_design_dns_checkpoint.csv"

EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+$")
ASSET_RE = re.compile(r"\.(?:png|jpe?g|gif|svg|webp|css|js|ico|woff2?|ttf|pdf|xml|php|html?)$", re.I)
PLACEHOLDER_RE = re.compile(
    r"(?:^|[._-])(?:test|testing|teste|prueba|example|exemple|esempio|exemplo|sample|dummy|fake|falso|invalid|asdf|qwerty|unknown|null|none|spam|demo|domain|mailbox|fulano|sicrano|beltrano|mario[._-]?rossi|john[._-]?doe|jane[._-]?doe)(?:$|[._-])",
    re.I,
)
PHONEISH_RE = re.compile(r"(?:\d[\s_.()-]*){5,}")
HEX_RE = re.compile(r"^[0-9a-f]{20,}$", re.I)
UUID_RE = re.compile(r"^[0-9a-f]{8}-?[0-9a-f]{4}-?[0-9a-f]{4}-?[0-9a-f]{4}-?[0-9a-f]{12}$", re.I)
ENCODED_RE = re.compile(r"(?:u00[0-9a-f]{2}|%[0-9a-f]{2}|x[0-9a-f]{2})", re.I)
REPEATED_RE = re.compile(r"(.)\1{4,}", re.I)

DISPOSABLE = {
    "10minutemail.com", "guerrillamail.com", "mailinator.com", "tempmail.com",
    "temp-mail.org", "yopmail.com", "throwawaymail.com", "trashmail.com",
    "maildrop.cc", "sharklasers.com", "getnada.com", "dispostable.com",
}
BAD_DOMAINS = {
    "example.com", "example.org", "example.net", "localhost", "email.com",
    "correo.com", "mail.com.br", "yourmail.com", "website.com", "mysite.com",
}
ROLE_LOCALS = {
    "admin", "administracao", "administracion", "amministrazione", "atendimento",
    "billing", "booking", "careers", "commercial", "comercial", "compras",
    "contact", "contacto", "contato", "contatti", "contabilidad", "contabilidade",
    "customer", "customerservice", "direcao", "direccion", "direzione", "email",
    "enquiries", "finance", "geral", "hello", "help", "hr", "info", "informacion",
    "informazioni", "jobs", "mail", "marketing", "office", "orders", "postmaster",
    "privacy", "recepcao", "reception", "reservas", "sales", "segreteria",
    "service", "servicio", "servicos", "shop", "soporte", "support", "suporte",
    "webmaster", "abuse", "root", "noreply", "no-reply", "donotreply",
    "do-not-reply", "mailer-daemon", "newsletter", "unsubscribe",
}
COMPACT_ROLE_LOCALS = {re.sub(r"[^a-z0-9]", "", value) for value in ROLE_LOCALS}
VALID_DNS = {"valid_mx"}
FINAL_DNS = VALID_DNS | {"dns_nxdomain", "dns_null_mx", "dns_no_mx"}


def normalize(raw: str) -> str:
    value = (raw or "").strip().lower().replace("\ufeff", "")
    while value.startswith("%20"):
        value = value[3:]
    return value.removeprefix("mailto:").strip(" \t\r\n,;:'\"<>[]()")


def entropy(value: str) -> float:
    counts = Counter(value)
    return -sum((n / len(value)) * math.log2(n / len(value)) for n in counts.values()) if value else 0.0


def load_bounce_evidence() -> tuple[set[str], set[str], dict[str, tuple[int, int]]]:
    with BOUNCES.open(encoding="utf-8-sig", newline="") as handle:
        known = {normalize(row.get("email", "")) for row in csv.DictReader(handle, delimiter="|") if row.get("email")}
    risky: set[str] = set()
    evidence: dict[str, tuple[int, int]] = {}
    with DOMAIN_EVIDENCE.open(encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle, delimiter="|"):
            domain = row["domain"].strip().lower()
            attempts, bounces = int(row["attempts"]), int(row["bounces"])
            evidence[domain] = (attempts, bounces)
            rate = bounces / attempts if attempts else 0
            if (attempts >= 3 and rate >= .20) or (attempts >= 10 and rate >= .15) or (attempts >= 25 and rate >= .10):
                risky.add(domain)
    return known, risky, evidence


def reject_reason(email: str, known: set[str], risky_domains: set[str]) -> str | None:
    if email in known:
        return "known_vps_bounce"
    if email.count("@") != 1 or not EMAIL_RE.fullmatch(email):
        return "invalid_syntax"
    try:
        validate_email(email, check_deliverability=False, allow_smtputf8=True)
    except EmailNotValidError:
        return "invalid_syntax"
    local, domain = email.rsplit("@", 1)
    compact = re.sub(r"[^a-z0-9]", "", local)
    if domain in BAD_DOMAINS or domain in DISPOSABLE or PLACEHOLDER_RE.search(domain):
        return "placeholder_or_disposable_domain"
    if domain in risky_domains:
        return "observed_high_bounce_domain"
    if local in ROLE_LOCALS or compact in COMPACT_ROLE_LOCALS:
        return "generic_or_technical_role"
    if PLACEHOLDER_RE.search(local):
        return "placeholder_local"
    if len(local) <= 4 or len(local) >= 40:
        return "implausible_local_length"
    if any(ch.isdigit() for ch in local):
        return "numeric_or_id_local"
    if any(ch in local for ch in "-_+"):
        return "risky_separator_or_alias"
    if PHONEISH_RE.search(local):
        return "phoneish_local"
    if ASSET_RE.search(email):
        return "asset_false_positive"
    if HEX_RE.fullmatch(compact) or UUID_RE.fullmatch(local) or ENCODED_RE.search(local):
        return "encoded_or_machine_token"
    if REPEATED_RE.search(compact):
        return "implausible_repetition"
    if len(compact) >= 20 and compact == local and entropy(compact) >= 3.6:
        return "random_high_entropy_token"
    return None


def load_dns_cache() -> dict[str, tuple[str, str]]:
    cache: dict[str, tuple[str, str]] = {}
    for path in (ROOT / "listmonk_emails").glob("clean_emails_*/domain_validation_cache.csv"):
        with path.open(encoding="utf-8-sig", newline="") as handle:
            for row in csv.DictReader(handle):
                domain = row.get("domain", "").strip().lower().rstrip(".")
                if domain:
                    cache[domain] = (row.get("status", ""), row.get("detail", ""))
    if CHECKPOINT.exists():
        with CHECKPOINT.open(encoding="utf-8-sig", newline="") as handle:
            for row in csv.DictReader(handle):
                cache[row["domain"].strip().lower()] = (row["status"], row.get("detail", ""))
    return cache


def check_mx(domain: str) -> tuple[str, str]:
    resolver = dns.resolver.Resolver(configure=True)
    resolver.timeout, resolver.lifetime = 1.5, 2.5
    try:
        answers = resolver.resolve(domain, "MX")
        if any(int(record.preference) == 0 and str(record.exchange) == "." for record in answers):
            return "dns_null_mx", "."
        return "valid_mx", ",".join(sorted(str(record.exchange).rstrip(".") for record in answers))
    except dns.resolver.NXDOMAIN:
        return "dns_nxdomain", "NXDOMAIN"
    except dns.resolver.NoAnswer:
        return "dns_no_mx", "NoAnswer"
    except (dns.resolver.NoNameservers, dns.exception.Timeout) as exc:
        return "dns_inconclusive", type(exc).__name__


def write_checkpoint(cache: dict[str, tuple[str, str]], domains: set[str]) -> None:
    with CHECKPOINT.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["domain", "status", "detail"])
        writer.writerows((domain, *cache[domain]) for domain in sorted(domains) if domain in cache)


def main() -> None:
    started = time.time()
    if OUTPUT.exists():
        raise SystemExit(f"Refusing to overwrite existing output: {OUTPUT}")
    for required in (SOURCE, BOUNCES, DOMAIN_EVIDENCE):
        if not required.exists():
            raise SystemExit(f"Missing required input: {required}")

    known, risky_domains, _ = load_bounce_evidence()
    candidates: dict[str, dict[str, dict[str, str]]] = {}
    raw_counts, reasons = Counter(), Counter()
    removed: list[tuple[str, str, str]] = []
    domains: set[str] = set()
    country_dirs = sorted(path for path in SOURCE.iterdir() if path.is_dir() and (path / "lead_emails.csv").exists())

    for country_dir in country_dirs:
        country = country_dir.name
        candidates[country] = {}
        with (country_dir / "lead_emails.csv").open(encoding="utf-8-sig", newline="") as handle:
            for row in csv.DictReader(handle):
                for token in re.split(r"[;,\s]+", row.get("EMAIL", "") or ""):
                    email = normalize(token)
                    if not email:
                        continue
                    raw_counts[country] += 1
                    reason = reject_reason(email, known, risky_domains)
                    if reason:
                        reasons[reason] += 1
                        removed.append((country, email, reason))
                        continue
                    if email in candidates[country]:
                        reasons["duplicate_within_country"] += 1
                        removed.append((country, email, "duplicate_within_country"))
                        continue
                    candidates[country][email] = row
                    domains.add(email.rsplit("@", 1)[1])

    cache = load_dns_cache()
    to_check = sorted(domain for domain in domains if cache.get(domain, ("", ""))[0] not in FINAL_DNS)
    with ThreadPoolExecutor(max_workers=80) as pool:
        futures = {pool.submit(check_mx, domain): domain for domain in to_check}
        for index, future in enumerate(as_completed(futures), 1):
            domain = futures[future]
            try:
                cache[domain] = future.result()
            except Exception as exc:
                cache[domain] = ("dns_inconclusive", type(exc).__name__)
            if index % 250 == 0:
                write_checkpoint(cache, domains)
    write_checkpoint(cache, domains)

    global_seen: set[str] = set()
    kept: dict[str, list[tuple[str, dict[str, str]]]] = {}
    for country in sorted(candidates):
        kept[country] = []
        for email, row in sorted(candidates[country].items()):
            status = cache.get(email.rsplit("@", 1)[1], ("dns_unknown", ""))[0]
            if status not in VALID_DNS:
                reason = status or "dns_unknown"
                reasons[reason] += 1
                removed.append((country, email, reason))
                continue
            if email in global_seen:
                reasons["duplicate_across_countries"] += 1
                removed.append((country, email, "duplicate_across_countries"))
                continue
            global_seen.add(email)
            kept[country].append((email, row))

    OUTPUT.mkdir()
    summary_rows = []
    for rank, country in enumerate(sorted(kept, key=lambda name: (-len(kept[name]), name.casefold())), 1):
        records = kept[country]
        folder = OUTPUT / f"{rank:03d} - {country} ({len(records)})"
        folder.mkdir()
        (folder / f"emails({len(records)}).txt").write_text("\n".join(email for email, _ in records) + ("\n" if records else ""), encoding="utf-8")
        with (folder / "listmonk_subscribers.csv").open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=["email", "name", "attributes"], quoting=csv.QUOTE_ALL)
            writer.writeheader()
            for email, row in records:
                attributes = {
                    "telephone": row.get("TELEPHONE", ""), "website": row.get("WEBSITE / INSTAGRAM / FACEBOOK", ""),
                    "city": row.get("CITY", ""), "country": row.get("COUNTRY", country), "sector": "interior_design",
                }
                writer.writerow({"email": email, "name": row.get("NAME", ""), "attributes": json.dumps(attributes, ensure_ascii=False, separators=(",", ":"))})
        summary_rows.append({"rank": rank, "country": country, "input_nonempty": raw_counts[country], "kept": len(records), "removed": raw_counts[country] - len(records)})

    with (OUTPUT / "country_summary.csv").open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(summary_rows[0]))
        writer.writeheader(); writer.writerows(summary_rows)
    with (OUTPUT / "domain_validation_cache.csv").open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.writer(handle); writer.writerow(["domain", "status", "detail"])
        writer.writerows((domain, *cache.get(domain, ("dns_unknown", ""))) for domain in sorted(domains))
    with (OUTPUT / "removed_email_audit.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle); writer.writerow(["country", "email", "reason"]); writer.writerows(removed)

    total_input, total_kept = sum(raw_counts.values()), len(global_seen)
    summary = {
        "generated_utc": datetime.now(timezone.utc).isoformat(), "source": SOURCE.name,
        "countries": len(country_dirs), "input_nonempty_email_entries": total_input,
        "kept_unique_emails": total_kept, "removed_entries": total_input - total_kept,
        "known_vps_bounces_loaded": len(known), "risky_domains_from_vps": len(risky_domains),
        "candidate_domains": len(domains), "dns_live_checks": len(to_check),
        "reason_counts": dict(reasons.most_common()), "processing_seconds": round(time.time() - started, 1),
    }
    (OUTPUT / "validation_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    report = ["# Interior design email cleanup", "", "Strict local-only filtering based on historical production bounce evidence and confirmed MX routing.", "", f"- Input email entries: **{total_input:,}**", f"- Kept unique emails: **{total_kept:,}**", f"- Removed: **{total_input-total_kept:,}**", f"- Countries: **{len(country_dirs)}**", f"- Known VPS bounces loaded: **{len(known):,}**", f"- Empirically risky domains: **{len(risky_domains):,}**", "", "## Removal signals", "", "| Signal | Matches |", "|---|---:|"]
    report += [f"| {reason} | {count:,} |" for reason, count in reasons.most_common()]
    report += ["", "Only confirmed MX domains were retained. Individual mailbox existence cannot be guaranteed without recipient verification.", ""]
    (OUTPUT / "VALIDATION_REPORT.md").write_text("\n".join(report), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
