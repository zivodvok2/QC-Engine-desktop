"""
QC Automation Engine — Streamlit UI
Run: streamlit run app.py
"""

import streamlit as st
import pandas as pd
import numpy as np
import json
import io
import sys
import os
from datetime import datetime

sys.path.insert(0, os.path.dirname(__file__))

from core.loader import DataLoader
from core.cleaner import DataCleaner
from core.rule_engine import RuleEngine
from core.reporter import Reporter
from core.utils import load_json_config

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="QC Engine",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Custom CSS ────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Syne:wght@600;700;800&family=DM+Mono:wght@300;400;500&display=swap');

html, body, [class*="css"] {
    font-family: 'DM Mono', monospace;
}
h1, h2, h3 { font-family: 'Syne', sans-serif !important; }

/* Metric cards */
[data-testid="metric-container"] {
    background: #111318;
    border: 1px solid #1f2330;
    border-radius: 6px;
    padding: 12px 16px;
}
[data-testid="metric-container"] label {
    font-size: 10px !important;
    letter-spacing: 0.1em;
    text-transform: uppercase;
    color: #8b90a8 !important;
}
[data-testid="metric-container"] [data-testid="stMetricValue"] {
    font-family: 'Syne', sans-serif !important;
    font-weight: 800 !important;
    font-size: 2rem !important;
}

/* Sidebar */
section[data-testid="stSidebar"] {
    background: #111318;
    border-right: 1px solid #1f2330;
}

/* Tabs */
button[data-baseweb="tab"] {
    font-family: 'DM Mono', monospace !important;
    font-size: 11px !important;
    letter-spacing: 0.08em;
    text-transform: uppercase;
}

