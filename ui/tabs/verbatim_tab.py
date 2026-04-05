"""
ui/tabs/verbatim_tab.py — Verbatim Quality Check tab (Groq-powered)

Uses Groq API to batch-score open-ended responses for grammar, coherence,
relevance, and length quality. Free API key at https://console.groq.com
"""

import streamlit as st
import pandas as pd
from ui.components.drag_drop import drop_zone

_SCORE_COLS = [
    "_verbatim_column", "_verbatim_text",
    "_grammar_score", "_coherence_score", "_relevance_score", "_length_quality",
    "_gibberish", "_copy_paste", "_too_short",
]


def render(df: pd.DataFrame, results: list):
    st.markdown(
        "<p style='color:var(--ds-text2);font-size:13px;margin-bottom:16px;'>"
        "Evaluate open-ended responses for grammar, coherence, relevance, and length "
        "quality using <strong>Groq AI</strong> (fast, free). "
        "Get a free API key at "
        "<a href='https://console.groq.com' target='_blank' style='color:var(--ds-accent);'>"
        "console.groq.com</a> and enter it in ⚙️ Settings.</p>",
        unsafe_allow_html=True,
    )

    all_cols = df.columns.tolist()

    # ── API key check ─────────────────────────────────────────────────────────
    api_key = st.session_state.get("ds_groq_api_key", "")
    if not api_key:
        st.warning(
            "Groq API key not configured. Enter it in **⚙️ Settings → Verbatim checks (Groq)**."
        )

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
        model = st.session_state.get("ds_groq_model", "llama-3.1-8b-instant")
        st.caption(f"Model: **{model}** · Change in ⚙️ Settings")

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
            "Batch size",
            min_value=1, max_value=20, value=10,
            help="Responses scored per API call (larger = faster but may reduce accuracy)",
        )

    # Sync config so sidebar Rerun picks up current settings
    st.session_state.rules_config["verbatim_check"] = {
        "enabled":            bool(v_cols),
        "verbatim_columns":   v_cols,
        "model":              model,
        "min_score":          min_score,
        "sample_size":        int(sample_size),
        "batch_size":         int(batch_size),
        "interviewer_column": int_col,
    }

    if not v_cols:
        st.info("Select verbatim columns above to run the check.")
        return

    st.caption(f"Checking {len(v_cols)} column(s): {', '.join(v_cols)}")

    if st.button("▶ Run verbatim check", type="primary", disabled=not api_key):
        from checks.verbatim_checks import VerbatimQualityCheck
        total = min(int(sample_size), len(df))
        n_batches = max(1, total // int(batch_size))
        with st.spinner(f"Scoring {total} responses in ~{n_batches} batch(es) via Groq…"):
            result = VerbatimQualityCheck(
                verbatim_columns=v_cols,
                model=model,
                min_score=min_score,
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
        st.info(
            "Get a free Groq API key at https://console.groq.com, then enter it in ⚙️ Settings."
        )
        return

    # Score cards
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Evaluated",    meta.get("responses_evaluated", 0))
    c2.metric("Flagged",      vb_result.flag_count)
    c3.metric("Avg grammar",  meta.get("avg_grammar",   "—"))
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
