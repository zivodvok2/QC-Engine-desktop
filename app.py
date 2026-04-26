"""
app.py — Servallab QC Engine
Run: streamlit run app.py

Performance notes:
- QC pipeline only reruns when file changes or user clicks Rerun QC
- Session state holds results; no DataFrame hashing on every render
- Excel report cached per file so the download button doesn't rebuild on every interaction
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__) or "."))

import io
import json
from datetime import datetime

import streamlit as st
import pandas as pd

from ui.sidebar import render_sidebar, init_state
from ui.onboarding import render_onboarding, init_onboarding
from ui.settings import get_theme_css, init_settings
from ui.tabs import (qc_tab, eda_tab, logic_tab, straightlining_tab,
                     data_tab, verbatim_tab, interviewer_tab, compare_tab,
                     quota_tab)

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Servallab",
    page_icon="🐆",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Theme CSS ─────────────────────────────────────────────────────────────────
init_settings()
st.markdown(get_theme_css(st.session_state.get("ds_theme", "dark")), unsafe_allow_html=True)

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Syne:wght@600;700;800&family=DM+Mono:wght@300;400;500&display=swap');

html, body, [class*="css"] { font-family: var(--ds-mono, 'DM Mono', monospace); }
h1, h2, h3                 { font-family: var(--ds-head, 'Syne', sans-serif) !important; }

[data-testid="metric-container"] {
    background: var(--ds-surface);
    border: 1px solid var(--ds-border);
    border-radius: 8px;
    padding: 14px 18px;
}
[data-testid="metric-container"] label {
    font-size: 10px !important; letter-spacing: 0.1em;
    text-transform: uppercase; color: var(--ds-text2) !important;
}
[data-testid="metric-container"] [data-testid="stMetricValue"] {
    font-family: var(--ds-head) !important;
    font-weight: 800 !important; font-size: 1.9rem !important;
    color: var(--ds-text) !important;
}

section[data-testid="stSidebar"] {
    background: var(--ds-surface);
    border-right: 1px solid var(--ds-border);
}

button[data-baseweb="tab"] {
    font-family: var(--ds-mono) !important; font-size: 11px !important;
    letter-spacing: 0.08em; text-transform: uppercase; color: var(--ds-text2) !important;
}
button[data-baseweb="tab"][aria-selected="true"] {
    color: var(--ds-text) !important; border-bottom-color: var(--ds-accent) !important;
}

[data-testid="stDataFrame"] { border: 1px solid var(--ds-border); border-radius: 6px; }

.stButton > button {
    font-family: var(--ds-mono) !important; font-size: 11px !important;
    letter-spacing: 0.05em; border-radius: 6px !important;
    border: 1px solid var(--ds-border) !important;
    color: var(--ds-text) !important; background: var(--ds-surface2) !important;
    transition: border-color 0.15s;
}
.stButton > button:hover { border-color: var(--ds-accent) !important; }
.stButton > button[kind="primary"] {
    background: var(--ds-accent) !important; color: #0b0c0f !important;
    border-color: var(--ds-accent) !important; font-weight: 600 !important;
}
[data-testid="stDownloadButton"] > button {
    font-family: var(--ds-mono) !important; font-size: 11px !important;
    letter-spacing: 0.05em; border-radius: 6px !important;
    border: 1px solid var(--ds-border) !important;
    color: var(--ds-text) !important; background: var(--ds-surface2) !important;
    transition: border-color 0.15s;
}
[data-testid="stDownloadButton"] > button:hover { border-color: var(--ds-accent) !important; }
[data-testid="stDownloadButton"] > button[kind="primary"] {
    background: var(--ds-accent) !important; color: #0b0c0f !important;
    border-color: var(--ds-accent) !important; font-weight: 600 !important;
}

div[data-testid="stExpander"] {
    border: 1px solid var(--ds-border) !important;
    border-radius: 8px !important; background: var(--ds-surface) !important;
}
div[data-testid="stExpander"] summary {
    color: var(--ds-text) !important; font-family: var(--ds-mono) !important;
    font-size: 12px !important; padding: 10px 14px !important;
}
hr { border-color: var(--ds-border) !important; }
[data-testid="stAlert"] {
    border-radius: 6px !important; font-family: var(--ds-mono) !important;
    font-size: 12px !important;
}
[data-testid="stFileUploaderDropzone"] {
    border: 1px dashed var(--ds-border) !important;
    border-radius: 6px !important; background: var(--ds-surface2) !important;
    padding: 12px !important;
}
</style>
""", unsafe_allow_html=True)

# ── Init ──────────────────────────────────────────────────────────────────────
init_state()
init_onboarding()
render_sidebar()
render_onboarding()

