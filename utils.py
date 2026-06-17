"""Shared helpers for the Streamlit Email Verifier Tool."""

from __future__ import annotations

import hashlib
import hmac
import os
from dataclasses import dataclass
from typing import Any
from urllib.parse import quote_plus

import pandas as pd


NAME_COLUMNS = {"name", "full_name", "fullname", "contact_name", "contact", "full name", "contact name"}
COMPANY_COLUMNS = {"company", "company_name", "companyname", "organization", "organisation", "org", "company name"}
EMAIL_COLUMNS = {"email", "email_address", "emailaddress", "work_email", "work email", "e-mail", "email address"}

REQUIRED_COLUMN_GROUPS = {
    "Name": NAME_COLUMNS,
    "Company Name": COMPANY_COLUMNS,
    "Email": EMAIL_COLUMNS,
}

OUTPUT_COLUMNS = [
    "Name",
    "Company Name",
    "Email",
    "Domain",
    "MX Status",
    "SPF Status",
    "DMARC Status",
    "Email Format Valid/Invalid",
    "LinkedIn Search URL",
    "Verification Score",
    "Notes",
]

# Local default login for first run. Override these values with environment variables
# before exposing the app to other users.
DEFAULT_USERNAME = "admin"
DEFAULT_PASSWORD_SALT = "email-verifier-default-salt-v1"
DEFAULT_PASSWORD_HASH = "c38527b4d6cf55f0cd11ba8e6603ea924c94d2b601566e4f13b4b716296acf70"
PBKDF2_ITERATIONS = 260_000


@dataclass(frozen=True)
class AuthConfig:
    """Authentication settings loaded from environment variables."""

    username: str
    password_hash: str
    password_salt: str


def get_auth_config() -> AuthConfig:
    """Load auth config from environment variables with safe local defaults."""
    return AuthConfig(
        username=os.getenv("EMAIL_VERIFIER_USERNAME", DEFAULT_USERNAME),
        password_hash=os.getenv("EMAIL_VERIFIER_PASSWORD_HASH", DEFAULT_PASSWORD_HASH),
        password_salt=os.getenv("EMAIL_VERIFIER_PASSWORD_SALT", DEFAULT_PASSWORD_SALT),
    )


def hash_password(password: str, salt: str | None = None) -> str:
    """Return a PBKDF2-SHA256 hash for a password."""
    salt_value = salt or os.getenv("EMAIL_VERIFIER_PASSWORD_SALT", DEFAULT_PASSWORD_SALT)
    password_bytes = password.encode("utf-8")
    salt_bytes = salt_value.encode("utf-8")
    digest = hashlib.pbkdf2_hmac("sha256", password_bytes, salt_bytes, PBKDF2_ITERATIONS)
    return digest.hex()


def authenticate(username: str, password: str, config: AuthConfig | None = None) -> bool:
    """Validate credentials without storing or comparing plaintext passwords."""
    auth_config = config or get_auth_config()
    if not username or not password:
        return False
    if not hmac.compare_digest(username.strip(), auth_config.username):
        return False
    submitted_hash = hash_password(password, auth_config.password_salt)
    return hmac.compare_digest(submitted_hash, auth_config.password_hash)


def is_using_default_credentials() -> bool:
    """Return True when the app is still using the bundled local credentials."""
    config = get_auth_config()
    return (
        config.username == DEFAULT_USERNAME
        and config.password_hash == DEFAULT_PASSWORD_HASH
        and config.password_salt == DEFAULT_PASSWORD_SALT
    )


def normalize_column_name(column_name: Any) -> str:
    """Normalize uploaded file headers for flexible matching."""
    return str(column_name).strip().lower().replace("-", "_").replace(" ", "_")


def _column_aliases(aliases: set[str]) -> set[str]:
    normalized = {normalize_column_name(alias) for alias in aliases}
    normalized.update(alias.replace("_", "") for alias in normalized)
    return normalized


def detect_required_columns(df: pd.DataFrame) -> tuple[dict[str, str], list[str]]:
    """Find Name, Company Name, and Email columns in a user-uploaded dataframe."""
    normalized_to_original = {normalize_column_name(column): column for column in df.columns}
    compact_to_original = {name.replace("_", ""): original for name, original in normalized_to_original.items()}
    detected: dict[str, str] = {}
    missing: list[str] = []

    for output_name, aliases in REQUIRED_COLUMN_GROUPS.items():
        match = None
        for alias in _column_aliases(aliases):
            if alias in normalized_to_original:
                match = normalized_to_original[alias]
                break
            if alias in compact_to_original:
                match = compact_to_original[alias]
                break
        if match is None:
            missing.append(output_name)
        else:
            detected[output_name] = match

    return detected, missing


def read_uploaded_file(uploaded_file: Any) -> pd.DataFrame:
    """Read a CSV or XLSX upload into a dataframe."""
    filename = uploaded_file.name.lower()
    if filename.endswith(".csv"):
        return pd.read_csv(uploaded_file)
    if filename.endswith(".xlsx"):
        return pd.read_excel(uploaded_file, engine="openpyxl")
    raise ValueError("Unsupported file type. Upload a CSV or XLSX file.")


def standardize_input_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """Return a clean dataframe with standardized Name, Company Name, and Email columns."""
    if df.empty:
        raise ValueError("The uploaded file is empty.")

    detected, missing = detect_required_columns(df)
    if missing:
        expected = ", ".join(missing)
        raise ValueError(f"Missing required column(s): {expected}.")

    standardized = pd.DataFrame(
        {
            "Name": df[detected["Name"]],
            "Company Name": df[detected["Company Name"]],
            "Email": df[detected["Email"]],
        }
    )

    for column in ["Name", "Company Name", "Email"]:
        standardized[column] = standardized[column].fillna("").astype(str).str.strip()

    return standardized


def clean_email(email: Any) -> str:
    """Normalize a raw email value from an uploaded spreadsheet."""
    if pd.isna(email):
        return ""
    return str(email).strip().lower()


def extract_domain(email: str) -> str:
    """Extract the domain from a normalized email address."""
    if not email or "@" not in email:
        return ""
    return email.rsplit("@", 1)[-1].strip().lower()


def generate_linkedin_search_urls(name: str, company_name: str) -> str:
    """Generate Google search URLs for LinkedIn profiles without scraping LinkedIn."""
    clean_name = str(name or "").strip()
    clean_company = str(company_name or "").strip()
    if not clean_name or not clean_company:
        return ""

    searches = [
        f'site:linkedin.com/in "{clean_name}" "{clean_company}"',
        f'site:linkedin.com "{clean_name}" "{clean_company}"',
    ]
    return " | ".join(f"https://www.google.com/search?q={quote_plus(search)}" for search in searches)


def dataframe_to_csv_bytes(df: pd.DataFrame) -> bytes:
    """Serialize results for Streamlit's download button."""
    return df.to_csv(index=False).encode("utf-8-sig")


def ensure_output_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Return a dataframe containing the required output columns in order."""
    output = df.copy()
    for column in OUTPUT_COLUMNS:
        if column not in output.columns:
            output[column] = ""
    return output[OUTPUT_COLUMNS]
