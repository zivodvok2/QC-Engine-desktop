"""
ui/tabs/interviewer_tab.py — Interviewer Risk Scoring

Composite risk score per interviewer, aggregated from:
  - Fabrication flags   (40%)
  - Duration anomaly    (25%)
  - Straightlining rate (25%)
  - Productivity        (10%)
"""

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

    return scores.reset_index().sort_values("risk_score", ascending=False)


def render(df: pd.DataFrame, results: list):
    st.markdown("#### Interviewer Risk Scoring")
    st.markdown(
        "<p style='color:var(--ds-text2);font-size:13px;margin-bottom:16px;'>"
        "Composite risk score per interviewer — weighted from fabrication flags, "
        "duration anomalies, straightlining rate, and productivity outliers.</p>",
        unsafe_allow_html=True,
    )

    # Pick interviewer column — default from config
    cfg_int = (
        st.session_state.rules_config.get("interviewer_duration_check", {}).get("interviewer_column", "")
        or st.session_state.rules_config.get("interviewer_productivity_check", {}).get("interviewer_column", "")
    )
    all_cols = df.columns.tolist()
    opts = ["— select —"] + all_cols
    default_idx = opts.index(cfg_int) if cfg_int in opts else 0
    sel = st.selectbox("Interviewer column", opts, index=default_idx, key="int_risk_col")
    int_col = sel if sel != "— select —" else None

    if not int_col:
        st.info("Select the interviewer column above to generate risk scores.")
        return

    scores = _build_risk_table(df, results, int_col)
    if scores is None or scores.empty:
        st.warning("No interviewer data found. Enable interviewer checks in the sidebar and rerun QC.")
        return

    high = int((scores["risk_score"] >= 60).sum())
    med  = int(((scores["risk_score"] >= 30) & (scores["risk_score"] < 60)).sum())
    low  = int((scores["risk_score"] < 30).sum())

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Interviewers", len(scores))
    c2.metric("🔴 High risk",   high)
    c3.metric("🟡 Medium risk", med)
    c4.metric("🟢 Low risk",    low)

    st.divider()

    display_cols = [int_col, "risk_score", "risk_level", "total_interviews", "total_flags",
                    "fabrication_flags", "duration_flags", "straightlining_flags",
                    "productivity_flags", "verbatim_flags"]
    display_cols = [c for c in display_cols if c in scores.columns]

    st.dataframe(
        scores[display_cols],
        width="stretch",
        hide_index=True,
        column_config={
            "risk_score": st.column_config.ProgressColumn(
                "Risk Score (0–100)", min_value=0, max_value=100, format="%.1f"
            ),
        },
    )

    # Bar chart — top 20
    if PLOTLY and len(scores) > 1:
        top = scores.head(min(20, len(scores)))
        color_map = top["risk_score"].apply(
            lambda s: "#f04a6a" if s >= 60 else ("#f0c04a" if s >= 30 else "#4af0a0")
        )
        fig = go.Figure(go.Bar(
            x=top[int_col].astype(str),
            y=top["risk_score"],
            marker_color=color_map.tolist(),
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
        st.plotly_chart(fig, width="stretch")

    with st.expander("⚖️ Score weights"):
        st.markdown("""
| Component | Weight | Populated by |
|-----------|--------|--------------|
| Fabrication | **40%** | Fabrication detection check |
| Duration anomaly | **25%** | Interviewer duration check |
| Straightlining | **25%** | Straightlining check |
| Productivity | **10%** | Interviewer productivity check |

Enable each check in the sidebar so its data feeds into the composite score.
        """)
