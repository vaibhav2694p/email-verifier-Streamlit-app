from __future__ import annotations

import re
import ssl
import socket
from pathlib import Path
from urllib.parse import urlparse

import dns.resolver
import requests
from email_validator import validate_email as ev_validate, EmailSyntaxError

_EMAIL_PROVIDERS: dict[str, str] = {
    "gmail.com": "Google Workspace",
    "googlemail.com": "Google Workspace",
    "yahoo.com": "Yahoo Mail",
    "ymail.com": "Yahoo Mail",
    "outlook.com": "Microsoft 365",
    "hotmail.com": "Microsoft 365",
    "live.com": "Microsoft 365",
    "msn.com": "Microsoft 365",
    "aol.com": "AOL Mail",
    "icloud.com": "Apple iCloud",
    "proton.me": "Proton Mail",
    "protonmail.com": "Proton Mail",
    "mail.com": "mail.com",
    "zoho.com": "Zoho Mail",
    "yandex.com": "Yandex Mail",
    "gmx.com": "GMX",
    "gmx.net": "GMX",
    "gmx.de": "GMX",
    "gmx.ch": "GMX",
    "gmx.at": "GMX",
    "fastmail.com": "Fastmail",
    "tutanota.com": "Tutanota",
    "tutamail.com": "Tutanota",
    "rediffmail.com": "Rediffmail",
    "qq.com": "QQ Mail",
    "naver.com": "Naver",
    "daum.net": "Daum",
    "163.com": "163 Mail",
    "126.com": "126 Mail",
    "sina.com": "Sina Mail",
    "sohu.com": "Sohu Mail",
    "mail.ru": "Mail.ru",
    "bk.ru": "Mail.ru",
    "list.ru": "Mail.ru",
    "inbox.ru": "Mail.ru",
    "facebook.com": "Facebook",
    "amazon.com": "Amazon",
    "apple.com": "Apple",
    "microsoft.com": "Microsoft",
    "github.com": "GitHub",
    "gitlab.com": "GitLab",
    "atlassian.com": "Atlassian",
    "slack.com": "Slack",
    "notion.so": "Notion",
    "stripe.com": "Stripe",
    "shopify.com": "Shopify",
}

_DISPOSABLE_DOMAINS: set[str] | None = None


def _load_disposable_domains() -> set[str]:
    global _DISPOSABLE_DOMAINS
    if _DISPOSABLE_DOMAINS is not None:
        return _DISPOSABLE_DOMAINS
    _DISPOSABLE_DOMAINS = set()
    txt_path = Path(__file__).parent / "disposable_domains.txt"
    if txt_path.exists():
        for line in txt_path.read_text(encoding="utf-8").splitlines():
            domain = line.strip().lower()
            if domain and not domain.startswith("#"):
                _DISPOSABLE_DOMAINS.add(domain)
    return _DISPOSABLE_DOMAINS


def extract_domain(email: str) -> str:
    email = str(email).strip().lower()
    if "@" in email:
        return email.split("@", 1)[1].strip()
    return ""


def is_valid_email_syntax(email: str) -> bool:
    try:
        ev_validate(email, check_deliverability=False)
        return True
    except EmailSyntaxError:
        return False


def normalize_email(email: str) -> str:
    try:
        result = ev_validate(email, check_deliverability=False)
        return result.normalized
    except EmailSyntaxError:
        return email.strip().lower()


def lookup_mx(domain: str) -> tuple[bool, str]:
    if not domain:
        return False, "No domain"
    try:
        answers = dns.resolver.resolve(domain, "MX", lifetime=5)
        records = sorted([f"{r.preference} {str(r.exchange).rstrip('.')}" for r in answers])
        if records:
            return True, ", ".join(records)
        return False, "No MX records"
    except dns.resolver.NXDOMAIN:
        return False, "NXDOMAIN"
    except dns.resolver.NoAnswer:
        return False, "No MX records"
    except dns.resolver.NoNameservers:
        return False, "No nameservers"
    except dns.exception.Timeout:
        return False, "DNS timeout"
    except Exception as e:
        return False, f"Error: {e}"


def detect_provider(domain: str) -> str:
    return _EMAIL_PROVIDERS.get(domain.strip().lower(), "Custom / Business")


