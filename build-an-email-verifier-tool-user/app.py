from __future__ import annotations

from io import BytesIO

import pandas as pd
import streamlit as st
import openpyxl  # noqa: F401 (required by pd.ExcelWriter)

from email_verifier.new_verifier import verify_email, clean_domain

st.set_page_config(page_title="Email Verifier", page_icon="@", layout="centered")

OUTPUT_COLUMNS = [
    "Original Email",
    "Normalized Email",
    "Email Domain",
    "Company Domain",
    "MX Status",
    "Email Provider",
    "Public Email",
    "Disposable Email",
    "Role Based Email",
    "Company Domain Match",
    "Verification Status",
    "Verification Score",
    "Notes",
]


def render_app() -> None:
    st.title("Email Verifier")
    st.markdown("Upload your file and verify emails accurately.")

    uploaded_file = st.file_uploader("Choose a CSV or Excel file", type=["csv", "xlsx"])

    if uploaded_file is None:
        return

    try:
        if uploaded_file.name.endswith(".csv"):
            df = pd.read_csv(uploaded_file, dtype=str, keep_default_na=False)
        else:
            df = pd.read_excel(uploaded_file, dtype=str, keep_default_na=False)
    except Exception as e:
        st.error(f"Failed to read file: {e}")
        return

    df = df.fillna("").astype(str)
    columns = list(df.columns)

    st.subheader("File Preview")
    st.dataframe(df.head(10), hide_index=True, use_container_width=True)

    st.subheader("Column Selection")
    email_col = st.selectbox("Email column *", columns, index=_guess_email_column(columns))
    company_col = st.selectbox(
        "Company domain column (optional)", [""] + columns, index=0
    )

    if st.button("Verify Emails", type="primary"):
        total = len(df)
        if total == 0:
            st.warning("The file is empty.")
            return

        progress_bar = st.progress(0)
        status_text = st.empty()
        results = []

        for idx, row in df.iterrows():
            email = str(row.get(email_col, "")).strip()
            company_domain_raw = (
                str(row.get(company_col, "")).strip()
                if company_col
                else None
            )
            status_text.text(f"Verifying {idx + 1} of {total}: {email or '(empty)'}")
            result = verify_email(email, company_domain_raw)
            results.append(result)
            progress_bar.progress((idx + 1) / total)

        result_df = pd.DataFrame(results, columns=OUTPUT_COLUMNS)
        status_text.success(f"Verification complete. {total} emails processed.")

        st.subheader("Results")
        st.dataframe(result_df, hide_index=True, use_container_width=True)

        st.subheader("Download")
        c1, c2 = st.columns(2)

        excel_buf = BytesIO()
        with pd.ExcelWriter(excel_buf, engine="openpyxl") as writer:
            result_df.to_excel(writer, index=False, sheet_name="Results")
        excel_bytes = excel_buf.getvalue()

        with c1:
            st.download_button(
                "Download Excel",
                data=excel_bytes,
                file_name="email_verification_results.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
            )
        with c2:
            st.download_button(
                "Download CSV",
                data=result_df.to_csv(index=False).encode("utf-8"),
                file_name="email_verification_results.csv",
                mime="text/csv",
                use_container_width=True,
            )


def _guess_email_column(columns: list[str]) -> int:
    lower = [c.strip().lower() for c in columns]
    for keyword in ("email", "e-mail", "mail", "email address"):
        if keyword in lower:
            return lower.index(keyword)
    return 0


if __name__ == "__main__":
    render_app()
