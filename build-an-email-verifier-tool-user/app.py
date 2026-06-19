from __future__ import annotations

from io import BytesIO

import pandas as pd
import streamlit as st
import openpyxl  # noqa: F401

from email_verifier.new_verifier import verify_email

st.set_page_config(page_title="Email Verifier", page_icon="@", layout="wide")

CSS = """
<style>
#MainMenu {visibility: hidden;}
footer {visibility: hidden;}
header {visibility: hidden;}

.stApp {
    background: #f6f7fb;
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
}

.main-title {
    font-size: 42px;
    font-weight: 800;
    color: #111827;
    margin-bottom: 4px;
    letter-spacing: -0.5px;
}

.subtitle {
    color: #6b7280;
    font-size: 16px;
    margin-bottom: 28px;
}

.card {
    background: white;
    padding: 24px;
    border-radius: 16px;
    box-shadow: 0 8px 24px rgba(15, 23, 42, 0.08);
    margin-bottom: 22px;
    border: 1px solid #eef2f7;
}

.metric-card {
    background: white;
    padding: 18px;
    border-radius: 14px;
    box-shadow: 0 6px 18px rgba(15, 23, 42, 0.06);
    border: 1px solid #eef2f7;
    text-align: center;
}

.metric-label {
    color: #6b7280;
    font-size: 13px;
    font-weight: 500;
    text-transform: uppercase;
    letter-spacing: 0.5px;
}

.metric-value {
    color: #111827;
    font-size: 28px;
    font-weight: 800;
    margin-top: 4px;
}

.stButton > button[kind="primary"] {
    background: #ff4b4b;
    color: white;
    border-radius: 12px;
    border: none;
    padding: 10px 22px;
    font-weight: 700;
    font-size: 15px;
    transition: background 0.2s;
}

.stButton > button[kind="primary"]:hover {
    background: #e63f3f;
    color: white;
}

.stButton > button:not([kind="primary"]) {
    border-radius: 12px;
    font-weight: 600;
    border: 1px solid #e5e7eb;
    background: white;
    color: #374151;
}

.stButton > button:not([kind="primary"]):hover {
    background: #f9fafb;
    border-color: #d1d5db;
}

.stDownloadButton > button {
    border-radius: 12px;
    font-weight: 700;
    padding: 10px 20px;
}

.stProgress > div > div > div > div {
    background: #ff4b4b;
    border-radius: 999px;
}

.stProgress > div > div > div {
    background: #eef2f7;
    border-radius: 999px;
    height: 8px;
}

.stSelectbox > div > div {
    border-radius: 10px;
    border: 1px solid #e5e7eb;
}

.stSelectbox > div > div:focus-within {
    border-color: #ff4b4b;
    box-shadow: 0 0 0 3px rgba(255, 75, 75, 0.15);
}

.stFileUploader > div {
    border-radius: 14px;
    border: 2px dashed #e5e7eb;
    background: #fafbfc;
    padding: 24px;
}

.stFileUploader > div:hover {
    border-color: #ff4b4b;
    background: #fff5f5;
}

.stFileUploader > div:focus-within {
    border-color: #ff4b4b;
    box-shadow: 0 0 0 3px rgba(255, 75, 75, 0.15);
}

.stFileUploader label {
    color: #374151 !important;
    font-weight: 600;
}

.stFileUploader small {
    color: #9ca3af !important;
}

.stDataFrame {
    border-radius: 12px;
    overflow: hidden;
    border: 1px solid #eef2f7;
}

[data-testid="stTable"] {
    border-radius: 12px;
    overflow: hidden;
}

.section-title {
    font-size: 18px;
    font-weight: 700;
    color: #111827;
    margin-bottom: 16px;
    display: flex;
    align-items: center;
    gap: 8px;
}

.status-badge {
    display: inline-block;
    padding: 4px 12px;
    border-radius: 999px;
    font-size: 12px;
    font-weight: 700;
    color: white;
    text-align: center;
    min-width: 90px;
}

.badge-verified { background: #16a34a; }
.badge-risky { background: #f59e0b; }
.badge-invalid { background: #dc2626; }
.badge-nomx { background: #6b7280; }

.upload-icon {
    font-size: 32px;
    margin-bottom: 12px;
}

.upload-text {
    color: #6b7280;
    font-size: 14px;
}

.result-row:hover {
    background: #fafbfc;
}
</style>
"""

STATUS_COLORS = {
    "Verified": "#16a34a",
    "Risky": "#f59e0b",
    "Invalid": "#dc2626",
    "No MX Found": "#6b7280",
    "NXDOMAIN": "#6b7280",
    "DNS error": "#6b7280",
    "DNS timeout": "#6b7280",
    "No domain": "#6b7280",
    "Timeout": "#6b7280",
    "Unreachable": "#6b7280",
    "Inactive": "#6b7280",
    "Active (No SSL)": "#f59e0b",
    "Error": "#dc2626",
}


