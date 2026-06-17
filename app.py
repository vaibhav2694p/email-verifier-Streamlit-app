from __future__ import annotations

from datetime import datetime

import pandas as pd
import streamlit as st

from email_verifier.enhanced_verifier import verify_single_email
from email_verifier.export_utils import (
    dataframe_to_csv_bytes,
    dataframe_to_pdf_bytes,
    dataframe_to_xlsx_bytes,
    dataframe_valid_xlsx_bytes,
    dataframe_risky_xlsx_bytes,
    dataframe_invalid_xlsx_bytes,
)
from email_verifier.io import (
    ColumnMapping,
    get_default_column_index,
    infer_column,
    read_uploaded_table,
)
from email_verifier.processor import VerificationOptions, process_dataframe

st.set_page_config(page_title="Email Verifier", page_icon="@", layout="wide")


def render_single_verification() -> None:
    st.subheader("Real-Time Email Verification")
    email_input = st.text_input(
        "Enter an email address to verify",
        placeholder="e.g. name@company.com",
    )

    if not email_input:
        return

    col1, col2 = st.columns([1, 5])
    with col1:
        verify_clicked = st.button("Verify Email", type="primary")
    with col2:
        st.caption("Performs format, domain, professional, and mailbox checks in real time.")

    if not verify_clicked:
        return

    with st.spinner("Verifying email..."):
        result = verify_single_email(email_input)

    st.markdown("---")
    st.markdown(f"### Email Verification Results")
    st.markdown(f"📧 **Email:** `{result.email}`")

    overall_icon = "✅" if result.overall_valid else "❌"
    overall_color = "green" if result.overall_valid else "red"
    st.markdown(
        f"### {overall_icon} Overall Status: "
        f"<span style='color:{overall_color}'>"
        f"{'VALID' if result.overall_valid else 'INVALID'}</span>",
        unsafe_allow_html=True,
    )

    st.markdown("━━━━━━━━━━━━━━━━━━━━")

    checks = [
        ("Format", result.format_check),
        ("Professional", result.professional_check),
        ("Domain Status", result.domain_check),
        ("Mailbox", result.mailbox_check),
    ]

    for label, check in checks:
        icon = "✅" if check.valid else ("⚠️" if "Unable" in check.status else "❌")
        status_color = "green" if check.valid else ("orange" if "Unable" in check.status else "red")
        st.markdown(
            f"{icon} **{label}**  \n"
            f"Status: <span style='color:{status_color}'>{check.status}</span>  \n"
            f"{check.details}",
            unsafe_allow_html=True,
        )
        st.markdown("")

    st.markdown("━━━━━━━━━━━━━━━━━━━━")

    col_a, col_b, col_c = st.columns(3)
    with col_a:
        st.markdown(f"**Verification Date:** {result.verification_date}")
    with col_b:
        st.markdown(f"**Verification Time:** {result.verification_time}")
    with col_c:
        r = result.result
        if r == "Deliverable":
            st.markdown(f"**Result:** 🟢 {r}")
        elif r == "Risky":
            st.markdown(f"**Result:** 🟡 {r}")
        else:
            st.markdown(f"**Result:** 🔴 {r}")

    st.markdown("")
    if result.overall_valid:
        st.success("🟢 Safe to Send Emails")
    elif result.result == "Risky":
        st.warning("🟡 Risky - Proceed with Caution")
    else:
        st.error("🔴 Undeliverable - Do not send")

    st.markdown("---")
    st.markdown("### Advanced Details")
    tabs = st.tabs(["Name Detection", "Domain Info", "Provider Info", "Score Breakdown"])

    with tabs[0]:
        st.markdown(f"**First Name:** {result.first_name or 'N/A'} {'✓' if result.first_name else ''}")
        st.markdown(f"**Last Name:** {result.last_name or 'N/A'} {'✓' if result.last_name else ''}")
        st.markdown(f"**Full Name:** {result.full_name or 'N/A'}")
        role_str = (
            "⚠️ Yes - This appears to be a generic/role account"
            if result.role_account
            else "✅ No - This is not a role account"
        )
        st.markdown(f"**Role Account:** {role_str}")

    with tabs[1]:
        st.markdown(f"**Domain:** `{result.domain}`")
        mx_str = "✅ Available ✓" if result.mx_records_available else "❌ Not Available"
        st.markdown(f"**MX Records:** {mx_str}")
        catch_all_str = (
            "⚠️ Yes - Domain accepts all emails"
            if result.catch_all is True
            else ("✅ No" if result.catch_all is False else "N/A")
        )
        st.markdown(f"**Catch-All:** {catch_all_str}")

    with tabs[2]:
        provider_str = "🏢 Business" if result.provider_type == "Business" else "📧 Free Email Provider"
        st.markdown(f"**Provider Type:** {provider_str}")
        disposable_str = "❌ Yes - Disposable/temporary" if result.disposable_email else "✅ No ✓"
        st.markdown(f"**Disposable Email:** {disposable_str}")

    with tabs[3]:
        score_color = "green" if result.score >= 70 else ("orange" if result.score >= 40 else "red")
        st.markdown(
            f"### <span style='color:{score_color}'>{result.score}/100</span>",
            unsafe_allow_html=True,
        )
        st.markdown(f"- Format: {25 if result.format_check.valid else 0}/25")
        st.markdown(f"- Domain: {25 if result.domain_check.valid else 0}/25")
        st.markdown(f"- Professional: {20 if result.professional_check.valid else 0}/20")
        st.markdown(f"- Mailbox: {30 if result.mailbox_check.valid else 0}/30")