# ── Landing page ──────────────────────────────────────────────────────────────
if st.session_state.df_clean is None:
    st.markdown("""
    <div style="text-align:center;padding:80px 40px 40px;">
        <div style="font-family:var(--ds-head);font-size:3rem;font-weight:800;
                    letter-spacing:-0.02em;">Servallab</div>
        <div style="font-size:10px;letter-spacing:0.25em;text-transform:uppercase;
                    color:var(--ds-accent);margin-top:6px;">Survey Quality Control Engine</div>
        <p style="color:var(--ds-text2);margin-top:20px;font-size:14px;
                  line-height:1.8;max-width:500px;margin-left:auto;margin-right:auto;">
            Upload a CSV or Excel file in the sidebar to get started.
        </p>
    </div>
    """, unsafe_allow_html=True)

    features = [
        ("🔍", "Missing Values",     "Per-column detection"),
        ("📐", "Range Checks",       "Outlier detection"),
        ("🔗", "Logic Rules",        "Multi-condition + AI builder"),
        ("📋", "Straightlining",     "Repeated answer detection"),
        ("🕵️", "Fabrication",        "Sequence & variance flags"),
        ("👤", "Interviewer Risk",   "Weighted risk score (RAG)"),
        ("📊", "Quota Monitoring",   "Target vs achieved, RAG"),
        ("🔁", "Wave Comparison",    "Drift detection across waves"),
        ("🔎", "Near-Duplicates",    "Phone match, pattern clones"),
        ("💬", "Verbatim QC",        "AI grammar scoring (Groq)"),
        ("📊", "EDA Charts",         "Multi-variable, Plotly"),
        ("💾", "Project Config",     "Save & reload settings"),
    ]
    cols = st.columns(4)
    for i, (icon, title, desc) in enumerate(features):
        with cols[i % 4]:
            st.markdown(
                f"<div style='background:var(--ds-surface);border:1px solid var(--ds-border);"
                f"border-radius:10px;padding:16px;margin-bottom:12px;text-align:center;'>"
                f"<div style='font-size:1.4rem;margin-bottom:6px;'>{icon}</div>"
                f"<div style='font-family:var(--ds-head);font-weight:700;font-size:12px;"
                f"color:var(--ds-text);'>{title}</div>"
                f"<div style='font-size:10px;color:var(--ds-text2);margin-top:3px;'>{desc}</div>"
                f"</div>",
                unsafe_allow_html=True,
            )
    st.stop()


df       = st.session_state.df_clean
results  = st.session_state.qc_results
filename = st.session_state.filename


# ── Report builders ───────────────────────────────────────────────────────────
def _build_excel_report() -> bytes:
    """Excel report — cached per file hash so it doesn't rebuild on every render."""
    hash_key  = "_excel_hash"
    cache_key = "_excel_cache"
    cur_hash  = st.session_state.get("_last_file_hash", "")
    if st.session_state.get(hash_key) == cur_hash and st.session_state.get(cache_key):
        return st.session_state[cache_key]
    out = io.BytesIO()
    with pd.ExcelWriter(out, engine="openpyxl") as w:
        pd.DataFrame([r.summary() for r in results]).to_excel(
            w, sheet_name="QC Summary", index=False)
        frames = [
            r.flagged_rows.assign(_check=r.check_name, _sev=r.severity)
            for r in results if r.flag_count > 0
        ]
        if frames:
            pd.concat(frames, ignore_index=True).to_excel(
                w, sheet_name="Flagged Records", index=False)
        nc = df.select_dtypes(include="number").columns
        if len(nc):
            df[nc].describe().T.to_excel(w, sheet_name="EDA Numeric")
        df.head(500).to_excel(w, sheet_name="Clean Data", index=False)
    data = out.getvalue()
    st.session_state[cache_key] = data
    st.session_state[hash_key]  = cur_hash
    return data


