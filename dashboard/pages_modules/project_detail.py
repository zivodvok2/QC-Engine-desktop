import streamlit as st
import database as db
from config import (
    SL_ACCENT, SL_CRITICAL, SL_WARNING, SL_INFO,
    SL_TX, SL_MUTED, SL_SURFACE, SL_SURFACE2, SL_LINE,
)
from pages_modules import (
    quality_report, backcheck_report, cancelled_interviews,
    performance_report, timing_report, listen_in, wave_comparison,
)
from utils.exports import generate_project_report
from utils.charts import status_badge

TABS = [
    ("Quality Report",       "quality_report"),
    ("Back-check Report",    "backcheck_report"),
    ("Cancelled Interviews", "cancelled_interviews"),
    ("Performance Report",   "performance_report"),
    ("Timing Report",        "timing_report"),
    ("Listen-in",            "listen_in"),
    ("Wave Comparison",      "wave_comparison"),
]


def _stat_cell(label: str, value: str, target: str = "", on_target: bool | None = None) -> str:
    if on_target is None:
        val_color = SL_TX
    else:
        val_color = SL_ACCENT if on_target else SL_CRITICAL
    tgt_html = (
        f'<div style="font-size:0.68rem;color:{SL_MUTED};margin-top:2px;">Target: {target}</div>'
        if target else ""
    )
    return (
        f'<div style="background:rgba(255,255,255,0.04);border:1px solid {SL_LINE};'
        f'border-radius:8px;padding:0.6rem 1rem;text-align:center;min-width:100px;">'
        f'<div style="font-size:0.68rem;color:{SL_MUTED};font-family:DM Mono,monospace;'
        f'text-transform:uppercase;letter-spacing:0.07em;">{label}</div>'
        f'<div style="font-size:1.35rem;font-weight:700;font-family:Syne,sans-serif;'
        f'color:{val_color};line-height:1.2;margin-top:2px;">{value}</div>'
        f'{tgt_html}'
        f'</div>'
    )


def show():
    project_id = st.session_state.get("project_id")
    if not project_id:
        st.error("No project selected.")
        return

    project = db.get_project(project_id)
    if not project:
        st.error("Project not found.")
        return

    user_id = st.session_state["user_id"]
    role    = st.session_state["user_role"]
    if not db.user_can_drilldown(user_id, project_id, role):
        st.error("You do not have access to this project's details.")
        return

    # ── Nav bar ──
    nav1, nav2 = st.columns([3, 1])
    with nav1:
        if st.button("← Back to Dashboard"):
            st.session_state["page"]       = "dashboard"
            st.session_state["project_id"] = None
            st.rerun()
    with nav2:
        try:
            report_bytes = generate_project_report(project_id)
            safe_name = (project.get("name") or "project").replace(" ", "_")
            job_part  = f"_{project['job_number']}" if project.get("job_number") else ""
            st.download_button(
                "Download Full Report",
                data=report_bytes,
                file_name=f"QC_Report{job_part}_{safe_name}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
                type="primary",
            )
        except Exception:
            pass

    # ── Live quota stats ──
    qr_records     = db.get_quality_records(project_id)
    approved_count = sum(1 for r in qr_records if str(r.get("approval_status", "")).lower() == "approved")
    target         = project.get("sample_target") or 0
    overflow       = approved_count - target
    overflow_str   = (f"+{overflow}" if overflow > 0 else str(overflow)) if target > 0 else "—"
    pct_done       = round(approved_count / target * 100, 1) if target > 0 else 0

    bc_records     = db.get_backcheck_records(project_id)
    bc_rate        = round(len(bc_records) / approved_count * 100, 1) if approved_count else 0
    bc_target_pct  = round((project.get("backcheck_target") or 0.20) * 100)

    li_records     = db.get_listen_in_records(project_id)
    li_rate        = round(len(li_records) / approved_count * 100, 1) if approved_count else 0
    li_target_pct  = round((project.get("listenin_target") or 0.10) * 100)

    job_str = f" · Job: {project['job_number']}" if project.get("job_number") else ""

    # ── Project header card ──
    stat_cells = "".join([
        _stat_cell("Sample Target",  f"{target:,}"),
        _stat_cell("Achieved",       f"{approved_count:,} ({pct_done}%)",
                   f"{target:,}", pct_done >= 80),
        _stat_cell("Back-checks",    f"{bc_rate}%",
                   f"{bc_target_pct}%", bc_rate >= bc_target_pct),
        _stat_cell("Listen-in",      f"{li_rate}%",
                   f"{li_target_pct}%", li_rate >= li_target_pct),
    ])

    st.markdown(
        f"""<div style="background:{SL_SURFACE};border:1px solid {SL_LINE};
             border-left:3px solid {SL_ACCENT};border-radius:10px;
             padding:1.25rem 1.5rem;margin-bottom:1.25rem;">
            <div style="display:flex;justify-content:space-between;
                        align-items:flex-start;flex-wrap:wrap;gap:1rem;">
                <div>
                    <div style="display:flex;align-items:center;gap:10px;margin-bottom:4px;">
                        <h2 style="margin:0;font-family:Syne,sans-serif;font-weight:800;
                                   font-size:1.25rem;color:{SL_TX};">{project['name']}</h2>
                        {status_badge(project['status'])}
                    </div>
                    <div style="font-size:0.75rem;color:{SL_MUTED};font-family:DM Mono,monospace;">
                        {project.get('client') or '—'}{job_str}
                        &nbsp;·&nbsp;
                        {project.get('start_date', '?')} → {project.get('end_date', '?')}
                    </div>
                </div>
                <div style="display:flex;gap:8px;align-items:center;flex-wrap:wrap;">
                    {stat_cells}
                </div>
            </div>
        </div>""",
        unsafe_allow_html=True,
    )

    # ── Sub-tabs ──
    tab_labels = [t[0] for t in TABS]
    tab_modules = [
        quality_report, backcheck_report, cancelled_interviews,
        performance_report, timing_report, listen_in, wave_comparison,
    ]
    tabs = st.tabs(tab_labels)
    for tab, module in zip(tabs, tab_modules):
        with tab:
            module.show(project_id)
