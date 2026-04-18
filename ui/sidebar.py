"""
ui/sidebar.py — DataSense sidebar

Performance notes:
- Pipeline only reruns when file hash changes or user clicks Rerun QC
- No @st.cache_data on DataFrames (eliminates per-render hashing overhead)
- Results stored in session state; rerenders just read from there
"""

import hashlib
import json
import requests
import io
from datetime import datetime
from pathlib import Path

import streamlit as st
import pandas as pd

from core.loader import DataLoader
from core.cleaner import DataCleaner
from core.rule_engine import RuleEngine
from ui.settings import render_settings, init_settings


# ── Pipeline ──────────────────────────────────────────────────────────────────

def run_pipeline(df: pd.DataFrame, filename: str):
    """Clean → check → store in session state. No caching — gated by file hash."""
    aliases = st.session_state.get("column_aliases", {})
    df_work = df.rename(columns=aliases) if aliases else df

    df_clean = DataCleaner().clean(df_work)
    cfg      = _build_cfg()
    results  = RuleEngine(config=cfg).run(df_clean)

    st.session_state.df_raw     = df
    st.session_state.df_clean   = df_clean
    st.session_state.qc_results = results
    st.session_state.filename   = filename
    st.session_state.project_name = st.session_state.get("project_name", "")

    # Audit trail
    entry = {
        "timestamp":  datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "filename":   filename,
        "rows":       len(df_clean),
        "checks_run": len(results),
        "total_flags": sum(r.flag_count for r in results),
        "critical":   sum(1 for r in results if r.severity == "critical" and r.flag_count > 0),
        "warnings":   sum(1 for r in results if r.severity == "warning"  and r.flag_count > 0),
    }
    st.session_state._audit_log = st.session_state.get("_audit_log", []) + [entry]
    # Invalidate cached Excel report
    st.session_state.pop("_excel_hash",  None)
    st.session_state.pop("_excel_cache", None)


def _build_cfg() -> dict:
    rc  = dict(st.session_state.get("rules_config", _default_config()))
    cfg = rc.copy()
    cfg["logic_rules"] = cfg.get("logic_rules", []) + st.session_state.get("custom_logic_rules", [])
    return cfg


def init_state():
    defaults = {
        "df_raw":             None,
        "df_clean":           None,
        "qc_results":         None,
        "filename":           None,
        "custom_logic_rules": [],
        "rules_config":       _default_config(),
        "column_aliases":     {},
        "_audit_log":         [],
        "project_name":       "",
        "quota_targets":      [],
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


def _default_config() -> dict:
    return {
        "missing_threshold": 0.1,
        "range_rules":       [],
        "logic_rules":       [],
        "pattern_rules": [
            {"column": "phone", "pattern": r"^\+?[0-9 ()-]{7,15}$", "description": "Valid phone"},
            {"column": "email", "pattern": r"^[^@]+@[^@]+\.[^@]+$",  "description": "Valid email"},
        ],
        "duplicate_check":                {"enabled": True,  "subset_columns": []},
        "interview_duration":             {"enabled": False, "column": "duration_minutes", "min_expected": 5, "max_expected": 120},
        "straightlining":                 {"enabled": False, "question_columns": [], "threshold": 0.9, "min_questions": 3},
        "interviewer_duration_check":     {"enabled": False, "interviewer_column": "", "duration_column": "duration_minutes", "multiplier": 1.5, "min_interviews": 3},
        "interviewer_productivity_check": {"enabled": False, "interviewer_column": "", "multiplier": 1.5},
        "consent_eligibility_check":      {"enabled": False, "screener_column": "", "disqualify_operator": "!=", "disqualify_value": "", "subsequent_columns": []},
        "fabrication_check":              {"enabled": False, "id_column": None, "numeric_columns": [], "interviewer_column": None, "variance_threshold": 0.1, "sequence_run_length": 5},
        "near_duplicate_check":           {"enabled": False, "id_column": None, "unique_columns": [], "combo_columns": [], "max_combo_count": 3},
        "verbatim_check":                 {"enabled": False, "verbatim_columns": [], "model": "llama-3.1-8b-instant", "min_score": 2, "sample_size": 50},
    }


# ── NL → check config helper ──────────────────────────────────────────────────

def _nl_to_check_config(description: str, columns: list) -> dict | None:
    try:
        from checks.verbatim_checks import _get_api_key
        api_key = _get_api_key()
    except Exception:
        return None
    if not api_key:
        return None
    prompt = (
        f'Convert this survey QC rule to JSON.\n\nDescription: "{description}"\n'
        f'Available columns: {columns[:50]}\n\n'
        'Return ONE of these JSON formats — no explanation, no markdown:\n\n'
        '1. Range: {"type":"range","column":"col","min":N,"max":N,"description":"..."}\n'
        '2. Logic: {"type":"logic","description":"...","if_conditions":[{"column":"col","operator":"op","value":"val"}],"then_conditions":[{"column":"col","operator":"op"}]}\n'
        '3. Duration: {"type":"duration","column":"col","min":N,"max":N}\n'
        '4. Pattern: {"type":"pattern","column":"col","pattern":"regex","description":"..."}\n\n'
        'Operators: >, <, >=, <=, ==, !=, is_null, not_null, in_list, not_in_list\n'
        'Return ONLY the JSON object.'
    )
    try:
        r = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            json={"model": "llama-3.1-8b-instant",
                  "messages": [{"role": "user", "content": prompt}],
                  "temperature": 0.1, "max_tokens": 400},
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            timeout=15,
        )
        r.raise_for_status()
        raw = r.json()["choices"][0]["message"]["content"].strip()
        s, e = raw.find("{"), raw.rfind("}") + 1
        return json.loads(raw[s:e]) if s != -1 and e > 0 else None
    except Exception:
        return None


