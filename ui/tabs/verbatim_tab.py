"""
ui/tabs/verbatim_tab.py — Verbatim Quality Check tab (Groq-powered)

Uses Groq API to batch-score open-ended responses for grammar, coherence,
relevance, and length quality. Free API key at https://console.groq.com
"""

import os
import streamlit as st
import pandas as pd
from ui.components.drag_drop import drop_zone

_SCORE_COLS = [
    "_verbatim_column", "_verbatim_text",
    "_grammar_score", "_coherence_score", "_relevance_score", "_length_quality",
    "_gibberish", "_copy_paste", "_too_short",
]

GROQ_MODELS = [
    "llama-3.1-8b-instant",
    "llama-3.3-70b-versatile",
    "mixtral-8x7b-32768",
    "gemma2-9b-it",
]


def _resolve_key() -> tuple[str, str]:
    """
    Returns (active_key, source) where source is 'server', 'personal', or ''.
    Server key = GROQ_API_KEY env var or st.secrets.
    Personal key = user-entered in this tab or in Settings.
    """
    # 1. Server key via env var
    server = os.environ.get("GROQ_API_KEY", "").strip()

    # 2. Server key via st.secrets (Streamlit Cloud / secrets.toml)
    if not server:
        try:
            server = st.secrets.get("GROQ_API_KEY", "").strip()
        except Exception:
            pass

    # 3. Personal key from session state (entered in this tab or Settings)
    personal = st.session_state.get("ds_groq_api_key", "").strip()

    if server:
        return server, "server"
    if personal:
        return personal, "personal"
    return "", ""


