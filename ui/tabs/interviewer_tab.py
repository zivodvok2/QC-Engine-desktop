"""
ui/tabs/interviewer_tab.py — Interviewer Risk Scoring + Feedback Letters

Composite risk score per interviewer, aggregated from:
  - Fabrication flags   (40%)
  - Duration anomaly    (25%)
  - Straightlining rate (25%)
  - Productivity        (10%)
"""

import io
import requests
import streamlit as st
import pandas as pd

try:
    import plotly.graph_objects as go
    PLOTLY = True
except ImportError:
    PLOTLY = False


def _generate_feedback_letter(interviewer_id: str, row: pd.Series) -> str | None:
    """Call Groq to generate a structured feedback letter for the selected interviewer."""
    try:
        from checks.verbatim_checks import _get_api_key
        api_key = _get_api_key()
    except Exception:
        return None
    if not api_key:
        return None

    issue_lines = []
    for col, label in [
        ("fabrication_flags",    "Fabrication / sequential-ID flags"),
        ("duration_flags",       "Duration anomaly flags"),
        ("straightlining_flags", "Straightlining flags"),
        ("productivity_flags",   "Productivity outlier flags"),
        ("verbatim_flags",       "Verbatim quality flags"),
    ]:
        n = int(row.get(col, 0))
        if n > 0:
            issue_lines.append(f"  • {label}: {n} ({round(n / max(int(row['total_interviews']), 1) * 100, 1)}%)")

    issues_text = "\n".join(issue_lines) if issue_lines else "  • No specific flags — general review."

    context = (
        f"Interviewer ID: {interviewer_id}\n"
        f"Risk Score: {row['risk_score']}/100 ({row['risk_level']})\n"
        f"Total interviews: {int(row['total_interviews'])}\n"
        f"Total flags: {int(row['total_flags'])} "
        f"({row['flag_rate_pct']:.1f}% flag rate)\n\n"
        f"Issues identified:\n{issues_text}"
    )

    prompt = (
        "You are a senior survey QC manager writing a formal but constructive feedback letter "
        "to a field interviewer based on automated QC findings.\n\n"
        f"QC Summary:\n{context}\n\n"
        "Write a professional letter structured as:\n"
        "1. Opening — acknowledge their effort and explain the purpose of the review\n"
        "2. Findings — describe each flagged issue clearly and what it indicates\n"
        "3. Standards — briefly state what good quality looks like\n"
        "4. Required actions — specific, actionable steps to improve\n"
        "5. Next steps — what happens next (re-check, retraining, etc.)\n"
        "6. Closing — supportive, professional tone\n\n"
        f"Address it: 'Dear Interviewer {interviewer_id},'\n"
        "Write the complete letter. Plain business English, no bullet points in the letter body."
    )

    try:
        r = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            json={
                "model": "llama-3.1-8b-instant",
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.35,
                "max_tokens": 900,
            },
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            timeout=30,
        )
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"].strip()
    except Exception:
        return None

WEIGHTS = {"fabrication": 0.40, "duration": 0.25, "straightlining": 0.25, "productivity": 0.10}


def _build_risk_table(df: pd.DataFrame, results: list, interviewer_col: str) -> pd.DataFrame | None:
    if not interviewer_col or interviewer_col not in df.columns:
        return None

    total_by_int = df.groupby(interviewer_col).size().rename("total_interviews")
    scores = pd.DataFrame(index=total_by_int.index)
    scores.index.name = interviewer_col
    scores = scores.join(total_by_int)

    for col in ["fabrication_flags", "duration_flags", "straightlining_flags",
                "productivity_flags", "verbatim_flags"]:
        scores[col] = 0

    mappings = [
        ("interviewer_duration_check",       "duration_flags"),
        ("straightlining_check",             "straightlining_flags"),
        ("fabrication_check",                "fabrication_flags"),
        ("interviewer_productivity_check",   "productivity_flags"),
        ("verbatim_quality_check",           "verbatim_flags"),
    ]
    for check_name, flag_col in mappings:
        r = next((r for r in results if r.check_name == check_name), None)
        if r and r.flag_count > 0 and interviewer_col in r.flagged_rows.columns:
            counts = r.flagged_rows.groupby(interviewer_col).size()
            scores[flag_col] = scores.index.map(counts).fillna(0).astype(int)

    for base in ["fabrication", "duration", "straightlining", "productivity", "verbatim"]:
        scores[f"{base}_rate"] = (
            scores[f"{base}_flags"] / scores["total_interviews"].clip(lower=1)
        ).clip(0, 1)

    scores["risk_score"] = (
        scores["fabrication_rate"]   * WEIGHTS["fabrication"]   +
        scores["duration_rate"]      * WEIGHTS["duration"]      +
        scores["straightlining_rate"] * WEIGHTS["straightlining"] +
        scores["productivity_rate"]  * WEIGHTS["productivity"]
    ).mul(100).round(1)

    scores["risk_level"] = scores["risk_score"].apply(
        lambda s: "🔴 HIGH" if s >= 60 else ("🟡 MEDIUM" if s >= 30 else "🟢 LOW")
    )
    scores["total_flags"] = (
        scores["fabrication_flags"] + scores["duration_flags"] +
        scores["straightlining_flags"] + scores["productivity_flags"] + scores["verbatim_flags"]
    )
    scores["flag_rate_pct"] = (
        scores["total_flags"] / scores["total_interviews"].clip(lower=1) * 100
    ).round(1)

    return scores.reset_index().sort_values("risk_score", ascending=False)


