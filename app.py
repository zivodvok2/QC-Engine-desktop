"""
app.py — QC Automation Engine Streamlit UI
Run: streamlit run app.py
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__) or "."))

import io
import json
from datetime import datetime

import streamlit as st
import pandas as pd

from core.loader import DataLoader
from core.cleaner import DataCleaner
from core.rule_engine import RuleEngine
from core.utils import load_json_config

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="QC Engine",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Syne:wght@600;700;800&family=DM+Mono:wght@300;400;500&display=swap');
html, body, [class*="css"] { font-family: 'DM Mono', monospace; }
h1, h2, h3 { font-family: 'Syne', sans-serif !important; }
[data-testid="metric-container"] {
    background: #111318; border: 1px solid #1f2330; border-radius: 6px; padding: 12px 16px;
}
[data-testid="metric-container"] label {
    font-size: 10px !important; letter-spacing: 0.1em;
    text-transform: uppercase; color: #8b90a8 !important;
}
[data-testid="metric-container"] [data-testid="stMetricValue"] {
    font-family: 'Syne', sans-serif !important; font-weight: 800 !important; font-size: 2rem !important;
}
section[data-testid="stSidebar"] { background: #111318; border-right: 1px solid #1f2330; }
button[data-baseweb="tab"] {
    font-family: 'DM Mono', monospace !important; font-size: 11px !important;
    letter-spacing: 0.08em; text-transform: uppercase;
}
[data-testid="stDataFrame"] { border: 1px solid #1f2330; border-radius: 6px; }
.stButton > button {
    font-family: 'DM Mono', monospace !important; font-size: 11px !important;
    letter-spacing: 0.05em; border-radius: 6px !important;
}
div[data-testid="stExpander"] { border: 1px solid #1f2330 !important; border-radius: 6px !important; }
</style>
""", unsafe_allow_html=True)


# ── Default config ────────────────────────────────────────────────────────────
DEFAULT_CONFIG = {
    "missing_threshold": 0.1,
    "range_rules": [],
    "logic_rules": [],
    "pattern_rules": [
        {"column": "phone", "pattern": r"^\+?[0-9 ()-]{7,15}$", "description": "Valid phone format"},
        {"column": "email", "pattern": r"^[^@]+@[^@]+\.[^@]+$",  "description": "Valid email format"},
    ],
    "duplicate_check":                {"enabled": True,  "subset_columns": []},
    "interview_duration":             {"enabled": False, "column": "duration_minutes", "min_expected": 5, "max_expected": 120},
    "straightlining":                 {"enabled": False, "question_columns": [], "threshold": 0.9, "interviewer_column": None, "min_questions": 3},
    "interviewer_duration_check":     {"enabled": False, "interviewer_column": "interviewer_id", "duration_column": "duration_minutes", "multiplier": 1.5, "min_interviews": 3},
    "interviewer_productivity_check": {"enabled": False, "interviewer_column": "interviewer_id", "multiplier": 1.5},
    "consent_eligibility_check":      {"enabled": False, "screener_column": "consent", "disqualify_operator": "!=", "disqualify_value": "Yes", "subsequent_columns": []},
    "fabrication_check":              {"enabled": False, "id_column": None, "numeric_columns": [], "interviewer_column": None, "variance_threshold": 0.1, "sequence_run_length": 5},
}