def render(df: pd.DataFrame, results: list):
    all_cols = df.columns.tolist()

    active_key, key_source = _resolve_key()

    # ── Description — always visible ──────────────────────────────────────────
    st.info(
        "Evaluate open-ended responses for grammar, coherence, relevance, and length quality "
        "using Groq AI (fast, free). Get a free API key at "
        "[console.groq.com](https://console.groq.com) and enter it below."
    )

    # ── API key panel ─────────────────────────────────────────────────────────
    if key_source == "server":
        st.success("✓ Server API key active — users can add a personal key as fallback")
    elif key_source == "personal":
        st.success("✓ Personal key configured")

    # Always show personal key input so users can add/update theirs
    with st.expander(
        "🔑 " + ("Personal key (fallback when server limit is reached)"
                 if key_source == "server" else "Enter your Groq API key"),
        expanded=(key_source == ""),
    ):
        typed_key = st.text_input(
            "Groq API key",
            value=st.session_state.get("ds_groq_api_key", ""),
            type="password",
            placeholder="gsk_…",
            key="vb_groq_key_input",
            label_visibility="collapsed",
            help="Your personal Groq key. Used as fallback when the server key is rate-limited.",
        )
        if typed_key != st.session_state.get("ds_groq_api_key", ""):
            st.session_state.ds_groq_api_key = typed_key
            st.rerun()
        st.caption("Free at [console.groq.com](https://console.groq.com)")

    # Re-resolve after possible key entry
    active_key, key_source = _resolve_key()

    st.divider()

    # ── Configuration ─────────────────────────────────────────────────────────
    st.markdown("#### Configure")
    col_a, col_b = st.columns(2)

    with col_a:
        v_cols = drop_zone(
            "Verbatim columns",
            key="vb_cols",
            options=all_cols,
            multi=True,
            help_text="Select open-ended question columns to evaluate",
        )

        int_col_sel = drop_zone(
            "Interviewer column (optional)",
            key="vb_int_col",
            options=all_cols,
            multi=False,
            help_text="Group results by interviewer",
        )
        int_col = int_col_sel[0] if int_col_sel else None

    with col_b:
        model = st.selectbox(
            "Model",
            options=GROQ_MODELS,
            index=GROQ_MODELS.index(st.session_state.get("ds_groq_model", GROQ_MODELS[0]))
                  if st.session_state.get("ds_groq_model") in GROQ_MODELS else 0,
            key="vb_model_select",
            help="llama-3.1-8b-instant is fastest; llama-3.3-70b-versatile is most accurate",
        )
        st.session_state.ds_groq_model = model

        sample_size = st.number_input(
            "Sample size",
            min_value=5, max_value=500,
            value=st.session_state.rules_config.get("verbatim_check", {}).get("sample_size", 100),
            help="Responses to evaluate (batched for speed — 100 takes ~10s)",
        )
        min_score = st.slider(
            "Min quality score (1–5)", 1, 5,
            value=st.session_state.rules_config.get("verbatim_check", {}).get("min_score", 2),
            help="Flag responses scoring below this on any quality dimension",
        )
        batch_size = st.number_input(
            "Batch size", min_value=1, max_value=20, value=10,
            help="Responses scored per API call (larger = fewer calls but may reduce accuracy)",
        )

    # Sync config so sidebar Rerun picks up current settings
    st.session_state.rules_config["verbatim_check"] = {
        "enabled":            bool(v_cols),
        "verbatim_columns":   v_cols,
        "model":              model,
        "min_score":          int(min_score),
        "sample_size":        int(sample_size),
        "batch_size":         int(batch_size),
        "interviewer_column": int_col,
    }

    if not v_cols:
        st.info("Select verbatim columns above to run the check.")
        return

    st.caption(f"Checking {len(v_cols)} column(s): {', '.join(v_cols)}")

    total     = min(int(sample_size), len(df))
    n_batches = max(1, (total + int(batch_size) - 1) // int(batch_size))
    st.caption(f"~{n_batches} API call(s) for {total} responses at batch size {int(batch_size)}")

    if st.button(
        "▶ Run verbatim check",
        type="primary",
        disabled=not active_key,
        help="Configure a Groq API key above to enable" if not active_key else None,
    ):
        from checks.verbatim_checks import VerbatimQualityCheck
        with st.spinner(f"Scoring {total} responses via Groq ({model})…"):
            result = VerbatimQualityCheck(
                verbatim_columns=v_cols,
                model=model,
                min_score=int(min_score),
                sample_size=int(sample_size),
                batch_size=int(batch_size),
                interviewer_column=int_col,
            ).run(df)
            st.session_state["_vb_result"] = result

    # ── Results ───────────────────────────────────────────────────────────────
    vb_result = st.session_state.get("_vb_result") or next(
        (r for r in results if r.check_name == "verbatim_quality_check"), None
    )

    if vb_result is None:
        return

    meta = vb_result.metadata
    st.divider()

    if meta.get("status") == "skipped":
        st.warning(f"Skipped — {meta.get('reason', 'API key not configured')}")
        return

    if meta.get("used_fallback_key"):
        st.info("ℹ️ Server key hit rate limit — results completed using your personal key.")

    # Score cards
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Evaluated",     meta.get("responses_evaluated", 0))
    c2.metric("Flagged",       vb_result.flag_count)
    c3.metric("Avg grammar",   meta.get("avg_grammar",   "—"))
    c4.metric("Avg coherence", meta.get("avg_coherence", "—"))
    c5.metric("Avg relevance", meta.get("avg_relevance", "—"))

    if vb_result.flag_count == 0:
        st.success("No low-quality responses found.")
        return

    st.markdown("#### Flagged responses")
    user_cols  = [c for c in vb_result.flagged_rows.columns if not c.startswith("_")]
    extra_cols = [c for c in _SCORE_COLS if c in vb_result.flagged_rows.columns]
    st.dataframe(
        vb_result.flagged_rows[user_cols + extra_cols].head(200),
        width="stretch", hide_index=True,
    )

    if "interviewer_summary" in meta and meta["interviewer_summary"]:
        st.markdown("##### By interviewer")
        st.dataframe(
            pd.DataFrame(meta["interviewer_summary"]),
            width="stretch", hide_index=True,
        )
