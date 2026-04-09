"""
ui/sidebar.py — DataSense sidebar

Handles file upload, basic QC settings, logic rule builder,
advanced check toggles, and settings panel.
"""

import io
import hashlib
import json
import requests
import streamlit as st
import pandas as pd
from datetime import datetime
from core.loader import DataLoader
from core.cleaner import DataCleaner
from core.rule_engine import RuleEngine
from ui.settings import render_settings, init_settings


@st.cache_data(show_spinner=False, max_entries=10)
def _cached_load_clean(file_bytes: bytes, filename: str) -> pd.DataFrame:
    """Load and clean a file — cached by content so rerenders never re-process."""
    buf = io.BytesIO(file_bytes)
    buf.name = filename
    df = DataLoader().load_from_buffer(buf)
    return DataCleaner().clean(df)


def _nl_to_check_config(description: str, columns: list) -> dict | None:
    """
    Convert a plain-English QC check description to a typed config dict via Groq.
    Returns one of: range / logic / duration / pattern (keyed by "type").
    """
    try:
        from checks.verbatim_checks import _get_api_key
        api_key = _get_api_key()
    except Exception:
        return None
    if not api_key:
        return None

    prompt = (
        f'Convert this survey QC rule to JSON.\n\n'
        f'Description: "{description}"\n'
        f'Available columns: {columns[:50]}\n\n'
        'Return ONE of the following JSON formats — no explanation, no markdown:\n\n'
        '1. Range rule (column must be within bounds):\n'
        '   {"type":"range","column":"col","min":N,"max":N,"description":"..."}\n\n'
        '2. Logic rule (IF condition THEN condition):\n'
        '   {"type":"logic","description":"...","if_conditions":[{"column":"col","operator":"op","value":"val"}],"then_conditions":[{"column":"col","operator":"op"}]}\n\n'
        '3. Duration check (interview length bounds):\n'
        '   {"type":"duration","column":"col","min":N,"max":N}\n\n'
        '4. Pattern rule (regex format check):\n'
        '   {"type":"pattern","column":"col","pattern":"regex","description":"..."}\n\n'
        'Logic operators: >, <, >=, <=, ==, !=, is_null, not_null, in_list, not_in_list\n'
        'Omit "value" for is_null/not_null. Only use column names from the list above.\n'
        'Return ONLY the JSON object.'
    )
    try:
        r = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            json={
                "model": "llama-3.1-8b-instant",
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.1,
                "max_tokens": 400,
            },
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            timeout=15,
        )
        r.raise_for_status()
        raw = r.json()["choices"][0]["message"]["content"].strip()
        start = raw.find("{")
        end   = raw.rfind("}") + 1
        if start == -1 or end == 0:
            return None
        return json.loads(raw[start:end])
    except Exception:
        return None


def _apply_nl_check(cfg: dict) -> tuple[bool, str]:
    """Apply a parsed NL check config to session state. Returns (ok, message)."""
    ctype = cfg.get("type")
    if ctype == "range":
        rule = {k: v for k, v in cfg.items() if k != "type"}
        st.session_state.rules_config.setdefault("range_rules", []).append(rule)
        return True, f"Range rule added: {cfg.get('description', cfg.get('column'))}"
    elif ctype == "logic":
        rule = {k: v for k, v in cfg.items() if k != "type"}
        st.session_state.custom_logic_rules.append(rule)
        return True, f"Logic rule added: {cfg.get('description', '')}"
    elif ctype == "duration":
        st.session_state.rules_config["interview_duration"] = {
            "enabled": True,
            "column":  cfg.get("column", "duration_minutes"),
            "min_expected": cfg.get("min", 5),
            "max_expected": cfg.get("max", 120),
        }
        return True, f"Duration check set: {cfg.get('column')} ({cfg.get('min')}–{cfg.get('max')} mins)"
    elif ctype == "pattern":
        rule = {k: v for k, v in cfg.items() if k != "type"}
        st.session_state.rules_config.setdefault("pattern_rules", []).append(rule)
        return True, f"Pattern rule added for: {cfg.get('column')}"
    return False, f"Unknown check type: {ctype!r}"