def _apply_nl_check(cfg: dict) -> tuple[bool, str]:
    ctype = cfg.get("type")
    if ctype == "range":
        st.session_state.rules_config.setdefault("range_rules", []).append(
            {k: v for k, v in cfg.items() if k != "type"})
        return True, f"Range rule added: {cfg.get('description', cfg.get('column'))}"
    elif ctype == "logic":
        st.session_state.custom_logic_rules.append(
            {k: v for k, v in cfg.items() if k != "type"})
        return True, f"Logic rule added: {cfg.get('description', '')}"
    elif ctype == "duration":
        st.session_state.rules_config["interview_duration"] = {
            "enabled": True, "column": cfg.get("column", "duration_minutes"),
            "min_expected": cfg.get("min", 5), "max_expected": cfg.get("max", 120),
        }
        return True, f"Duration check: {cfg.get('column')} ({cfg.get('min')}–{cfg.get('max')} mins)"
    elif ctype == "pattern":
        st.session_state.rules_config.setdefault("pattern_rules", []).append(
            {k: v for k, v in cfg.items() if k != "type"})
        return True, f"Pattern rule added for: {cfg.get('column')}"
    return False, f"Unknown type: {ctype!r}"


# ── Sidebar ───────────────────────────────────────────────────────────────────

def render_sidebar():
    init_state()
    init_settings()

    with st.sidebar:

        # ── Branding ──────────────────────────────────────────────────────
        st.markdown(
            """<div style="padding:8px 0 14px;">
                <div style="font-family:'Syne',sans-serif;font-weight:800;font-size:18px;
                            color:var(--ds-text);letter-spacing:0.02em;">
                    <span style="color:var(--ds-accent);">■</span> DataSense
                </div>
                <div style="font-size:9px;color:var(--ds-text2);letter-spacing:0.15em;
                            text-transform:uppercase;margin-top:2px;">
                    Survey QC Engine
                </div>
            </div>""",
            unsafe_allow_html=True,
        )

        # ── Upload ────────────────────────────────────────────────────────
        st.caption("UPLOAD DATA")
        uploaded_files = st.file_uploader(
            "Upload",
            type=["csv", "xlsx", "xls"],
            label_visibility="collapsed",
            accept_multiple_files=True,
            help="Upload one file or multiple files for batch QC.",
        )

        if uploaded_files:
            file_hash = hashlib.md5(
                b"||".join(f.getvalue() for f in uploaded_files)
            ).hexdigest()

            if st.session_state.get("_last_file_hash") != file_hash:
                with st.spinner("Loading…"):
                    try:
                        if len(uploaded_files) == 1:
                            df       = DataLoader().load_from_buffer(uploaded_files[0])
                            filename = uploaded_files[0].name
                        else:
                            dfs = []
                            for f in uploaded_files:
                                df_i = DataLoader().load_from_buffer(f)
                                df_i["_source_file"] = f.name
                                dfs.append(df_i)
                            df       = pd.concat(dfs, ignore_index=True)
                            filename = f"Batch — {len(uploaded_files)} files"

                        run_pipeline(df, filename)
                        st.session_state["_last_file_hash"] = file_hash
                        n = len(st.session_state.df_clean)
                        st.success(
                            f"✓ {n:,} rows · {len(st.session_state.df_clean.columns)} cols"
                            if len(uploaded_files) == 1
                            else f"✓ {n:,} rows from {len(uploaded_files)} files"
                        )
                    except Exception as e:
                        st.error(f"Error: {e}")
            else:
                df = st.session_state.get("df_clean")
                if df is not None:
                    label = (
                        f"{len(df):,} rows · {len(df.columns)} cols"
                        if len(uploaded_files) == 1
                        else f"{len(df):,} rows · {len(uploaded_files)} files"
                    )
                    st.caption(label)

        st.divider()

        # ── Column Aliases ────────────────────────────────────────────────
        with st.expander("🗂 Column Aliases"):
            st.caption("Map your column names to standard names before QC runs.")
            aliases = st.session_state.get("column_aliases", {})
            to_del  = []
            for orig, tgt in list(aliases.items()):
                ca, cb, cc = st.columns([5, 5, 1])
                ca.caption(orig)
                cb.caption(f"→ {tgt}")
                if cc.button("✕", key=f"del_alias_{orig}"):
                    to_del.append(orig)
            for k in to_del:
                del st.session_state.column_aliases[k]
            if to_del:
                st.rerun()
            a1, a2 = st.columns(2)
            from_col = a1.text_input("Your column",   placeholder="INT_CODE",      key="alias_from", label_visibility="collapsed")
            to_col   = a2.text_input("Standard name", placeholder="interviewer_id", key="alias_to",   label_visibility="collapsed")
            if st.button("Add alias", use_container_width=True, key="alias_add_btn"):
                if from_col.strip() and to_col.strip():
                    st.session_state.column_aliases[from_col.strip()] = to_col.strip()
                    st.rerun()
                else:
                    st.warning("Enter both names.")

        # ── Project Config ────────────────────────────────────────────────
        with st.expander("💾 Project Config"):
            st.session_state.project_name = st.text_input(
                "Project name",
                value=st.session_state.get("project_name", ""),
                placeholder="e.g. Kenya Wave 3",
                key="proj_name_input",
            )
            proj_data = {
                "project_name":   st.session_state.project_name or "Untitled",
                "saved_at":       datetime.now().isoformat(),
                "rules_config":   st.session_state.rules_config,
                "custom_logic_rules": st.session_state.get("custom_logic_rules", []),
                "column_aliases": st.session_state.get("column_aliases", {}),
            }
            st.download_button(
                "↓ Save project config",
                data=json.dumps(proj_data, indent=2, default=str),
                file_name=f"{st.session_state.project_name or 'project'}.datasense.json",
                mime="application/json",
                use_container_width=True,
            )
            proj_file = st.file_uploader(
                "Load saved config",
                type=["json"],
                key="proj_load",
                label_visibility="visible",
                help="Upload a previously saved .datasense.json file",
            )
            if proj_file:
                try:
                    loaded = json.loads(proj_file.read())
                    if "rules_config" in loaded:
                        st.session_state.rules_config = loaded["rules_config"]
                    if "custom_logic_rules" in loaded:
                        st.session_state.custom_logic_rules = loaded["custom_logic_rules"]
                    if "column_aliases" in loaded:
                        st.session_state.column_aliases = loaded["column_aliases"]
                    if "project_name" in loaded:
                        st.session_state.project_name = loaded["project_name"]
                    st.success(f"Loaded: {loaded.get('project_name', 'Config')}. Click ↺ Rerun QC.")
                except Exception as e:
                    st.error(f"Failed to load: {e}")

        st.divider()

        # ── QC Settings ───────────────────────────────────────────────────
        st.caption("QC SETTINGS")

        thr = st.slider(
            "Missing threshold", 0.0, 1.0,
            float(st.session_state.rules_config.get("missing_threshold", 0.1)),
            0.01, format="%.0f%%",
        )
        st.session_state.rules_config["missing_threshold"] = thr

        dur_col = st.text_input(
            "Duration column",
            value=st.session_state.rules_config.get("interview_duration", {}).get("column", "duration_minutes"),
        )
        d1, d2 = st.columns(2)
        min_dur = d1.number_input("Min (mins)", value=int(st.session_state.rules_config.get("interview_duration", {}).get("min_expected", 5)),   min_value=0)
        max_dur = d2.number_input("Max (mins)", value=int(st.session_state.rules_config.get("interview_duration", {}).get("max_expected", 120)), min_value=1)
        st.session_state.rules_config["interview_duration"] = {
            "enabled": bool(dur_col), "column": dur_col,
            "min_expected": min_dur, "max_expected": max_dur,
        }

        st.divider()

        # ── Interviewer Checks ────────────────────────────────────────────
        st.caption("INTERVIEWER CHECKS")
        int_col = st.text_input(
            "Interviewer column",
            value=st.session_state.rules_config.get("interviewer_duration_check", {}).get("interviewer_column", ""),
            placeholder="interviewer_id",
        )
        id_on = st.toggle(
            "Duration anomaly",
            value=st.session_state.rules_config.get("interviewer_duration_check", {}).get("enabled", False),
            help="Flag interviewers whose mean duration is an outlier vs peers",
        )
        st.session_state.rules_config["interviewer_duration_check"] = {
            "enabled": id_on and bool(int_col and dur_col),
            "interviewer_column": int_col, "duration_column": dur_col,
            "multiplier": 1.5, "min_interviews": 3,
        }
        ip_on = st.toggle(
            "Productivity outliers",
            value=st.session_state.rules_config.get("interviewer_productivity_check", {}).get("enabled", False),
            help="Flag interviewers completing unusually many or few interviews",
        )
        st.session_state.rules_config["interviewer_productivity_check"] = {
            "enabled": ip_on and bool(int_col),
            "interviewer_column": int_col, "multiplier": 1.5,
        }

        st.divider()

        # ── Consent / Eligibility ─────────────────────────────────────────
        ce_cfg = st.session_state.rules_config.get("consent_eligibility_check", {})
        ce_on  = st.toggle(
            "Consent / eligibility check",
            value=ce_cfg.get("enabled", False),
            help="Flag disqualified respondents who still have data in survey questions",
        )
        if ce_on:
            sc_col  = st.text_input("Screener column",         value=ce_cfg.get("screener_column", ""),  placeholder="consent")
            dq_op   = st.selectbox("Disqualify if",           ["!=","==","<",">","<=",">="],
                                   index=["!=","==","<",">","<=",">="].index(ce_cfg.get("disqualify_operator","!=")))
            dq_val  = st.text_input("Value",                   value=ce_cfg.get("disqualify_value", ""), placeholder="Yes")
            sub_raw = st.text_input("Subsequent columns",      value=", ".join(ce_cfg.get("subsequent_columns", [])), placeholder="Q1, Q2, Q3")
            st.session_state.rules_config["consent_eligibility_check"] = {
                "enabled": bool(sc_col and dq_val), "screener_column": sc_col,
                "disqualify_operator": dq_op, "disqualify_value": dq_val,
                "subsequent_columns": [c.strip() for c in sub_raw.split(",") if c.strip()],
            }
        else:
            st.session_state.rules_config["consent_eligibility_check"] = {
                "enabled": False, "screener_column": "", "disqualify_operator": "!=",
                "disqualify_value": "", "subsequent_columns": [],
            }

        st.divider()

        # ── Fabrication ───────────────────────────────────────────────────
        fab_cfg = st.session_state.rules_config.get("fabrication_check", {})
        fab_on  = st.toggle(
            "Fabrication detection",
            value=fab_cfg.get("enabled", False),
            help="Detect sequential respondent IDs and suspiciously uniform numeric responses",
        )
        fab_id = ""
        if fab_on:
            fab_id  = st.text_input("Respondent ID column", value=fab_cfg.get("id_column") or "", placeholder="respondent_id")
            fab_num = st.text_input("Numeric columns (comma-sep)", value=", ".join(fab_cfg.get("numeric_columns", [])), placeholder="Q1, Q2, Q3")
            f1, f2  = st.columns(2)
            fab_vt  = f1.slider("Variance thr.", 0.01, 0.5, float(fab_cfg.get("variance_threshold", 0.1)), 0.01)
            fab_rl  = f2.number_input("Run length", value=int(fab_cfg.get("sequence_run_length", 5)), min_value=2)
            st.session_state.rules_config["fabrication_check"] = {
                "enabled": True, "id_column": fab_id or None,
                "numeric_columns": [c.strip() for c in fab_num.split(",") if c.strip()],
                "interviewer_column": int_col or None,
                "variance_threshold": fab_vt, "sequence_run_length": int(fab_rl),
            }
        else:
            st.session_state.rules_config["fabrication_check"] = {"enabled": False}

        st.divider()

        # ── Near-Duplicate Detection ──────────────────────────────────────
        nd_cfg = st.session_state.rules_config.get("near_duplicate_check", {})
        nd_on  = st.toggle(
            "Near-duplicate detection",
            value=nd_cfg.get("enabled", False),
            help="Detect fabricated interviews: shared phone/email across IDs, or repeated demographic combos",
        )
        if nd_on:
            nd_unique = st.text_input(
                "Unique-ID columns (comma-sep)",
                value=", ".join(nd_cfg.get("unique_columns", [])),
                placeholder="phone, email",
                help="Values in these columns should be unique per respondent",
            )
            nd_combo = st.text_input(
                "Demographic combo columns (comma-sep)",
                value=", ".join(nd_cfg.get("combo_columns", [])),
                placeholder="age, gender, location",
                help="Flag this demographic combination when it repeats suspiciously often",
            )
            n1, n2 = st.columns(2)
            nd_max = n1.number_input("Max combo reps", value=int(nd_cfg.get("max_combo_count", 3)), min_value=1)
            nd_id  = n2.text_input("Respondent ID col", value=nd_cfg.get("id_column") or "", placeholder="respondent_id", label_visibility="visible")
            st.session_state.rules_config["near_duplicate_check"] = {
                "enabled": True,
                "id_column":      nd_id.strip() or (fab_id.strip() if fab_on else None),
                "unique_columns": [c.strip() for c in nd_unique.split(",") if c.strip()],
                "combo_columns":  [c.strip() for c in nd_combo.split(",")  if c.strip()],
                "max_combo_count": int(nd_max),
            }
        else:
            st.session_state.rules_config["near_duplicate_check"] = {"enabled": False}

        st.divider()

        # ── Verbatim (Groq) ───────────────────────────────────────────────
        verb_cfg = st.session_state.rules_config.get("verbatim_check", {})
        verb_on  = st.toggle(
            "Verbatim quality check",
            value=verb_cfg.get("enabled", False),
            help="Use Groq AI to score grammar, coherence, and relevance of open-ended responses",
        )
        if verb_on:
            vb_cols = st.text_input(
                "Verbatim columns (comma-sep)",
                value=", ".join(verb_cfg.get("verbatim_columns", [])),
                placeholder="Q10_text, comments",
            )
            v1, v2 = st.columns(2)
            vb_sample    = v1.number_input("Sample size", value=int(verb_cfg.get("sample_size", 50)),  min_value=5, max_value=500)
            vb_min_score = v2.slider("Min score", 1, 5, int(verb_cfg.get("min_score", 2)))
            st.session_state.rules_config["verbatim_check"] = {
                "enabled": True,
                "verbatim_columns": [c.strip() for c in vb_cols.split(",") if c.strip()],
                "model":       st.session_state.get("ds_groq_model", "llama-3.1-8b-instant"),
                "min_score":   vb_min_score,
                "sample_size": int(vb_sample),
            }
        else:
            st.session_state.rules_config["verbatim_check"] = {"enabled": False}

        # ── AI QC Assistant ───────────────────────────────────────────────
        if st.session_state.df_clean is not None:
            st.divider()
            with st.expander("✨ AI QC Assistant"):
                st.caption(
                    "Describe any check in plain English — Groq converts it to a rule automatically."
                )
                nl_desc = st.text_area(
                    "Describe a check",
                    placeholder=(
                        "e.g. age should be between 18 and 99\n"
                        "e.g. if consent is No then Q1 should be empty\n"
                        "e.g. phone must match format +1234567890"
                    ),
                    key="sb_nl_input",
                    label_visibility="collapsed",
                    height=80,
                )
                if st.button("✨ Convert & add", use_container_width=True, key="sb_nl_btn", type="primary"):
                    if nl_desc.strip():
                        with st.spinner("Converting…"):
                            cfg = _nl_to_check_config(
                                nl_desc.strip(),
                                st.session_state.df_clean.columns.tolist(),
                            )
                        if cfg and cfg.get("type"):
                            ok, msg = _apply_nl_check(cfg)
                            (st.success if ok else st.error)(msg)
                            if ok:
                                st.caption("Click ↺ Rerun QC to apply.")
                        else:
                            st.error("Could not parse — try being more specific. (Groq API key required)")
                    else:
                        st.warning("Enter a description first.")

        # ── Rerun QC ──────────────────────────────────────────────────────
        if st.session_state.df_clean is not None:
            st.divider()
            if st.button("↺ Rerun QC", use_container_width=True, type="primary"):
                with st.spinner("Running checks…"):
                    run_pipeline(st.session_state.df_raw, st.session_state.filename)
                st.success("Done")

        # ── Settings ──────────────────────────────────────────────────────
        render_settings()