/* Dataframe */
[data-testid="stDataFrame"] { border: 1px solid #1f2330; border-radius: 6px; }

/* File uploader */
[data-testid="stFileUploaderDropzone"] {
    border: 2px dashed #1f2330 !important;
    border-radius: 8px !important;
    background: #111318 !important;
}

/* Buttons */
.stButton > button {
    font-family: 'DM Mono', monospace !important;
    font-size: 11px !important;
    letter-spacing: 0.05em;
    border-radius: 6px !important;
}

/* Flag severity colours */
.flag-critical { border-left: 3px solid #f04a6a !important; background: #f04a6a08; }
.flag-warning  { border-left: 3px solid #f0c04a !important; background: #f0c04a08; }
.flag-info     { border-left: 3px solid #4a9ef0 !important; background: #4a9ef008; }

div[data-testid="stExpander"] { border: 1px solid #1f2330 !important; border-radius: 6px !important; }
</style>
""", unsafe_allow_html=True)


# ── Session state ─────────────────────────────────────────────────────────────
def init_state():
    defaults = {
        "df_raw": None,
        "df_clean": None,
        "qc_results": None,
        "filename": None,
        "rules_config": load_json_config("config/rules.json"),
        "custom_rules": [],
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

init_state()


# ── Helpers ───────────────────────────────────────────────────────────────────
def severity_emoji(s):
    return {"critical": "🔴", "warning": "🟡", "info": "🔵"}.get(s, "⚪")

def severity_color(s):
    return {"critical": "#f04a6a", "warning": "#f0c04a", "info": "#4a9ef0"}.get(s, "#8b90a8")

def run_pipeline(df: pd.DataFrame, filename: str):
    cleaner = DataCleaner()
    df_clean = cleaner.clean(df)

    # Merge custom logic rules into config
    cfg = dict(st.session_state.rules_config)
    cfg["logic_rules"] = cfg.get("logic_rules", []) + st.session_state.custom_rules

    # Write temp config for rule engine
    tmp_cfg = "config/_session_rules.json"
    with open(tmp_cfg, "w") as f:
        json.dump(cfg, f)

    engine = RuleEngine(config_path=tmp_cfg)
    results = engine.run(df_clean)

    st.session_state.df_raw = df
    st.session_state.df_clean = df_clean
    st.session_state.qc_results = results
    st.session_state.filename = filename

    if os.path.exists(tmp_cfg):
        os.remove(tmp_cfg)


def build_excel_report(df_clean, results):
    """Build in-memory Excel report."""
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        # Sheet 1 — QC Summary
        summary = pd.DataFrame([r.summary() for r in results])
        summary.to_excel(writer, sheet_name="QC Summary", index=False)

        # Sheet 2 — All flagged rows
        flagged_frames = []
        for r in results:
            if r.flag_count > 0:
                tmp = r.flagged_rows.copy()
                tmp["_qc_check"] = r.check_name
                tmp["_severity"] = r.severity
                flagged_frames.append(tmp)
        if flagged_frames:
            pd.concat(flagged_frames, ignore_index=True).to_excel(writer, sheet_name="Flagged Records", index=False)

        # Sheet 3 — EDA numeric
        numeric_cols = df_clean.select_dtypes(include="number").columns
        if len(numeric_cols):
            df_clean[numeric_cols].describe().T.to_excel(writer, sheet_name="EDA Numeric")

        # Sheet 4 — Clean data snapshot
        df_clean.head(500).to_excel(writer, sheet_name="Clean Data (500 rows)", index=False)

    output.seek(0)
    return output


# ══════════════════════════════════════════════════════════════════════════════
# SIDEBAR
# ══════════════════════════════════════════════════════════════════════════════

with st.sidebar:
    st.markdown("## 📊 QC Engine")
    st.caption("Survey Quality Control System")
    st.divider()

    # ── File upload ──────────────────────────────────────────────────────────
    st.markdown("### Upload Data")
    uploaded = st.file_uploader(
        "Drop CSV or Excel file",
        type=["csv", "xlsx", "xls"],
        label_visibility="collapsed",
    )

    if uploaded:
        with st.spinner("Loading & running QC..."):
            try:
                loader = DataLoader()
                df = loader.load_from_buffer(uploaded)
                run_pipeline(df, uploaded.name)
                st.success(f"✓ Loaded {len(df):,} rows")
            except Exception as e:
                st.error(f"Error: {e}")

    st.divider()

    # ── Thresholds ───────────────────────────────────────────────────────────
    st.markdown("### QC Settings")
    missing_threshold = st.slider("Missing value threshold", 0.0, 1.0, 0.10, 0.01, format="%.0f%%",
                                   help="Flag columns with more than this % missing")
    st.session_state.rules_config["missing_threshold"] = missing_threshold

    duration_col = st.text_input("Duration column name", value="duration_minutes",
                                  help="Column holding interview duration")
    min_dur = st.number_input("Min interview duration (mins)", value=5, min_value=0)
    max_dur = st.number_input("Max interview duration (mins)", value=120, min_value=1)

    st.session_state.rules_config["interview_duration"] = {
        "enabled": bool(duration_col),
        "column": duration_col,
        "min_expected": min_dur,
        "max_expected": max_dur,
    }

    st.divider()

    # ── Custom logic rules ───────────────────────────────────────────────────
    st.markdown("### Logic Rules")
    st.caption("Skip-logic / conditional checks")

    with st.expander("+ Add rule", expanded=False):
        if_col = st.text_input("If column", key="r_if_col")
        if_val = st.text_input("Equals value", key="r_if_val")
        then_col = st.text_input("Then column", key="r_then_col")
        condition = st.selectbox("Condition", ["must_be_null", "must_not_be_null"], key="r_cond")
        if st.button("Add Rule", use_container_width=True):
            if if_col and if_val and then_col:
                st.session_state.custom_rules.append({
                    "if_column": if_col, "if_value": if_val,
                    "then_column": then_col, "then_condition": condition,
                    "description": f"If {if_col}={if_val} → {then_col} {condition}",
                })
                st.success("Rule added")

    if st.session_state.custom_rules:
        for i, r in enumerate(st.session_state.custom_rules):
            cols = st.columns([5, 1])
            cols[0].caption(r["description"])
            if cols[1].button("✕", key=f"del_rule_{i}"):
                st.session_state.custom_rules.pop(i)
                st.rerun()

    if st.session_state.df_clean is not None:
        st.divider()
        if st.button("↺ Re-run QC", use_container_width=True, type="primary"):
            with st.spinner("Running..."):
                run_pipeline(st.session_state.df_raw, st.session_state.filename)
            st.success("Done")


# ══════════════════════════════════════════════════════════════════════════════
# MAIN CONTENT
# ══════════════════════════════════════════════════════════════════════════════

if st.session_state.df_clean is None:
    # ── Landing ───────────────────────────────────────────────────────────────
    st.markdown("""
    <div style="text-align:center; padding: 80px 40px;">
        <h1 style="font-size:2.8rem; font-weight:800; letter-spacing:-0.01em;">QC Automation Engine</h1>
        <p style="font-size:1rem; color:#8b90a8; margin-top:12px;">
            Upload a CSV or Excel file to run automated quality control checks,<br>
            exploratory analysis, and generate a structured QC report.
        </p>
        <div style="margin-top:40px; display:flex; justify-content:center; gap:32px; flex-wrap:wrap;">
            <div style="background:#111318; border:1px solid #1f2330; border-radius:8px; padding:20px 28px; width:180px;">
                <div style="font-size:1.4rem;">🔍</div>
                <div style="font-family:Syne,sans-serif; font-weight:700; margin-top:8px;">Missing Values</div>
                <div style="font-size:11px; color:#8b90a8; margin-top:4px;">Per-column detection & rate</div>
            </div>
            <div style="background:#111318; border:1px solid #1f2330; border-radius:8px; padding:20px 28px; width:180px;">
                <div style="font-size:1.4rem;">📐</div>
                <div style="font-family:Syne,sans-serif; font-weight:700; margin-top:8px;">Range Checks</div>
                <div style="font-size:11px; color:#8b90a8; margin-top:4px;">Outliers & bound violations</div>
            </div>
            <div style="background:#111318; border:1px solid #1f2330; border-radius:8px; padding:20px 28px; width:180px;">
                <div style="font-size:1.4rem;">🔗</div>
                <div style="font-family:Syne,sans-serif; font-weight:700; margin-top:8px;">Logic Rules</div>
                <div style="font-size:11px; color:#8b90a8; margin-top:4px;">Skip-pattern violations</div>
            </div>
            <div style="background:#111318; border:1px solid #1f2330; border-radius:8px; padding:20px 28px; width:180px;">
                <div style="font-size:1.4rem;">📊</div>
                <div style="font-family:Syne,sans-serif; font-weight:700; margin-top:8px;">EDA</div>
                <div style="font-size:11px; color:#8b90a8; margin-top:4px;">Distributions & summaries</div>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)
    st.stop()


# ── Header ────────────────────────────────────────────────────────────────────
df = st.session_state.df_clean
results = st.session_state.qc_results
filename = st.session_state.filename

col_title, col_export = st.columns([5, 1])
with col_title:
    st.markdown(f"### {filename}")
    st.caption(f"{len(df):,} rows · {len(df.columns)} columns · Last run: {datetime.now().strftime('%H:%M:%S')}")
with col_export:
    report_bytes = build_excel_report(df, results)
    st.download_button(
        "↓ Export Report",
        data=report_bytes,
        file_name=f"QC_Report_{filename.rsplit('.', 1)[0]}_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True,
        type="primary",
    )

st.divider()

# ── Scorecards ────────────────────────────────────────────────────────────────
total   = len(results)
crits   = sum(1 for r in results if r.severity == "critical" and r.flag_count > 0)
warns   = sum(1 for r in results if r.severity == "warning"  and r.flag_count > 0)
infos   = sum(1 for r in results if r.severity == "info"     and r.flag_count > 0)
total_flags = sum(r.flag_count for r in results)

m1, m2, m3, m4, m5 = st.columns(5)
m1.metric("Total Checks", total)
m2.metric("Total Flags", total_flags)
m3.metric("🔴 Critical", crits)
m4.metric("🟡 Warnings", warns)
m5.metric("🔵 Info", infos)

st.divider()

# ── Tabs ──────────────────────────────────────────────────────────────────────
tab_qc, tab_eda, tab_data, tab_raw = st.tabs(["QC Report", "EDA", "Data Preview", "Raw Config"])


# ════════════════════════════════════
# TAB 1 — QC REPORT
# ════════════════════════════════════
with tab_qc:
    if total_flags == 0:
        st.success("✅ No issues detected — dataset passed all checks.")
    else:
        # Group by severity
        for sev, label in [("critical", "Critical Issues"), ("warning", "Warnings"), ("info", "Info")]:
            sev_results = [r for r in results if r.severity == sev and r.flag_count > 0]
            if not sev_results:
                continue

            color = severity_color(sev)
            st.markdown(f"<h4 style='color:{color}; margin-top:1.2rem;'>{severity_emoji(sev)} {label}</h4>",
                        unsafe_allow_html=True)

            for r in sev_results:
                pct = r.flag_count / max(len(df), 1) * 100
                with st.expander(
                    f"{r.check_name} — **{r.flag_count:,}** rows ({pct:.1f}%)",
                    expanded=(sev == "critical"),
                ):
                    meta_col, data_col = st.columns([2, 3])
                    with meta_col:
                        st.markdown("**Check metadata**")
                        st.json(r.summary(), expanded=False)
                    with data_col:
                        if not r.flagged_rows.empty:
                            st.markdown(f"**Flagged rows** (showing first 50)")
                            display_cols = [c for c in r.flagged_rows.columns if not c.startswith("_")]
                            st.dataframe(
                                r.flagged_rows[display_cols].head(50),
                                use_container_width=True,
                                hide_index=True,
                            )

    # Summary table
    st.markdown("#### All checks summary")
    summary_df = pd.DataFrame([r.summary() for r in results])
    st.dataframe(summary_df, use_container_width=True, hide_index=True)


# ════════════════════════════════════
# TAB 2 — EDA
# ════════════════════════════════════
with tab_eda:
    st.markdown("#### Exploratory Data Analysis")

    numeric_cols = df.select_dtypes(include="number").columns.tolist()
    cat_cols = df.select_dtypes(exclude="number").columns.tolist()

    # ── Numeric summary ──────────────────────────────────────────────────────
    if numeric_cols:
        st.markdown("##### Numeric Columns")
        desc = df[numeric_cols].describe().T
        desc["missing"] = df[numeric_cols].isnull().sum()
        desc["missing_%"] = (df[numeric_cols].isnull().mean() * 100).round(1)
        st.dataframe(desc.style.background_gradient(cmap="Blues", subset=["mean", "std"]),
                     use_container_width=True)

        st.markdown("##### Distributions")
        cols_per_row = 3
        rows = [numeric_cols[i:i+cols_per_row] for i in range(0, len(numeric_cols), cols_per_row)]
        for row in rows:
            chart_cols = st.columns(len(row))
            for col, c in zip(row, chart_cols):
                vals = df[col].dropna()
                if len(vals) > 1:
                    hist_data = pd.cut(vals, bins=min(20, vals.nunique())).value_counts().sort_index()
                    chart_df = pd.DataFrame({
                        "bin": [str(b) for b in hist_data.index],
                        "count": hist_data.values,
                    })
                    c.markdown(f"**{col}**")
                    c.bar_chart(chart_df.set_index("bin"), height=160, use_container_width=True)
                    c.caption(f"μ={vals.mean():.2f} · σ={vals.std():.2f} · n={len(vals):,}")

    # ── Categorical summary ──────────────────────────────────────────────────
    if cat_cols:
        st.markdown("##### Categorical Columns")
        cols_per_row = 2
        rows = [cat_cols[i:i+cols_per_row] for i in range(0, len(cat_cols), cols_per_row)]
        for row in rows:
            chart_cols = st.columns(len(row))
            for col, c in zip(row, chart_cols):
                vc = df[col].value_counts().head(10)
                missing = df[col].isnull().sum()
                c.markdown(f"**{col}**")
                c.bar_chart(vc, height=160, use_container_width=True)
                c.caption(f"{df[col].nunique()} unique · {missing} missing")

    # ── Correlation matrix ───────────────────────────────────────────────────
    if len(numeric_cols) >= 2:
        st.markdown("##### Correlation Matrix")
        corr = df[numeric_cols].corr().round(2)
        st.dataframe(
            corr.style.background_gradient(cmap="RdYlGn", vmin=-1, vmax=1),
            use_container_width=True,
        )

    # ── Missing heatmap ──────────────────────────────────────────────────────
    st.markdown("##### Missing Values by Column")
    missing_df = pd.DataFrame({
        "column": df.columns,
        "missing_count": df.isnull().sum().values,
        "missing_pct": (df.isnull().mean() * 100).round(1).values,
    }).sort_values("missing_pct", ascending=False)
    missing_df = missing_df[missing_df["missing_count"] > 0]
    if missing_df.empty:
        st.success("No missing values found.")
    else:
        st.dataframe(missing_df, use_container_width=True, hide_index=True)
        st.bar_chart(missing_df.set_index("column")["missing_pct"], height=200)


# ════════════════════════════════════
# TAB 3 — DATA PREVIEW
# ════════════════════════════════════
with tab_data:
    st.markdown("#### Data Preview")

    search = st.text_input("Filter rows (search any value)", placeholder="Type to filter...")
    col_filter = st.multiselect("Show columns", options=df.columns.tolist(), default=df.columns.tolist())

    display_df = df[col_filter] if col_filter else df
    if search:
        mask = display_df.apply(lambda row: row.astype(str).str.contains(search, case=False).any(), axis=1)
        display_df = display_df[mask]

    st.caption(f"Showing {len(display_df):,} of {len(df):,} rows")
    st.dataframe(display_df, use_container_width=True, height=500)


# ════════════════════════════════════
# TAB 4 — RAW CONFIG
# ════════════════════════════════════
with tab_raw:
    st.markdown("#### Active Rules Config")
    st.caption("Edit rules.json directly to add range rules, pattern checks, etc.")
    st.json(st.session_state.rules_config)

    st.markdown("#### Active Custom Logic Rules")
    if st.session_state.custom_rules:
        st.json(st.session_state.custom_rules)
    else:
        st.caption("No custom rules added yet.")
