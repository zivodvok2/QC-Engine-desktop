import streamlit as st
import pandas as pd
import database as db
from config import (
    IPSOS_NAVY, IPSOS_TEAL, IPSOS_ORANGE, IPSOS_YELLOW, UPLOAD_ROLES,
    BACKCHECK_ERRORS, BACKCHECK_IFIELD_COL_MAP,
)
from utils.charts import kpi_card, donut_chart, stacked_bar, bar_chart, gauge_chart
from utils.exports import to_excel_bytes, to_sav_bytes


def _make_template() -> bytes:
    cols = [
        "BC_INSTANCE_ID", "ORIGINAL_INSTANCE_ID", "INTERVIEW_STATUS",
        "REGION", "LOCATION", "SAMPLE_POINT_ID",
        "BACKCHECKER_ID", "INTERVIEWER_ID", "SCRIPT_NAME",
        "INTERVIEW_DATE", "INTERVIEW_START_TIME", "BACKCHECK_DATE", "BACKCHECK_TIME",
    ] + [f"ERROR_{i:02d}" for i in range(1, 14)]
    df = pd.DataFrame(columns=cols)
    df.loc[0] = {
        "BC_INSTANCE_ID": "3782466", "ORIGINAL_INSTANCE_ID": "3782413",
        "INTERVIEW_STATUS": "Completed - Pending Export",
        "REGION": "Nairobi", "LOCATION": "Githunguri road", "SAMPLE_POINT_ID": "NB09",
        "BACKCHECKER_ID": "LE0018", "INTERVIEWER_ID": "NB0664",
        "SCRIPT_NAME": "Project Name", "INTERVIEW_DATE": "2025-04-15",
        "INTERVIEW_START_TIME": "14:56:22", "BACKCHECK_DATE": "2025-04-16",
        "BACKCHECK_TIME": "08:50",
        **{f"ERROR_{i:02d}": "" for i in range(1, 14)},
    }
    return to_excel_bytes(df, "Back-check Template")


def _normalise(df: pd.DataFrame) -> pd.DataFrame:
    df.columns = [str(c).strip() for c in df.columns]
    df = df.rename(columns={k: v for k, v in BACKCHECK_IFIELD_COL_MAP.items() if k in df.columns})
    df.columns = [c.lower() for c in df.columns]

    # Map iField numeric error cols (cols 18-30) if named by position
    error_db_cols = [f"error_{i:02d}" for i in range(1, 14)]
    for i, ecol in enumerate(error_db_cols, 1):
        if ecol not in df.columns:
            ifield_name = f"({i})"
            candidates = [c for c in df.columns if c.startswith(ifield_name)]
            if candidates:
                df = df.rename(columns={candidates[0]: ecol})

    for ecol in error_db_cols:
        if ecol in df.columns:
            df[ecol] = pd.to_numeric(df[ecol], errors="coerce").fillna(0).astype(int)
        else:
            df[ecol] = 0

    if "interview_date" in df.columns:
        df["interview_date"] = pd.to_datetime(df["interview_date"], errors="coerce").dt.date.astype(str)
    if "backcheck_date" in df.columns:
        df["backcheck_date"] = pd.to_datetime(df["backcheck_date"], errors="coerce").dt.date.astype(str)

    return df


def _upload_section(project_id: int):
    st.markdown("#### Upload Back-check Report")

    wave_label = st.text_input("Wave / Period label", placeholder="e.g. Wave 1, April 2025",
                                key="bc_wave", help="Tag this upload for wave comparison.")

    c1, c2 = st.columns([1, 2])
    with c1:
        st.download_button("Download Template", data=_make_template(),
                           file_name="backcheck_template.xlsx",
                           mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                           use_container_width=True)
    with c2:
        uploaded = st.file_uploader("Upload Excel (.xlsx / .xls)", type=["xlsx", "xls"],
                                    key="bc_uploader")

    if not uploaded:
        return

    try:
        df = pd.read_excel(uploaded)
    except Exception as e:
        st.error(f"Could not read file: {e}")
        return

    df = df.dropna(how="all")
    df = _normalise(df)

    st.info(f"{len(df)} rows detected. Preview:")
    st.dataframe(df.head(5), use_container_width=True)

    if st.button("Save Back-check Data", type="primary", key="bc_save"):
        records = df.where(pd.notna(df), None).to_dict("records")
        uid = db.insert_backcheck_records(
            project_id, st.session_state["user_id"], uploaded.name, records,
            wave_label=wave_label.strip() or None,
        )
        st.success(f"Saved {len(records)} records.")
        st.rerun()


def _upload_history(project_id: int):
    logs = [l for l in db.get_upload_log(project_id) if l["report_type"] == "backcheck"]
    if not logs:
        return
    st.markdown("##### Upload History")
    for log in logs:
        c1, c2, c3 = st.columns([3, 2, 1])
        c1.write(f"📂 {log['filename']} — {log['row_count']} rows")
        c2.caption(f"by {log.get('uploader_name', '?')} on {log['upload_date'][:16]}")
        if st.session_state["user_role"] in ("qc_executive", "operations_manager"):
            if c3.button("Delete", key=f"del_bc_{log['upload_id']}"):
                db.delete_upload(log["upload_id"], "backcheck")
                st.rerun()


