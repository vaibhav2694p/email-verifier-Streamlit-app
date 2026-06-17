from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

import pandas as pd

from email_verifier.enhanced_verifier import verify_single_email
from email_verifier.io import ColumnMapping, clean_cell


ProgressCallback = Callable[[int, int], None]


@dataclass(frozen=True)
class VerificationOptions:
    linkedin_scope: str = "profiles"
    dns_timeout: float = 3.0


OUTPUT_COLUMNS = [
    "Email Address",
    "First Name",
    "Last Name",
    "Format",
    "Domain Status",
    "Professional Domain",
    "Disposable",
    "Role Account",
    "MX Record",
    "Mailbox Status",
    "Catch-All",
    "Company Website",
    "Email Score",
    "SMTP Response",
    "LinkedIn URL",
    "Website Status",
    "Verification Date",
    "Verification Source",
    "Overall Status",
]


def process_dataframe(
    dataframe: pd.DataFrame,
    mapping: ColumnMapping,
    options: VerificationOptions | None = None,
    progress_callback: ProgressCallback | None = None,
) -> pd.DataFrame:
    if mapping.email not in dataframe.columns:
        raise ValueError("The selected email column was not found in the uploaded file.")

    total_rows = len(dataframe)
    output_rows: list[dict[str, object]] = []

    for processed_count, (_, row) in enumerate(dataframe.iterrows(), start=1):
        email_raw = clean_cell(row.get(mapping.email, ""))
        if not email_raw:
            output_rows.append(_empty_row(email_raw))
            if progress_callback:
                progress_callback(processed_count, total_rows)
            continue

        try:
            result = verify_single_email(email_raw)
            output_rows.append(_result_to_row(result))
        except Exception:
            output_rows.append(_empty_row(email_raw))

        if progress_callback:
            progress_callback(processed_count, total_rows)

    return pd.DataFrame(output_rows, columns=OUTPUT_COLUMNS)


def _result_to_row(result: object) -> dict[str, object]:
    from email_verifier.enhanced_verifier import EnhancedVerificationResult
    r = result
    if not isinstance(r, EnhancedVerificationResult):
        return _empty_row(getattr(r, "email", ""))
    return {
        "Email Address": r.email,
        "First Name": r.first_name or "Not Found",
        "Last Name": r.last_name or "Not Found",
        "Format": "Valid" if r.format_check.valid else "Invalid",
        "Domain Status": "Valid" if r.domain_check.valid else "Invalid",
        "Professional Domain": "Valid" if r.professional_check.valid else "Invalid",
        "Disposable": "Yes" if r.disposable_email else "No",
        "Role Account": "Yes" if r.role_account else "No",
        "MX Record": "Valid" if r.mx_records_available else "Missing",
        "Mailbox Status": "Exists" if r.mailbox_check.valid else ("Unable" if "Unable" in r.mailbox_check.status else "Not Exists"),
        "Catch-All": "Yes" if r.catch_all is True else ("No" if r.catch_all is False else "N/A"),
        "Company Website": r.domain or "Not Found",
        "Email Score": r.score,
        "SMTP Response": r.smtp_response or "N/A",
        "LinkedIn URL": r.linkedin_url or "",
        "Website Status": r.website_status,
        "Verification Date": f"{r.verification_date} {r.verification_time}",
        "Verification Source": r.verification_source,
        "Overall Status": "VALID" if r.overall_valid else ("RISKY" if r.result == "Risky" else "INVALID"),
    }


def _empty_row(email: str) -> dict[str, object]:
    return {
        "Email Address": email,
        "First Name": "Not Found",
        "Last Name": "Not Found",
        "Format": "Invalid",
        "Domain Status": "Invalid",
        "Professional Domain": "Invalid",
        "Disposable": "N/A",
        "Role Account": "N/A",
        "MX Record": "Missing",
        "Mailbox Status": "Not Exists",
        "Catch-All": "N/A",
        "Company Website": "Not Found",
        "Email Score": 0,
        "SMTP Response": "N/A",
        "LinkedIn URL": "",
        "Website Status": "Unknown",
        "Verification Date": "",
        "Verification Source": "Real-Time",
        "Overall Status": "INVALID",
    }
