"""
app.py — DataSense QC Engine — Streamlit UI
Run: streamlit run app.py
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__) or "."))

import io
from datetime import datetime

import streamlit as st
import pandas as pd

from ui.sidebar import render_sidebar, init_state
from ui.settings import get_theme_css, init_settings
from ui.onboarding import render_onboarding
from ui.tabs import qc_tab, eda_tab, logic_tab, straightlining_tab, data_tab, verbatim_tab

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="DataSense — QC Engine",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── PWA manifest (enables "Install as app" in Chrome) ─────────────────────────
st.markdown(
    '<link rel="manifest" href="/app/static/manifest.json">'
    '<meta name="mobile-web-app-capable" content="yes">'
    '<meta name="apple-mobile-web-app-capable" content="yes">'
    '<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">'
    '<meta name="theme-color" content="#4af0a0">',
    unsafe_allow_html=True,
)

# ── Theme CSS ─────────────────────────────────────────────────────────────────
init_state()
init_settings()   # ensure ds_theme is in session_state before reading it
theme_key = st.session_state.get("ds_theme", "dark")
st.markdown(get_theme_css(theme_key), unsafe_allow_html=True)
st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Syne:wght@600;700;800&family=DM+Mono:wght@300;400;500&display=swap');
    html, body, [class*="css"]      { font-family: 'DM Mono', monospace; }
    h1, h2, h3, h4                  { font-family: 'Syne', sans-serif !important; }
    [data-testid="metric-container"] {
        background: var(--ds-surface); border: 1px solid var(--ds-border);
        border-radius: 6px; padding: 12px 16px;
    }
    [data-testid="metric-container"] label {
        font-size: 10px !important; letter-spacing: 0.1em;
        text-transform: uppercase; color: var(--ds-text2) !important;
    }
    [data-testid="metric-container"] [data-testid="stMetricValue"] {
        font-family: 'Syne', sans-serif !important; font-weight: 800 !important;
        font-size: 2rem !important; color: var(--ds-text) !important;
    }
    section[data-testid="stSidebar"] {
        background: var(--ds-surface); border-right: 1px solid var(--ds-border);
    }
    button[data-baseweb="tab"] {
        font-family: 'DM Mono', monospace !important; font-size: 11px !important;
        letter-spacing: 0.08em; text-transform: uppercase;
    }
    [data-testid="stDataFrame"]   { border: 1px solid var(--ds-border); border-radius: 6px; }
    .stButton > button            { font-family: 'DM Mono', monospace !important;
                                    font-size: 11px !important; border-radius: 6px !important; }
    div[data-testid="stExpander"] { border: 1px solid var(--ds-border) !important;
                                    border-radius: 6px !important; }
    </style>
    """,
    unsafe_allow_html=True,
)

# ── Sidebar ───────────────────────────────────────────────────────────────────
render_sidebar()

# ── Onboarding ────────────────────────────────────────────────────────────────
render_onboarding()

# ── Landing screen ────────────────────────────────────────────────────────────
if st.session_state.df_clean is None:
    st.markdown(
        """
        <div style="text-align:center;padding:80px 40px;">
            <h1 style="font-size:2.8rem;font-weight:800;">DataSense</h1>
            <p style="color:var(--ds-text2);margin-top:12px;line-height:1.8;">
                Upload a CSV or Excel file in the sidebar to run automated quality control,<br>
                exploratory analysis, and generate a structured report.
            </p>
            <div style="margin-top:40px;display:flex;justify-content:center;gap:20px;flex-wrap:wrap;">
        """ + "".join([
            f'<div style="background:var(--ds-surface);border:1px solid var(--ds-border);'
            f'border-radius:8px;padding:18px 22px;width:160px;">'
            f'<div style="font-size:1.3rem;">{ic}</div>'
            f'<div style="font-family:Syne,sans-serif;font-weight:700;margin-top:6px;font-size:12px;">{tt}</div>'
            f'<div style="font-size:10px;color:var(--ds-text2);margin-top:4px;">{dd}</div></div>'
            for ic, tt, dd in [
                ("🔍", "Missing Values",  "Per-column rates"),
                ("📐", "Range Checks",    "Outlier detection"),
                ("🔗", "Logic Rules",     "Multi-condition IF/THEN"),
                ("📋", "Straightlining",  "Repeated answer detection"),
                ("💬", "Verbatim QC",     "LLM quality scoring"),
                ("🕵️", "Fabrication",    "Sequence & variance"),
            ]
        ]) + "</div></div>",
        unsafe_allow_html=True,
    )
    st.stop()


df       = st.session_state.df_clean
results  = st.session_state.qc_results
filename = st.session_state.filename