# ── Session state ─────────────────────────────────────────────────────────────
def init_state():
    defaults = {
        "df_raw": None, "df_clean": None, "qc_results": None,
        "filename": None,
        "rules_config": DEFAULT_CONFIG.copy(),
        "custom_logic_rules": [],
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

init_state()


# ── Helpers ───────────────────────────────────────────────────────────────────
def sev_emoji(s): return {"critical": "🔴", "warning": "🟡", "info": "🔵"}.get(s, "⚪")
def sev_color(s): return {"critical": "#f04a6a", "warning": "#f0c04a", "info": "#4a9ef0"}.get(s, "#8b90a8")

def run_pipeline(df: pd.DataFrame, filename: str):
    df_clean = DataCleaner().clean(df)
    cfg = dict(st.session_state.rules_config)
    # Merge UI-added logic rules into config
    cfg["logic_rules"] = cfg.get("logic_rules", []) + st.session_state.custom_logic_rules
    results = RuleEngine(config=cfg).run(df_clean)
    st.session_state.df_raw     = df
    st.session_state.df_clean   = df_clean
    st.session_state.qc_results = results
    st.session_state.filename   = filename

def build_report(df_clean, results) -> io.BytesIO:
    out = io.BytesIO()
    with pd.ExcelWriter(out, engine="openpyxl") as writer:
        pd.DataFrame([r.summary() for r in results]).to_excel(
            writer, sheet_name="QC Summary", index=False)
        frames = []
        for r in results:
            if r.flag_count > 0:
                tmp = r.flagged_rows.copy()
                tmp["_qc_check"]  = r.check_name
                tmp["_severity"]  = r.severity
                frames.append(tmp)
        if frames:
            pd.concat(frames, ignore_index=True).to_excel(
                writer, sheet_name="Flagged Records", index=False)
        nc = df_clean.select_dtypes(include="number").columns
        if len(nc):
            df_clean[nc].describe().T.to_excel(writer, sheet_name="EDA Numeric")
        df_clean.head(500).to_excel(writer, sheet_name="Clean Data (500 rows)", index=False)
    out.seek(0)
    return out


# ══════════════════════════════════════════════════════════════════════════════
# SIDEBAR
# ══════════════════════════════════════════════════════════════════════════════

with st.sidebar:
    st.markdown("## 📊 QC Engine")
    st.caption("Survey Quality Control System")
    st.divider()

    # ── File upload ──────────────────────────────────────────────────────────
    st.markdown("### Upload Data")
    uploaded = st.file_uploader("CSV or Excel", type=["csv", "xlsx", "xls"],
                                label_visibility="collapsed")
    if uploaded:
        with st.spinner("Loading..."):
            try:
                df_up = DataLoader().load_from_buffer(uploaded)
                run_pipeline(df_up, uploaded.name)
                st.success(f"Loaded {len(df_up):,} rows")
            except Exception as e:
                st.error(f"Error: {e}")

    st.divider()

    # ── Basic settings ───────────────────────────────────────────────────────
    st.markdown("### Basic Settings")
    thr = st.slider("Missing value threshold", 0.0, 1.0, 0.10, 0.01, format="%.0f%%")
    st.session_state.rules_config["missing_threshold"] = thr

    dur_col = st.text_input("Duration column", value="duration_minutes")
    min_dur = st.number_input("Min duration (mins)", value=5,   min_value=0)
    max_dur = st.number_input("Max duration (mins)", value=120, min_value=1)
    st.session_state.rules_config["interview_duration"] = {
        "enabled": bool(dur_col), "column": dur_col,
        "min_expected": min_dur, "max_expected": max_dur,
    }

    st.divider()

    # ── Logic rules ──────────────────────────────────────────────────────────
    st.markdown("### Logic Rules")
    st.caption("Operators: >, <, >=, <=, ==, !=, is_null, not_null, in_list, not_in_list")

    with st.expander("+ Add logic rule"):
        rule_desc = st.text_input("Description", placeholder="e.g. Under 18 not married", key="ld")
        st.markdown("**IF**")
        if_col = st.text_input("Column",   key="li_col")
        if_op  = st.selectbox("Operator", [">","<",">=","<=","==","!=",
                                            "is_null","not_null","is_numeric","is_string",
                                            "in_list","not_in_list"], key="li_op")
        if_val = st.text_input("Value (blank for is_null/not_null)", key="li_val")
        st.markdown("**THEN**")
        th_col = st.text_input("Column",   key="lt_col")
        th_op  = st.selectbox("Operator", ["is_null","not_null",">","<",">=","<=",
                                            "==","!=","in_list","not_in_list"], key="lt_op")
        th_val = st.text_input("Value (optional)", key="lt_val")

        if st.button("Add Rule", use_container_width=True):
            if if_col and th_col:
                st.session_state.custom_logic_rules.append({
                    "description": rule_desc or f"If {if_col} {if_op} {if_val} → {th_col} {th_op}",
                    "if_conditions":   [{"column": if_col, "operator": if_op, "value": if_val or None}],
                    "then_conditions": [{"column": th_col, "operator": th_op, "value": th_val or None}],
                })
                st.success("Rule added")

    for i, r in enumerate(st.session_state.custom_logic_rules):
        c1, c2 = st.columns([5, 1])
        c1.caption(r["description"])
        if c2.button("x", key=f"dlr_{i}"):
            st.session_state.custom_logic_rules.pop(i)
            st.rerun()

    st.divider()

    # ── Straightlining ───────────────────────────────────────────────────────
    st.markdown("### Straightlining")
    sl_on = st.toggle("Enable", key="sl_toggle")
    if sl_on:
        sl_q   = st.text_input("Question columns (comma-sep)", placeholder="Q1,Q2,Q3,Q4,Q5")
        sl_thr = st.slider("Same-answer threshold", 0.5, 1.0, 0.9, 0.05)
        sl_int = st.text_input("Interviewer column (optional)", placeholder="interviewer_id", key="sl_int")
        st.session_state.rules_config["straightlining"] = {
            "enabled": True,
            "question_columns": [c.strip() for c in sl_q.split(",") if c.strip()],
            "threshold": sl_thr,
            "interviewer_column": sl_int or None,
            "min_questions": 3,
        }
    else:
        st.session_state.rules_config["straightlining"] = {"enabled": False, "question_columns": []}

    st.divider()

    # ── Interviewer checks ────────────────────────────────────────────────────
    st.markdown("### Interviewer Checks")
    int_col = st.text_input("Interviewer column", placeholder="interviewer_id", key="int_col")

    id_on = st.toggle("Duration anomaly by interviewer", key="id_toggle")
    st.session_state.rules_config["interviewer_duration_check"] = {
        "enabled": id_on and bool(int_col and dur_col),
        "interviewer_column": int_col,
        "duration_column": dur_col,
        "multiplier": 1.5,
        "min_interviews": 3,
    }

    ip_on = st.toggle("Productivity outliers", key="ip_toggle")
    st.session_state.rules_config["interviewer_productivity_check"] = {
        "enabled": ip_on and bool(int_col),
        "interviewer_column": int_col,
        "multiplier": 1.5,
    }

    st.divider()

    # ── Consent / eligibility ────────────────────────────────────────────────
    st.markdown("### Consent / Eligibility")
    ce_on = st.toggle("Enable consent check", key="ce_toggle")
    if ce_on:
        sc_col  = st.text_input("Screener column", placeholder="consent")
        dq_op   = st.selectbox("Disqualify operator", ["!=","==","<",">","<=",">="])
        dq_val  = st.text_input("Disqualify value", placeholder="Yes")
        sub_raw = st.text_input("Subsequent columns (comma-sep)", placeholder="Q1,Q2,Q3")
        st.session_state.rules_config["consent_eligibility_check"] = {
            "enabled": bool(sc_col and dq_val),
            "screener_column": sc_col,
            "disqualify_operator": dq_op,
            "disqualify_value": dq_val,
            "subsequent_columns": [c.strip() for c in sub_raw.split(",") if c.strip()],
        }
    else:
        st.session_state.rules_config["consent_eligibility_check"] = {
            "enabled": False, "screener_column": "",
            "disqualify_operator": "!=", "disqualify_value": "", "subsequent_columns": [],
        }

    st.divider()

    # ── Fabrication detection ────────────────────────────────────────────────
    st.markdown("### Fabrication Detection")
    fab_on = st.toggle("Enable fabrication check", key="fab_toggle")
    if fab_on:
        fab_id  = st.text_input("Respondent ID column", placeholder="respondent_id")
        fab_num = st.text_input("Numeric columns for variance (comma-sep)", placeholder="Q1,Q2,Q3")
        fab_vt  = st.slider("Variance threshold", 0.01, 0.5, 0.1, 0.01)
        fab_rl  = st.number_input("Sequential run length to flag", value=5, min_value=2)
        st.session_state.rules_config["fabrication_check"] = {
            "enabled": True,
            "id_column": fab_id or None,
            "numeric_columns": [c.strip() for c in fab_num.split(",") if c.strip()],
            "interviewer_column": int_col or None,
            "variance_threshold": fab_vt,
            "sequence_run_length": int(fab_rl),
        }
    else:
        st.session_state.rules_config["fabrication_check"] = {"enabled": False}

    # ── Rerun ─────────────────────────────────────────────────────────────────
    if st.session_state.df_clean is not None:
        st.divider()
        if st.button("↺ Rerun QC", use_container_width=True, type="primary"):
            with st.spinner("Running..."):
                run_pipeline(st.session_state.df_raw, st.session_state.filename)
            st.success("Done")


# ══════════════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════════════

if st.session_state.df_clean is None:
    st.markdown("""
    <div style="text-align:center; padding:80px 40px;">
        <h1 style="font-size:2.8rem; font-weight:800;">QC Automation Engine</h1>
        <p style="color:#8b90a8; margin-top:12px;">
            Upload a CSV or Excel file to run automated quality control,<br>
            exploratory analysis, and generate a structured report.
        </p>
        <div style="margin-top:40px; display:flex; justify-content:center; gap:20px; flex-wrap:wrap;">
    """ + "".join([
        f'<div style="background:#111318;border:1px solid #1f2330;border-radius:8px;'
        f'padding:18px 22px;width:160px;">'
        f'<div style="font-size:1.3rem;">{ic}</div>'
        f'<div style="font-family:Syne,sans-serif;font-weight:700;margin-top:6px;font-size:12px;">{tt}</div>'
        f'<div style="font-size:10px;color:#8b90a8;margin-top:4px;">{dd}</div></div>'
        for ic, tt, dd in [
            ("🔍", "Missing Values",  "Per-column rates"),
            ("📐", "Range Checks",    "Outlier detection"),
            ("🔗", "Logic Rules",     "Rich multi-condition"),
            ("📋", "Straightlining",  "Repeated answer detection"),
            ("🕵️", "Fabrication",    "Sequence & variance"),
            ("👤", "Interviewer QC",  "Duration & productivity"),
        ]
    ]) + "</div></div>", unsafe_allow_html=True)
    st.stop()


df       = st.session_state.df_clean
results  = st.session_state.qc_results
filename = st.session_state.filename

# ── Header ────────────────────────────────────────────────────────────────────
h1, h2 = st.columns([5, 1])
with h1:
    st.markdown(f"### {filename}")
    st.caption(f"{len(df):,} rows · {len(df.columns)} columns · "
               f"Last run: {datetime.now().strftime('%H:%M:%S')}")
with h2:
    st.download_button(
        "↓ Report",
        data=build_report(df, results),
        file_name=f"QC_{filename.rsplit('.',1)[0]}_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True, type="primary",
    )

st.divider()

# ── Score cards ───────────────────────────────────────────────────────────────
total_flags = sum(r.flag_count for r in results)
crits = sum(1 for r in results if r.severity == "critical" and r.flag_count > 0)
warns = sum(1 for r in results if r.severity == "warning"  and r.flag_count > 0)
infos = sum(1 for r in results if r.severity == "info"     and r.flag_count > 0)

m1, m2, m3, m4, m5 = st.columns(5)
m1.metric("Checks Run",  len(results))
m2.metric("Total Flags", total_flags)
m3.metric("Critical",    crits)
m4.metric("Warnings",    warns)
m5.metric("Info",        infos)
st.divider()

# ── Tabs ──────────────────────────────────────────────────────────────────────
tab_qc, tab_sl, tab_int, tab_eda, tab_data, tab_cfg = st.tabs([
    "QC Report", "Straightlining", "Interviewers", "EDA", "Data Preview", "Config"
])


# ── TAB: QC Report ────────────────────────────────────────────────────────────
with tab_qc:
    if total_flags == 0:
        st.success("No issues detected — dataset passed all checks.")
    else:
        for sev, label in [("critical","Critical Issues"),("warning","Warnings"),("info","Info")]:
            sev_res = [r for r in results if r.severity == sev and r.flag_count > 0]
            if not sev_res:
                continue
            st.markdown(f"<h4 style='color:{sev_color(sev)};margin-top:1rem;'>"
                        f"{sev_emoji(sev)} {label}</h4>", unsafe_allow_html=True)
            for r in sev_res:
                pct = r.flag_count / max(len(df), 1) * 100
                with st.expander(f"{r.check_name} — **{r.flag_count:,}** rows ({pct:.1f}%)",
                                 expanded=(sev == "critical")):
                    mc, dc = st.columns([2, 3])
                    with mc:
                        st.markdown("**Metadata**")
                        st.json(r.summary(), expanded=False)
                    with dc:
                        if not r.flagged_rows.empty:
                            show = [c for c in r.flagged_rows.columns if not c.startswith("_")]
                            st.dataframe(r.flagged_rows[show].head(50),
                                         use_container_width=True, hide_index=True)

    st.markdown("#### All checks summary")
    st.dataframe(pd.DataFrame([r.summary() for r in results]),
                 use_container_width=True, hide_index=True)


# ── TAB: Straightlining ───────────────────────────────────────────────────────
with tab_sl:
    st.markdown("#### Straightlining Analysis")
    sl_r = next((r for r in results if r.check_name == "straightlining_check"), None)
    if not sl_r:
        st.info("Enable straightlining in the sidebar and re-run.")
    elif sl_r.flag_count == 0:
        st.success("No straightliners detected.")
    else:
        meta = sl_r.metadata
        c1, c2, c3 = st.columns(3)
        c1.metric("Flagged respondents", meta.get("flagged_respondents", 0))
        c2.metric("% of total",          f"{meta.get('pct_of_total', 0)}%")
        c3.metric("Threshold",           f"{int(meta.get('threshold', 1) * 100)}%")

        show = [c for c in sl_r.flagged_rows.columns if not c.startswith("_")]
        st.dataframe(sl_r.flagged_rows[show], use_container_width=True, hide_index=True)

        if "interviewer_summary" in meta and meta["interviewer_summary"]:
            st.markdown("##### By interviewer")
            int_df = pd.DataFrame(meta["interviewer_summary"])
            st.dataframe(int_df, use_container_width=True, hide_index=True)
            st.bar_chart(int_df.set_index(int_df.columns[0])["sl_count"], height=220)


# ── TAB: Interviewers ─────────────────────────────────────────────────────────
with tab_int:
    st.markdown("#### Interviewer Analysis")
    dur_r  = next((r for r in results if r.check_name == "interviewer_duration_check"),    None)
    prod_r = next((r for r in results if r.check_name == "interviewer_productivity_check"), None)
    fab_r  = next((r for r in results if r.check_name == "fabrication_check"),              None)

    if not any([dur_r, prod_r, fab_r]):
        st.info("Enable interviewer checks in the sidebar and re-run.")

    if dur_r and dur_r.flag_count > 0:
        st.markdown("##### Duration anomalies")
        meta = dur_r.metadata
        c1, c2, c3 = st.columns(3)
        c1.metric("Outlier interviewers", meta.get("outlier_interviewers", 0))
        c2.metric("Too fast", meta.get("too_fast", 0))
        c3.metric("Too slow", meta.get("too_slow", 0))
        show = [c for c in dur_r.flagged_rows.columns if not c.startswith("_")]
        st.dataframe(dur_r.flagged_rows[show].drop_duplicates(),
                     use_container_width=True, hide_index=True)

    if prod_r and prod_r.flag_count > 0:
        st.markdown("##### Productivity outliers")
        meta = prod_r.metadata
        c1, c2, c3 = st.columns(3)
        c1.metric("Outlier interviewers", meta.get("outlier_interviewers", 0))
        c2.metric("Unusually high", meta.get("unusually_high", 0))
        c3.metric("Unusually low",  meta.get("unusually_low",  0))
        show = [c for c in prod_r.flagged_rows.columns if not c.startswith("_")]
        st.dataframe(prod_r.flagged_rows[show].drop_duplicates(),
                     use_container_width=True, hide_index=True)

    if fab_r and fab_r.flag_count > 0:
        st.markdown("##### Fabrication flags")
        show = [c for c in fab_r.flagged_rows.columns if not c.startswith("_")]
        st.dataframe(fab_r.flagged_rows[show].head(100),
                     use_container_width=True, hide_index=True)
        st.json(fab_r.metadata, expanded=False)


# ── TAB: EDA ─────────────────────────────────────────────────────────────────
with tab_eda:
    st.markdown("#### Exploratory Data Analysis")
    num_cols = df.select_dtypes(include="number").columns.tolist()
    cat_cols = df.select_dtypes(exclude="number").columns.tolist()

    if num_cols:
        st.markdown("##### Numeric Summary")
        desc = df[num_cols].describe().T
        desc["missing"]   = df[num_cols].isnull().sum()
        desc["missing_%"] = (df[num_cols].isnull().mean() * 100).round(1)
        st.dataframe(desc, use_container_width=True)

        st.markdown("##### Distributions")
        for row in [num_cols[i:i+3] for i in range(0, len(num_cols), 3)]:
            cc = st.columns(len(row))
            for col, c in zip(row, cc):
                vals = df[col].dropna()
                if len(vals) > 1:
                    hist = pd.cut(vals, bins=min(20, vals.nunique())).value_counts().sort_index()
                    c.markdown(f"**{col}**")
                    c.bar_chart(pd.DataFrame({"count": hist.values},
                                             index=[str(b) for b in hist.index]),
                                height=160, use_container_width=True)
                    c.caption(f"mean={vals.mean():.2f} · std={vals.std():.2f} · n={len(vals):,}")

    if cat_cols:
        st.markdown("##### Categorical Columns")
        for row in [cat_cols[i:i+2] for i in range(0, len(cat_cols), 2)]:
            cc = st.columns(len(row))
            for col, c in zip(row, cc):
                vc = df[col].value_counts().head(10)
                c.markdown(f"**{col}**")
                c.bar_chart(vc, height=160, use_container_width=True)
                c.caption(f"{df[col].nunique()} unique · {df[col].isnull().sum()} missing")

    if len(num_cols) >= 2:
        st.markdown("##### Correlation Matrix")
        st.dataframe(df[num_cols].corr().round(2), use_container_width=True)

    st.markdown("##### Missing by Column")
    miss = pd.DataFrame({
        "column":        df.columns,
        "missing_count": df.isnull().sum().values,
        "missing_%":     (df.isnull().mean() * 100).round(1).values,
    }).sort_values("missing_%", ascending=False)
    miss = miss[miss["missing_count"] > 0]
    if miss.empty:
        st.success("No missing values found.")
    else:
        st.dataframe(miss, use_container_width=True, hide_index=True)
        st.bar_chart(miss.set_index("column")["missing_%"], height=200)


# ── TAB: Data Preview ─────────────────────────────────────────────────────────
with tab_data:
    st.markdown("#### Data Preview")
    search     = st.text_input("Filter rows", placeholder="Type to filter...")
    col_filter = st.multiselect("Show columns", df.columns.tolist(), default=df.columns.tolist())
    disp = df[col_filter] if col_filter else df
    if search:
        mask = disp.apply(lambda row: row.astype(str).str.contains(search, case=False).any(), axis=1)
        disp = disp[mask]
    st.caption(f"Showing {len(disp):,} of {len(df):,} rows")
    st.dataframe(disp, use_container_width=True, height=500)


# ── TAB: Config ───────────────────────────────────────────────────────────────
with tab_cfg:
    st.markdown("#### Active Config")
    st.json(st.session_state.rules_config)
    st.markdown("#### Custom Logic Rules")
    if st.session_state.custom_logic_rules:
        st.json(st.session_state.custom_logic_rules)
    else:
        st.caption("No custom logic rules added yet.")
