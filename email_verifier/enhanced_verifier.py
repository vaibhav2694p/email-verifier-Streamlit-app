from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

from email_verifier.dns_checks import DnsVerifier
from email_verifier.email_checks import extract_domain, normalize_email, validate_email_format
from email_verifier.linkedin import build_linkedin_search_url
from email_verifier.name_extractor import extract_names_from_email
from email_verifier.professional_check import is_disposable_email, is_free_email, is_role_account
from email_verifier.smtp_check import verify_mailbox_smtp


@dataclass
class VerificationDetail:
    status: str
    valid: bool
    details: str = ""


@dataclass
class EnhancedVerificationResult:
    email: str
    domain: str

    format_check: VerificationDetail = field(default_factory=lambda: VerificationDetail("", False))
    professional_check: VerificationDetail = field(default_factory=lambda: VerificationDetail("", False))
    domain_check: VerificationDetail = field(default_factory=lambda: VerificationDetail("", False))
    mailbox_check: VerificationDetail = field(default_factory=lambda: VerificationDetail("", False))

    overall_valid: bool = False
    score: int = 0
    verification_date: str = ""
    verification_time: str = ""
    result: str = ""

    first_name: str = ""
    last_name: str = ""
    full_name: str = ""

    mx_records_available: bool = False
    catch_all: bool | None = None
    provider_type: str = ""
    disposable_email: bool = False
    role_account: bool = False
    smtp_response: str = ""
    linkedin_url: str = ""
    website_status: str = ""
    verification_source: str = "Real-Time"


def verify_single_email(email_address: str) -> EnhancedVerificationResult:
    email = normalize_email(email_address)
    domain = extract_domain(email)

    now = datetime.now(timezone.utc)
    date_str = now.strftime("%d-%b-%Y")
    time_str = now.strftime("%I:%M %p UTC")

    result = EnhancedVerificationResult(
        email=email,
        domain=domain,
        verification_date=date_str,
        verification_time=time_str,
    )

    format_valid, format_reason = validate_email_format(email)
    result.format_check = VerificationDetail(
        status="Valid" if format_valid else "Invalid",
        valid=format_valid,
        details=(
            "The email address is correctly formatted and is not gibberish."
            if format_valid
            else format_reason
        ),
    )

    if not format_valid:
        result.overall_valid = False
        result.result = "Undeliverable"
        return result

    is_free = is_free_email(domain)
    is_disposable = is_disposable_email(domain)
    result.disposable_email = is_disposable
    result.provider_type = "Free" if is_free else "Business"

    if is_disposable:
        result.professional_check = VerificationDetail(
            status="Invalid",
            valid=False,
            details="The domain is associated with disposable or temporary email services.",
        )
    elif is_free:
        result.professional_check = VerificationDetail(
            status="Invalid",
            valid=False,
            details="The domain is a free webmail provider and not a professional business domain.",
        )
    else:
        result.professional_check = VerificationDetail(
            status="Valid",
            valid=True,
            details="The domain is not associated with disposable, temporary, or free webmail services.",
        )

    local_part = email.split("@")[0] if "@" in email else ""
    result.role_account = is_role_account(local_part)

    result.linkedin_url = build_linkedin_search_url(
        name=result.first_name or result.full_name,
        company="",
    )
    result.website_status = "Active" if domain else "Unknown"

    dns_verifier = DnsVerifier(timeout=5.0)
    dns_result = dns_verifier.verify_domain(domain) if domain else None

    if dns_result and dns_result.exists:
        mx_valid = dns_result.mx.found
        result.mx_records_available = mx_valid
        spf_valid = dns_result.spf.found
        dmarc_valid = dns_result.dmarc.found

        mx_detail = (
            "MX records are configured." if mx_valid
            else "No MX records found. The domain may not receive emails."
        )
        spf_note = " SPF record present." if spf_valid else " No SPF record."
        dmarc_note = " DMARC record present." if dmarc_valid else " No DMARC record."

        result.domain_check = VerificationDetail(
            status="Valid",
            valid=True,
            details=f"The domain exists and has valid DNS records.{mx_detail}{spf_note}{dmarc_note}",
        )
    elif dns_result:
        result.domain_check = VerificationDetail(
            status="Invalid",
            valid=False,
            details=f"{dns_result.existence_status}. The domain does not appear to have valid DNS records.",
        )
    else:
        result.domain_check = VerificationDetail(
            status="Invalid",
            valid=False,
            details="Could not resolve domain.",
        )

    if dns_result and dns_result.mx.found:
        smtp_result = verify_mailbox_smtp(email, domain)
        result.smtp_response = smtp_result.error or "Mail server responded"
        if smtp_result.mailbox_exists is True:
            result.mailbox_check = VerificationDetail(
                status="Valid",
                valid=True,
                details="The mail server responded and confirmed the mailbox exists.",
            )
        elif smtp_result.mailbox_exists is False:
            result.mailbox_check = VerificationDetail(
                status="Invalid",
                valid=False,
                details=f"The mail server rejected the recipient: {smtp_result.error}",
            )
        else:
            result.mailbox_check = VerificationDetail(
                status="Unable to verify",
                valid=False,
                details=f"Could not definitively verify the mailbox: {smtp_result.error or 'Server did not provide confirmation'}",
            )
        result.catch_all = smtp_result.catch_all
    else:
        result.mailbox_check = VerificationDetail(
            status="Invalid",
            valid=False,
            details="No MX records found. Cannot verify mailbox without a mail server.",
        )

    names = extract_names_from_email(email)
    result.first_name = names["first_name"]
    result.last_name = names["last_name"]
    result.full_name = names["full_name"]

    checks = [
        result.format_check.valid,
        result.professional_check.valid,
        result.domain_check.valid,
    ]
    passed = sum(1 for c in checks if c)
    total = len(checks)
    if result.mailbox_check.valid:
        passed += 1
    total += 1

    result.score = int((passed / total) * 100) if total else 0
    result.overall_valid = (
        result.format_check.valid
        and result.domain_check.valid
        and result.mailbox_check.valid
    )

    if result.overall_valid:
        result.result = "Deliverable"
    elif result.format_check.valid and result.domain_check.valid and result.mailbox_check.status == "Unable to verify":
        result.result = "Risky"
    else:
        result.result = "Undeliverable"

    return result
