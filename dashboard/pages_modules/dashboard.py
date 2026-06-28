import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import date, datetime
import database as db
from config import (
    SL_ACCENT, SL_CRITICAL, SL_WARNING, SL_INFO, SL_TX, SL_MUTED,
    SL_SURFACE, SL_SURFACE2, SL_LINE, CHART_COLORS, DRILLDOWN_ROLES,
    # legacy aliases still used by callers that haven't been updated
    IPSOS_NAVY, IPSOS_TEAL, IPSOS_ORANGE, IPSOS_YELLOW,
)
from utils.charts import kpi_card, bar_chart, section_header, status_badge

REPORT_LABELS = {
    "quality_report":      "Quality Report",
    "backcheck":           "Back-check Report",
    "cancelled_interviews":"Cancelled Interviews",
    "performance":         "Performance Report",
    "timing":              "Timing Report",
    "listen_in":           "Listen-in",
}


def _risk_alerts(summary: list[dict]):
    alerts = []
    today = date.today()

    for s in summary:
        if s["status"] != "active":
            continue
        name = s["name"]

        try:
            end = date.fromisoformat(str(s.get("end_date", "")))
            days_left = (end - today).days
            if days_left <= 7 and s["completion_pct"] < 80:
                alerts.append(("critical", name,
                    f"End date in {days_left} day(s) — only {s['completion_pct']}% complete"))
            elif days_left <= 14 and s["completion_pct"] < 50:
                alerts.append(("warning", name,
                    f"End date in {days_left} days — only {s['completion_pct']}% complete"))
        except Exception:
            pass

        bc_target = round((s.get("backcheck_target") or 0.20) * 100)
        if s["backcheck_rate"] < bc_target:
            alerts.append(("warning", name,
                f"Back-check rate {s['backcheck_rate']}% below target {bc_target}%"))

        total = s.get("total_submitted", 0) or (s.get("approved", 0) + s.get("flagged", 0))
        warn_thresh = s.get("flag_warning_pct") or 5.0
        crit_thresh = s.get("flag_critical_pct") or 10.0
        if total > 0:
            flag_pct = round(s["flagged"] / total * 100, 1)
            if flag_pct >= crit_thresh:
                alerts.append(("critical", name,
                    f"High flagged rate: {flag_pct}% of submitted records"))
            elif flag_pct >= warn_thresh:
                alerts.append(("warning", name,
                    f"Elevated flagged rate: {flag_pct}%"))

        if s["approved"] == 0:
            alerts.append(("info", name, "No approved interviews uploaded yet"))

    if not alerts:
        return

    st.markdown(section_header("Risk & Alert Status"), unsafe_allow_html=True)

    _colors = {
        "critical": (SL_CRITICAL, "rgba(240,74,106,0.08)"),
        "warning":  (SL_WARNING,  "rgba(240,192,74,0.08)"),
        "info":     (SL_INFO,     "rgba(74,158,240,0.08)"),
    }
    _icons = {"critical": "✕", "warning": "⚠", "info": "i"}

    for level, project_name, message in alerts:
        color, bg = _colors[level]
        icon = _icons[level]
        st.markdown(
            f"""<div style="background:{bg};border-left:3px solid {color};
                 padding:0.55rem 1rem;margin:3px 0;border-radius:0 6px 6px 0;
                 font-family:DM Mono,monospace;font-size:0.82rem;color:{SL_TX};">
                <span style="color:{color};font-weight:700;">[{icon}]</span>
                &nbsp;<strong>{project_name}</strong> — {message}
            </div>""",
            unsafe_allow_html=True,
        )