def render_bulk_verification() -> None:
    st.subheader("Bulk Email Verification Upload")
    st.markdown("Upload **CSV**, **XLSX**, or **TXT** files containing email addresses.")

    with st.sidebar:
        linkedin_scope_label = st.radio(
            "LinkedIn search",
            options=["Profiles only", "All LinkedIn"],
            index=0,
        )
        dns_timeout = st.slider(
            "DNS timeout",
            min_value=1.0,
            max_value=10.0,
            value=3.0,
            step=0.5,
        )

    uploaded_file = st.file_uploader(
        "Choose a file", type=["csv", "xlsx", "txt"]
    )
    if uploaded_file is None:
        return

    try:
        dataframe = read_uploaded_table(uploaded_file)
    except ValueError as exc:
        st.error(str(exc))
        return

    columns = list(dataframe.columns)
    email_guess = infer_column(columns, "email")
    use_simple_mode = columns == ["Email"]

    if use_simple_mode:
        email_column = "Email"
        name_column = ""
        company_column = ""
        st.info("TXT file detected — treating each line as an email address.")
    else:
        name_guess = infer_column(columns, "name")
        company_guess = infer_column(columns, "company")
        mapping_cols = st.columns(3)
        with mapping_cols[0]:
            email_column = st.selectbox(
                "Email column",
                options=[""] + columns,
                index=get_default_column_index(columns, email_guess),
            )
        with mapping_cols[1]:
            name_column = st.selectbox(
                "Name column",
                options=[""] + columns,
                index=get_default_column_index(columns, name_guess),
            )
        with mapping_cols[2]:
            company_column = st.selectbox(
                "Company column",
                options=[""] + columns,
                index=get_default_column_index(columns, company_guess),
            )

    st.dataframe(dataframe.head(25), width="stretch", hide_index=True)
    st.caption(f"Showing first 25 of {len(dataframe)} rows")

    if not email_column:
        st.error("Select an email column before verification.")
        return

    run_clicked = st.button("Verify Emails", type="primary")
    if not run_clicked:
        return

    mapping = ColumnMapping(
        email=email_column,
        name=name_column or None,
        company=company_column or None,
    )
    options = VerificationOptions(
        linkedin_scope="profiles" if linkedin_scope_label == "Profiles only" else "all",
        dns_timeout=dns_timeout,
    )

    progress_bar = st.progress(0)
    status_text = st.empty()
    results_container = st.container()

    def update_progress(done: int, total: int) -> None:
        progress_bar.progress(done / total if total else 1.0)
        status_text.write(f"Verified {done} of {total} rows")

    try:
        result_df = process_dataframe(
            dataframe,
            mapping=mapping,
            options=options,
            progress_callback=update_progress,
        )
    except ValueError as exc:
        st.error(str(exc))
        return
    except Exception as exc:
        st.error(f"Verification failed: {exc}")
        return

    status_text.write(f"Verified {len(result_df)} rows")
    st.success("Verification complete.")

    total = len(result_df)
    valid_count = int((result_df["Overall Status"] == "VALID").sum())
    risky_count = int((result_df["Overall Status"] == "RISKY").sum())
    invalid_count = int((result_df["Overall Status"] == "INVALID").sum())

    st.markdown("---")
    st.markdown("### Bulk Upload Summary")

    summary_cols = st.columns(4)
    with summary_cols[0]:
        st.metric("Total Emails", f"{total:,}")
    with summary_cols[1]:
        st.metric("Valid Emails", f"{valid_count:,}", delta_color="off")
        st.markdown(
            f"<p style='color:green; font-size:1.2rem; font-weight:bold;'"
            f">🟢 {valid_count:,}</p>",
            unsafe_allow_html=True,
        )
    with summary_cols[2]:
        st.metric("Risky Emails", f"{risky_count:,}", delta_color="off")
        st.markdown(
            f"<p style='color:orange; font-size:1.2rem; font-weight:bold;'"
            f">🟡 {risky_count:,}</p>",
            unsafe_allow_html=True,
        )
    with summary_cols[3]:
        st.metric("Invalid Emails", f"{invalid_count:,}", delta_color="off")
        st.markdown(
            f"<p style='color:red; font-size:1.2rem; font-weight:bold;'"
            f">🔴 {invalid_count:,}</p>",
            unsafe_allow_html=True,
        )

    st.markdown("---")
    st.markdown("### Detailed Results")

    def highlight_status(val: object) -> str:
        s = str(val)
        if s == "VALID":
            return "background-color: #d4edda; color: #155724"
        if s == "RISKY":
            return "background-color: #fff3cd; color: #856404"
        if s == "INVALID":
            return "background-color: #f8d7da; color: #721c24"
        if s in ("Valid", "Yes"):
            return "background-color: #d4edda; color: #155724"
        if s in ("Invalid", "N/A"):
            return "background-color: #f8d7da; color: #721c24"
        return ""

    styled_df = result_df.style.applymap(highlight_status, subset=[
        "Overall Status", "Format", "Professional Domain",
        "Domain Status", "Mailbox Status", "Disposable",
        "Role Account", "MX Record", "First Name", "Last Name",
    ])

    st.dataframe(styled_df, width="stretch", hide_index=True)

    st.markdown("---")
    st.markdown("### Per-Email Detailed View")

    email_list = result_df["Email Address"].tolist()
    selected_email = st.selectbox("Select an email to view details", options=email_list)
    if selected_email:
        row = result_df[result_df["Email Address"] == selected_email].iloc[0]
        overall = str(row.get("Overall Status", ""))

        if overall == "VALID":
            st.success(f"🟢 VALID — {selected_email}")
        elif overall == "RISKY":
            st.warning(f"🟡 RISKY — {selected_email}")
        else:
            st.error(f"🔴 INVALID — {selected_email}")

        detail_items = [
            ("First Name", "First Name", "green" if str(row.get("First Name")) != "Not Found" else "red"),
            ("Last Name", "Last Name", "green" if str(row.get("Last Name")) != "Not Found" else "red"),
            ("Format", "Format", "green" if str(row.get("Format")) == "Valid" else "red"),
            ("Domain Status", "Domain Status", "green" if str(row.get("Domain Status")) == "Valid" else "red"),
            ("Professional Domain", "Professional Domain", "green" if str(row.get("Professional Domain")) == "Valid" else "red"),
            ("Disposable", "Disposable", "red" if str(row.get("Disposable")) == "Yes" else "green"),
            ("Role Account", "Role Account", "red" if str(row.get("Role Account")) == "Yes" else "green"),
            ("MX Record", "MX Record", "green" if str(row.get("MX Record")) == "Valid" else "red"),
            ("Mailbox Status", "Mailbox Status", "green" if str(row.get("Mailbox Status")) == "Exists" else "red"),
            ("Catch-All", "Catch-All", "orange" if str(row.get("Catch-All")) == "Yes" else "green"),
            ("Company Website", "Company Website", "green" if str(row.get("Company Website")) != "Not Found" else "orange"),
        ]

        for label, key, color in detail_items:
            val = str(row.get(key, ""))
            icon_map = {"green": "✅", "red": "❌", "orange": "⚠️"}
            st.markdown(
                f"{icon_map[color]} **{label}:** "
                f"<span style='color:{color}'>{val}</span>",
                unsafe_allow_html=True,
            )

        st.markdown("")
        score_val = int(row.get("Email Score", 0))
        date_val = str(row.get("Verification Date", ""))
        smtp_val = str(row.get("SMTP Response", ""))

        col_sc, col_sm, col_dt = st.columns(3)
        with col_sc:
            score_color = "green" if score_val >= 70 else ("orange" if score_val >= 40 else "red")
            st.markdown(f"**Score:** <span style='color:{score_color}'>{score_val}/100</span>", unsafe_allow_html=True)
        with col_sm:
            st.markdown(f"**SMTP Response:** {smtp_val[:50]}")
        with col_dt:
            st.markdown(f"**Date:** {date_val}")

    st.markdown("---")
    st.markdown("### Export Options")
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    base = f"email_verification_report_{timestamp}"

    exp_tabs = st.tabs(["📥 Full Report", "📥 Filtered Exports"])

    with exp_tabs[0]:
        ec1, ec2, ec3 = st.columns(3)
        with ec1:
            csv_data = dataframe_to_csv_bytes(result_df)
            st.download_button(
                "📄 Download CSV",
                data=csv_data,
                file_name=f"{base}.csv",
                mime="text/csv",
                use_container_width=True,
            )
        with ec2:
            xlsx_data = dataframe_to_xlsx_bytes(result_df)
            st.download_button(
                "📗 Download Full Report (XLSX)",
                data=xlsx_data,
                file_name=f"{base}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
            )
        with ec3:
            try:
                pdf_data = dataframe_to_pdf_bytes(result_df)
                st.download_button(
                    "📕 Download PDF Report",
                    data=pdf_data,
                    file_name=f"{base}.pdf",
                    mime="application/pdf",
                    use_container_width=True,
                )
            except Exception as exc:
                st.error(f"PDF failed: {exc}")

    with exp_tabs[1]:
        fe1, fe2, fe3 = st.columns(3)
        has_valid = valid_count > 0
        has_risky = risky_count > 0
        has_invalid = invalid_count > 0
        with fe1:
            if has_valid:
                vx = dataframe_valid_xlsx_bytes(result_df)
                st.download_button(
                    "🟢 Valid Emails (XLSX)",
                    data=vx,
                    file_name=f"Valid_Emails_{timestamp}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True,
                )
            else:
                st.button("🟢 Valid Emails", disabled=True, use_container_width=True)
        with fe2:
            if has_risky:
                rx = dataframe_risky_xlsx_bytes(result_df)
                st.download_button(
                    "🟡 Risky Emails (XLSX)",
                    data=rx,
                    file_name=f"Risky_Emails_{timestamp}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True,
                )
            else:
                st.button("🟡 Risky Emails", disabled=True, use_container_width=True)
        with fe3:
            if has_invalid:
                ix = dataframe_invalid_xlsx_bytes(result_df)
                st.download_button(
                    "🔴 Invalid Emails (XLSX)",
                    data=ix,
                    file_name=f"Invalid_Emails_{timestamp}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True,
                )
            else:
                st.button("🔴 Invalid Emails", disabled=True, use_container_width=True)


def render_app() -> None:
    st.title("Email Verifier")

    tab1, tab2 = st.tabs(["🔍 Single Verification", "📊 Bulk Upload"])

    with tab1:
        render_single_verification()

    with tab2:
        render_bulk_verification()


if __name__ == "__main__":
    render_app()