def _auto_detect_columns(df: pd.DataFrame) -> dict | None:
    """
    Use Groq to suggest column assignments (interviewer, duration, id, verbatim)
    from column names and a small sample of values.
    """
    try:
        from checks.verbatim_checks import _get_api_key
        api_key = _get_api_key()
    except Exception:
        return None
    if not api_key:
        return None

    sample_rows = df.head(3).to_dict(orient="records")
    col_names = df.columns.tolist()

    prompt = (
        "You are analyzing a survey dataset. Given these column names and sample rows, "
        "identify which columns serve each role.\n\n"
        f"Columns: {col_names}\n\n"
        f"Sample rows (first 3): {json.dumps(sample_rows, default=str)[:2000]}\n\n"
        "Return ONLY a JSON object with these keys (use null if unsure):\n"
        '{"interviewer_column": "col_name_or_null", '
        '"duration_column": "col_name_or_null", '
        '"id_column": "col_name_or_null", '
        '"verbatim_columns": ["col1", "col2"]}\n\n'
        "Only include column names that actually exist in the list. No explanation."
    )
    try:
        r = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            json={
                "model": "llama-3.1-8b-instant",
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.1,
                "max_tokens": 300,
            },
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            timeout=15,
        )
        r.raise_for_status()
        raw = r.json()["choices"][0]["message"]["content"].strip()
        start = raw.find("{")
        end   = raw.rfind("}") + 1
        if start == -1 or end == 0:
            return None
        return json.loads(raw[start:end])
    except Exception:
        return None


