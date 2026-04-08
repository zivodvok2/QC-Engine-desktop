"""
ui/tabs/interviewer_tab.py — Interviewer Risk Scoring

Composite risk score per interviewer, aggregated from:
  - Fabrication flags   (40%)
  - Duration anomaly    (25%)
  - Straightlining rate (25%)
  - Productivity        (10%)
"""

import io
import streamlit as st
import pandas as pd

try:
    import plotly.graph_objects as go
    PLOTLY = True
except ImportError:
    PLOTLY = False

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