def _at_risk_interviewers():
    try:
        at_risk = db.get_at_risk_interviewers_cross_project()
    except Exception:
        return
    if not at_risk:
        return

    st.markdown(section_header("Cross-Project At-Risk Interviewers"), unsafe_allow_html=True)
    st.caption("Interviewers with ≥ 15% QC flag rate (duration + straight-lining) across all projects. Min. 5 interviews.")

    cols_h = ["Interviewer ID", "Projects", "Interviews", "Duration Flags", "SL Flags", "Total Flags", "Flag Rate %"]
    header_html = "".join(
        f'<th style="padding:6px 12px;text-align:left;font-size:0.73rem;'
        f'color:{SL_MUTED};border-bottom:1px solid {SL_LINE};">{h}</th>'
        for h in cols_h
    )

    rows_html = ""
    for row in at_risk[:25]:
        rate = row["flag_rate_pct"]
        if rate >= 30:
            badge_color, bg = SL_CRITICAL, "rgba(240,74,106,0.06)"
        elif rate >= 15:
            badge_color, bg = SL_WARNING, "rgba(240,192,74,0.06)"
        else:
            badge_color, bg = SL_ACCENT, "transparent"

        rows_html += (
            f'<tr style="background:{bg}">'
            f'<td style="padding:5px 12px;font-size:0.8rem;color:{SL_TX};font-weight:500;">'
            f'{row["interviewer_id"]}</td>'
            f'<td style="padding:5px 12px;font-size:0.8rem;color:{SL_MUTED};">{row["project_count"]}</td>'
            f'<td style="padding:5px 12px;font-size:0.8rem;color:{SL_MUTED};">{row["total_interviews"]:,}</td>'
            f'<td style="padding:5px 12px;font-size:0.8rem;color:{SL_MUTED};">{row["duration_flags"]}</td>'
            f'<td style="padding:5px 12px;font-size:0.8rem;color:{SL_MUTED};">{row["sl_flags"]}</td>'
            f'<td style="padding:5px 12px;font-size:0.8rem;color:{badge_color};font-weight:600;">'
            f'{row["total_flags"]}</td>'
            f'<td style="padding:5px 12px;font-size:0.8rem;font-weight:700;color:{badge_color};">'
            f'{rate}%</td>'
            f'</tr>'
        )

    st.markdown(
        f'<table style="width:100%;border-collapse:collapse;font-family:DM Mono,monospace;">'
        f'<thead><tr style="border-bottom:1px solid {SL_LINE};">{header_html}</tr></thead>'
        f'<tbody>{rows_html}</tbody>'
        f'</table>',
        unsafe_allow_html=True,
    )
    if len(at_risk) > 25:
        st.caption(f"Showing top 25 of {len(at_risk)} at-risk interviewers.")
    st.markdown("<br>", unsafe_allow_html=True)


def _activity_feed():
    activities = db.get_project_activity(limit=10)
    if not activities:
        return

    st.markdown(section_header("Recent Activity"), unsafe_allow_html=True)

    for act in activities:
        report_label = REPORT_LABELS.get(act["report_type"], act["report_type"])
        wave_str     = f" · {act['wave_label']}" if act.get("wave_label") else ""
        uploader     = act.get("uploader") or "System"
        try:
            dt     = datetime.fromisoformat(str(act["upload_date"]))
            dt_str = dt.strftime("%d %b %Y %H:%M")
        except Exception:
            dt_str = str(act["upload_date"])[:16]

        st.markdown(
            f"""<div style="display:flex;justify-content:space-between;align-items:center;
                 padding:0.45rem 0.85rem;margin:2px 0;background:{SL_SURFACE};
                 border:1px solid {SL_LINE};border-radius:6px;
                 font-family:DM Mono,monospace;font-size:0.8rem;">
                <div>
                    <span style="color:{SL_ACCENT};font-weight:500;">{act['project_name']}</span>
                    <span style="color:{SL_MUTED};"> · {report_label}{wave_str}
                     · {act['row_count']:,} rows</span>
                </div>
                <div style="color:{SL_MUTED};font-size:0.75rem;white-space:nowrap;padding-left:1rem;">
                    {uploader} · {dt_str}
                </div>
            </div>""",
            unsafe_allow_html=True,
        )


