from __future__ import annotations

from datetime import datetime

import streamlit as st

from email_verifier.io import (
    ColumnMapping,
    get_default_column_index,
    infer_column,
    read_uploaded_table,
)
from email_verifier.processor import VerificationOptions, process_dataframe


st.set_page_config(page_title="Email Verifier", page_icon="@", layout="wide")


def render_app() -> None:
    st.title("Email Verifier")

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

    uploaded_file = st.file_uploader("Upload CSV or XLSX", type=["csv", "xlsx"])
    if uploaded_file is None:
        return

    try:
        dataframe = read_uploaded_table(uploaded_file)
    except ValueError as exc:
        st.error(str(exc))
        return

    columns = list(dataframe.columns)
    email_guess = infer_column(columns, "email")
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

    st.dataframe(dataframe.head(25), width='stretch', hide_index=True)

    if not email_column:
        st.error("Select an email column before verification.")
        return

    run_clicked = st.button("Verify emails", type="primary")
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

    def update_progress(done: int, total: int) -> None:
        progress_bar.progress(done / total if total else 1.0)
        status_text.write(f"Verified {done} of {total} rows")

    try:
        result = process_dataframe(
            dataframe,
            mapping=mapping,
            options=options,
            progress_callback=update_progress,
        )
    except ValueError as exc:
        st.error(str(exc))
        return
    except Exception as exc:  # pragma: no cover - last line of defense for UI clarity.
        st.error(f"Verification failed: {exc}")
        return

    status_text.write(f"Verified {len(result)} rows")
    st.success("Verification complete.")
    st.dataframe(result, width='stretch', hide_index=True)

    csv_bytes = result.to_csv(index=False).encode("utf-8")
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    st.download_button(
        "Download CSV",
        data=csv_bytes,
        file_name=f"email_verification_results_{timestamp}.csv",
        mime="text/csv",
    )


if __name__ == "__main__":
    render_app()
