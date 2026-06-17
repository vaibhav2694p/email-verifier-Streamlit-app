"""Email and domain verification logic for the CRM-style verifier app."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import dns.exception
import dns.resolver
import pandas as pd
from email_validator import EmailNotValidError, validate_email

from utils import clean_email, ensure_output_columns, extract_domain, generate_linkedin_search_urls


@dataclass(frozen=True)
class DnsCheckResult:
    """A normalized DNS lookup result."""

    exists: bool | None
    status: str
    notes: list[str]


@dataclass(frozen=True)
class DomainVerification:
    """Cached verification state for a domain."""

    domain_exists: bool | None
    domain_status: str
    mx_exists: bool | None
    mx_status: str
    spf_exists: bool | None
    spf_status: str
    dmarc_exists: bool | None
    dmarc_status: str
    notes: list[str]


class EmailVerifier:
    """Verify emails with format checks, DNS lookups, and scoring."""

    def __init__(self, timeout: float = 3.0, lifetime: float = 5.0) -> None:
        self.resolver = dns.resolver.Resolver()
        self.resolver.timeout = timeout
        self.resolver.lifetime = lifetime
        self._domain_cache: dict[str, DomainVerification] = {}

    def verify_row(self, row: dict[str, Any]) -> dict[str, Any]:
        """Verify one CRM contact row and return the downloadable output record."""
        name = str(row.get("Name", "") or "").strip()
        company_name = str(row.get("Company Name", "") or "").strip()
        email = clean_email(row.get("Email", ""))

        notes: list[str] = []
        format_valid, normalized_email, format_note = self._validate_email_format(email)
        if format_note:
            notes.append(format_note)

        domain = extract_domain(normalized_email if format_valid else email)
        domain_result = self._verify_domain(domain) if domain else self._empty_domain_result()
        notes.extend(domain_result.notes)

        if not name:
            notes.append("Name is missing.")
        if not company_name:
            notes.append("Company name is missing.")
        if not email:
            notes.append("Email is missing.")

        score = self._score(
            format_valid=format_valid,
            domain_exists=domain_result.domain_exists,
            mx_exists=domain_result.mx_exists,
            spf_exists=domain_result.spf_exists,
            dmarc_exists=domain_result.dmarc_exists,
            name=name,
            company_name=company_name,
            email=email,
        )

        return {
            "Name": name,
            "Company Name": company_name,
            "Email": normalized_email if format_valid else email,
            "Domain": domain,
            "MX Status": domain_result.mx_status,
            "SPF Status": domain_result.spf_status,
            "DMARC Status": domain_result.dmarc_status,
            "Email Format Valid/Invalid": "Valid" if format_valid else "Invalid",
            "LinkedIn Search URL": generate_linkedin_search_urls(name, company_name),
            "Verification Score": score,
            "Notes": " ".join(dict.fromkeys(notes)) or "All checks passed.",
        }

    def verify_dataframe(self, df: pd.DataFrame, progress_callback: Any | None = None) -> pd.DataFrame:
        """Verify every row in a standardized dataframe."""
        records: list[dict[str, Any]] = []
        total = len(df)

        for index, row in enumerate(df.to_dict(orient="records"), start=1):
            records.append(self.verify_row(row))
            if progress_callback:
                progress_callback(index, total)

        return ensure_output_columns(pd.DataFrame(records))

    def _validate_email_format(self, email: str) -> tuple[bool, str, str]:
        if not email:
            return False, "", "Email format is invalid: value is empty."
        try:
            validated = validate_email(email, check_deliverability=False)
            return True, validated.normalized.lower(), ""
        except EmailNotValidError as exc:
            return False, email, f"Email format is invalid: {exc}."

    def _verify_domain(self, domain: str) -> DomainVerification:
        if domain in self._domain_cache:
            return self._domain_cache[domain]

        domain_check = self._check_domain_exists(domain)
        mx_check = self._check_mx(domain) if domain_check.exists is not False else DnsCheckResult(False, "Missing", ["MX check skipped because domain was not found."])
        spf_check = self._check_spf(domain) if domain_check.exists is not False else DnsCheckResult(False, "Missing", ["SPF check skipped because domain was not found."])
        dmarc_check = self._check_dmarc(domain) if domain_check.exists is not False else DnsCheckResult(False, "Missing", ["DMARC check skipped because domain was not found."])

        notes = [*domain_check.notes, *mx_check.notes, *spf_check.notes, *dmarc_check.notes]
        result = DomainVerification(
            domain_exists=domain_check.exists,
            domain_status=domain_check.status,
            mx_exists=mx_check.exists,
            mx_status=mx_check.status,
            spf_exists=spf_check.exists,
            spf_status=spf_check.status,
            dmarc_exists=dmarc_check.exists,
            dmarc_status=dmarc_check.status,
            notes=notes,
        )
        self._domain_cache[domain] = result
        return result

    def _empty_domain_result(self) -> DomainVerification:
        return DomainVerification(
            domain_exists=False,
            domain_status="Missing",
            mx_exists=False,
            mx_status="Missing",
            spf_exists=False,
            spf_status="Missing",
            dmarc_exists=False,
            dmarc_status="Missing",
            notes=["Domain could not be extracted from the email."],
        )

    def _check_domain_exists(self, domain: str) -> DnsCheckResult:
        for record_type in ("NS", "A", "AAAA", "MX"):
            try:
                self.resolver.resolve(domain, record_type)
                return DnsCheckResult(True, "Exists", [])
            except dns.resolver.NXDOMAIN:
                return DnsCheckResult(False, "Not Found", [f"Domain {domain} does not exist."])
            except dns.resolver.NoAnswer:
                continue
            except dns.resolver.NoNameservers:
                return DnsCheckResult(None, "DNS Error", [f"No responsive nameservers for {domain}."])
            except dns.exception.Timeout:
                return DnsCheckResult(None, "Timeout", [f"DNS lookup timed out for {domain}."])
            except dns.exception.DNSException as exc:
                return DnsCheckResult(None, "DNS Error", [f"DNS error while checking {domain}: {exc}."])

        # Reaching NoAnswer across known record types still means the name was not NXDOMAIN.
        return DnsCheckResult(True, "Exists", [f"Domain {domain} exists, but common records were not returned."])

    def _check_mx(self, domain: str) -> DnsCheckResult:
        try:
            answers = self.resolver.resolve(domain, "MX")
            mx_hosts = sorted(str(answer.exchange).rstrip(".") for answer in answers)
            if mx_hosts:
                return DnsCheckResult(True, "Present", [])
            return DnsCheckResult(False, "Missing", [f"No MX records found for {domain}."])
        except dns.resolver.NXDOMAIN:
            return DnsCheckResult(False, "Missing", [f"Domain {domain} does not exist."])
        except dns.resolver.NoAnswer:
            return DnsCheckResult(False, "Missing", [f"No MX records found for {domain}."])
        except dns.resolver.NoNameservers:
            return DnsCheckResult(None, "DNS Error", [f"No responsive nameservers for MX lookup on {domain}."])
        except dns.exception.Timeout:
            return DnsCheckResult(None, "Timeout", [f"MX lookup timed out for {domain}."])
        except dns.exception.DNSException as exc:
            return DnsCheckResult(None, "DNS Error", [f"DNS error during MX lookup for {domain}: {exc}."])

    def _check_spf(self, domain: str) -> DnsCheckResult:
        txt = self._lookup_txt(domain, "SPF")
        if txt.exists is None:
            return txt
        if txt.exists:
            return DnsCheckResult(True, "Present", [])
        return DnsCheckResult(False, "Missing", [f"No SPF record found for {domain}."])

    def _check_dmarc(self, domain: str) -> DnsCheckResult:
        dmarc_domain = f"_dmarc.{domain}"
        txt = self._lookup_txt(dmarc_domain, "DMARC")
        if txt.exists is None:
            return txt
        if txt.exists:
            return DnsCheckResult(True, "Present", [])
        return DnsCheckResult(False, "Missing", [f"No DMARC record found for {domain}."])

    def _lookup_txt(self, domain: str, expected: str) -> DnsCheckResult:
        expected_prefix = "v=spf1" if expected == "SPF" else "v=dmarc1"
        try:
            answers = self.resolver.resolve(domain, "TXT")
            for answer in answers:
                txt_value = "".join(part.decode("utf-8", errors="ignore") for part in answer.strings).strip().lower()
                if txt_value.startswith(expected_prefix):
                    return DnsCheckResult(True, "Present", [])
            return DnsCheckResult(False, "Missing", [])
        except dns.resolver.NXDOMAIN:
            return DnsCheckResult(False, "Missing", [])
        except dns.resolver.NoAnswer:
            return DnsCheckResult(False, "Missing", [])
        except dns.resolver.NoNameservers:
            return DnsCheckResult(None, "DNS Error", [f"No responsive nameservers for {expected} TXT lookup on {domain}."])
        except dns.exception.Timeout:
            return DnsCheckResult(None, "Timeout", [f"{expected} TXT lookup timed out for {domain}."])
        except dns.exception.DNSException as exc:
            return DnsCheckResult(None, "DNS Error", [f"DNS error during {expected} TXT lookup for {domain}: {exc}."])

    def _score(
        self,
        *,
        format_valid: bool,
        domain_exists: bool | None,
        mx_exists: bool | None,
        spf_exists: bool | None,
        dmarc_exists: bool | None,
        name: str,
        company_name: str,
        email: str,
    ) -> int:
        score = 0
        if format_valid:
            score += 20
        if domain_exists is True:
            score += 20
        if mx_exists is True:
            score += 25
        if spf_exists is True:
            score += 20
        if dmarc_exists is True:
            score += 15

        if not name:
            score -= 5
        if not company_name:
            score -= 5
        if not email:
            score -= 20

        return max(0, min(100, score))
