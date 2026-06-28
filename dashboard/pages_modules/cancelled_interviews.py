import streamlit as st
import pandas as pd
import database as db
from config import (
    IPSOS_NAVY, IPSOS_TEAL, IPSOS_ORANGE, UPLOAD_ROLES, CANCELLED_IFIELD_COL_MAP
)
from utils.charts import kpi_card, bar_chart, stacked_bar, histogram, donut_chart
from utils.exports import to_excel_bytes, to_sav_bytes


def _make_template() -> bytes:
    cols = [
        "INSTANCE_ID", "REGION", "LOCATION", "SAMPLE_POINT_ID", "INTERVIEWER_ID",
        "SCRIPT_NAME", "INTERVIEW_DATE", "START_TIME", "END_TIME",
        "INTERVIEW_LENGTH", "ACTIVE_LENGTH", "AVG_LENGTH_SAMPLE_POINT",
        "AVG_LENGTH_REGION", "AVG_LENGTH_PROJECT", "IDLE_TIME", "GAP_TO_LAST",
        "SAME_DAY_FINISH", "QF_A", "QF_B", "QF_C", "QF_D", "QF_E", "QF_F",
        "INTERVIEWER_PERFORMANCE", "BACKCHECK_RESULT_TELEPHONE",
        "BACKCHECK_RESULT_F2F", "BACKCHECK_RESULT_INDEPENDENT",
    ]
    return to_excel_bytes(pd.DataFrame(columns=cols), "Cancelled Interviews Template")


