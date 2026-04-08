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
h1, h2, h3 = st.columns([5, 1, 1])
with h1:
    st.markdown(f"### {filename}")
    st.caption(
        f"{len(df):,} rows · {len(df.columns)} columns · "
        f"Last run: {datetime.now().strftime('%H:%M:%S')}"
    )
with h2:
    st.download_button(
        "↓ Excel",
        data=build_report(df, results),
        file_name=f"QC_{filename.rsplit('.', 1)[0]}_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True,
        type="primary",
    )
with h3:
    st.download_button(
        "↓ PDF",
        data=build_pdf_report(filename, df, results),
        file_name=f"QC_{filename.rsplit('.', 1)[0]}_{datetime.now().strftime('%Y%m%d_%H%M')}.html",
        mime="text/html",
        use_container_width=True,
        help="Downloads as HTML — open in browser and File → Print → Save as PDF",
    )

st.divider()

# ── Tabs ──────────────────────────────────────────────────────────────────────
tab_qc, tab_logic, tab_sl, tab_verb, tab_int, tab_eda, tab_data, tab_cmp, tab_batch, tab_log, tab_cfg = st.tabs([
    "QC Report", "Logic", "Straightlining", "Verbatim",
    "Interviewers", "EDA", "Data", "Compare", "Batch", "Log", "Config",
])

with tab_qc:
    qc_tab.render(df, results)

with tab_logic:
    logic_tab.render(df, results)

with tab_sl:
    straightlining_tab.render(df, results)

with tab_verb:
    verbatim_tab.render(df, results)

with tab_int:
    interviewer_tab.render(df, results)

with tab_eda:
    eda_tab.render(df, results)

with tab_data:
    data_tab.render(df)

with tab_cmp:
    compare_tab.render(df)

with tab_batch:
    batch_tab.render(df, results)

with tab_log:
    st.markdown("#### Audit Trail")
    st.caption(
        "Timestamped record of every QC run this session — file, config, flags raised. "
        "Export for client accountability or project documentation."
    )
    audit_log = st.session_state.get("_audit_log", [])
    if not audit_log:
        st.info("No runs logged yet. Upload a file and run QC to start the audit trail.")
    else:
        summary_rows = [{
            "Timestamp":   e["timestamp"],
            "File":        e["filename"],
            "Rows":        e["rows"],
            "Checks Run":  e["checks_run"],
            "Total Flags": e["total_flags"],
            "Critical":    e["critical"],
            "Warnings":    e["warnings"],
            "Aliases Used": ", ".join(e.get("aliases_applied", [])) or "—",
        } for e in audit_log]
        st.dataframe(pd.DataFrame(summary_rows), use_container_width=True, hide_index=True)

        log_buf = io.BytesIO(
            pd.DataFrame(summary_rows).to_csv(index=False).encode()
        )
        st.download_button(
            "↓ Export audit log (CSV)",
            data=log_buf,
            file_name=f"QC_AuditLog_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
            mime="text/csv",
        )

        # Most recent run detail
        latest = audit_log[-1]
        with st.expander("Most recent run — check detail"):
            if latest["flags_by_check"]:
                check_rows = [{"Check": k, "Flags": v} for k, v in latest["flags_by_check"].items()]
                st.dataframe(pd.DataFrame(check_rows), use_container_width=True, hide_index=True)
            else:
                st.caption("No flags raised in the most recent run.")
            if latest.get("aliases_applied"):
                st.caption(f"Aliases applied: {', '.join(latest['aliases_applied'])}")
            st.json(latest["config_snapshot"], expanded=False)

        if st.button("Clear audit log", type="secondary", key="clear_audit_log"):
            st.session_state._audit_log = []
            st.rerun()

with tab_cfg:
    st.markdown("#### Config Profiles")
    st.markdown(
        "<p style='color:var(--ds-text2);font-size:13px;margin-bottom:12px;'>"
        "Save the current rule configuration as a named profile and reload it for future waves.</p>",
        unsafe_allow_html=True,
    )

    PROFILES_DIR.mkdir(exist_ok=True)
    saved_profiles = sorted(PROFILES_DIR.glob("*.json"))

    cp1, cp2 = st.columns([3, 1])
    with cp1:
        profile_name = st.text_input("Profile name", placeholder="Ipsos Kenya Household 2025",
                                     key="cfg_profile_name")
    with cp2:
        st.markdown("<div style='height:28px'></div>", unsafe_allow_html=True)
        if st.button("💾 Save", use_container_width=True, key="cfg_save"):
            if profile_name.strip():
                safe = "".join(c if c.isalnum() or c in " _-" else "_" for c in profile_name.strip())
                path = PROFILES_DIR / f"{safe}.json"
                payload = {
                    "rules_config": st.session_state.rules_config,
                    "custom_logic_rules": st.session_state.custom_logic_rules,
                    "column_aliases": st.session_state.get("column_aliases", {}),
                }
                path.write_text(json.dumps(payload, indent=2))
                st.success(f"Saved: {path.name}")
                st.rerun()
            else:
                st.warning("Enter a profile name first.")

    if saved_profiles:
        st.markdown("##### Load a saved profile")
        profile_opts = {p.stem: p for p in saved_profiles}
        selected_profile = st.selectbox("Saved profiles", ["— select —"] + list(profile_opts.keys()),
                                        key="cfg_load_sel")
        if st.button("↩ Load profile", key="cfg_load_btn"):
            if selected_profile != "— select —":
                data = json.loads(profile_opts[selected_profile].read_text())
                st.session_state.rules_config = data.get("rules_config", st.session_state.rules_config)
                st.session_state.custom_logic_rules = data.get("custom_logic_rules", [])
                st.session_state.column_aliases = data.get("column_aliases", {})
                st.success(f"Profile '{selected_profile}' loaded — click ↺ Rerun QC to apply.")
                st.rerun()

    st.divider()
    st.markdown("#### Column Aliases")
    st.caption(
        "Map your column names to standard names before QC runs. "
        "e.g. 'INT_CODE' → 'interviewer_id'. Aliases are saved with profiles."
    )

    aliases = st.session_state.get("column_aliases", {})

    # Show existing aliases with inline ✕ delete buttons
    to_delete = []
    for orig, target in list(aliases.items()):
        a1, a2, a3 = st.columns([5, 5, 1])
        a1.caption(orig)
        a2.caption(f"→ {target}")
        if a3.button("✕", key=f"del_alias_{orig}", help="Remove alias"):
            to_delete.append(orig)
    for k in to_delete:
        del st.session_state.column_aliases[k]
    if to_delete:
        st.rerun()

    if not aliases:
        st.caption("No aliases defined yet.")

    # Add new alias
    ac1, ac2 = st.columns(2)
    from_col = ac1.text_input("Your column",   placeholder="INT_CODE",       key="alias_from")
    to_col   = ac2.text_input("Standard name", placeholder="interviewer_id", key="alias_to")
    if st.button("Add alias", use_container_width=False, key="alias_add_btn"):
        if from_col.strip() and to_col.strip():
            st.session_state.column_aliases[from_col.strip()] = to_col.strip()
            st.rerun()
        else:
            st.warning("Enter both the original column name and the standard name.")

    st.divider()
    st.markdown("#### Active Config")
    st.json(st.session_state.rules_config)
    st.markdown("#### Custom Logic Rules")
    if st.session_state.custom_logic_rules:
        st.json(st.session_state.custom_logic_rules)
    else:
        st.caption("No custom logic rules added yet.")
