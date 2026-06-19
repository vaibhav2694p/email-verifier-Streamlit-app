from __future__ import annotations

import re
from pathlib import Path

import dns.resolver
from email_validator import validate_email as ev_validate, EmailSyntaxError

ROLE_PREFIXES = frozenset({
    "info", "sales", "support", "admin", "contact",
    "hello", "marketing", "hr", "careers", "billing",
    "team", "help", "enquiries", "enquiry", "office",
    "noreply", "no-reply", "newsletter", "jobs",
    "feedback", "test", "mail", "service", "events",
})

_PUBLIC_DOMAINS: frozenset[str] = frozenset({
    "gmail.com", "yahoo.com", "outlook.com", "hotmail.com",
    "aol.com", "icloud.com", "proton.me", "protonmail.com",
    "live.com", "msn.com", "ymail.com", "mail.com",
    "zoho.com", "yandex.com", "gmx.com", "gmx.net",
    "fastmail.com", "tutanota.com", "tutamail.com",
    "rediffmail.com", "qq.com", "naver.com", "daum.net",
    "163.com", "126.com", "sina.com", "sohu.com",
})

_EMAIL_PROVIDERS: dict[str, str] = {
    "gmail.com": "Google",
    "yahoo.com": "Yahoo",
    "ymail.com": "Yahoo",
    "outlook.com": "Microsoft",
    "hotmail.com": "Microsoft",
    "live.com": "Microsoft",
    "msn.com": "Microsoft",
    "aol.com": "AOL",
    "icloud.com": "Apple",
    "proton.me": "ProtonMail",
    "protonmail.com": "ProtonMail",
    "mail.com": "mail.com",
    "zoho.com": "Zoho",
    "yandex.com": "Yandex",
    "gmx.com": "GMX",
    "gmx.net": "GMX",
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
    "gmx.de": "GMX",
    "gmx.ch": "GMX",
    "gmx.at": "GMX",
    "mail.ru": "Mail.ru",
    "bk.ru": "Mail.ru",
    "list.ru": "Mail.ru",
    "inbox.ru": "Mail.ru",
    "facebook.com": "Facebook",
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


def clean_domain(value: str | None) -> str:
    if value is None or value == "" or (isinstance(value, float) and str(value) == "nan"):
        return ""
    domain = str(value).strip().lower()
    domain = re.sub(r"^https?://", "", domain)
    domain = re.sub(r"^www\.", "", domain)
    domain = domain.split("/")[0]
    domain = domain.split(":")[0]
    domain = domain.strip()
    if not re.match(r"^[a-z0-9.-]+\.[a-z]{2,}$", domain):
        return ""
    return domain


def normalize_email(email: str) -> tuple[str, str, str]:
    try:
        result = ev_validate(email, check_deliverability=False)
        return result.normalized, result.local_part, result.domain
    except EmailSyntaxError:
        return email.strip(), "", ""


def is_valid_email_syntax(email: str) -> bool:
    try:
        ev_validate(email, check_deliverability=False)
        return True
    except EmailSyntaxError:
        return False


def lookup_mx(domain: str) -> tuple[bool, str]:
    if not domain:
        return False, "No domain provided"
    try:
        answers = dns.resolver.resolve(domain, "MX", lifetime=5)
        records = sorted(
            [f"{r.preference} {str(r.exchange).rstrip('.')}" for r in answers]
        )
        if records:
            return True, ", ".join(records)
        return False, "No MX records found"
    except dns.resolver.NXDOMAIN:
        return False, "Domain does not exist"
    except dns.resolver.NoAnswer:
        return False, "No MX records found"
    except dns.resolver.NoNameservers:
        return False, "DNS error"
    except dns.exception.Timeout:
        return False, "DNS timeout"
    except Exception as e:
        return False, f"Lookup failed: {e}"


def detect_provider(domain: str) -> str:
    return _EMAIL_PROVIDERS.get(domain.strip().lower(), "Unknown")


def is_public_domain(domain: str) -> bool:
    return domain.strip().lower() in _PUBLIC_DOMAINS


def is_disposable_domain(domain: str) -> bool:
    return domain.strip().lower() in _load_disposable_domains()


def is_role_based(email: str) -> bool:
    local = str(email).split("@", 1)[0].strip().lower() if "@" in email else ""
    local = re.sub(r"[^a-zA-Z0-9]", "", local)
    return local in ROLE_PREFIXES


def _determine_status(score: int, flags: dict) -> str:
    if not flags.get("syntax_valid"):
        return "Invalid"
    if flags.get("is_disposable"):
        return "Disposable"
    if not flags.get("mx_found"):
        return "No MX"
    if flags.get("is_public_email"):
        return "Public Email"
    if flags.get("is_role_based"):
        return "Risky"
    if flags.get("company_domain_match") is False:
        return "Company Domain Mismatch"
    if score >= 80:
        return "Verified"
    if score >= 50:
        return "Risky"
    return "Invalid"


def _compute_score(flags: dict) -> int:
    if not flags.get("syntax_valid"):
        return 0
    if flags.get("is_disposable"):
        return min(10, 10)

    score = 0
    if flags.get("mx_found"):
        score += 30
        if flags.get("spf_found"):
            score += 10
        if flags.get("dmarc_found"):
            score += 10
    else:
        score = min(score, 20)

    if flags.get("is_public_email"):
        score = min(score, 45)

    if flags.get("company_domain_match") is True:
        score += 30
    elif flags.get("company_domain_match") is False:
        score = min(score, 50)

    if flags.get("is_role_based"):
        score = max(0, score - 10)

    return max(0, min(score, 100))


def _build_notes(flags: dict, status: str) -> str:
    parts = []
    if not flags.get("syntax_valid"):
        return "Invalid email format"
    if flags.get("is_disposable"):
        return "Disposable email domain"
    if not flags.get("mx_found"):
        parts.append("No MX records found")
    if flags.get("is_public_email"):
        parts.append("Public/free email provider")
    if flags.get("is_role_based"):
        parts.append("Role-based email account")
    if flags.get("company_domain_match") is False:
        parts.append("Email domain does not match company domain")
    return "; ".join(parts) if parts else status


def verify_email(email: str, company_domain: str | None = None) -> dict:
    email = str(email).strip()
    normalized, local_part, email_domain = normalize_email(email)
    syntax_valid = bool(email_domain and local_part)
    is_disp = is_disposable_domain(email_domain) if email_domain else False
    is_pub = is_public_domain(email_domain) if email_domain else False
    is_role = is_role_based(email) if email_domain else False

    mx_found = False
    mx_details = ""
    spf_found = False
    dmarc_found = False

    if syntax_valid and email_domain and not is_disp:
        mx_found, mx_details = lookup_mx(email_domain)
        if mx_found:
            try:
                answers = dns.resolver.resolve(email_domain, "TXT", lifetime=5)
                for r in answers:
                    txt = str(r).lower()
                    if "v=spf1" in txt:
                        spf_found = True
                        break
            except Exception:
                pass
            try:
                dmarc_domain = f"_dmarc.{email_domain}"
                answers = dns.resolver.resolve(dmarc_domain, "TXT", lifetime=5)
                for r in answers:
                    txt = str(r).lower()
                    if "v=dmarc1" in txt:
                        dmarc_found = True
                        break
            except Exception:
                pass

    company_match: bool | None = None
    clean_company = ""
    if company_domain:
        clean_company = clean_domain(company_domain)
        if clean_company:
            company_match = email_domain == clean_company

    flags = {
        "syntax_valid": syntax_valid,
        "mx_found": mx_found,
        "spf_found": spf_found,
        "dmarc_found": dmarc_found,
        "is_public_email": is_pub,
        "is_disposable": is_disp,
        "is_role_based": is_role,
        "company_domain_match": company_match,
    }

    score = _compute_score(flags)
    status = _determine_status(score, flags)
    notes = _build_notes(flags, status)

    return {
        "Original Email": email,
        "Normalized Email": normalized,
        "Email Domain": email_domain,
        "Company Domain": clean_company,
        "MX Status": "Found" if mx_found else "Not Found",
        "Email Provider": detect_provider(email_domain) if email_domain else "Unknown",
        "Public Email": "Yes" if is_pub else "No",
        "Disposable Email": "Yes" if is_disp else "No",
        "Role Based Email": "Yes" if is_role else "No",
        "Company Domain Match": (
            "Yes" if company_match is True
            else "No" if company_match is False
            else "N/A"
        ),
        "Verification Status": status,
        "Verification Score": score,
        "Notes": notes,
    }
