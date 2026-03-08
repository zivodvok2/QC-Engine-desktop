"""
QC Automation Engine — Streamlit UI (self-contained)
All engine logic is embedded so this runs on Streamlit Cloud
with zero local import issues.

Run locally:  streamlit run app.py
"""

import streamlit as st
import pandas as pd
import numpy as np
import json
import io
import re
import logging
import os
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional

# ══════════════════════════════════════════════════════════════════════════════
# ENGINE — utils
# ══════════════════════════════════════════════════════════════════════════════

def setup_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)
    if not logger.handlers:
        logger.setLevel(logging.INFO)
        h = logging.StreamHandler()
        h.setFormatter(logging.Formatter("[%(asctime)s] %(levelname)s | %(name)s | %(message)s",
                                         datefmt="%H:%M:%S"))
        logger.addHandler(h)
    return logger


# ══════════════════════════════════════════════════════════════════════════════
# ENGINE — validator base
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class CheckResult:
    check_name: str
    issue_type: str
    flagged_rows: pd.DataFrame
    severity: str = "warning"
    metadata: dict = field(default_factory=dict)

    @property
    def flag_count(self) -> int:
        return len(self.flagged_rows)

    def summary(self) -> dict:
        return {
            "check_name": self.check_name,
            "issue_type": self.issue_type,
            "severity": self.severity,
            "flagged_count": self.flag_count,
            **self.metadata,
        }


class BaseCheck(ABC):
    name: str = "base_check"
    issue_type: str = "generic"
    severity: str = "warning"

    @abstractmethod
    def run(self, df: pd.DataFrame) -> CheckResult:
        raise NotImplementedError

    def _make_result(self, flagged: pd.DataFrame, metadata: Optional[dict] = None) -> CheckResult:
        return CheckResult(
            check_name=self.name,
            issue_type=self.issue_type,
            flagged_rows=flagged,
            severity=self.severity,
            metadata=metadata or {},
        )


# ══════════════════════════════════════════════════════════════════════════════
# ENGINE — loader
# ══════════════════════════════════════════════════════════════════════════════

class DataLoader:
    log = setup_logger("loader")

    def load_from_buffer(self, uploaded_file) -> pd.DataFrame:
        name = uploaded_file.name
        ext = os.path.splitext(name)[-1].lower()
        if ext == ".csv":
            df = pd.read_csv(uploaded_file, low_memory=False)
        elif ext in (".xlsx", ".xls"):
            df = pd.read_excel(uploaded_file)
        else:
            raise ValueError(f"Unsupported format: {ext}. Use CSV or XLSX.")
        self.log.info(f"Loaded '{name}': {len(df)} rows, {len(df.columns)} cols.")
        return df

    def load(self, filepath: str) -> pd.DataFrame:
        if not os.path.exists(filepath):
            raise FileNotFoundError(f"File not found: {filepath}")
        ext = os.path.splitext(filepath)[-1].lower()
        if ext == ".csv":
            return pd.read_csv(filepath, low_memory=False)
        elif ext in (".xlsx", ".xls"):
            return pd.read_excel(filepath)
        raise ValueError(f"Unsupported format: {ext}")


# ══════════════════════════════════════════════════════════════════════════════
# ENGINE — cleaner
# ══════════════════════════════════════════════════════════════════════════════

