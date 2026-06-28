import streamlit as st
import database as db
from config import (
    SL_ACCENT, SL_CRITICAL, SL_WARNING, SL_TX, SL_MUTED,
    SL_LINE, SL_SURFACE, SL_SURFACE2,
)
from utils.charts import kpi_card, section_header


def _risk_badge(flag_pct: float, has_data: bool) -> tuple[str, str]:
    if not has_data:
        return "—", SL_MUTED
    if flag_pct >= 30:
        return "HIGH", SL_CRITICAL
    if flag_pct >= 15:
        return "MED", SL_WARNING
    return "LOW", SL_ACCENT


def show():
    st.markdown(
        f'<h2 style="font-family:Syne,sans-serif;font-weight:800;font-size:1.5rem;'
        f'color:{SL_TX};margin-bottom:0.25rem;">Interviewer Registry</h2>'
        f'<p style="color:{SL_MUTED};font-size:0.8rem;font-family:DM Mono,monospace;'
        f'margin-bottom:1.5rem;">All registered interviewers · Cross-project performance overview</p>',
        unsafe_allow_html=True,
    )

    try:
        interviewers = db.get_all_interviewers()
        supervisors = db.get_all_supervisors()
        at_risk = db.get_at_risk_interviewers_cross_project(min_interviews=1, flag_pct_threshold=0)
    except Exception as e:
        st.error(f"Could not load data: {e}")
        return

    at_risk_map = {r["interviewer_id"]: r for r in at_risk}

    total = len(interviewers)
    active = sum(1 for i in interviewers if i.get("is_active", 1))
    high_risk = sum(
        1 for i in interviewers
        if at_risk_map.get(i["interviewer_code"], {}).get("flag_rate_pct", 0) >= 30
    )

    # ── KPI row ──────────────────────────────────────────────────────────────
    c1, c2, c3, c4 = st.columns(4)
    c1.markdown(kpi_card("Total Interviewers", total, color=SL_TX), unsafe_allow_html=True)
    c2.markdown(kpi_card("Active", active, color=SL_ACCENT), unsafe_allow_html=True)
    c3.markdown(kpi_card("Supervisors", len(supervisors), color=SL_TX), unsafe_allow_html=True)
    c4.markdown(kpi_card("High Risk", high_risk, color=SL_CRITICAL), unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    if not interviewers:
        st.info(
            "No interviewers registered yet. "
            "Run a QC analysis on Servallab with an interviewer column set — "
            "they will be auto-registered here."
        )
        return

    # ── Supervisor summary cards ──────────────────────────────────────────────
    if supervisors:
        st.markdown(section_header("Supervisors"), unsafe_allow_html=True)
        cols = st.columns(min(len(supervisors), 5))
        for idx, sup in enumerate(supervisors):
            count = sum(1 for i in interviewers if i.get("supervisor_id") == sup["id"])
            cols[idx % 5].markdown(
                f'<div style="background:{SL_SURFACE2};border:1px solid {SL_LINE};border-radius:8px;'
                f'padding:0.7rem 0.9rem;margin-bottom:4px;">'
                f'<div style="font-family:Syne,sans-serif;font-weight:700;font-size:0.88rem;color:{SL_TX};">'
                f'{sup["name"]}</div>'
                + (f'<div style="font-size:0.72rem;color:{SL_MUTED};">{sup["region"]}</div>'
                   if sup.get("region") else "")
                + f'<div style="font-size:0.8rem;color:{SL_ACCENT};margin-top:4px;">'
                f'{count} interviewer{"s" if count != 1 else ""}</div>'
                f'</div>',
                unsafe_allow_html=True,
            )
        st.markdown("<br>", unsafe_allow_html=True)

    # ── Filters ───────────────────────────────────────────────────────────────
    st.markdown(section_header("Interviewers"), unsafe_allow_html=True)

    fcol1, fcol2, fcol3 = st.columns([2, 2, 2])
    with fcol1:
        sup_options = ["All supervisors"] + [s["name"] for s in supervisors]
        selected_sup = st.selectbox("Supervisor", sup_options, key="itv_sup_filter", label_visibility="collapsed")
    with fcol2:
        risk_options = ["All risk levels", "HIGH", "MED", "LOW", "No data"]
        selected_risk = st.selectbox("Risk level", risk_options, key="itv_risk_filter", label_visibility="collapsed")
    with fcol3:
        search = st.text_input("Search", placeholder="Search interviewer code…", key="itv_search", label_visibility="collapsed")

    # ── Filter logic ──────────────────────────────────────────────────────────
    filtered = interviewers
    if selected_sup != "All supervisors":
        sup_id = next((s["id"] for s in supervisors if s["name"] == selected_sup), None)
        if sup_id:
            filtered = [i for i in filtered if i.get("supervisor_id") == sup_id]
    if search:
        q = search.lower()
        filtered = [i for i in filtered if q in (i["interviewer_code"] or "").lower()
                    or q in (i.get("name") or "").lower()]
    if selected_risk != "All risk levels":
        def _matches_risk(itv):
            r = at_risk_map.get(itv["interviewer_code"], {})
            has_data = r.get("total_interviews", 0) > 0
            label, _ = _risk_badge(r.get("flag_rate_pct", 0), has_data)
            return label == selected_risk
        filtered = [i for i in filtered if _matches_risk(i)]

    # ── Interviewer table ─────────────────────────────────────────────────────
    headers = [
        "Code", "Name", "Supervisor", "Region",
        "Interviews", "Duration Flags", "SL Flags", "Flag Rate", "Risk", "Status",
    ]
    header_html = "".join(
        f'<th style="padding:6px 12px;text-align:left;font-size:0.73rem;color:{SL_MUTED};'
        f'border-bottom:1px solid {SL_LINE};white-space:nowrap;">{h}</th>'
        for h in headers
    )

    rows_html = ""
    for itv in filtered:
        code = itv["interviewer_code"]
        r = at_risk_map.get(code, {})
        has_data = r.get("total_interviews", 0) > 0
        flag_pct = r.get("flag_rate_pct", 0)
        risk_label, risk_color = _risk_badge(flag_pct, has_data)
        status_color = SL_ACCENT if itv.get("is_active", 1) else SL_MUTED
        status_text = "Active" if itv.get("is_active", 1) else "Inactive"

        rows_html += (
            f'<tr>'
            f'<td style="padding:5px 12px;font-size:0.8rem;color:{SL_ACCENT};font-family:DM Mono,monospace;">{code}</td>'
            f'<td style="padding:5px 12px;font-size:0.8rem;color:{SL_TX};">{itv.get("name") or "—"}</td>'
            f'<td style="padding:5px 12px;font-size:0.8rem;color:{SL_MUTED};">{itv.get("supervisor_name") or "—"}</td>'
            f'<td style="padding:5px 12px;font-size:0.8rem;color:{SL_MUTED};">{itv.get("region") or "—"}</td>'
            f'<td style="padding:5px 12px;font-size:0.8rem;color:{SL_MUTED};">'
            f'{r.get("total_interviews", "—")}</td>'
            f'<td style="padding:5px 12px;font-size:0.8rem;color:{SL_MUTED};">'
            f'{r.get("duration_flags", "—")}</td>'
            f'<td style="padding:5px 12px;font-size:0.8rem;color:{SL_MUTED};">'
            f'{r.get("sl_flags", "—")}</td>'
            f'<td style="padding:5px 12px;font-size:0.8rem;color:{risk_color};font-weight:600;">'
            f'{f"{flag_pct}%" if has_data else "—"}</td>'
            f'<td style="padding:5px 12px;font-size:0.8rem;color:{risk_color};font-weight:700;">{risk_label}</td>'
            f'<td style="padding:5px 12px;font-size:0.8rem;color:{status_color};">{status_text}</td>'
            f'</tr>'
        )

    if filtered:
        st.markdown(
            f'<table style="width:100%;border-collapse:collapse;font-family:DM Mono,monospace;">'
            f'<thead><tr style="border-bottom:1px solid {SL_LINE};">{header_html}</tr></thead>'
            f'<tbody>{rows_html}</tbody>'
            f'</table>',
            unsafe_allow_html=True,
        )
        st.caption(f"Showing {len(filtered)} of {len(interviewers)} interviewers. Flag rates are from quality report records uploaded to this dashboard.")
    else:
        st.info("No interviewers match the current filters.")
