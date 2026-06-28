"""
Wave Comparison page.

Compares key QC metrics across waves/periods of the same project:
  - Error rate trend (estimated vs actual vs variance)
  - Back-check rate vs target per wave
  - Average interview duration per wave
  - Productivity (approved interviews / active days) per wave
  - Listen-in rate per wave
  - Interviewer count and volume per wave

Data is grouped by the wave_label set at upload time.
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

import database as db
from config import (
    IPSOS_NAVY, IPSOS_TEAL, IPSOS_ORANGE, IPSOS_YELLOW, IPSOS_CYAN,
    CHART_COLORS,
)
from utils.charts import kpi_card


def _no_waves_notice():
    st.info(
        "No wave data yet. Tag your uploads with a Wave / Period label when uploading "
        "any report (Quality, Back-check, etc.) to enable wave-over-wave comparison."
    )


def show(project_id: int):
    project = db.get_project(project_id)
    if not project:
        st.error("Project not found.")
        return

    st.markdown(
        f'<h3 style="color:{IPSOS_NAVY};">Wave Comparison — {project["name"]}</h3>',
        unsafe_allow_html=True,
    )
    st.caption(
        "Compare QC performance metrics across waves or data collection periods. "
        "Tag uploads with a wave label to populate this view."
    )

    waves_data = db.get_wave_comparison_data(project_id)

    if not waves_data:
        _no_waves_notice()
        return

    df = pd.DataFrame(waves_data)
    n_waves = len(df)

    # ── Summary KPI row ────────────────────────────────────────────────────
    st.markdown("### Across All Waves")
    cols = st.columns(5)
    cols[0].markdown(kpi_card("Waves Tracked", n_waves, color=IPSOS_NAVY), unsafe_allow_html=True)
    cols[1].markdown(kpi_card("Total Approved", f"{df['approved'].sum():,}", color=IPSOS_TEAL), unsafe_allow_html=True)
    cols[2].markdown(kpi_card("Avg Error Rate", f"{df['error_rate'].mean():.1f}", suffix="%",
                               color=IPSOS_ORANGE if df['error_rate'].mean() > 5 else IPSOS_TEAL),
                     unsafe_allow_html=True)
    cols[3].markdown(kpi_card("Avg BC Rate", f"{df['bc_rate'].mean():.1f}", suffix="%",
                               color=IPSOS_TEAL if df['bc_rate'].mean() >= 20 else IPSOS_ORANGE),
                     unsafe_allow_html=True)
    cols[4].markdown(kpi_card("Avg Duration", f"{df['avg_duration'].mean():.1f}", suffix=" min",
                               color=IPSOS_NAVY), unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Error Rate: Estimated vs Actual vs Variance ────────────────────────
    st.markdown("### Error Rate Trend Across Waves")
    st.caption("Actual error rate per wave. Estimated = rolling average of prior waves (baseline).")

    # Compute estimated = rolling mean of prior waves (or project avg as baseline)
    df["estimated_error_rate"] = df["error_rate"].expanding().mean().shift(1).fillna(df["error_rate"].mean())
    df["estimated_error_rate"] = df["estimated_error_rate"].round(1)
    df["variance"] = (df["error_rate"] - df["estimated_error_rate"]).round(1)

    fig_err = go.Figure()
    fig_err.add_trace(go.Scatter(
        x=df["wave"], y=df["estimated_error_rate"],
        mode="lines+markers+text",
        name="Estimated Error Rate",
        text=[f"{v}%" for v in df["estimated_error_rate"]],
        textposition="top center",
        line=dict(color=IPSOS_TEAL, width=2, dash="dash"),
        marker=dict(size=8),
    ))
    fig_err.add_trace(go.Scatter(
        x=df["wave"], y=df["error_rate"],
        mode="lines+markers+text",
        name="Actual Error Rate",
        text=[f"{v}%" for v in df["error_rate"]],
        textposition="bottom center",
        line=dict(color=IPSOS_NAVY, width=2),
        marker=dict(size=8),
    ))
    fig_err.add_trace(go.Bar(
        x=df["wave"], y=df["variance"],
        name="Variance",
        marker_color=[IPSOS_ORANGE if v > 0 else IPSOS_TEAL for v in df["variance"]],
        text=[f"{v:+.1f}%" for v in df["variance"]],
        textposition="outside",
        opacity=0.6,
        yaxis="y2",
    ))
    fig_err.update_layout(
        yaxis=dict(title="Error Rate (%)", ticksuffix="%"),
        yaxis2=dict(title="Variance (pp)", overlaying="y", side="right", showgrid=False),
        legend=dict(orientation="h", y=1.1),
        paper_bgcolor="white",
        plot_bgcolor="#F5F5F5",
        height=380,
        margin=dict(l=20, r=20, t=30, b=60),
    )
    st.plotly_chart(fig_err, use_container_width=True, key="wc_error_rate")

    # ── Row 2: BC Rate + Listen-in Rate ───────────────────────────────────
    st.markdown("### Back-check & Listen-in Rates by Wave")
    c1, c2 = st.columns(2)

    bc_target = project.get("backcheck_target", 0.20) * 100
    li_target = project.get("listenin_target", 0.10) * 100

    with c1:
        fig_bc = go.Figure()
        fig_bc.add_hline(y=bc_target, line_dash="dot", line_color=IPSOS_ORANGE,
                         annotation_text=f"Target {bc_target:.0f}%", annotation_position="top right")
        fig_bc.add_trace(go.Bar(
            x=df["wave"], y=df["bc_rate"],
            marker_color=[IPSOS_TEAL if v >= bc_target else IPSOS_ORANGE for v in df["bc_rate"]],
            text=[f"{v}%" for v in df["bc_rate"]],
            textposition="outside",
            name="BC Rate",
        ))
        fig_bc.update_layout(
            title="Back-check Rate vs Target",
            yaxis=dict(title="Rate (%)", ticksuffix="%"),
            paper_bgcolor="white", plot_bgcolor="#F5F5F5",
            height=300, margin=dict(l=10, r=10, t=40, b=50),
            showlegend=False,
        )
        st.plotly_chart(fig_bc, use_container_width=True, key="wc_bc_rate")

    with c2:
        fig_li = go.Figure()
        fig_li.add_hline(y=li_target, line_dash="dot", line_color=IPSOS_ORANGE,
                         annotation_text=f"Target {li_target:.0f}%", annotation_position="top right")
        fig_li.add_trace(go.Bar(
            x=df["wave"], y=df["li_rate"],
            marker_color=[IPSOS_TEAL if v >= li_target else IPSOS_ORANGE for v in df["li_rate"]],
            text=[f"{v}%" for v in df["li_rate"]],
            textposition="outside",
            name="Listen-in Rate",
        ))
        fig_li.update_layout(
            title="Listen-in Rate vs Target",
            yaxis=dict(title="Rate (%)", ticksuffix="%"),
            paper_bgcolor="white", plot_bgcolor="#F5F5F5",
            height=300, margin=dict(l=10, r=10, t=40, b=50),
            showlegend=False,
        )
        st.plotly_chart(fig_li, use_container_width=True, key="wc_li_rate")

    # ── Row 3: Productivity + Duration ────────────────────────────────────
    st.markdown("### Productivity & Duration by Wave")
    c3, c4 = st.columns(2)

    with c3:
        fig_prod = px.bar(
            df, x="wave", y="approved",
            text="approved",
            color_discrete_sequence=[IPSOS_NAVY],
            labels={"approved": "Approved Interviews", "wave": "Wave"},
            title="Approved Interviews per Wave",
        )
        fig_prod.add_trace(go.Scatter(
            x=df["wave"], y=df["productivity"],
            mode="lines+markers",
            name="Productivity (per day)",
            yaxis="y2",
            line=dict(color=IPSOS_TEAL, width=2),
            marker=dict(size=7),
        ))
        fig_prod.update_layout(
            yaxis2=dict(title="Interviews/Day", overlaying="y", side="right", showgrid=False),
            legend=dict(orientation="h", y=1.1),
            paper_bgcolor="white", plot_bgcolor="#F5F5F5",
            height=300, margin=dict(l=10, r=10, t=40, b=50),
        )
        st.plotly_chart(fig_prod, use_container_width=True, key="wc_productivity")

    with c4:
        fig_dur = go.Figure()
        fig_dur.add_trace(go.Scatter(
            x=df["wave"], y=df["avg_duration"],
            mode="lines+markers+text",
            text=[f"{v} min" for v in df["avg_duration"]],
            textposition="top center",
            line=dict(color=IPSOS_CYAN, width=2),
            marker=dict(size=8),
            fill="tozeroy",
            fillcolor="rgba(79,195,247,0.15)",
            name="Avg Duration",
        ))
        fig_dur.update_layout(
            title="Average Interview Duration per Wave",
            yaxis=dict(title="Minutes"),
            paper_bgcolor="white", plot_bgcolor="#F5F5F5",
            height=300, margin=dict(l=10, r=10, t=40, b=50),
            showlegend=False,
        )
        st.plotly_chart(fig_dur, use_container_width=True, key="wc_duration")

    # ── Summary table ──────────────────────────────────────────────────────
    st.markdown("### Wave Summary Table")
    disp = df[[
        "wave", "total_interviews", "approved", "flagged",
        "error_rate", "bc_rate", "li_rate", "avg_duration", "productivity", "interviewers",
    ]].copy()
    disp.columns = [
        "Wave", "Total", "Approved", "Flagged",
        "Error Rate %", "BC Rate %", "Listen-in Rate %", "Avg Duration (min)",
        "Productivity (per day)", "Interviewers",
    ]
    st.dataframe(disp, use_container_width=True, hide_index=True)
