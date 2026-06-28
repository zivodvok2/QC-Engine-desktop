import streamlit as st
import pandas as pd
import database as db
from config import (
    IPSOS_NAVY, IPSOS_TEAL, IPSOS_ORANGE, UPLOAD_ROLES,
    PERFORMANCE_IFIELD_COL_MAP,
)
from utils.charts import kpi_card, bar_chart, donut_chart, gauge_chart, line_chart
from utils.exports import to_excel_bytes, to_sav_bytes


def _make_template() -> bytes:
    cols = [
        "INTERVIEWER_ID", "REGION", "FIRST_INTERVIEW", "LAST_INTERVIEW",
        "INTERVIEW_COMPLETES", "FOLLOWUP_COMPLETES", "ECS_COMPLETES",
        "WORK_SUMMARY", "ACCOMPANIMENTS", "CANCELLED_INTERVIEWS",
        "BACKCHECK_TELEPHONE_CREATED", "BACKCHECK_F2F_CREATED",
        "BACKCHECK_F2F_INFIELD", "BACKCHECK_TOTAL", "BACKCHECK_COMPLETED",
    ]
    return to_excel_bytes(pd.DataFrame(columns=cols), "Performance Report Template")


def _normalise(df: pd.DataFrame) -> pd.DataFrame:
    df.columns = [str(c).strip() for c in df.columns]
    df = df.rename(columns={k: v for k, v in PERFORMANCE_IFIELD_COL_MAP.items() if k in df.columns})
    df.columns = [c.lower() for c in df.columns]
    num_cols = [
        "interview_completes", "followup_completes", "ecs_completes", "work_summary",
        "accompaniments", "cancelled_interviews", "backcheck_telephone_created",
        "backcheck_f2f_created", "backcheck_f2f_infield", "backcheck_total",
        "backcheck_completed",
    ]
    for col in num_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0).astype(int)
    return df


def _upload_section(project_id: int):
    st.markdown("#### Upload Performance Report")
    wave_label = st.text_input("Wave / Period label", placeholder="e.g. Wave 1, April 2025",
                                key="perf_wave", help="Tag this upload for wave comparison.")
    c1, c2 = st.columns([1, 2])
    with c1:
        st.download_button("Download Template", data=_make_template(),
                           file_name="performance_template.xlsx",
                           mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                           use_container_width=True)
    with c2:
        uploaded = st.file_uploader("Upload Excel", type=["xlsx", "xls"], key="perf_uploader")
    if not uploaded:
        return
    try:
        df = pd.read_excel(uploaded, skiprows=2)  # iField report has 2 header rows
    except Exception as e:
        st.error(f"Read error: {e}")
        return
    df = df.dropna(how="all")
    df = _normalise(df)
    st.info(f"{len(df)} rows. Preview:")
    st.dataframe(df.head(5), use_container_width=True)
    if st.button("Save Performance Data", type="primary", key="perf_save"):
        records = df.where(pd.notna(df), None).to_dict("records")
        db.insert_performance_records(project_id, st.session_state["user_id"], uploaded.name, records,
                                     wave_label=wave_label.strip() or None)
        st.success(f"Saved {len(records)} records.")
        st.rerun()