def _build_html_report() -> bytes:
    now         = datetime.now().strftime("%Y-%m-%d %H:%M")
    total_flags = sum(r.flag_count for r in results)
    summary_rows = "".join(
        f"<tr><td>{r.check_name}</td><td>{r.severity}</td>"
        f"<td>{r.flag_count:,}</td>"
        f"<td>{r.flag_count / max(len(df), 1) * 100:.1f}%</td></tr>"
        for r in sorted(results, key=lambda x: -x.flag_count)
    )
    flagged_sections = ""
    for r in [x for x in results if x.flag_count > 0]:
        show = [c for c in r.flagged_rows.columns if not c.startswith("_")]
        sample = r.flagged_rows[show].head(50)
        th    = "".join(f"<th>{c}</th>" for c in sample.columns)
        tbody = "".join(
            "<tr>" + "".join(f"<td>{v}</td>" for v in row) + "</tr>"
            for row in sample.itertuples(index=False)
        )
        col = {"critical": "#f04a6a", "warning": "#f0c04a", "info": "#4a9ef0"}.get(r.severity, "#888")
        flagged_sections += (
            f"<h3 style='color:{col};border-left:4px solid {col};padding-left:10px;margin-top:32px;'>"
            f"{r.check_name} — {r.flag_count:,} flags</h3>"
            f"<table><thead><tr>{th}</tr></thead><tbody>{tbody}</tbody></table>"
        )
    html = f"""<!DOCTYPE html><html><head><meta charset="utf-8">
<title>Servallab QC — {filename}</title>
<style>
body{{font-family:'DM Mono',monospace,sans-serif;margin:40px;color:#1a1a2e;font-size:13px;}}
h1{{font-size:26px;}} h2{{font-size:15px;color:#555;border-bottom:1px solid #ddd;
    padding-bottom:6px;margin-top:28px;}} h3{{font-size:13px;}}
.meta{{color:#888;font-size:12px;margin-bottom:28px;}}
.cards{{display:flex;gap:16px;flex-wrap:wrap;margin:16px 0;}}
.card{{background:#f5f7ff;border:1px solid #dde;border-radius:8px;padding:14px 20px;}}
.card .val{{font-size:26px;font-weight:800;}} .card .lbl{{font-size:10px;color:#888;text-transform:uppercase;letter-spacing:0.08em;}}
table{{border-collapse:collapse;width:100%;font-size:12px;margin-top:8px;}}
th{{background:#f0f2ff;text-align:left;padding:6px 10px;border:1px solid #dde;}}
td{{padding:5px 10px;border:1px solid #eee;word-break:break-word;max-width:280px;}}
tr:nth-child(even) td{{background:#fafafa;}}
</style></head><body>
<h1>Servallab QC Report</h1>
<div class="meta">{filename} &nbsp;·&nbsp; {len(df):,} rows · {len(df.columns)} cols
&nbsp;·&nbsp; Generated {now}</div>
<div class="cards">
  <div class="card"><div class="val">{len(results)}</div><div class="lbl">Checks</div></div>
  <div class="card"><div class="val" style="color:#f04a6a">{total_flags:,}</div><div class="lbl">Flags</div></div>
</div>
<h2>Check Summary</h2>
<table><thead><tr><th>Check</th><th>Severity</th><th>Flags</th><th>Flag Rate</th></tr></thead>
<tbody>{summary_rows}</tbody></table>
<h2>Flagged Records</h2>
{flagged_sections or "<p style='color:#888'>No flags.</p>"}
</body></html>"""
    return html.encode("utf-8")


# ── Header ────────────────────────────────────────────────────────────────────
h1, h2, h3 = st.columns([6, 1, 1])
stamp = datetime.now().strftime("%Y%m%d_%H%M")
base  = filename.rsplit(".", 1)[0] if "." in filename else filename

with h1:
    project = st.session_state.get("project_name", "")
    title   = f"{project} · {filename}" if project else filename
    st.markdown(
        f"<div style='display:flex;align-items:baseline;gap:12px;padding:4px 0;'>"
        f"<span style='font-family:var(--ds-head);font-weight:800;font-size:1.2rem;"
        f"color:var(--ds-text);'>{title}</span>"
        f"<span style='font-size:11px;color:var(--ds-text2);'>"
        f"{len(df):,} rows · {len(df.columns)} cols · "
        f"{datetime.now().strftime('%H:%M')}</span>"
        f"</div>",
        unsafe_allow_html=True,
    )

with h2:
    st.download_button(
        "↓ Excel",
        data=_build_excel_report(),
        file_name=f"Servallab_{base}_{stamp}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True,
        type="primary",
    )

with h3:
    st.download_button(
        "↓ Report",
        data=_build_html_report(),
        file_name=f"Servallab_{base}_{stamp}.html",
        mime="text/html",
        use_container_width=True,
        help="Open in browser → File → Print → Save as PDF",
    )

st.divider()


# ── Tabs ──────────────────────────────────────────────────────────────────────
(
    tab_qc, tab_int, tab_sl, tab_verb, tab_logic,
    tab_quota, tab_wave, tab_eda, tab_data, tab_cfg,
) = st.tabs([
    "QC Report", "Interviewers", "Straightlining", "Verbatim", "Logic Rules",
    "Quotas", "Wave Compare", "EDA", "Data", "Config & Audit",
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

with tab_quota:
    quota_tab.render(df)

with tab_wave:
    compare_tab.render(df)

with tab_eda:
    eda_tab.render(df, results)

with tab_data:
    data_tab.render(df)

with tab_cfg:
    st.markdown("#### Active Config")
    st.json(st.session_state.rules_config, expanded=False)
    if st.session_state.get("custom_logic_rules"):
        st.markdown("#### Custom Logic Rules")
        st.json(st.session_state.custom_logic_rules, expanded=False)
    if st.session_state.get("column_aliases"):
        st.markdown("#### Column Aliases")
        st.json(st.session_state.column_aliases, expanded=False)

    st.divider()
    st.markdown("#### Audit Trail")
    audit = st.session_state.get("_audit_log", [])
    if not audit:
        st.info("No runs logged yet — upload a file and run QC to start the audit trail.")
    else:
        rows = [
            {"Time": e["timestamp"], "File": e["filename"], "Rows": e["rows"],
             "Checks": e["checks_run"], "Flags": e["total_flags"],
             "Critical": e["critical"]}
            for e in audit
        ]
        st.dataframe(rows, use_container_width=True, hide_index=True)
        buf = io.BytesIO(pd.DataFrame(rows).to_csv(index=False).encode())
        c1, c2 = st.columns(2)
        c1.download_button("↓ Export CSV", data=buf, file_name="Servallab_audit.csv",
                           mime="text/csv", use_container_width=True)
        if c2.button("Clear log", type="secondary", use_container_width=True):
            st.session_state._audit_log = []
            st.rerun()
