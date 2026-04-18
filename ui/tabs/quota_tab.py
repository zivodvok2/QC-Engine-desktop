"""
ui/tabs/quota_tab.py — Quota monitoring

Track achieved sample quotas against targets in real time.
Flag over-filled cells and cells at risk of being missed.
"""

import streamlit as st
import pandas as pd

try:
    import plotly.graph_objects as go
    PLOTLY = True
except ImportError:
    PLOTLY = False


def render(df: pd.DataFrame):
    st.markdown(
        "<p style='color:var(--ds-text2);font-size:13px;margin-bottom:16px;'>"
        "Define target sample quotas and track how achieved data compares in real time. "
        "Over-filled cells and cells at risk of being missed are flagged automatically.</p>",
        unsafe_allow_html=True,
    )

    if "quota_targets" not in st.session_state:
        st.session_state.quota_targets = []

    # ── Add quota ─────────────────────────────────────────────────────────────
    with st.expander("+ Add Quota Cell", expanded=not bool(st.session_state.quota_targets)):
        q_cols = df.columns.tolist()
        qa, qb, qc, qd = st.columns([2, 2, 1, 1])
        q_col      = qa.selectbox("Column", q_cols, key="qt_col")
        q_val      = qb.text_input("Value", placeholder="Female", key="qt_val")
        q_target_n = qc.number_input("Target n", min_value=0, value=0, key="qt_n",
                                     help="Absolute target count (leave 0 to use % instead)")
        q_target_pct = qd.number_input(
            "Target %", min_value=0.0, max_value=100.0, value=0.0,
            format="%.1f", key="qt_pct",
            help="Target as percentage of total sample (used if Target n = 0)",
        )

        if st.button("Add", key="qt_add", use_container_width=True, type="primary"):
            if q_col and q_val.strip():
                if q_target_n > 0:
                    t_n   = int(q_target_n)
                    t_pct = round(q_target_n / max(len(df), 1) * 100, 1)
                elif q_target_pct > 0:
                    t_n   = int(round(q_target_pct / 100 * len(df)))
                    t_pct = float(q_target_pct)
                else:
                    st.warning("Enter either a Target n or Target %.")
                    st.stop()

                st.session_state.quota_targets.append({
                    "column":     q_col,
                    "value":      q_val.strip(),
                    "target_n":   t_n,
                    "target_pct": t_pct,
                })
                st.rerun()
            else:
                st.warning("Select a column and enter a value.")

    if not st.session_state.quota_targets:
        st.info("No quota cells defined yet. Use the form above to add your first quota.")
        return

    # ── Compute achieved ──────────────────────────────────────────────────────
    rows = []
    for qt in st.session_state.quota_targets:
        col, val, target_n = qt["column"], qt["value"], qt["target_n"]
        target_pct = qt["target_pct"]

        if col not in df.columns:
            achieved_n = 0
        else:
            achieved_n = int((df[col].astype(str).str.strip() == str(val)).sum())

        achieved_pct = round(achieved_n / max(len(df), 1) * 100, 1)

        if target_n > 0:
            fill_rate = achieved_n / target_n
        elif target_pct > 0:
            fill_rate = achieved_pct / target_pct
        else:
            fill_rate = 0.0

        remaining = max(0, target_n - achieved_n)

        if fill_rate > 1.05:
            status = "🔴 OVERFILLED"
        elif fill_rate >= 0.90:
            status = "✅ ON TRACK"
        elif fill_rate >= 0.60:
            status = "🟡 AT RISK"
        else:
            status = "❌ BEHIND"

        rows.append({
            "Column":       col,
            "Value":        val,
            "Target n":     target_n,
            "Target %":     f"{target_pct:.1f}%",
            "Achieved n":   achieved_n,
            "Achieved %":   f"{achieved_pct:.1f}%",
            "Remaining":    remaining,
            "Fill Rate":    round(fill_rate * 100, 1),
            "Status":       status,
        })

    tbl = pd.DataFrame(rows)

    # ── Headline metrics ──────────────────────────────────────────────────────
    on_track   = sum(1 for r in rows if "ON TRACK"   in r["Status"])
    overfilled = sum(1 for r in rows if "OVERFILLED" in r["Status"])
    at_risk    = sum(1 for r in rows if "AT RISK" in r["Status"] or "BEHIND" in r["Status"])

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Quota cells",      len(rows))
    m2.metric("✅ On track",      on_track)
    m3.metric("🔴 Overfilled",    overfilled)
    m4.metric("⚠️ At risk / behind", at_risk)

    st.divider()

    # ── Quota table ───────────────────────────────────────────────────────────
    st.dataframe(
        tbl,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Fill Rate": st.column_config.ProgressColumn(
                "Fill Rate %",
                help="Achieved ÷ Target. >100% = overfilled, shaded red.",
                min_value=0, max_value=150, format="%.1f%%",
            ),
        },
    )

    # ── Bar chart — achieved vs target ────────────────────────────────────────
    if PLOTLY and len(rows) > 0:
        labels   = [f"{r['Column']}={r['Value']}" for r in rows]
        achieved = [r["Achieved n"] for r in rows]
        targets  = [r["Target n"]   for r in rows]
        bar_colors = [
            "#f04a6a" if "OVERFILLED" in r["Status"]
            else ("#4af0a0" if "ON TRACK"   in r["Status"]
            else ("#f0c04a" if "AT RISK"    in r["Status"]
            else "#888"))
            for r in rows
        ]
        fig = go.Figure()
        fig.add_trace(go.Bar(
            name="Target",
            x=labels, y=targets,
            marker_color="rgba(255,255,255,0.08)",
            marker_line=dict(color="rgba(255,255,255,0.25)", width=1.5),
        ))
        fig.add_trace(go.Bar(
            name="Achieved",
            x=labels, y=achieved,
            marker_color=bar_colors,
            text=[f"{a:,}" for a in achieved],
            textposition="outside",
        ))
        fig.update_layout(
            barmode="overlay",
            title="Achieved vs. Target by Quota Cell",
            plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
            font_family="DM Mono, monospace", font_size=11,
            margin=dict(l=40, r=20, t=50, b=90),
            legend=dict(orientation="h", y=1.12),
            xaxis_tickangle=-35,
        )
        st.plotly_chart(fig, use_container_width=True)

    # ── Manage / clear ────────────────────────────────────────────────────────
    st.divider()
    if st.button("Clear all quotas", type="secondary", key="qt_clear", use_container_width=True):
        st.session_state.quota_targets = []
        st.rerun()