def show(project_id: int):
    project = db.get_project(project_id)
    st.markdown(f'<h3 style="color:{IPSOS_NAVY};">Performance Report — {project["name"]}</h3>',
                unsafe_allow_html=True)

    role = st.session_state["user_role"]
    records = db.get_performance_records(project_id)

    if role in UPLOAD_ROLES:
        with st.expander("Upload New Data", expanded=True):
            _upload_section(project_id)
        st.markdown("---")

    if not records:
        st.info("No performance report data yet.")
        return

    df = pd.DataFrame(records)
    acc_target = project.get("accompaniment_target", 0.20)
    bc_target = project.get("backcheck_target", 0.20)

    total_interviewers = df["interviewer_id"].nunique() if "interviewer_id" in df.columns else 0
    total_completes = int(df["interview_completes"].sum()) if "interview_completes" in df.columns else 0
    total_acc = int(df["accompaniments"].sum()) if "accompaniments" in df.columns else 0
    total_bc_done = int(df["backcheck_completed"].sum()) if "backcheck_completed" in df.columns else 0
    acc_rate = round(total_acc / total_completes * 100, 1) if total_completes else 0
    bc_rate = round(total_bc_done / total_completes * 100, 1) if total_completes else 0

    # KPI cards
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.markdown(kpi_card("Total Interviewers", total_interviewers, color=IPSOS_NAVY), unsafe_allow_html=True)
    c2.markdown(kpi_card("Interview Completes", f"{total_completes:,}", color=IPSOS_TEAL), unsafe_allow_html=True)
    c3.markdown(kpi_card("Accompaniments", f"{total_acc:,}", color=IPSOS_TEAL), unsafe_allow_html=True)
    c4.markdown(kpi_card("Acc. Rate", acc_rate, suffix="%",
                         color=IPSOS_TEAL if acc_rate >= acc_target * 100 else IPSOS_ORANGE), unsafe_allow_html=True)
    c5.markdown(kpi_card("BC Completed", f"{total_bc_done:,}", color=IPSOS_TEAL), unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # Gauge charts
    g1, g2 = st.columns(2)
    with g1:
        fig = gauge_chart(acc_rate, acc_target, "Accompaniment Rate vs Target")
        st.plotly_chart(fig, use_container_width=True, key="perf_acc_gauge")
    with g2:
        fig = gauge_chart(bc_rate, bc_target, "Back-check Completion Rate vs Target")
        st.plotly_chart(fig, use_container_width=True, key="perf_bc_gauge")

    # Interviewers by completes
    if "interviewer_id" in df.columns and "interview_completes" in df.columns:
        st.markdown("##### Interviewers by Interview Completes")
        by_int = df.groupby("interviewer_id")["interview_completes"].sum().reset_index()
        by_int.columns = ["Interviewer", "Completes"]
        by_int = by_int.sort_values("Completes", ascending=False)
        fig = bar_chart(by_int, x="Interviewer", y="Completes",
                        title="Completes per Interviewer")
        st.plotly_chart(fig, use_container_width=True, key="perf_completes_by_interviewer")

    # Completes by region
    if "region" in df.columns and "interview_completes" in df.columns:
        c1, c2 = st.columns(2)
        with c1:
            by_reg = df.groupby("region")["interview_completes"].sum().reset_index()
            by_reg.columns = ["Region", "Completes"]
            fig = bar_chart(by_reg, x="Region", y="Completes", title="Completes by Region")
            st.plotly_chart(fig, use_container_width=True, key="perf_completes_by_region")
        with c2:
            acc_donut_vals = [total_acc, max(total_completes - total_acc, 0)]
            fig = donut_chart(acc_donut_vals, ["Accompanied", "Not Accompanied"],
                              "Accompaniment Rate",
                              colors=["#00B5AD", "#F5F5F5"])
            st.plotly_chart(fig, use_container_width=True, key="perf_acc_donut")

    # Back-check breakdown
    bc_cols = ["backcheck_telephone_created", "backcheck_f2f_created", "backcheck_f2f_infield", "backcheck_completed"]
    present_bc = [c for c in bc_cols if c in df.columns]
    if present_bc:
        st.markdown("##### Back-check Activity Summary")
        bc_totals = {c.replace("backcheck_", "").replace("_", " ").title(): int(df[c].sum()) for c in present_bc}
        bc_df = pd.DataFrame({"Type": list(bc_totals.keys()), "Count": list(bc_totals.values())})
        fig = bar_chart(bc_df, x="Type", y="Count", title="Back-check Activity by Type")
        st.plotly_chart(fig, use_container_width=True, key="perf_bc_activity")

    # Team Retention — interviewers active across multiple projects
    st.markdown("##### Team Retention (Interviewers Across Projects)")
    retention = db.get_interviewer_cross_project_count()
    if retention:
        ret_df = pd.DataFrame(retention)
        ret_df.columns = ["Interviewer", "Projects Active", "Total Completes"]
        multi = ret_df[ret_df["Projects Active"] > 1].copy()
        if not multi.empty:
            fig = bar_chart(multi, x="Interviewer", y="Projects Active",
                            title="Interviewers Active Across Multiple Projects")
            st.plotly_chart(fig, use_container_width=True, key="perf_retention")
            st.caption(f"{len(multi)} of {len(ret_df)} interviewers have worked on more than one project.")
        else:
            st.info("No interviewers have been recorded across multiple projects yet.")

    # Data table
    st.markdown("---")
    st.markdown("#### Raw Data")
    disp_cols = [c for c in [
        "interviewer_id", "region", "first_interview", "last_interview",
        "interview_completes", "followup_completes", "accompaniments",
        "cancelled_interviews", "backcheck_total", "backcheck_completed",
    ] if c in df.columns]
    st.dataframe(df[disp_cols], use_container_width=True, height=300)
    c1, c2 = st.columns(2)
    xls = to_excel_bytes(df[disp_cols], "Performance")
    c1.download_button("Export to Excel", data=xls, file_name="performance_report.xlsx",
                       mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                       use_container_width=True)
    try:
        sav = to_sav_bytes(df[disp_cols])
        c2.download_button("Export to SAV (SPSS)", data=sav, file_name="performance_report.sav",
                           mime="application/octet-stream", use_container_width=True)
    except Exception as e:
        c2.caption(f"SAV export: {e}")