class DataCleaner:
    log = setup_logger("cleaner")

    def clean(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        df = self._normalize_nulls(df)
        df = self._strip_whitespace(df)
        return df

    def _normalize_nulls(self, df):
        null_vals = ["", "N/A", "n/a", "NA", "na", "None", "none", "NULL", "null", "-", "--"]
        df.replace(null_vals, pd.NA, inplace=True)
        return df

    def _strip_whitespace(self, df):
        str_cols = df.select_dtypes(include="object").columns
        df[str_cols] = df[str_cols].apply(lambda c: c.str.strip() if c.dtype == "object" else c)
        return df


# ══════════════════════════════════════════════════════════════════════════════
# ENGINE — checks
# ══════════════════════════════════════════════════════════════════════════════

class MissingValueCheck(BaseCheck):
    name = "missing_value_check"
    issue_type = "missing_data"
    severity = "warning"

    def __init__(self, columns=None, threshold=None):
        self.columns = columns
        self.threshold = threshold

    def run(self, df):
        cols = [c for c in (self.columns or df.columns) if c in df.columns]
        if self.threshold is not None:
            rates = df[cols].isnull().mean()
            bad = rates[rates > self.threshold].index.tolist()
            flagged = df[df[bad].isnull().any(axis=1)] if bad else df.iloc[0:0]
            meta = {"threshold": self.threshold, "columns_exceeding_threshold": bad}
        else:
            flagged = df[df[cols].isnull().any(axis=1)].copy()
            flagged["_missing_columns"] = flagged[cols].apply(
                lambda r: [c for c in cols if pd.isnull(r[c])], axis=1)
            meta = {"checked_columns": cols}
        return self._make_result(flagged, meta)


class HighMissingColumnCheck(BaseCheck):
    name = "high_missing_column_check"
    issue_type = "column_missing_rate"
    severity = "info"

    def __init__(self, threshold=0.2):
        self.threshold = threshold

    def run(self, df):
        rates = df.isnull().mean()
        bad = rates[rates > self.threshold]
        summary = pd.DataFrame({"column": bad.index, "missing_rate": bad.values})
        return self._make_result(summary, {"threshold": self.threshold,
                                           "flagged_columns": bad.index.tolist()})


class RangeCheck(BaseCheck):
    name = "range_check"
    issue_type = "out_of_range"
    severity = "warning"

    def __init__(self, rules):
        self.rules = rules

    def run(self, df):
        all_flagged = []
        for rule in self.rules:
            col, lo, hi = rule.get("column"), rule.get("min"), rule.get("max")
            if col not in df.columns:
                continue
            num = pd.to_numeric(df[col], errors="coerce")
            mask = pd.Series(False, index=df.index)
            if lo is not None:
                mask |= num < lo
            if hi is not None:
                mask |= num > hi
            flagged = df[mask].copy()
            flagged["_range_issue"] = col
            flagged["_value"] = num[mask]
            flagged["_expected_range"] = f"[{lo}, {hi}]"
            all_flagged.append(flagged)
        combined = pd.concat(all_flagged, ignore_index=True) if all_flagged else df.iloc[0:0]
        return self._make_result(combined, {"rules_applied": len(self.rules)})


class DurationCheck(BaseCheck):
    name = "duration_check"
    issue_type = "interview_duration"
    severity = "warning"

    def __init__(self, column, min_minutes=5, max_minutes=120):
        self.column = column
        self.min_minutes = min_minutes
        self.max_minutes = max_minutes

    def run(self, df):
        if self.column not in df.columns:
            return self._make_result(df.iloc[0:0])
        dur = pd.to_numeric(df[self.column], errors="coerce")
        mask = (dur < self.min_minutes) | (dur > self.max_minutes)
        flagged = df[mask].copy()
        flagged["_duration_issue"] = dur[mask]
        return self._make_result(flagged, {
            "min_expected": self.min_minutes, "max_expected": self.max_minutes,
            "too_short": int((dur < self.min_minutes).sum()),
            "too_long": int((dur > self.max_minutes).sum()),
        })


class LogicCheck(BaseCheck):
    name = "logic_check"
    issue_type = "logic_violation"
    severity = "critical"

    def __init__(self, rules):
        self.rules = rules

    def run(self, df):
        all_flagged = []
        for rule in self.rules:
            if_col = rule.get("if_column")
            if_val = rule.get("if_value")
            then_col = rule.get("then_column")
            cond = rule.get("then_condition")
            desc = rule.get("description", f"{if_col}={if_val} -> {then_col} {cond}")
            if if_col not in df.columns or then_col not in df.columns:
                continue
            trigger = df[if_col] == if_val
            if cond == "must_be_null":
                violation = trigger & df[then_col].notna()
            elif cond == "must_not_be_null":
                violation = trigger & df[then_col].isna()
            else:
                continue
            flagged = df[violation].copy()
            flagged["_logic_rule"] = desc
            all_flagged.append(flagged)
        combined = pd.concat(all_flagged, ignore_index=True) if all_flagged else df.iloc[0:0]
        return self._make_result(combined, {"rules_applied": len(self.rules)})


class DuplicateCheck(BaseCheck):
    name = "duplicate_check"
    issue_type = "duplicate_record"
    severity = "critical"

    def __init__(self, subset=None):
        self.subset = subset

    def run(self, df):
        subset = [c for c in self.subset if c in df.columns] if self.subset else None
        dupes = df[df.duplicated(subset=subset, keep=False)].copy()
        return self._make_result(dupes, {"subset": subset, "duplicate_count": len(dupes)})


class PatternCheck(BaseCheck):
    name = "pattern_check"
    issue_type = "pattern_mismatch"
    severity = "warning"

    def __init__(self, rules):
        self.rules = rules

    def run(self, df):
        all_flagged = []
        for rule in self.rules:
            col = rule.get("column")
            pattern = rule.get("pattern")
            desc = rule.get("description", f"{col} pattern check")
            if col not in df.columns:
                continue
            compiled = re.compile(pattern)
            str_col = df[col].astype(str).where(df[col].notna(), other=pd.NA)
            invalid = str_col.notna() & ~str_col.apply(
                lambda x: bool(compiled.match(x)) if pd.notna(x) else True)
            flagged = df[invalid].copy()
            flagged["_pattern_issue"] = desc
            all_flagged.append(flagged)
        combined = pd.concat(all_flagged, ignore_index=True) if all_flagged else df.iloc[0:0]
        return self._make_result(combined, {"rules_applied": len(self.rules)})


class AnomalyCheck(BaseCheck):
    name = "anomaly_check"
    issue_type = "statistical_anomaly"
    severity = "info"

    def __init__(self, columns, multiplier=1.5):
        self.columns = columns
        self.multiplier = multiplier

    def run(self, df):
        all_flagged = []
        for col in self.columns:
            if col not in df.columns:
                continue
            num = pd.to_numeric(df[col], errors="coerce")
            q1, q3 = num.quantile(0.25), num.quantile(0.75)
            iqr = q3 - q1
            lo, hi = q1 - self.multiplier * iqr, q3 + self.multiplier * iqr
            mask = (num < lo) | (num > hi)
            flagged = df[mask].copy()
            flagged["_anomaly_column"] = col
            flagged["_anomaly_value"] = num[mask]
            flagged["_anomaly_bounds"] = f"[{lo:.2f}, {hi:.2f}]"
            all_flagged.append(flagged)
        combined = pd.concat(all_flagged, ignore_index=True) if all_flagged else df.iloc[0:0]
        return self._make_result(combined, {"multiplier": self.multiplier})


# ══════════════════════════════════════════════════════════════════════════════
# ENGINE — rule engine
# ══════════════════════════════════════════════════════════════════════════════

class RuleEngine:
    log = setup_logger("rule_engine")

    def __init__(self, config: dict):
        self.config = config
        self.checks: List[BaseCheck] = []
        self.results: List[CheckResult] = []
        self._build_checks()

    def _build_checks(self):
        cfg = self.config
        threshold = cfg.get("missing_threshold")
        if threshold is not None:
            self.checks.append(MissingValueCheck(threshold=threshold))
            self.checks.append(HighMissingColumnCheck(threshold=threshold))
        if cfg.get("range_rules"):
            self.checks.append(RangeCheck(rules=cfg["range_rules"]))
        if cfg.get("logic_rules"):
            self.checks.append(LogicCheck(rules=cfg["logic_rules"]))
        if cfg.get("pattern_rules"):
            self.checks.append(PatternCheck(rules=cfg["pattern_rules"]))
        dup = cfg.get("duplicate_check", {})
        if dup.get("enabled"):
            self.checks.append(DuplicateCheck(subset=dup.get("subset_columns") or None))
        dur = cfg.get("interview_duration", {})
        if dur.get("enabled"):
            self.checks.append(DurationCheck(
                column=dur["column"],
                min_minutes=dur.get("min_expected", 5),
                max_minutes=dur.get("max_expected", 120),
            ))

    def add_check(self, check: BaseCheck):
        self.checks.append(check)

    def run(self, df: pd.DataFrame) -> List[CheckResult]:
        self.results = []
        for check in self.checks:
            try:
                result = check.run(df)
                self.results.append(result)
            except Exception as e:
                self.log.error(f"{check.name} failed: {e}", exc_info=True)
        return self.results


# ══════════════════════════════════════════════════════════════════════════════
# DEFAULT CONFIG
# ══════════════════════════════════════════════════════════════════════════════

DEFAULT_CONFIG = {
    "missing_threshold": 0.1,
    "range_rules": [],
    "logic_rules": [],
    "pattern_rules": [
        {"column": "phone", "pattern": r"^\+?[0-9\-\s]{7,15}$", "description": "Valid phone format"},
        {"column": "email", "pattern": r"^[^@]+@[^@]+\.[^@]+$", "description": "Valid email format"},
    ],
    "duplicate_check": {"enabled": True, "subset_columns": []},
    "interview_duration": {"enabled": False, "column": "duration_minutes",
                           "min_expected": 5, "max_expected": 120},
}


# ══════════════════════════════════════════════════════════════════════════════
# STREAMLIT UI
# ══════════════════════════════════════════════════════════════════════════════

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


# ── Session state ─────────────────────────────────────────────────────────────
def init_state():
    defaults = {
        "df_raw": None, "df_clean": None, "qc_results": None,
        "filename": None,
        "rules_config": DEFAULT_CONFIG.copy(),
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
    df_clean = DataCleaner().clean(df)
    cfg = dict(st.session_state.rules_config)
    cfg["logic_rules"] = cfg.get("logic_rules", []) + st.session_state.custom_rules
    results = RuleEngine(config=cfg).run(df_clean)
    st.session_state.df_raw = df
    st.session_state.df_clean = df_clean
    st.session_state.qc_results = results
    st.session_state.filename = filename

def build_excel_report(df_clean, results):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        pd.DataFrame([r.summary() for r in results]).to_excel(
            writer, sheet_name="QC Summary", index=False)
        flagged_frames = []
        for r in results:
            if r.flag_count > 0:
                tmp = r.flagged_rows.copy()
                tmp["_qc_check"] = r.check_name
                tmp["_severity"] = r.severity
                flagged_frames.append(tmp)
        if flagged_frames:
            pd.concat(flagged_frames, ignore_index=True).to_excel(
                writer, sheet_name="Flagged Records", index=False)
        numeric_cols = df_clean.select_dtypes(include="number").columns
        if len(numeric_cols):
            df_clean[numeric_cols].describe().T.to_excel(writer, sheet_name="EDA Numeric")
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

    st.markdown("### Upload Data")
    uploaded = st.file_uploader("Drop CSV or Excel file", type=["csv", "xlsx", "xls"],
                                 label_visibility="collapsed")
    if uploaded:
        with st.spinner("Loading & running QC..."):
            try:
                df = DataLoader().load_from_buffer(uploaded)
                run_pipeline(df, uploaded.name)
                st.success(f"Loaded {len(df):,} rows")
            except Exception as e:
                st.error(f"Error: {e}")

    st.divider()

    st.markdown("### QC Settings")
    missing_threshold = st.slider("Missing value threshold", 0.0, 1.0, 0.10, 0.01, format="%.0f%%")
    st.session_state.rules_config["missing_threshold"] = missing_threshold

    duration_col = st.text_input("Duration column name", value="duration_minutes")
    min_dur = st.number_input("Min interview duration (mins)", value=5, min_value=0)
    max_dur = st.number_input("Max interview duration (mins)", value=120, min_value=1)
    st.session_state.rules_config["interview_duration"] = {
        "enabled": bool(duration_col),
        "column": duration_col,
        "min_expected": min_dur,
        "max_expected": max_dur,
    }

    st.divider()

    st.markdown("### Logic Rules")
    st.caption("Skip-logic / conditional checks")
    with st.expander("+ Add rule", expanded=False):
        if_col  = st.text_input("If column",     key="r_if_col")
        if_val  = st.text_input("Equals value",  key="r_if_val")
        then_col = st.text_input("Then column",  key="r_then_col")
        condition = st.selectbox("Condition", ["must_be_null", "must_not_be_null"], key="r_cond")
        if st.button("Add Rule", use_container_width=True):
            if if_col and if_val and then_col:
                st.session_state.custom_rules.append({
                    "if_column": if_col, "if_value": if_val,
                    "then_column": then_col, "then_condition": condition,
                    "description": f"If {if_col}={if_val} -> {then_col} {condition}",
                })
                st.success("Rule added")

    for i, r in enumerate(st.session_state.custom_rules):
        c1, c2 = st.columns([5, 1])
        c1.caption(r["description"])
        if c2.button("x", key=f"del_{i}"):
            st.session_state.custom_rules.pop(i)
            st.rerun()

    if st.session_state.df_clean is not None:
        st.divider()
        if st.button("Rerun QC", use_container_width=True, type="primary"):
            with st.spinner("Running..."):
                run_pipeline(st.session_state.df_raw, st.session_state.filename)
            st.success("Done")


# ══════════════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════════════

if st.session_state.df_clean is None:
    st.markdown("""
    <div style="text-align:center; padding: 80px 40px;">
        <h1 style="font-size:2.8rem; font-weight:800; letter-spacing:-0.01em;">QC Automation Engine</h1>
        <p style="font-size:1rem; color:#8b90a8; margin-top:12px;">
            Upload a CSV or Excel file to run automated quality control checks,<br>
            exploratory analysis, and generate a structured QC report.
        </p>
        <div style="margin-top:40px; display:flex; justify-content:center; gap:32px; flex-wrap:wrap;">
            <div style="background:#111318;border:1px solid #1f2330;border-radius:8px;padding:20px 28px;width:180px;">
                <div style="font-size:1.4rem;">🔍</div>
                <div style="font-family:Syne,sans-serif;font-weight:700;margin-top:8px;">Missing Values</div>
                <div style="font-size:11px;color:#8b90a8;margin-top:4px;">Per-column detection & rate</div>
            </div>
            <div style="background:#111318;border:1px solid #1f2330;border-radius:8px;padding:20px 28px;width:180px;">
                <div style="font-size:1.4rem;">📐</div>
                <div style="font-family:Syne,sans-serif;font-weight:700;margin-top:8px;">Range Checks</div>
                <div style="font-size:11px;color:#8b90a8;margin-top:4px;">Outliers & bound violations</div>
            </div>
            <div style="background:#111318;border:1px solid #1f2330;border-radius:8px;padding:20px 28px;width:180px;">
                <div style="font-size:1.4rem;">🔗</div>
                <div style="font-family:Syne,sans-serif;font-weight:700;margin-top:8px;">Logic Rules</div>
                <div style="font-size:11px;color:#8b90a8;margin-top:4px;">Skip-pattern violations</div>
            </div>
            <div style="background:#111318;border:1px solid #1f2330;border-radius:8px;padding:20px 28px;width:180px;">
                <div style="font-size:1.4rem;">📊</div>
                <div style="font-family:Syne,sans-serif;font-weight:700;margin-top:8px;">EDA</div>
                <div style="font-size:11px;color:#8b90a8;margin-top:4px;">Distributions & summaries</div>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)
    st.stop()

df = st.session_state.df_clean
results = st.session_state.qc_results
filename = st.session_state.filename

# ── Header ────────────────────────────────────────────────────────────────────
col_title, col_export = st.columns([5, 1])
with col_title:
    st.markdown(f"### {filename}")
    st.caption(f"{len(df):,} rows · {len(df.columns)} columns · "
               f"Last run: {datetime.now().strftime('%H:%M:%S')}")
with col_export:
    st.download_button(
        "Download Report",
        data=build_excel_report(df, results),
        file_name=f"QC_Report_{filename.rsplit('.', 1)[0]}_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True, type="primary",
    )

st.divider()

# ── Scorecards ────────────────────────────────────────────────────────────────
total_flags = sum(r.flag_count for r in results)
crits = sum(1 for r in results if r.severity == "critical" and r.flag_count > 0)
warns = sum(1 for r in results if r.severity == "warning"  and r.flag_count > 0)
infos = sum(1 for r in results if r.severity == "info"     and r.flag_count > 0)

m1, m2, m3, m4, m5 = st.columns(5)
m1.metric("Total Checks", len(results))
m2.metric("Total Flags",  total_flags)
m3.metric("Critical",     crits)
m4.metric("Warnings",     warns)
m5.metric("Info",         infos)
st.divider()

# ── Tabs ──────────────────────────────────────────────────────────────────────
tab_qc, tab_eda, tab_data, tab_cfg = st.tabs(["QC Report", "EDA", "Data Preview", "Config"])


# ── TAB 1: QC Report ─────────────────────────────────────────────────────────
with tab_qc:
    if total_flags == 0:
        st.success("No issues detected — dataset passed all checks.")
    else:
        for sev, label in [("critical", "Critical Issues"), ("warning", "Warnings"), ("info", "Info")]:
            sev_results = [r for r in results if r.severity == sev and r.flag_count > 0]
            if not sev_results:
                continue
            color = severity_color(sev)
            st.markdown(f"<h4 style='color:{color};margin-top:1.2rem;'>"
                        f"{severity_emoji(sev)} {label}</h4>", unsafe_allow_html=True)
            for r in sev_results:
                pct = r.flag_count / max(len(df), 1) * 100
                with st.expander(f"{r.check_name} — **{r.flag_count:,}** rows ({pct:.1f}%)",
                                 expanded=(sev == "critical")):
                    meta_col, data_col = st.columns([2, 3])
                    with meta_col:
                        st.markdown("**Check metadata**")
                        st.json(r.summary(), expanded=False)
                    with data_col:
                        if not r.flagged_rows.empty:
                            display_cols = [c for c in r.flagged_rows.columns if not c.startswith("_")]
                            st.dataframe(r.flagged_rows[display_cols].head(50),
                                         use_container_width=True, hide_index=True)

    st.markdown("#### All checks summary")
    st.dataframe(pd.DataFrame([r.summary() for r in results]),
                 use_container_width=True, hide_index=True)


# ── TAB 2: EDA ───────────────────────────────────────────────────────────────
with tab_eda:
    st.markdown("#### Exploratory Data Analysis")
    numeric_cols = df.select_dtypes(include="number").columns.tolist()
    cat_cols     = df.select_dtypes(exclude="number").columns.tolist()

    if numeric_cols:
        st.markdown("##### Numeric Summary")
        desc = df[numeric_cols].describe().T
        desc["missing"]   = df[numeric_cols].isnull().sum()
        desc["missing_%"] = (df[numeric_cols].isnull().mean() * 100).round(1)
        st.dataframe(desc.style.background_gradient(cmap="Blues", subset=["mean", "std"]),
                     use_container_width=True)

        st.markdown("##### Distributions")
        for row in [numeric_cols[i:i+3] for i in range(0, len(numeric_cols), 3)]:
            chart_cols = st.columns(len(row))
            for col, c in zip(row, chart_cols):
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
            chart_cols = st.columns(len(row))
            for col, c in zip(row, chart_cols):
                vc = df[col].value_counts().head(10)
                c.markdown(f"**{col}**")
                c.bar_chart(vc, height=160, use_container_width=True)
                c.caption(f"{df[col].nunique()} unique · {df[col].isnull().sum()} missing")

    if len(numeric_cols) >= 2:
        st.markdown("##### Correlation Matrix")
        st.dataframe(df[numeric_cols].corr().round(2).style.background_gradient(
            cmap="RdYlGn", vmin=-1, vmax=1), use_container_width=True)

    st.markdown("##### Missing Values by Column")
    missing_df = pd.DataFrame({
        "column":        df.columns,
        "missing_count": df.isnull().sum().values,
        "missing_%":     (df.isnull().mean() * 100).round(1).values,
    }).sort_values("missing_%", ascending=False)
    missing_df = missing_df[missing_df["missing_count"] > 0]
    if missing_df.empty:
        st.success("No missing values found.")
    else:
        st.dataframe(missing_df, use_container_width=True, hide_index=True)
        st.bar_chart(missing_df.set_index("column")["missing_%"], height=200)


# ── TAB 3: Data Preview ───────────────────────────────────────────────────────
with tab_data:
    st.markdown("#### Data Preview")
    search     = st.text_input("Filter rows", placeholder="Type to filter any value...")
    col_filter = st.multiselect("Show columns", options=df.columns.tolist(),
                                 default=df.columns.tolist())
    display_df = df[col_filter] if col_filter else df
    if search:
        mask = display_df.apply(
            lambda row: row.astype(str).str.contains(search, case=False).any(), axis=1)
        display_df = display_df[mask]
    st.caption(f"Showing {len(display_df):,} of {len(df):,} rows")
    st.dataframe(display_df, use_container_width=True, height=500)


# ── TAB 4: Config ─────────────────────────────────────────────────────────────
with tab_cfg:
    st.markdown("#### Active Rules Config")
    st.json(st.session_state.rules_config)
    st.markdown("#### Custom Logic Rules")
    if st.session_state.custom_rules:
        st.json(st.session_state.custom_rules)
    else:
        st.caption("No custom rules added yet. Use the sidebar to add them.")