def status_badge(status: str) -> str:
    color = STATUS_COLORS.get(status, "#6b7280")
    cls = ""
    if "Verified" in status:
        cls = "badge-verified"
    elif "Risky" in status:
        cls = "badge-risky"
    elif "Invalid" in status:
        cls = "badge-invalid"
    elif "No MX" in status or "NXDOMAIN" in status or "DNS" in status or "No domain" in status:
        cls = "badge-nomx"
    return f"<span class='status-badge {cls}' style='background:{color};'>{status}</span>"


def render_app() -> None:
    st.markdown(CSS, unsafe_allow_html=True)

    st.markdown('<h1 class="main-title">Email Verifier</h1>', unsafe_allow_html=True)
    st.markdown(
        '<p class="subtitle">Upload your email list and verify domains, MX records, providers, and website status.</p>',
        unsafe_allow_html=True,
    )

    uploaded_file = st.file_uploader(
        "Choose a CSV or Excel file",
        type=["csv", "xlsx"],
        label_visibility="collapsed",
    )

    if uploaded_file is None:
        st.markdown(
            """
            <div class="card" style="text-align: center; padding: 60px 24px;">
                <div class="upload-icon">📁</div>
                <p style="font-size: 18px; font-weight: 600; color: #111827; margin-bottom: 8px;">
                    Drag & drop your file here</p>
                <p class="upload-text">or click to browse</p>
                <p class="upload-text" style="margin-top: 16px;">Accepted formats: <strong>CSV</strong>, <strong>XLSX</strong></p>
            </div>
            """,
            unsafe_allow_html=True,
        )
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

    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown('<div class="section-title">📋 File Preview</div>', unsafe_allow_html=True)
    st.dataframe(df.head(10), hide_index=True, use_container_width=True)
    st.caption(f"Total rows: {len(df):,} • Columns: {len(columns)}")
    st.markdown('</div>', unsafe_allow_html=True)

    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown('<div class="section-title">⚙️ Column Selection</div>', unsafe_allow_html=True)

    col1, col2 = st.columns([2, 1])
    with col1:
        email_col = st.selectbox("Email column *", columns, index=_guess_email_column(columns))
    with col2:
        st.markdown("<br>", unsafe_allow_html=True)
        st.caption("Required • Select the column containing email addresses")

    verify_clicked = st.button("Verify Emails", type="primary", use_container_width=True)
    st.markdown('</div>', unsafe_allow_html=True)

    if not verify_clicked:
        return

    total = len(df)
    if total == 0:
        st.warning("The file is empty.")
        return

    progress_bar = st.progress(0)
    status_text = st.empty()
    results = []

    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown('<div class="section-title">🔄 Processing</div>', unsafe_allow_html=True)

    for idx, row in df.iterrows():
        email = str(row.get(email_col, "")).strip()
        status_text.text(f"Verifying {idx + 1} of {total}: {email or '(empty)'}")
        result = verify_email(email)
        results.append(result)
        progress_bar.progress((idx + 1) / total)

    result_df = pd.DataFrame(results)
    status_text.success(f"✅ Verification complete. {total} emails processed.")
    st.markdown('</div>', unsafe_allow_html=True)

    total_count = len(result_df)
    verified_count = int((result_df["Verification Status"] == "Verified").sum())
    risky_count = int((result_df["Verification Status"] == "Risky").sum())
    invalid_count = int((result_df["Verification Status"] == "Invalid").sum())

    st.markdown('<div class="section-title">📊 Summary</div>', unsafe_allow_html=True)
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-label">Total Emails</div>
            <div class="metric-value">{total_count:,}</div>
        </div>""", unsafe_allow_html=True)
    with c2:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-label" style="color: #16a34a;">Verified</div>
            <div class="metric-value" style="color: #16a34a;">{verified_count:,}</div>
        </div>""", unsafe_allow_html=True)
    with c3:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-label" style="color: #f59e0b;">Risky</div>
            <div class="metric-value" style="color: #f59e0b;">{risky_count:,}</div>
        </div>""", unsafe_allow_html=True)
    with c4:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-label" style="color: #dc2626;">Invalid</div>
            <div class="metric-value" style="color: #dc2626;">{invalid_count:,}</div>
        </div>""", unsafe_allow_html=True)

    st.markdown('<div class="section-title">📋 Results</div>', unsafe_allow_html=True)

    display_df = result_df.copy()
    display_df["Verification Status"] = display_df["Verification Status"].apply(status_badge)

    st.markdown(
        display_df.to_html(escape=False, index=False),
        unsafe_allow_html=True,
    )

    st.markdown('<div class="section-title">💾 Download</div>', unsafe_allow_html=True)
    c1, c2 = st.columns(2)

    excel_buf = BytesIO()
    with pd.ExcelWriter(excel_buf, engine="openpyxl") as writer:
        result_df.to_excel(writer, index=False, sheet_name="Results")
    excel_bytes = excel_buf.getvalue()

    with c1:
        st.download_button(
            "📗 Download Excel",
            data=excel_bytes,
            file_name="email_verification_results.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
        )
    with c2:
        st.download_button(
            "📄 Download CSV",
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