def show(project_id: int):
    project = db.get_project(project_id)
    st.markdown(f'<h3 style="color:{IPSOS_NAVY};">Back-check Report — {project["name"]}</h3>',
                unsafe_allow_html=True)

    role = st.session_state["user_role"]
    records = db.get_backcheck_records(project_id)

    if role in UPLOAD_ROLES:
        with st.expander("Upload New Data", expanded=True):
            _upload_section(project_id)
        _upload_history(project_id)
        st.markdown("---")

    if not records:
        st.info("No back-check data yet.")
        return

    df = pd.DataFrame(records)
    error_cols = [f"error_{i:02d}" for i in range(1, 14)]

    # Approved interviews from quality report for rate calculation
    qr = db.get_quality_records(project_id)
    approved = sum(1 for r in qr if str(r.get("approval_status", "")).lower() == "approved")
    bc_target = project.get("backcheck_target", 0.20)
    total_bc = len(df)
    bc_rate = round(total_bc / approved * 100, 1) if approved else 0

    # Any interview with no critical errors (01–04) is "effective"
    critical = ["error_01", "error_02", "error_03", "error_04"]
    crit_cols = [c for c in critical if c in df.columns]
    effective = int((df[crit_cols].sum(axis=1) == 0).sum()) if crit_cols else total_bc

    # ── KPI cards ──────────────────────────────────────────────────────────
    st.markdown("#### Summary")
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.markdown(kpi_card("Approved Interviews", f"{approved:,}", color=IPSOS_NAVY), unsafe_allow_html=True)
    c2.markdown(kpi_card("Back-checks Done", f"{total_bc:,}", color=IPSOS_TEAL), unsafe_allow_html=True)
    c3.markdown(kpi_card("Effective BCs", f"{effective:,}", color=IPSOS_TEAL), unsafe_allow_html=True)
    c4.markdown(kpi_card("BC Rate", bc_rate, suffix="%",
                         color=IPSOS_TEAL if bc_rate >= bc_target * 100 else IPSOS_ORANGE), unsafe_allow_html=True)
    c5.markdown(kpi_card("Target", f"{bc_target*100:.0f}", suffix="%", color=IPSOS_NAVY), unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Charts ─────────────────────────────────────────────────────────────
    c1, c2 = st.columns(2)
    with c1:
        fig = gauge_chart(bc_rate, bc_target, "Back-check Rate vs Target")
        st.plotly_chart(fig, use_container_width=True, key="bc_gauge")

    with c2:
        ec_totals = {BACKCHECK_ERRORS[ec]: int(df[ec].sum()) for ec in error_cols if ec in df.columns}
        ec_totals = {k: v for k, v in ec_totals.items() if v > 0}
        if ec_totals:
            fig = donut_chart(list(ec_totals.values()), list(ec_totals.keys()),
                              "Error Type Breakdown")
            st.plotly_chart(fig, use_container_width=True, key="bc_error_types")
        else:
            st.success("No errors recorded.")

    # Error distribution by interviewer
    if "interviewer_id" in df.columns:
        st.markdown("##### Error Distribution by Interviewer")
        err_rows = []
        for iid, grp in df.groupby("interviewer_id"):
            for ec in error_cols:
                if ec in grp.columns and grp[ec].sum() > 0:
                    err_rows.append({
                        "Interviewer": iid,
                        "Error": BACKCHECK_ERRORS.get(ec, ec),
                        "Count": int(grp[ec].sum()),
                    })
        if err_rows:
            err_df = pd.DataFrame(err_rows)
            fig = stacked_bar(err_df, x="Interviewer", y="Count", color="Error",
                              title="Back-check Errors by Interviewer")
            st.plotly_chart(fig, use_container_width=True, key="bc_errors_by_interviewer")

    # Error distribution by region
    if "region" in df.columns:
        st.markdown("##### Error Distribution by Region")
        reg_err = []
        for reg, grp in df.groupby("region"):
            for ec in error_cols:
                if ec in grp.columns and grp[ec].sum() > 0:
                    reg_err.append({"Region": reg, "Error": BACKCHECK_ERRORS.get(ec, ec), "Count": int(grp[ec].sum())})
        if reg_err:
            fig = stacked_bar(pd.DataFrame(reg_err), x="Region", y="Count", color="Error",
                              title="Back-check Errors by Region")
            st.plotly_chart(fig, use_container_width=True, key="bc_errors_by_region")

    # ── Data table ─────────────────────────────────────────────────────────
    st.markdown("---")
    st.markdown("#### Raw Data")
    display_cols = [c for c in [
        "bc_instance_id", "original_instance_id", "interviewer_id", "backchecker_id",
        "region", "location", "interview_date", "backcheck_date", "interview_status",
    ] + error_cols if c in df.columns]
    disp_df = df[display_cols]
    st.dataframe(disp_df, use_container_width=True, height=300)
    c1, c2 = st.columns(2)
    xls = to_excel_bytes(disp_df, "Back-check")
    c1.download_button("Export to Excel", data=xls, file_name="backcheck_report.xlsx",
                       mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                       use_container_width=True)
    try:
        sav = to_sav_bytes(disp_df)
        c2.download_button("Export to SAV (SPSS)", data=sav, file_name="backcheck_report.sav",
                           mime="application/octet-stream", use_container_width=True)
    except Exception as e:
        c2.caption(f"SAV export: {e}")
