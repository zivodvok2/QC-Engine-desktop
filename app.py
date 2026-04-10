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

import json
from pathlib import Path

from ui.sidebar import render_sidebar, init_state
from ui.settings import get_theme_css, init_settings
from ui.onboarding import render_onboarding
from ui.tabs import (qc_tab, eda_tab, logic_tab, straightlining_tab,
                     data_tab, verbatim_tab, interviewer_tab, compare_tab,
                     batch_tab)

PROFILES_DIR = Path(__file__).parent / "profiles"

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

    /* ── Base typography ──────────────────────────────────────────────── */
    html, body, [class*="css"]      { font-family: 'DM Mono', monospace; }
    h1, h2, h3, h4                  { font-family: 'Syne', sans-serif !important; }

    /* ── Metric cards ─────────────────────────────────────────────────── */
    [data-testid="metric-container"] {
        background: var(--ds-surface); border: 1px solid var(--ds-border);
        border-radius: 8px; padding: 14px 18px;
    }
    [data-testid="metric-container"] label {
        font-size: 10px !important; letter-spacing: 0.1em;
        text-transform: uppercase; color: var(--ds-text2) !important;
    }
    [data-testid="metric-container"] [data-testid="stMetricValue"] {
        font-family: 'Syne', sans-serif !important; font-weight: 800 !important;
        font-size: 2rem !important; color: var(--ds-text) !important;
    }

    /* ── Sidebar ──────────────────────────────────────────────────────── */
    section[data-testid="stSidebar"] {
        background: var(--ds-surface); border-right: 1px solid var(--ds-border);
    }

    /* ── DataFrames ───────────────────────────────────────────────────── */
    [data-testid="stDataFrame"]     { border: 1px solid var(--ds-border); border-radius: 8px; }

    /* ── Expanders ────────────────────────────────────────────────────── */
    div[data-testid="stExpander"]   { border: 1px solid var(--ds-border) !important;
                                      border-radius: 8px !important; }

    /* ── Button system ────────────────────────────────────────────────── */
    /* Base for all buttons */
    .stButton > button,
    [data-testid="stDownloadButton"] > button {
        font-family: 'DM Mono', monospace !important;
        font-size: 11px !important;
        letter-spacing: 0.06em !important;
        border-radius: 6px !important;
        height: 36px !important;
        padding: 0 14px !important;
        transition: all 0.15s ease !important;
        cursor: pointer !important;
    }

    /* Primary buttons — accent fill */
    [data-testid="baseButton-primary"] {
        background-color: var(--ds-accent) !important;
        color: #0b0c0f !important;
        border: none !important;
        font-weight: 600 !important;
        box-shadow: 0 2px 10px rgba(74,240,160,0.18) !important;
    }
    [data-testid="baseButton-primary"]:hover {
        opacity: 0.88 !important;
        box-shadow: 0 4px 16px rgba(74,240,160,0.28) !important;
        transform: translateY(-1px) !important;
    }
    [data-testid="baseButton-primary"]:active {
        transform: translateY(0px) !important;
        opacity: 1 !important;
    }

    /* Secondary buttons — ghost/outlined */
    [data-testid="baseButton-secondary"] {
        background-color: transparent !important;
        color: var(--ds-text) !important;
        border: 1px solid var(--ds-border) !important;
        font-weight: 400 !important;
    }
    [data-testid="baseButton-secondary"]:hover {
        border-color: var(--ds-text2) !important;
        background-color: var(--ds-surface) !important;
        color: var(--ds-text) !important;
    }

    /* Download buttons — outlined with accent hover */
    [data-testid="stDownloadButton"] > button {
        background-color: var(--ds-surface) !important;
        color: var(--ds-text) !important;
        border: 1px solid var(--ds-border) !important;
        font-weight: 500 !important;
    }
    [data-testid="stDownloadButton"] > button:hover {
        border-color: var(--ds-accent) !important;
        color: var(--ds-accent) !important;
        background-color: rgba(74,240,160,0.06) !important;
    }

    /* Primary download buttons */
    [data-testid="stDownloadButton"] > button[kind="primary"] {
        background-color: var(--ds-accent) !important;
        color: #0b0c0f !important;
        border: none !important;
        font-weight: 600 !important;
        box-shadow: 0 2px 10px rgba(74,240,160,0.18) !important;
    }
    [data-testid="stDownloadButton"] > button[kind="primary"]:hover {
        opacity: 0.88 !important;
        box-shadow: 0 4px 16px rgba(74,240,160,0.28) !important;
    }

    /* ── Tab bar ──────────────────────────────────────────────────────── */
    button[data-baseweb="tab"] {
        font-family: 'DM Mono', monospace !important;
        font-size: 11px !important;
        letter-spacing: 0.07em !important;
        text-transform: uppercase !important;
        padding: 8px 14px !important;
        border-radius: 0 !important;
        transition: color 0.15s ease !important;
    }
    button[data-baseweb="tab"]:hover {
        background-color: var(--ds-surface) !important;
    }
    /* Active tab indicator */
    [data-testid="stTabs"] [data-baseweb="tab-highlight"] {
        background-color: var(--ds-accent) !important;
        height: 2px !important;
        border-radius: 2px 2px 0 0 !important;
    }
    [data-testid="stTabs"] [data-baseweb="tab-border"] {
        background-color: var(--ds-border) !important;
    }
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
    # Hero
    st.markdown(
        """
        <div style="text-align:center;padding:72px 40px 48px;">
            <div style="display:inline-flex;align-items:center;justify-content:center;
                        width:52px;height:52px;background:var(--ds-accent);
                        border-radius:12px;margin-bottom:20px;">
                <svg width="26" height="26" viewBox="0 0 24 24" fill="none"
                     stroke="#0b0c0f" stroke-width="2.5" stroke-linecap="round">
                    <polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/>
                </svg>
            </div>
            <h1 style="font-size:2.6rem;font-weight:800;margin:0 0 12px;">DataSense</h1>
            <p style="color:var(--ds-text2);font-size:14px;line-height:1.8;
                      max-width:480px;margin:0 auto 8px;">
                Upload a survey dataset in the sidebar to run automated quality control,
                exploratory analysis, and generate a structured report.
            </p>
            <p style="color:var(--ds-text2);font-size:12px;">
                Supports <strong style="color:var(--ds-text)">CSV</strong>,
                <strong style="color:var(--ds-text)">Excel (.xlsx/.xls)</strong>,
                and <strong style="color:var(--ds-text)">SPSS (.sav)</strong>
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Feature cards — 3-column grid
    features = [
        ("🔍", "Missing Values",   "Per-column flag rates with configurable thresholds"),
        ("📐", "Range & Duration", "Outlier detection and interview length bounds"),
        ("🔗", "Logic Rules",      "Multi-condition IF/THEN constraint checks"),
        ("📋", "Straightlining",   "Grid question repeated-answer detection"),
        ("💬", "Verbatim QC",      "LLM-powered grammar, coherence & relevance scoring"),
        ("🕵️", "Fabrication",     "Sequential ID and low-variance response detection"),
        ("👥", "Interviewers",     "Duration anomalies and productivity outliers"),
        ("📊", "EDA & Charts",     "Interactive charts with AI chart builder"),
        ("📁", "Batch Processing", "QC multiple files at once with one config"),
    ]

    cols = st.columns(3)
    for i, (ic, tt, dd) in enumerate(features):
        with cols[i % 3]:
            st.markdown(
                f'<div style="background:var(--ds-surface);border:1px solid var(--ds-border);'
                f'border-radius:10px;padding:20px;margin-bottom:12px;'
                f'transition:border-color 0.2s;">'
                f'<div style="font-size:1.4rem;margin-bottom:10px;">{ic}</div>'
                f'<div style="font-family:Syne,sans-serif;font-weight:700;'
                f'font-size:13px;color:var(--ds-text);margin-bottom:6px;">{tt}</div>'
                f'<div style="font-size:11px;color:var(--ds-text2);line-height:1.5;">{dd}</div>'
                f'</div>',
                unsafe_allow_html=True,
            )

    st.markdown(
        '<p style="text-align:center;color:var(--ds-text2);font-size:11px;'
        'letter-spacing:0.06em;text-transform:uppercase;margin-top:8px;">'
        '← Upload a file in the sidebar to get started</p>',
        unsafe_allow_html=True,
    )
    st.stop()


df       = st.session_state.df_clean
results  = st.session_state.qc_results
filename = st.session_state.filename


# ── Report builders ───────────────────────────────────────────────────────────
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


def build_pdf_report(filename: str, df: pd.DataFrame, qc_results: list) -> bytes:
    """Generate a formatted HTML report (open in browser, File → Print → Save as PDF)."""
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    total_flags = sum(r.flag_count for r in qc_results)
    crits  = sum(1 for r in qc_results if r.severity == "critical" and r.flag_count > 0)
    warns  = sum(1 for r in qc_results if r.severity == "warning"  and r.flag_count > 0)

    summary_rows = "".join(
        f"<tr><td>{r.check_name}</td><td>{r.severity}</td><td>{r.flag_count:,}</td>"
        f"<td>{r.flag_count / max(len(df), 1) * 100:.1f}%</td></tr>"
        for r in sorted(qc_results, key=lambda x: -x.flag_count)
    )

    flagged_sections = ""
    for r in [x for x in qc_results if x.flag_count > 0]:
        show = [c for c in r.flagged_rows.columns if not c.startswith("_")]
        sample = r.flagged_rows[show].head(50)
        th = "".join(f"<th>{c}</th>" for c in sample.columns)
        tbody = "".join(
            "<tr>" + "".join(f"<td>{v}</td>" for v in row) + "</tr>"
            for row in sample.itertuples(index=False)
        )
        sev_color = {"critical": "#f04a6a", "warning": "#f0c04a", "info": "#4a9ef0"}.get(r.severity, "#888")
        flagged_sections += f"""
        <h3 style="color:{sev_color};border-left:4px solid {sev_color};padding-left:10px;margin-top:32px;">
            {r.check_name} — {r.flag_count:,} flags
        </h3>
        <table><thead><tr>{th}</tr></thead><tbody>{tbody}</tbody></table>
        """

    html = f"""<!DOCTYPE html><html><head><meta charset="utf-8">
    <title>DataSense QC Report — {filename}</title>
    <style>
        body {{ font-family: 'DM Mono', monospace, sans-serif; margin: 40px; color: #1a1a2e; font-size: 13px; }}
        h1 {{ font-size: 28px; margin-bottom: 4px; }}
        h2 {{ font-size: 16px; color: #555; border-bottom: 1px solid #ddd; padding-bottom: 8px; margin-top: 32px; }}
        h3 {{ font-size: 14px; margin-bottom: 8px; }}
        .meta {{ color: #888; font-size: 12px; margin-bottom: 32px; }}
        .cards {{ display: flex; gap: 20px; flex-wrap: wrap; margin: 20px 0; }}
        .card {{ background: #f5f7ff; border: 1px solid #dde; border-radius: 8px; padding: 16px 24px; min-width: 120px; }}
        .card .val {{ font-size: 28px; font-weight: 800; }}
        .card .lbl {{ font-size: 11px; color: #888; text-transform: uppercase; letter-spacing: 0.08em; }}
        table {{ border-collapse: collapse; width: 100%; margin-top: 8px; font-size: 12px; }}
        th {{ background: #f0f2ff; text-align: left; padding: 6px 10px; border: 1px solid #dde; }}
        td {{ padding: 5px 10px; border: 1px solid #eee; word-break: break-word; max-width: 300px; }}
        tr:nth-child(even) td {{ background: #fafafa; }}
        @media print {{ .no-print {{ display: none; }} }}
    </style></head><body>
    <h1>DataSense QC Report</h1>
    <div class="meta">{filename} &nbsp;·&nbsp; {len(df):,} rows · {len(df.columns)} columns &nbsp;·&nbsp; Generated {now}</div>

    <div class="cards">
        <div class="card"><div class="val">{len(qc_results)}</div><div class="lbl">Checks run</div></div>
        <div class="card"><div class="val" style="color:#f04a6a">{total_flags:,}</div><div class="lbl">Total flags</div></div>
        <div class="card"><div class="val" style="color:#f04a6a">{crits}</div><div class="lbl">Critical</div></div>
        <div class="card"><div class="val" style="color:#f0c04a">{warns}</div><div class="lbl">Warnings</div></div>
    </div>

    <h2>Check Summary</h2>
    <table><thead><tr><th>Check</th><th>Severity</th><th>Flags</th><th>Flag Rate</th></tr></thead>
    <tbody>{summary_rows}</tbody></table>

    <h2>Flagged Records</h2>
    {flagged_sections if flagged_sections else "<p style='color:#888'>No flags — dataset passed all checks.</p>"}

    </body></html>"""
    return html.encode("utf-8")


# ── Header ────────────────────────────────────────────────────────────────────
_total_flags = sum(r.flag_count for r in results)
_crits        = sum(1 for r in results if r.severity == "critical" and r.flag_count > 0)
_warns        = sum(1 for r in results if r.severity == "warning"  and r.flag_count > 0)

# Build status badge HTML
if _crits > 0:
    _badge = (
        f'<span style="background:rgba(240,74,106,0.12);color:#f04a6a;'
        f'border:1px solid rgba(240,74,106,0.3);border-radius:20px;'
        f'padding:3px 10px;font-size:11px;font-weight:600;letter-spacing:0.04em;">'
        f'🔴 {_crits} critical</span>'
    )
elif _warns > 0:
    _badge = (
        f'<span style="background:rgba(240,192,74,0.12);color:#f0c04a;'
        f'border:1px solid rgba(240,192,74,0.3);border-radius:20px;'
        f'padding:3px 10px;font-size:11px;font-weight:600;letter-spacing:0.04em;">'
        f'🟡 {_warns} warnings</span>'
    )
else:
    _badge = (
        '<span style="background:rgba(74,240,160,0.10);color:#4af0a0;'
        'border:1px solid rgba(74,240,160,0.25);border-radius:20px;'
        'padding:3px 10px;font-size:11px;font-weight:600;letter-spacing:0.04em;">'
        '✓ Clean</span>'
    )

h1, h2, h3, h4 = st.columns([5, 1, 1, 1])
with h1:
    st.markdown(
        f'<div style="display:flex;align-items:center;gap:12px;flex-wrap:wrap;">'
        f'<span style="font-family:Syne,sans-serif;font-weight:700;font-size:1.1rem;'
        f'color:var(--ds-text);">{filename}</span>'
        f'{_badge}</div>'
        f'<div style="margin-top:4px;font-size:11px;color:var(--ds-text2);'
        f'letter-spacing:0.04em;">'
        f'{len(df):,} rows &nbsp;·&nbsp; {len(df.columns)} columns &nbsp;·&nbsp; '
        f'{len(results)} checks &nbsp;·&nbsp; {_total_flags:,} flags &nbsp;·&nbsp; '
        f'{datetime.now().strftime("%H:%M")}</div>',
        unsafe_allow_html=True,
    )
with h2:
    st.download_button(
        "↓ Export Excel",
        data=build_report(df, results),
        file_name=f"QC_{filename.rsplit('.', 1)[0]}_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True,
        type="primary",
    )
with h3:
    st.download_button(
        "↓ HTML Report",
        data=build_pdf_report(filename, df, results),
        file_name=f"QC_{filename.rsplit('.', 1)[0]}_{datetime.now().strftime('%Y%m%d_%H%M')}.html",
        mime="text/html",
        use_container_width=True,
        help="Opens in browser — use File → Print → Save as PDF",
    )
with h4:
    if st.button("⇄ Compare", use_container_width=True,
                 help="Compare this dataset against another wave"):
        st.session_state["_open_compare"] = True
    if st.button("📁 Batch", use_container_width=True,
                 help="View batch QC results"):
        st.session_state["_open_batch"] = True

st.divider()


# ── Dialogs ───────────────────────────────────────────────────────────────────
@st.dialog("Wave Comparison", width="large")
def _compare_dialog():
    compare_tab.render(df)


@st.dialog("Batch QC Results", width="large")
def _batch_dialog():
    batch_tab.render(df, results)


if st.session_state.pop("_open_compare", False):
    _compare_dialog()

if st.session_state.pop("_open_batch", False):
    _batch_dialog()


# ── Tabs ──────────────────────────────────────────────────────────────────────
tab_qc, tab_int, tab_sl, tab_verb, tab_logic, tab_eda, tab_data = st.tabs([
    "QC Report",
    "Interviewers",
    "Straightlining",
    "Verbatim",
    "Logic Rules",
    "EDA",
    "Data",
])

with tab_qc:
    qc_tab.render(df, results)

with tab_int:
    interviewer_tab.render(df, results)

with tab_sl:
    straightlining_tab.render(df, results)

with tab_verb:
    verbatim_tab.render(df, results)

with tab_logic:
    logic_tab.render(df, results)

with tab_eda:
    eda_tab.render(df, results)

with tab_data:
    data_tab.render(df)