def is_disposable_domain(domain: str) -> bool:
    return domain.strip().lower() in _load_disposable_domains()


def check_domain_website(domain: str) -> dict:
    if not domain:
        return {
            "website_url": "",
            "status": "No Domain",
            "http_code": 0,
            "ssl_valid": False,
        }

    url = f"https://www.{domain}"
    try:
        resp = requests.get(url, timeout=8, allow_redirects=True, verify=True)
        http_code = resp.status_code
        ssl_valid = True
        status = "Active" if 200 <= http_code < 400 else "Inactive"
    except requests.exceptions.SSLError:
        try:
            resp = requests.get(url.replace("https://", "http://"), timeout=8, allow_redirects=True, verify=False)
            http_code = resp.status_code
            ssl_valid = False
            status = "Active (No SSL)" if 200 <= http_code < 400 else "Inactive"
        except Exception:
            return {
                "website_url": url,
                "status": "Unreachable",
                "http_code": 0,
                "ssl_valid": False,
            }
    except requests.exceptions.Timeout:
        return {
            "website_url": url,
            "status": "Timeout",
            "http_code": 0,
            "ssl_valid": False,
        }
    except requests.exceptions.ConnectionError:
        return {
            "website_url": url,
            "status": "Unreachable",
            "http_code": 0,
            "ssl_valid": False,
        }
    except Exception as e:
        return {
            "website_url": url,
            "status": f"Error: {type(e).__name__}",
            "http_code": 0,
            "ssl_valid": False,
        }

    return {
        "website_url": resp.url if 'resp' in locals() else url,
        "status": status,
        "http_code": http_code,
        "ssl_valid": ssl_valid,
    }


def check_domain_active(domain: str) -> tuple[bool, str]:
    """Check if domain resolves and has DNS records."""
    if not domain:
        return False, "No domain"
    try:
        dns.resolver.resolve(domain, "A", lifetime=3)
        return True, "Resolves"
    except dns.resolver.NXDOMAIN:
        return False, "NXDOMAIN"
    except dns.resolver.NoAnswer:
        return False, "No A record"
    except dns.exception.Timeout:
        return False, "Timeout"
    except Exception:
        return False, "DNS error"


def calculate_score(flags: dict) -> tuple[int, str, str]:
    syntax_valid = flags.get("syntax_valid", False)
    domain_active = flags.get("domain_active", False)
    website_active = flags.get("website_active", False)
    mx_found = flags.get("mx_found", False)
    is_disposable = flags.get("is_disposable", False)

    if not syntax_valid:
        return 0, "Invalid", "Invalid email syntax"

    if is_disposable:
        return 10, "Invalid", "Disposable email domain"

    score = 0
    notes = []

    if domain_active:
        score += 25
    else:
        notes.append("Domain not active")

    if website_active:
        score += 25
    else:
        notes.append("Website not accessible")

    if mx_found:
        score += 35
    else:
        notes.append("No MX records")

    score += 15

    score = max(0, min(score, 100))

    if score >= 80:
        status = "Verified"
    elif score >= 50:
        status = "Risky"
    else:
        status = "Invalid"

    note_str = "; ".join(notes) if notes else status
    return score, status, note_str


def verify_email(email: str) -> dict:
    email = str(email).strip()
    normalized = normalize_email(email)
    syntax_valid = is_valid_email_syntax(email)
    domain = extract_domain(email)

    mx_found, mx_details = lookup_mx(domain) if domain else (False, "No domain")
    provider = detect_provider(domain) if domain else "Unknown"
    is_disposable = is_disposable_domain(domain) if domain else False

    domain_active, domain_status = check_domain_active(domain)
    website_info = check_domain_website(domain)
    website_active = website_info["status"] == "Active"

    flags = {
        "syntax_valid": syntax_valid,
        "domain_active": domain_active,
        "website_active": website_active,
        "mx_found": mx_found,
        "is_disposable": is_disposable,
    }

    score, status, notes = calculate_score(flags)

    return {
        "Email": email,
        "Normalized Email": normalized,
        "Domain": domain,
        "Domain Active": "Yes" if domain_active else "No",
        "Website Status": website_info["status"],
        "MX Status": "Found" if mx_found else mx_details,
        "Email Provider": provider,
        "Verification Status": status,
        "Verification Score": score,
        "Notes": notes,
    }
