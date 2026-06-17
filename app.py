"""Streamlit CRM-style Email Verifier Tool."""

from __future__ import annotations

import streamlit as st

from utils import (
    authenticate,
    dataframe_to_csv_bytes,
    is_using_default_credentials,
    read_uploaded_file,
    standardize_input_dataframe,
)
from verifier import EmailVerifier


st.set_page_config(
    page_title="CRM Email Verifier",
    page_icon="Email",
    layout="wide",
    initial_sidebar_state="expanded",
)


def initialize_session() -> None:
    """Initialize Streamlit session state keys."""
    st.session_state.setdefault("authenticated", False)
    st.session_state.setdefault("results_df", None)
    st.session_state.setdefault("input_df", None)


def render_login() -> None:
    """Render the login screen and stop unauthenticated users."""
    st.title("CRM Email Verifier")
    st.caption("Secure email/domain verification with LinkedIn search URL generation.")

    col_left, col_center, col_right = st.columns([1, 1.2, 1])
    with col_center:
        st.subheader("Login")
        with st.form("login_form", clear_on_submit=False):
            username = st.text_input("Username", autocomplete="username")
            password = st.text_input("Password", type="password", autocomplete="current-password")
            submitted = st.form_submit_button("Sign in", use_container_width=True)

        if submitted:
            if authenticate(username, password):
                st.session_state.authenticated = True
                st.success("Login successful.")
                st.rerun()
            else:
                st.error("Invalid username or password.")

        if is_using_default_credentials():
            st.info("Local default login: username `admin`, password `admin123`. Change environment credentials before production use.")

    st.stop()


def render_sidebar() -> None:
    """Render sidebar controls."""
    st.sidebar.title("CRM Email Verifier")
    st.sidebar.write("Upload contact lists, verify email infrastructure, and export enriched results.")

    if st.sidebar.button("Log out", use_container_width=True):
        st.session_state.authenticated = False
        st.session_state.results_df = None
        st.session_state.input_df = None
        st.rerun()

    st.sidebar.divider()
    st.sidebar.caption("Required columns: Name, Company Name, Email")
    st.sidebar.caption("Accepted aliases include full_name, contact_name, company_name, organization, email_address, and work_email.")


def render_dashboard() -> None:
    """Render the protected verifier dashboard."""
    render_sidebar()

    st.title("Email Verifier Dashboard")
    st.write("Verify contact emails using format validation, DNS domain checks, MX, SPF, and DMARC records.")

    metric_cols = st.columns(4)
    metric_cols[0].metric("Checks", "5", "Format, Domain, MX, SPF, DMARC")
    metric_cols[1].metric("File Types", "CSV / XLSX")
    metric_cols[2].metric("LinkedIn", "Search URLs only")
    metric_cols[3].metric("Score", "0-100")

    st.divider()
    uploaded_file = st.file_uploader("Upload a CRM export", type=["csv", "xlsx"])

    if not uploaded_file:
        st.info("Upload a CSV or XLSX file to begin.")
        return

    try:
        raw_df = read_uploaded_file(uploaded_file)
        input_df = standardize_input_dataframe(raw_df)
        st.session_state.input_df = input_df
    except Exception as exc:
        st.error(str(exc))
        return

    st.success(f"Loaded {len(input_df):,} row(s). Required columns were detected successfully.")
    st.subheader("Uploaded Data Preview")
    st.dataframe(input_df.head(50), use_container_width=True, hide_index=True)

    run_col, clear_col = st.columns([1, 4])
    run_clicked = run_col.button("Run verification", type="primary", use_container_width=True)
    clear_clicked = clear_col.button("Clear results", use_container_width=False)

    if clear_clicked:
        st.session_state.results_df = None
        st.rerun()

    if run_clicked:
        verify_contacts(input_df)

    if st.session_state.results_df is not None:
        render_results()


def verify_contacts(input_df) -> None:
    """Run verification and store results in session state."""
    verifier = EmailVerifier()
    progress_bar = st.progress(0)
    status = st.empty()

    def update_progress(current: int, total: int) -> None:
        progress = int((current / total) * 100) if total else 100
        progress_bar.progress(progress)
        status.write(f"Verifying {current:,} of {total:,} contact(s)...")

    try:
        with st.spinner("Running verification checks..."):
            results_df = verifier.verify_dataframe(input_df, progress_callback=update_progress)
        st.session_state.results_df = results_df
        progress_bar.progress(100)
        status.empty()
        st.success("Verification completed successfully.")
    except Exception as exc:
        progress_bar.empty()
        status.empty()
        st.error(f"Verification failed: {exc}")


def render_results() -> None:
    """Render verification results and CSV download."""
    results_df = st.session_state.results_df
    if results_df is None or results_df.empty:
        return

    st.subheader("Verification Results")

    valid_count = int((results_df["Email Format Valid/Invalid"] == "Valid").sum())
    mx_count = int((results_df["MX Status"] == "Present").sum())
    spf_count = int((results_df["SPF Status"] == "Present").sum())
    dmarc_count = int((results_df["DMARC Status"] == "Present").sum())
    average_score = round(float(results_df["Verification Score"].mean()), 1)

    cols = st.columns(5)
    cols[0].metric("Rows", f"{len(results_df):,}")
    cols[1].metric("Valid Format", f"{valid_count:,}")
    cols[2].metric("MX Present", f"{mx_count:,}")
    cols[3].metric("SPF / DMARC", f"{spf_count:,} / {dmarc_count:,}")
    cols[4].metric("Avg. Score", average_score)

    st.dataframe(results_df, use_container_width=True, hide_index=True)

    st.download_button(
        "Download verified CSV",
        data=dataframe_to_csv_bytes(results_df),
        file_name="verified_email_results.csv",
        mime="text/csv",
        type="primary",
        use_container_width=True,
    )


def main() -> None:
    initialize_session()
    if not st.session_state.authenticated:
        render_login()
    render_dashboard()


if __name__ == "__main__":
    main()