def show():
    # ── Page title ──
    st.markdown(
        f'<h2 style="font-family:Syne,sans-serif;font-weight:800;font-size:1.5rem;'
        f'color:{SL_TX};margin-bottom:0.25rem;">Project Dashboard</h2>'
        f'<p style="color:{SL_MUTED};font-size:0.8rem;font-family:DM Mono,monospace;'
        f'margin-bottom:1.5rem;">All active projects · QC tracking overview</p>',
        unsafe_allow_html=True,
    )

    user_id  = st.session_state["user_id"]
    role     = st.session_state["user_role"]
    projects = db.get_user_projects(user_id, role)

    if not projects:
        st.info("No projects found. Ask your QC Executive to assign you to a project.")
        return

    summary     = db.get_dashboard_summary()
    visible_ids = {p["id"] for p in projects}
    summary     = [s for s in summary if s["id"] in visible_ids]

    # ── KPI row ──
    active        = sum(1 for s in summary if s["status"] == "active")
    total_target  = sum(s["sample_target"] or 0 for s in summary if s["status"] == "active")
    total_approved = sum(s["approved"] for s in summary if s["status"] == "active")
    total_flagged  = sum(s["flagged"] for s in summary if s["status"] == "active")
    avg_bc_rate    = (
        sum(s["backcheck_rate"] for s in summary if s["status"] == "active") / active
        if active else 0
    )

    cols = st.columns(5)
    cards = [
        ("Active Projects",        active,              "",  SL_ACCENT),
        ("Sample Target",          f"{total_target:,}", "",  SL_INFO),
        ("Approved Interviews",    f"{total_approved:,}","", SL_ACCENT),
        ("Avg Back-check Rate",    f"{avg_bc_rate:.1f}","%", SL_INFO),
        ("Total Flagged Records",  f"{total_flagged:,}", "",  SL_CRITICAL),
    ]
    for col, (label, val, suf, color) in zip(cols, cards):
        col.markdown(kpi_card(label, val, suffix=suf, color=color), unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Filters ──
    search_col, _ = st.columns([2, 3])
    with search_col:
        search_term = st.text_input(
            "Search", placeholder="Search by name, job number, or client…",
            key="dash_search", label_visibility="collapsed",
        )

    f1, f2, f3, f4, f5 = st.columns([2, 2, 1, 1, 1])
    with f1:
        status_filter = st.multiselect(
            "Status", ["active", "completed", "paused"],
            default=["active"], key="dash_status",
        )
    with f2:
        clients = sorted({s.get("client") or "" for s in summary if s.get("client")})
        client_filter = st.multiselect("Client", clients, key="dash_client")
    with f3:
        sort_by = st.selectbox(
            "Sort by", ["Name", "Completion %", "Sample Target", "Job No."], key="dash_sort",
        )
    with f4:
        date_from = st.date_input("End date from", value=None, key="dash_date_from")
    with f5:
        date_to = st.date_input("End date to", value=None, key="dash_date_to")

    df = pd.DataFrame(summary)
    if search_term:
        term = search_term.lower()
        mask = (
            df["name"].fillna("").str.lower().str.contains(term, na=False)
            | df.get("client", pd.Series(dtype=str)).fillna("").str.lower().str.contains(term, na=False)
            | df.get("job_number", pd.Series(dtype=str)).fillna("").str.lower().str.contains(term, na=False)
        )
        df = df[mask]
    if status_filter:
        df = df[df["status"].isin(status_filter)]
    if client_filter:
        df = df[df["client"].isin(client_filter)]
    if date_from and "end_date" in df.columns:
        df = df[pd.to_datetime(df["end_date"], errors="coerce") >= pd.Timestamp(date_from)]
    if date_to and "end_date" in df.columns:
        df = df[pd.to_datetime(df["end_date"], errors="coerce") <= pd.Timestamp(date_to)]

    if df.empty:
        st.warning("No projects match the current filter.")
        return

    sort_map = {
        "Name": "name", "Completion %": "completion_pct",
        "Sample Target": "sample_target", "Job No.": "job_number",
    }
    df = df.sort_values(sort_map[sort_by], ascending=(sort_by in ("Name", "Job No.")), na_position="last")

    # ── Completion chart ──
    st.markdown(section_header("Completion vs. Target"), unsafe_allow_html=True)
    fig_data = []
    for _, row in df.iterrows():
        fig_data.append({"Project": row["name"], "Count": row["sample_target"] or 0, "Series": "Target"})
        fig_data.append({"Project": row["name"], "Count": row["approved"],            "Series": "Approved"})
    fig_df = pd.DataFrame(fig_data)
    fig = px.bar(
        fig_df, x="Project", y="Count", color="Series", barmode="group",
        color_discrete_map={"Target": SL_SURFACE2, "Approved": SL_ACCENT},
        height=320,
    )
    fig.update_layout(
        paper_bgcolor=SL_SURFACE, plot_bgcolor=SL_SURFACE,
        font=dict(family="DM Mono, monospace", color=SL_MUTED),
        margin=dict(l=20, r=20, t=10, b=80),
        legend=dict(orientation="h", y=1.05, font=dict(color=SL_MUTED),
                    bgcolor="rgba(0,0,0,0)"),
        xaxis=dict(gridcolor=SL_LINE, tickfont=dict(color=SL_MUTED)),
        yaxis=dict(gridcolor=SL_LINE, tickfont=dict(color=SL_MUTED)),
    )
    fig.update_traces(marker_line_width=0)
    st.plotly_chart(fig, use_container_width=True, key="dash_completion_chart")

    # ── Project table ──
    st.markdown(section_header("All Projects"), unsafe_allow_html=True)
    can_drilldown = role in DRILLDOWN_ROLES

    for _, row in df.iterrows():
        pid = row["id"]
        pct = row["completion_pct"]
        bc_ok = row["backcheck_rate"] >= 20
        li_rate = row.get("listenin_rate", 0)

        with st.container():
            c1, c2, c3, c4, c5, c6 = st.columns([3, 2, 1, 1, 1, 1])
            with c1:
                job_tag = (
                    f'<span style="color:{SL_MUTED};font-size:0.72rem;"> [{row["job_number"]}]</span>'
                    if row.get("job_number") else ""
                )
                st.markdown(
                    f'<div style="font-family:Syne,sans-serif;font-weight:700;font-size:0.95rem;'
                    f'color:{SL_TX};">{row["name"]}{job_tag} &nbsp;'
                    f'{status_badge(row["status"])}</div>'
                    f'<div style="font-size:0.75rem;color:{SL_MUTED};font-family:DM Mono,monospace;'
                    f'margin-top:2px;">{row.get("client") or "—"}</div>',
                    unsafe_allow_html=True,
                )
            with c2:
                # Narrow progress bar
                bar_pct = min(pct / 100, 1.0)
                bar_color = SL_ACCENT if pct >= 80 else (SL_WARNING if pct >= 50 else SL_CRITICAL)
                st.markdown(
                    f'<div style="background:{SL_LINE};border-radius:3px;height:5px;margin-top:8px;">'
                    f'<div style="background:{bar_color};width:{bar_pct*100:.1f}%;height:100%;border-radius:3px;"></div>'
                    f'</div>'
                    f'<div style="font-size:0.75rem;color:{SL_MUTED};font-family:DM Mono,monospace;margin-top:4px;">'
                    f'{row["approved"]:,} / {row["sample_target"] or 0:,} &nbsp;({pct}%)</div>',
                    unsafe_allow_html=True,
                )
            with c3:
                bc_color = SL_ACCENT if bc_ok else SL_CRITICAL
                bc_icon  = "✓" if bc_ok else "⚠"
                st.markdown(
                    f'<div style="font-size:0.7rem;color:{SL_MUTED};font-family:DM Mono,monospace;">BC Rate</div>'
                    f'<div style="font-size:1.1rem;font-family:Syne,sans-serif;color:{bc_color};">'
                    f'{bc_icon} {row["backcheck_rate"]}%</div>',
                    unsafe_allow_html=True,
                )
            with c4:
                st.markdown(
                    f'<div style="font-size:0.7rem;color:{SL_MUTED};font-family:DM Mono,monospace;">Listen-in</div>'
                    f'<div style="font-size:1.1rem;font-family:Syne,sans-serif;color:{SL_TX};">{li_rate}%</div>',
                    unsafe_allow_html=True,
                )
            with c5:
                flag_color = SL_CRITICAL if row["flagged"] > 0 else SL_MUTED
                st.markdown(
                    f'<div style="font-size:0.7rem;color:{SL_MUTED};font-family:DM Mono,monospace;">Flagged</div>'
                    f'<div style="font-size:1.1rem;font-family:Syne,sans-serif;color:{flag_color};">'
                    f'{row["flagged"]:,}</div>',
                    unsafe_allow_html=True,
                )
            with c6:
                if can_drilldown and db.user_can_drilldown(
                    st.session_state["user_id"], pid, role
                ):
                    if st.button("View →", key=f"drill_{pid}", use_container_width=True):
                        st.session_state["page"]        = "project_detail"
                        st.session_state["project_id"]  = pid
                        st.session_state["project_tab"] = "quality_report"
                        st.rerun()
                else:
                    st.markdown(
                        f'<span style="color:{SL_MUTED};font-size:0.75rem;'
                        f'font-family:DM Mono,monospace;">Summary only</span>',
                        unsafe_allow_html=True,
                    )
            st.markdown(f'<hr style="border-color:{SL_LINE};margin:0.6rem 0;">', unsafe_allow_html=True)

    _risk_alerts(summary)
    _at_risk_interviewers()
    _activity_feed()