# ── Report builder ────────────────────────────────────────────────────────────
def build_report(df_clean: pd.DataFrame, qc_results: list) -> io.BytesIO:
    out = io.BytesIO()
    with pd.ExcelWriter(out, engine="openpyxl") as writer:
        pd.DataFrame([r.summary() for r in qc_results]).to_excel(
            writer, sheet_name="QC Summary", index=False)
        frames = [
            r.flagged_rows.assign(_qc_check=r.check_name, _severity=r.severity)
            for r in qc_results if r.flag_count > 0
        ]
        if frames:
            pd.concat(frames, ignore_index=True).to_excel(
                writer, sheet_name="Flagged Records", index=False)
        nc = df_clean.select_dtypes(include="number").columns
        if len(nc):
            df_clean[nc].describe().T.to_excel(writer, sheet_name="EDA Numeric")
        df_clean.head(500).to_excel(writer, sheet_name="Clean Data (500 rows)", index=False)
    out.seek(0)
    return out


# ── Header ────────────────────────────────────────────────────────────────────
h1, h2 = st.columns([5, 1])
with h1:
    st.markdown(f"### {filename}")
    st.caption(
        f"{len(df):,} rows · {len(df.columns)} columns · "
        f"Last run: {datetime.now().strftime('%H:%M:%S')}"
    )
with h2:
    st.download_button(
        "↓ Report",
        data=build_report(df, results),
        file_name=f"QC_{filename.rsplit('.', 1)[0]}_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True,
        type="primary",
    )

st.divider()

# ── Tabs ──────────────────────────────────────────────────────────────────────
tab_qc, tab_logic, tab_sl, tab_verb, tab_int, tab_eda, tab_data, tab_cfg = st.tabs([
    "QC Report", "Logic", "Straightlining", "Verbatim",
    "Interviewers", "EDA", "Data", "Config",
])

with tab_qc:
    qc_tab.render(df, results)

with tab_logic:
    logic_tab.render(df, results)

with tab_sl:
    straightlining_tab.render(df, results)

with tab_verb:
    verbatim_tab.render(df, results)

# ── Interviewers tab (inline — no standalone ui module yet) ───────────────────
with tab_int:
    st.markdown("#### Interviewer Analysis")

    dur_r  = next((r for r in results if r.check_name == "interviewer_duration_check"),    None)
    prod_r = next((r for r in results if r.check_name == "interviewer_productivity_check"), None)
    fab_r  = next((r for r in results if r.check_name == "fabrication_check"),              None)

    if not any([dur_r, prod_r, fab_r]):
        st.info("Enable interviewer checks in the sidebar and re-run QC.")
    else:
        if dur_r and dur_r.flag_count > 0:
            st.markdown("##### Duration anomalies")
            meta = dur_r.metadata
            c1, c2, c3 = st.columns(3)
            c1.metric("Outlier interviewers", meta.get("outlier_interviewers", 0))
            c2.metric("Too fast",             meta.get("too_fast", 0))
            c3.metric("Too slow",             meta.get("too_slow", 0))
            show = [c for c in dur_r.flagged_rows.columns if not c.startswith("_")]
            st.dataframe(
                dur_r.flagged_rows[show].drop_duplicates(),
                width="stretch", hide_index=True,
            )
        elif dur_r:
            st.success("Duration check passed — no outlier interviewers.")

        if prod_r and prod_r.flag_count > 0:
            st.markdown("##### Productivity outliers")
            meta = prod_r.metadata
            c1, c2, c3 = st.columns(3)
            c1.metric("Outlier interviewers", meta.get("outlier_interviewers", 0))
            c2.metric("Unusually high",       meta.get("unusually_high", 0))
            c3.metric("Unusually low",        meta.get("unusually_low",  0))
            show = [c for c in prod_r.flagged_rows.columns if not c.startswith("_")]
            st.dataframe(
                prod_r.flagged_rows[show].drop_duplicates(),
                width="stretch", hide_index=True,
            )
        elif prod_r:
            st.success("Productivity check passed — no outlier interviewers.")

        if fab_r and fab_r.flag_count > 0:
            st.markdown("##### Fabrication flags")
            show = [c for c in fab_r.flagged_rows.columns if not c.startswith("_")]
            st.dataframe(
                fab_r.flagged_rows[show].head(100),
                width="stretch", hide_index=True,
            )
            st.json(fab_r.metadata, expanded=False)
        elif fab_r:
            st.success("Fabrication check passed — no suspicious patterns detected.")

with tab_eda:
    eda_tab.render(df, results)

with tab_data:
    data_tab.render(df)

with tab_cfg:
    st.markdown("#### Active Config")
    st.json(st.session_state.rules_config)
    st.markdown("#### Custom Logic Rules")
    if st.session_state.custom_logic_rules:
        st.json(st.session_state.custom_logic_rules)
    else:
        st.caption("No custom logic rules added yet.")