def render(df: pd.DataFrame, results: list):
    st.markdown(
        "<p style='color:var(--ds-text2);font-size:13px;margin-bottom:16px;'>"
        "Combines all QC flags into a single weighted risk score per interviewer (0–100). "
        "One screen — no mental joins across tabs.</p>",
        unsafe_allow_html=True,
    )

    # ── Configuration row ─────────────────────────────────────────────────────
    cfg_int = (
        st.session_state.rules_config.get("interviewer_duration_check",     {}).get("interviewer_column", "")
        or st.session_state.rules_config.get("interviewer_productivity_check", {}).get("interviewer_column", "")
        or st.session_state.rules_config.get("fabrication_check",              {}).get("interviewer_column") or ""
    )
    c1, c2, c3, c4 = st.columns([2, 1, 1, 1])
    with c1:
        int_col = st.text_input(
            "Interviewer column",
            value=cfg_int,
            key="int_risk_col",
            help="Column in the dataset that identifies each interviewer",
        )
    with c2:
        flag_thr = st.number_input(
            "Flag % alert threshold",
            value=10, min_value=1, max_value=100,
            key="int_flag_threshold",
            help="Interviewers above this flag rate trigger an alert",
        )
    with c3:
        red_thr = st.number_input(
            "Red score ≥",
            value=60, min_value=2, max_value=100,
            key="int_red_thr",
            help="Risk score at or above this = High Risk (red)",
        )
    with c4:
        amber_thr = st.number_input(
            "Amber score ≥",
            value=30, min_value=1, max_value=99,
            key="int_amber_thr",
            help="Risk score at or above this = Medium Risk (amber)",
        )

    if not int_col:
        st.info("Enter the interviewer column name above to generate risk scores.")
        return
    if int_col not in df.columns:
        st.warning(f"Column '{int_col}' not found. Available: {', '.join(df.columns[:10])}…")
        return

    scores = _build_risk_table(df, results, int_col)
    if scores is None or scores.empty:
        st.info(
            "No interviewer-level flags found. Enable at least one interviewer check "
            "(duration, productivity, fabrication, or straightlining) and rerun QC."
        )
        return

    # Apply configurable RAG thresholds
    scores["risk_level"] = scores["risk_score"].apply(
        lambda s: "🔴 HIGH" if s >= red_thr else ("🟡 MED" if s >= amber_thr else "🟢 LOW")
    )

    # ── Headline metrics ──────────────────────────────────────────────────────
    high    = int((scores["risk_score"] >= red_thr).sum())
    med     = int(((scores["risk_score"] >= amber_thr) & (scores["risk_score"] < red_thr)).sum())
    low     = int((scores["risk_score"] < amber_thr).sum())
    above_n = int((scores["flag_rate_pct"] > flag_thr).sum())

    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("Interviewers",            len(scores))
    m2.metric("🔴 High risk",            high)
    m3.metric("🟡 Medium risk",          med)
    m4.metric("🟢 Low risk",             low)
    m5.metric(f"Above {flag_thr}% flag rate", above_n)

    st.divider()

    # ── Ranked table ──────────────────────────────────────────────────────────
    st.markdown("#### Interviewer Risk Rankings")
    st.caption("Sorted by Risk Score (highest = investigate first). Click a column header to re-sort.")

    display_cols = [int_col, "risk_score", "risk_level", "total_interviews", "total_flags",
                    "flag_rate_pct", "fabrication_flags", "duration_flags",
                    "straightlining_flags", "productivity_flags", "verbatim_flags"]
    display_cols = [c for c in display_cols if c in scores.columns]

    ranked = scores[display_cols].sort_values("risk_score", ascending=False).reset_index(drop=True)
    ranked.index = ranked.index + 1

    st.dataframe(
        ranked,
        use_container_width=True,
        column_config={
            "risk_score": st.column_config.ProgressColumn(
                "Risk Score",
                help="Weighted composite score (0–100). Higher = investigate first.",
                min_value=0, max_value=100, format="%d",
            ),
            "flag_rate_pct": st.column_config.NumberColumn(
                "Flag Rate %",
                help="% of this interviewer's rows flagged across all checks",
                format="%.1f%%",
            ),
        },
    )

    risk_csv = io.BytesIO()
    ranked.to_csv(risk_csv, index_label="Rank")
    risk_csv.seek(0)
    st.download_button(
        "↓ Export risk table (CSV)",
        data=risk_csv,
        file_name="interviewer_risk_scores.csv",
        mime="text/csv",
    )

    # ── Bar chart — top 20 ────────────────────────────────────────────────────
    if PLOTLY and len(scores) > 1:
        top = ranked.head(min(20, len(ranked)))
        colors = top["risk_score"].apply(
            lambda s: "#f04a6a" if s >= red_thr else ("#f0c04a" if s >= amber_thr else "#4af0a0")
        )
        fig = go.Figure(go.Bar(
            x=top[int_col].astype(str),
            y=top["risk_score"],
            marker_color=colors.tolist(),
            text=top["risk_score"].apply(lambda x: f"{x:.1f}"),
            textposition="outside",
        ))
        fig.update_layout(
            title="Interviewer Risk Scores",
            plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
            font_family="DM Mono, monospace", font_size=11,
            margin=dict(l=40, r=20, t=50, b=80),
            yaxis=dict(range=[0, 115]),
            xaxis_tickangle=-45,
        )
        st.plotly_chart(fig, use_container_width=True)

    # ── Flag rate alerts ──────────────────────────────────────────────────────
    st.divider()
    st.markdown(f"#### Flag Rate Alerts  ·  threshold: {flag_thr}%")

    above_rows = scores[scores["flag_rate_pct"] > flag_thr].sort_values("risk_score", ascending=False)
    if above_rows.empty:
        st.success(f"No interviewers exceed the {flag_thr}% flag rate threshold.")
    else:
        for _, row in above_rows.iterrows():
            st.warning(
                f"**{row[int_col]}**: {row['flag_rate_pct']:.1f}% of interviews flagged "
                f"({int(row['total_flags']):,} / {int(row['total_interviews']):,}) "
                f"— above {flag_thr}% threshold · Risk Score: **{int(row['risk_score'])}** · {row['risk_level']}"
            )

    # ── Feedback letter generator ─────────────────────────────────────────────
    st.divider()
    st.markdown("#### Interviewer Feedback Letter")
    st.caption(
        "Select an interviewer and generate a structured feedback letter via Groq AI — "
        "summarises their flags, expected standards, and corrective actions. "
        "Ready to send."
    )

    interviewer_options = scores[int_col].astype(str).tolist()
    fl_col1, fl_col2 = st.columns([3, 1])
    selected_int = fl_col1.selectbox(
        "Interviewer", interviewer_options,
        key="int_letter_sel", label_visibility="collapsed",
    )
    with fl_col2:
        st.markdown("<div style='height:4px'></div>", unsafe_allow_html=True)
        gen_btn = st.button(
            "Generate letter", key="int_letter_btn",
            use_container_width=True, type="primary",
        )

    if gen_btn:
        sel_row = scores[scores[int_col].astype(str) == selected_int].iloc[0]
        with st.spinner("Writing letter…"):
            letter = _generate_feedback_letter(selected_int, sel_row)
        if letter:
            st.session_state["_last_letter"] = (selected_int, letter)
        else:
            st.warning(
                "Could not generate — add a Groq API key in ⚙️ Settings first."
            )

    if st.session_state.get("_last_letter"):
        _int_id, _letter = st.session_state["_last_letter"]
        st.text_area(
            f"Letter — Interviewer {_int_id}",
            value=_letter,
            height=380,
            key="int_letter_output",
        )
        st.download_button(
            f"↓ Download letter ({_int_id})",
            data=_letter.encode("utf-8"),
            file_name=f"feedback_letter_{_int_id}.txt",
            mime="text/plain",
            use_container_width=True,
        )

    # ── Score methodology ─────────────────────────────────────────────────────
    with st.expander("Score methodology"):
        w_rows = [
            {"Component": label, "Weight": f"{w}%", "Populated by": check}
            for check, label, w in [
                ("fabrication_flags",       "Fabrication",      40),
                ("duration_flags",          "Duration anomaly", 25),
                ("straightlining_flags",    "Straightlining",   25),
                ("productivity_flags",      "Productivity",     10),
            ]
        ]
        st.dataframe(pd.DataFrame(w_rows), use_container_width=True, hide_index=True)
        st.caption(
            "Each component contributes points proportional to that interviewer's flag rate "
            "(flags ÷ total interviews × weight). Scores are summed and capped at 100."
        )