def _normalise(df: pd.DataFrame) -> pd.DataFrame:
    df.columns = [str(c).strip() for c in df.columns]
    df = df.rename(columns={k: v for k, v in CANCELLED_IFIELD_COL_MAP.items() if k in df.columns})
    df.columns = [c.lower() for c in df.columns]
    for col in ["interview_length", "active_length", "idle_time", "gap_to_last",
                "avg_length_sample_point", "avg_length_region", "avg_length_project"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    if "interview_date" in df.columns:
        df["interview_date"] = pd.to_datetime(df["interview_date"], errors="coerce").dt.date.astype(str)
    return df


def _upload_section(project_id: int):
    st.markdown("#### Upload Cancelled Interviews Report")
    wave_label = st.text_input("Wave / Period label", placeholder="e.g. Wave 1, April 2025",
                                key="ci_wave", help="Tag this upload for wave comparison.")
    c1, c2 = st.columns([1, 2])
    with c1:
        st.download_button("Download Template", data=_make_template(),
                           file_name="cancelled_template.xlsx",
                           mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                           use_container_width=True)
    with c2:
        uploaded = st.file_uploader("Upload Excel", type=["xlsx", "xls"], key="ci_uploader")
    if not uploaded:
        return
    try:
        df = pd.read_excel(uploaded)
    except Exception as e:
        st.error(f"Read error: {e}")
        return
    df = df.dropna(how="all")
    df = _normalise(df)
    st.info(f"{len(df)} rows. Preview:")
    st.dataframe(df.head(5), use_container_width=True)
    if st.button("Save Cancelled Interviews Data", type="primary", key="ci_save"):
        records = df.where(pd.notna(df), None).to_dict("records")
        db.insert_cancelled_records(project_id, st.session_state["user_id"], uploaded.name, records,
                                    wave_label=wave_label.strip() or None)
        st.success(f"Saved {len(records)} records.")
        st.rerun()


def show(project_id: int):
    project = db.get_project(project_id)
    st.markdown(f'<h3 style="color:{IPSOS_NAVY};">Cancelled Interviews — {project["name"]}</h3>',
                unsafe_allow_html=True)

    role = st.session_state["user_role"]
    records = db.get_cancelled_records(project_id)

    if role in UPLOAD_ROLES:
        with st.expander("Upload New Data", expanded=True):
            _upload_section(project_id)
        st.markdown("---")

    if not records:
        st.info("No cancelled interview data yet.")
        return

    df = pd.DataFrame(records)

    total = len(df)
    qr = db.get_quality_records(project_id)
    total_submitted = len(qr)
    cancel_rate = round(total / total_submitted * 100, 1) if total_submitted else 0

    avg_dur = df["interview_length"].mean() if "interview_length" in df.columns else 0
    avg_gap = df["gap_to_last"].mean() if "gap_to_last" in df.columns else 0

    # KPI cards
    c1, c2, c3, c4 = st.columns(4)
    c1.markdown(kpi_card("Total Cancellations", total, color=IPSOS_ORANGE), unsafe_allow_html=True)
    c2.markdown(kpi_card("Cancellation Rate", cancel_rate, suffix="%", color=IPSOS_ORANGE), unsafe_allow_html=True)
    c3.markdown(kpi_card("Avg Duration (min)", f"{avg_dur:.1f}" if avg_dur else "—", color=IPSOS_NAVY), unsafe_allow_html=True)
    c4.markdown(kpi_card("Avg Gap to Last (sec)", f"{avg_gap:.0f}" if avg_gap else "—", color=IPSOS_NAVY), unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # Cancellations by interviewer
    if "interviewer_id" in df.columns:
        c1, c2 = st.columns(2)
        with c1:
            by_int = df["interviewer_id"].value_counts().reset_index()
            by_int.columns = ["Interviewer", "Cancellations"]
            fig = bar_chart(by_int, x="Interviewer", y="Cancellations",
                            title="Cancellations by Interviewer", orientation="h")
            fig.update_layout(height=400)
            st.plotly_chart(fig, use_container_width=True, key="ci_by_interviewer")

        with c2:
            if "region" in df.columns:
                by_reg = df["region"].value_counts().reset_index()
                by_reg.columns = ["Region", "Cancellations"]
                fig = bar_chart(by_reg, x="Region", y="Cancellations",
                                title="Cancellations by Region")
                st.plotly_chart(fig, use_container_width=True, key="ci_by_region")

    # Quality flags breakdown
    qf_cols = ["qf_a", "qf_b", "qf_c", "qf_d", "qf_e", "qf_f"]
    present = [c for c in qf_cols if c in df.columns]
    if present:
        st.markdown("##### Quality Flag Rates")
        flag_data = []
        for qf in present:
            flagged = df[qf].notna() & (df[qf] != "") & (df[qf] != "0")
            flag_data.append({"Flag": qf.upper(), "Count": int(flagged.sum())})
        flag_df = pd.DataFrame(flag_data)
        if flag_df["Count"].sum() > 0:
            fig = donut_chart(flag_df["Count"], flag_df["Flag"], "Quality Flags Distribution")
            st.plotly_chart(fig, use_container_width=True, key="ci_quality_flags")

    # Gap to last interview histogram
    if "gap_to_last" in df.columns and df["gap_to_last"].notna().any():
        st.markdown("##### Gap to Last Interview Distribution (seconds)")
        fig = histogram(df.dropna(subset=["gap_to_last"]), x="gap_to_last",
                        title="Time Between Consecutive Interviews")
        st.plotly_chart(fig, use_container_width=True, key="ci_gap_histogram")

    # Data table
    st.markdown("---")
    st.markdown("#### Raw Data")
    show_cols = [c for c in [
        "instance_id", "interviewer_id", "region", "interview_date",
        "interview_length", "active_length", "gap_to_last",
        "qf_a", "qf_b", "qf_c", "qf_d", "qf_e", "qf_f",
        "interviewer_performance",
    ] if c in df.columns]
    st.dataframe(df[show_cols], use_container_width=True, height=300)
    c1, c2 = st.columns(2)
    xls = to_excel_bytes(df[show_cols], "Cancelled Interviews")
    c1.download_button("Export to Excel", data=xls, file_name="cancelled_interviews.xlsx",
                       mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                       use_container_width=True)
    try:
        sav = to_sav_bytes(df[show_cols])
        c2.download_button("Export to SAV (SPSS)", data=sav, file_name="cancelled_interviews.sav",
                           mime="application/octet-stream", use_container_width=True)
    except Exception as e:
        c2.caption(f"SAV export: {e}")