def init_state():
    defaults = {
        "df_raw": None, "df_clean": None, "qc_results": None,
        "filename": None, "custom_logic_rules": [],
        "rules_config": _default_config(),
        "column_aliases": {},
        "_audit_log": [],
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


def _default_config() -> dict:
    return {
        "missing_threshold": 0.1,
        "range_rules": [],
        "logic_rules": [],
        "pattern_rules": [
            {"column": "phone", "pattern": r"^\+?[0-9 ()-]{7,15}$", "description": "Valid phone"},
            {"column": "email", "pattern": r"^[^@]+@[^@]+\.[^@]+$",  "description": "Valid email"},
        ],
        "duplicate_check":                {"enabled": True,  "subset_columns": []},
        "interview_duration":             {"enabled": False, "column": "duration_minutes", "min_expected": 5, "max_expected": 120},
        "straightlining":                 {"enabled": False, "question_columns": [], "base_column": None, "threshold": 0.9, "min_questions": 3},
        "interviewer_duration_check":     {"enabled": False, "interviewer_column": "", "duration_column": "duration_minutes", "multiplier": 1.5, "min_interviews": 3},
        "interviewer_productivity_check": {"enabled": False, "interviewer_column": "", "multiplier": 1.5},
        "consent_eligibility_check":      {"enabled": False, "screener_column": "", "disqualify_operator": "!=", "disqualify_value": "", "subsequent_columns": []},
        "fabrication_check":              {"enabled": False, "id_column": None, "numeric_columns": [], "interviewer_column": None, "variance_threshold": 0.1, "sequence_run_length": 5},
        "verbatim_check":                 {"enabled": False, "verbatim_columns": [], "model": "llama3", "min_score": 2, "sample_size": 50},
    }


@st.cache_data(show_spinner=False, max_entries=10)
def _cached_run_checks(df_clean: pd.DataFrame, cfg_json: str) -> list:
    """Run QC checks — cached by (cleaned dataframe, config) so Rerun QC is instant when nothing changed."""
    cfg = json.loads(cfg_json)
    return RuleEngine(config=cfg).run(df_clean)


def run_pipeline(df: pd.DataFrame, filename: str):
    df_clean = DataCleaner().clean(df)
    # Apply column aliases before running checks
    aliases = st.session_state.get("column_aliases", {})
    if aliases:
        df_clean = df_clean.rename(columns=aliases)
    cfg = dict(st.session_state.rules_config)
    cfg["logic_rules"] = cfg.get("logic_rules", []) + st.session_state.custom_logic_rules
    results = _cached_run_checks(df_clean, json.dumps(cfg, default=str))
    st.session_state.df_raw     = df
    st.session_state.df_clean   = df_clean
    st.session_state.qc_results = results
    st.session_state.filename   = filename
    # Append audit log entry
    entry = {
        "timestamp":   datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "filename":    filename,
        "rows":        len(df_clean),
        "checks_run":  len(results),
        "total_flags": sum(r.flag_count for r in results),
        "critical":    sum(1 for r in results if r.severity == "critical" and r.flag_count > 0),
        "warnings":    sum(1 for r in results if r.severity == "warning"  and r.flag_count > 0),
        "aliases_applied": list(aliases.keys()) if aliases else [],
        "flags_by_check":  {r.check_name: r.flag_count for r in results if r.flag_count > 0},
        "config_snapshot": dict(st.session_state.rules_config),
    }
    st.session_state._audit_log = st.session_state.get("_audit_log", []) + [entry]


def render_sidebar():
    init_state()
    init_settings()

    with st.sidebar:
        # ── Branding ──────────────────────────────────────────────────────
        st.markdown(
            """
            <div style="display:flex;align-items:center;gap:10px;padding:4px 0 12px;">
                <div style="width:32px;height:32px;background:var(--ds-accent);border-radius:6px;
                            display:flex;align-items:center;justify-content:center;">
                    <svg width="18" height="18" viewBox="0 0 24 24" fill="none"
                         stroke="#0b0c0f" stroke-width="2.5" stroke-linecap="round">
                        <polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/>
                    </svg>
                </div>
                <div>
                    <div style="font-family:var(--ds-head);font-weight:800;font-size:16px;
                                color:var(--ds-text);letter-spacing:0.02em;">DataSense</div>
                    <div style="font-size:10px;color:var(--ds-text2);letter-spacing:0.1em;">
                        SURVEY QC ENGINE</div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        # ── Upload ────────────────────────────────────────────────────────
        st.markdown(
            "<div style='font-size:10px;letter-spacing:0.1em;text-transform:uppercase;"
            "color:var(--ds-text2);margin-bottom:6px;'>Data</div>",
            unsafe_allow_html=True,
        )
        uploaded = st.file_uploader(
            "Upload CSV or Excel",
            type=["csv", "xlsx", "xls"],
            label_visibility="collapsed",
        )
        if uploaded:
            file_hash = hashlib.md5(uploaded.getvalue()).hexdigest()
            if st.session_state.get("_last_file_hash") != file_hash:
                with st.spinner("Loading..."):
                    try:
                        df_clean = _cached_load_clean(uploaded.getvalue(), uploaded.name)
                        aliases  = st.session_state.get("column_aliases", {})
                        if aliases:
                            df_clean = df_clean.rename(columns=aliases)
                        cfg = dict(st.session_state.rules_config)
                        cfg["logic_rules"] = cfg.get("logic_rules", []) + st.session_state.get("custom_logic_rules", [])
                        results = _cached_run_checks(df_clean, json.dumps(cfg, default=str))
                        st.session_state.df_raw     = df_clean   # no raw needed post-clean cache
                        st.session_state.df_clean   = df_clean
                        st.session_state.qc_results = results
                        st.session_state.filename   = uploaded.name
                        st.session_state["_last_file_hash"] = file_hash
                        entry = {
                            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                            "filename": uploaded.name, "rows": len(df_clean),
                            "checks_run": len(results),
                            "total_flags": sum(r.flag_count for r in results),
                            "critical": sum(1 for r in results if r.severity == "critical" and r.flag_count > 0),
                            "warnings": sum(1 for r in results if r.severity == "warning"  and r.flag_count > 0),
                            "aliases_applied": list(aliases.keys()) if aliases else [],
                            "flags_by_check": {r.check_name: r.flag_count for r in results if r.flag_count > 0},
                            "config_snapshot": dict(st.session_state.rules_config),
                        }
                        st.session_state._audit_log = st.session_state.get("_audit_log", []) + [entry]
                        st.success(f"✓ {len(df_clean):,} rows loaded")
                    except Exception as e:
                        st.error(f"Error: {e}")

        # Auto-detect columns
        if st.session_state.df_clean is not None:
            if st.button("🔍 Auto-detect columns", use_container_width=True,
                         help="Use Groq AI to suggest interviewer, duration, ID, and verbatim columns"):
                with st.spinner("Detecting column types…"):
                    suggestions = _auto_detect_columns(st.session_state.df_clean)
                if suggestions:
                    st.session_state["_auto_detect"] = suggestions
                    st.success("Columns detected — applied below")
                    st.rerun()
                else:
                    st.warning("Could not detect — check Groq API key in ⚙️ Settings")

            if st.session_state.get("_auto_detect"):
                det = st.session_state["_auto_detect"]
                if any(v for v in det.values()):
                    with st.expander("🔍 Detected columns", expanded=False):
                        for k, v in det.items():
                            if v:
                                st.caption(f"{k}: **{v}**")

        if st.session_state.df_clean is not None:
            df = st.session_state.df_clean
            st.caption(
                f"{len(df):,} rows · {len(df.columns)} cols · {st.session_state.filename}"
            )

        st.divider()

        # ── Basic QC settings ─────────────────────────────────────────────
        st.markdown(
            "<div style='font-size:10px;letter-spacing:0.1em;text-transform:uppercase;"
            "color:var(--ds-text2);margin-bottom:6px;'>QC Settings</div>",
            unsafe_allow_html=True,
        )

        # Resolve auto-detect suggestions once here so all inputs below can use them
        _det = st.session_state.get("_auto_detect") or {}

        thr = st.slider("Missing threshold", 0.0, 1.0, 0.10, 0.01, format="%.0f%%",
                        help="Flag columns/rows with more than this % missing")
        st.session_state.rules_config["missing_threshold"] = thr

        dur_col = st.text_input(
            "Duration column",
            value=_det.get("duration_column", "") or "duration_minutes",
            help="Column holding interview duration in minutes",
        )
        min_dur = st.number_input("Min duration (mins)", value=5,   min_value=0)
        max_dur = st.number_input("Max duration (mins)", value=120, min_value=1)
        st.session_state.rules_config["interview_duration"] = {
            "enabled": bool(dur_col), "column": dur_col,
            "min_expected": min_dur, "max_expected": max_dur,
        }

        st.divider()

        # ── Interviewer checks ────────────────────────────────────────────
        st.markdown(
            "<div style='font-size:10px;letter-spacing:0.1em;text-transform:uppercase;"
            "color:var(--ds-text2);margin-bottom:6px;'>Interviewer Checks</div>",
            unsafe_allow_html=True,
        )
        int_col = st.text_input(
            "Interviewer column",
            value=_det.get("interviewer_column", "") or "",
            placeholder="interviewer_id",
            help="Column identifying each interviewer",
        )

        id_on = st.toggle("Duration anomaly", value=False,
                          help="Flag interviewers whose average duration is an outlier vs peers")
        st.session_state.rules_config["interviewer_duration_check"] = {
            "enabled": id_on and bool(int_col and dur_col),
            "interviewer_column": int_col, "duration_column": dur_col,
            "multiplier": 1.5, "min_interviews": 3,
        }

        ip_on = st.toggle("Productivity outliers", value=False,
                          help="Flag interviewers completing unusually many or few interviews")
        st.session_state.rules_config["interviewer_productivity_check"] = {
            "enabled": ip_on and bool(int_col),
            "interviewer_column": int_col, "multiplier": 1.5,
        }

        st.divider()

        # ── Consent / eligibility ─────────────────────────────────────────
        ce_on = st.toggle("Consent / eligibility check", value=False,
                          help="Flag disqualified respondents who still have data")
        if ce_on:
            sc_col  = st.text_input("Screener column", placeholder="consent")
            dq_op   = st.selectbox("Disqualify if", ["!=","==","<",">","<=",">="])
            dq_val  = st.text_input("Value", placeholder="Yes")
            sub_raw = st.text_input("Subsequent columns", placeholder="Q1, Q2, Q3",
                                    help="Columns that should be empty for disqualified respondents")
            st.session_state.rules_config["consent_eligibility_check"] = {
                "enabled": bool(sc_col and dq_val),
                "screener_column": sc_col, "disqualify_operator": dq_op,
                "disqualify_value": dq_val,
                "subsequent_columns": [c.strip() for c in sub_raw.split(",") if c.strip()],
            }
        else:
            st.session_state.rules_config["consent_eligibility_check"] = {
                "enabled": False, "screener_column": "", "disqualify_operator": "!=",
                "disqualify_value": "", "subsequent_columns": [],
            }

        st.divider()

        # ── Fabrication ───────────────────────────────────────────────────
        fab_on = st.toggle("Fabrication detection", value=False,
                           help="Detect sequential IDs and low-variance numeric responses")
        if fab_on:
            fab_id  = st.text_input("Respondent ID column", placeholder="respondent_id")
            fab_num = st.text_input("Numeric columns (comma-sep)",
                                    placeholder="Q1, Q2, Q3",
                                    help="Check these for suspiciously low variance per interviewer")
            fab_vt  = st.slider("Variance threshold", 0.01, 0.5, 0.1, 0.01)
            fab_rl  = st.number_input("Sequential run length", value=5, min_value=2)
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

        st.divider()

        # ── Verbatim ──────────────────────────────────────────────────────
        verb_on = st.toggle("Verbatim quality check", value=False,
                            help="Use local Ollama LLM to check grammar, coherence, and relevance")
        if verb_on:
            vb_cols_raw = st.text_input("Verbatim columns (comma-sep)",
                                        placeholder="Q10_text, comments")
            vb_sample   = st.number_input("Sample size", value=50, min_value=5, max_value=500,
                                          help="Number of responses to evaluate (for speed)")
            vb_min_score = st.slider("Min quality score (1–5)", 1, 5, 2,
                                     help="Flag responses scoring below this on any dimension")
            st.session_state.rules_config["verbatim_check"] = {
                "enabled": True,
                "verbatim_columns": [c.strip() for c in vb_cols_raw.split(",") if c.strip()],
                "model": st.session_state.get("ds_ollama_model", "llama3"),
                "min_score": vb_min_score,
                "sample_size": int(vb_sample),
            }
        else:
            st.session_state.rules_config["verbatim_check"] = {"enabled": False}

        # ── AI QC Assistant ───────────────────────────────────────────────
        if st.session_state.df_clean is not None:
            st.divider()
            with st.expander("✨ AI QC Assistant", expanded=False):
                st.caption(
                    "Describe any check in plain English — range, logic, duration, or pattern. "
                    "Groq converts it to a rule automatically."
                )
                nl_desc = st.text_area(
                    "Describe a check",
                    placeholder=(
                        "e.g. age should be between 18 and 99\n"
                        "e.g. if consent is No then Q1 should be empty\n"
                        "e.g. interviews should take 10–45 minutes\n"
                        "e.g. phone must match format +1234567890"
                    ),
                    key="sb_nl_input",
                    label_visibility="collapsed",
                    height=90,
                )
                if st.button("✨ Convert & add", use_container_width=True, key="sb_nl_btn"):
                    if not nl_desc.strip():
                        st.warning("Enter a description first.")
                    else:
                        with st.spinner("Converting…"):
                            cfg = _nl_to_check_config(
                                nl_desc.strip(),
                                st.session_state.df_clean.columns.tolist(),
                            )
                        if cfg and cfg.get("type"):
                            ok, msg = _apply_nl_check(cfg)
                            if ok:
                                st.success(msg)
                                st.caption("Click ↺ Rerun QC to apply.")
                            else:
                                st.error(msg)
                        else:
                            st.error(
                                "Could not parse a check from that description. "
                                "Try being more specific. (Groq API key required — ⚙️ Settings)"
                            )

        # ── Batch QC ──────────────────────────────────────────────────────
        if st.session_state.df_clean is not None:
            with st.expander("📁 Batch QC", expanded=False):
                st.caption(
                    "Upload multiple files to QC them all at once using current settings. "
                    "Results appear in the Batch tab."
                )
                batch_files = st.file_uploader(
                    "Batch files",
                    type=["csv", "xlsx", "xls"],
                    accept_multiple_files=True,
                    label_visibility="collapsed",
                    key="sb_batch_uploader",
                )
                if batch_files:
                    if st.button("▶ Run batch QC", use_container_width=True,
                                 type="primary", key="sb_batch_run"):
                        cfg_b = dict(st.session_state.rules_config)
                        cfg_b["logic_rules"] = (
                            cfg_b.get("logic_rules", []) +
                            st.session_state.get("custom_logic_rules", [])
                        )
                        aliases = st.session_state.get("column_aliases", {})
                        batch_results = []
                        errors = []
                        prog = st.progress(0.0, text="Starting…")
                        for i, f in enumerate(batch_files):
                            prog.progress(i / len(batch_files), text=f"Processing {f.name}…")
                            try:
                                df_r = DataLoader().load_from_buffer(f)
                                df_c = DataCleaner().clean(df_r)
                                if aliases:
                                    df_c = df_c.rename(columns=aliases)
                                res = RuleEngine(config=cfg_b).run(df_c)
                                total = sum(r.flag_count for r in res)
                                crits = sum(1 for r in res if r.severity == "critical" and r.flag_count > 0)
                                warns = sum(1 for r in res if r.severity == "warning"  and r.flag_count > 0)
                                batch_results.append({
                                    "filename": f.name, "rows": len(df_c),
                                    "columns": len(df_c.columns), "checks_run": len(res),
                                    "total_flags": total, "flag_rate_pct": round(total / max(len(df_c), 1) * 100, 1),
                                    "critical": crits, "warnings": warns,
                                    "status": "🔴 Issues" if crits > 0 else ("🟡 Warnings" if warns > 0 else "✅ Clean"),
                                    "_df": df_c, "_results": res,
                                })
                            except Exception as e:
                                errors.append(f"{f.name}: {e}")
                        prog.progress(1.0, text=f"Done — {len(batch_results)} file(s)")
                        st.session_state["_batch_results"] = batch_results
                        for err in errors:
                            st.error(err)
                        if batch_results:
                            st.success(f"Batch complete — see Batch tab for results.")

        # ── Rerun ─────────────────────────────────────────────────────────
        if st.session_state.df_clean is not None:
            st.divider()
            if st.button("↺ Rerun QC", use_container_width=True, type="primary"):
                with st.spinner("Running..."):
                    run_pipeline(st.session_state.df_raw, st.session_state.filename)
                st.success("Done")

        # ── Settings panel ────────────────────────────────────────────────
        render_settings()
