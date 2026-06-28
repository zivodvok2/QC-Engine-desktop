import streamlit as st
import pandas as pd
import database as db
from config import IPSOS_NAVY, IPSOS_TEAL, IPSOS_ORANGE, UPLOAD_ROLES
from utils.charts import kpi_card, bar_chart, line_chart, scatter_chart, histogram
from utils.exports import to_excel_bytes, to_sav_bytes


def _make_template() -> bytes:
    cols = ["INSTANCE_ID", "INTERVIEWER_ID", "REGION", "INTERVIEW_DATE", "DURATION_MINUTES"]
    return to_excel_bytes(pd.DataFrame(columns=cols), "Timing Report Template")


def _normalise(df: pd.DataFrame) -> pd.DataFrame:
    df.columns = [str(c).strip() for c in df.columns]
    df.columns = [c.lower() for c in df.columns]
    # Handle iField timing export which may have different column names
    rename = {
        "instance id": "instance_id",
        "interviewer id": "interviewer_id",
        "interview date": "interview_date",
        "duration": "duration_minutes",
        "interview length": "duration_minutes",
        "active length": "duration_minutes",
        " duration_1_system": "duration_minutes",
    }
    df = df.rename(columns={k: v for k, v in rename.items() if k in df.columns})
    if "duration_minutes" in df.columns:
        df["duration_minutes"] = pd.to_numeric(df["duration_minutes"], errors="coerce")
    if "interview_date" in df.columns:
        df["interview_date"] = pd.to_datetime(df["interview_date"], errors="coerce").dt.date.astype(str)
    return df


def _upload_section(project_id: int):
    st.markdown("#### Upload Timing Report")
    wave_label = st.text_input("Wave / Period label", placeholder="e.g. Wave 1, April 2025",
                                key="tim_wave", help="Tag this upload for wave comparison.")
    c1, c2 = st.columns([1, 2])
    with c1:
        st.download_button("Download Template", data=_make_template(),
                           file_name="timing_template.xlsx",
                           mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                           use_container_width=True)
    with c2:
        uploaded = st.file_uploader("Upload Excel", type=["xlsx", "xls"], key="tim_uploader")
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
    if st.button("Save Timing Data", type="primary", key="tim_save"):
        records = df.where(pd.notna(df), None).to_dict("records")
        db.insert_timing_records(project_id, st.session_state["user_id"], uploaded.name, records,
                                wave_label=wave_label.strip() or None)
        st.success(f"Saved {len(records)} records.")
        st.rerun()


def show(project_id: int):
    project = db.get_project(project_id)
    st.markdown(f'<h3 style="color:{IPSOS_NAVY};">Timing Report — {project["name"]}</h3>',
                unsafe_allow_html=True)

    role = st.session_state["user_role"]
    records = db.get_timing_records(project_id)

    if role in UPLOAD_ROLES:
        with st.expander("Upload New Data", expanded=True):
            _upload_section(project_id)
        st.markdown("---")

    # Also try to pull duration data from quality report if timing is empty
    if not records:
        # Fall back to quality report duration data
        qr = db.get_quality_records(project_id)
        if qr:
            df = pd.DataFrame(qr)[["instance_id", "interviewer_id", "region", "interview_date", "duration_minutes"]]
            st.info("Showing duration data from Quality Report (no dedicated Timing Report uploaded).")
        else:
            st.info("No timing data yet. Upload a Timing Report or upload a Quality Report first.")
            return
    else:
        df = pd.DataFrame(records)

    df = df.dropna(subset=["duration_minutes"])
    if df.empty:
        st.warning("No duration values found in the data.")
        return

    avg_dur = df["duration_minutes"].mean()
    max_dur = df["duration_minutes"].max()
    min_dur = df["duration_minutes"].min()
    median_dur = df["duration_minutes"].median()
    loi_threshold = avg_dur * 0.50
    short = (df["duration_minutes"] < loi_threshold).sum()

    # KPI cards
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.markdown(kpi_card("Average (min)", f"{avg_dur:.1f}", color=IPSOS_TEAL), unsafe_allow_html=True)
    c2.markdown(kpi_card("Median (min)", f"{median_dur:.1f}", color=IPSOS_TEAL), unsafe_allow_html=True)
    c3.markdown(kpi_card("Maximum (min)", f"{max_dur:.0f}", color=IPSOS_NAVY), unsafe_allow_html=True)
    c4.markdown(kpi_card("Minimum (min)", f"{min_dur:.0f}", color=IPSOS_NAVY), unsafe_allow_html=True)
    c5.markdown(kpi_card("Below 50% Avg", short, color=IPSOS_ORANGE), unsafe_allow_html=True)

    st.caption(f"LOI flag threshold (50% of average): {loi_threshold:.1f} min")
    st.markdown("<br>", unsafe_allow_html=True)

    # Distribution histogram
    c1, c2 = st.columns(2)
    with c1:
        fig = histogram(df, x="duration_minutes", title="Duration Distribution", nbins=30)
        fig.add_vline(x=avg_dur, line_dash="dash", line_color=IPSOS_NAVY,
                      annotation_text=f"Avg: {avg_dur:.1f}")
        fig.add_vline(x=loi_threshold, line_dash="dot", line_color=IPSOS_ORANGE,
                      annotation_text=f"50% Avg: {loi_threshold:.1f}")
        st.plotly_chart(fig, use_container_width=True, key="tim_histogram")

    with c2:
        if "interviewer_id" in df.columns:
            by_int = (df.groupby("interviewer_id")["duration_minutes"]
                      .agg(["mean", "min", "max"]).reset_index())
            by_int.columns = ["Interviewer", "Avg", "Min", "Max"]
            by_int = by_int.sort_values("Avg", ascending=False)
            fig = bar_chart(by_int, x="Interviewer", y="Avg",
                            title="Avg Duration by Interviewer (min)")
            st.plotly_chart(fig, use_container_width=True, key="tim_by_interviewer")

    # Duration by region
    if "region" in df.columns and df["region"].notna().any():
        st.markdown("##### Duration by Region")
        by_reg = df.groupby("region")["duration_minutes"].mean().reset_index()
        by_reg.columns = ["Region", "Avg Duration (min)"]
        fig = bar_chart(by_reg, x="Region", y="Avg Duration (min)", title="Avg Duration by Region")
        st.plotly_chart(fig, use_container_width=True, key="tim_by_region")

    # Duration trend over time
    if "interview_date" in df.columns and "interviewer_id" in df.columns:
        st.markdown("##### Duration Trend Over Time")
        trend = (df.groupby(["interview_date", "interviewer_id"])["duration_minutes"]
                 .mean().reset_index())
        trend["interview_date"] = pd.to_datetime(trend["interview_date"], errors="coerce")
        trend = trend.dropna(subset=["interview_date"])
        if not trend.empty:
            fig = line_chart(trend, x="interview_date", y="duration_minutes",
                             color="interviewer_id",
                             title="Avg Duration per Day per Interviewer")
            fig.add_hline(y=loi_threshold, line_dash="dot", line_color=IPSOS_ORANGE,
                          annotation_text="50% Avg threshold")
            st.plotly_chart(fig, use_container_width=True, key="tim_trend")

    # Scatter: productivity vs duration (if performance data available)
    perf = db.get_performance_records(project_id)
    if perf and "interviewer_id" in df.columns:
        st.markdown("##### Duration vs. Productivity Crosstab")
        perf_df = pd.DataFrame(perf)
        if "interview_completes" in perf_df.columns:
            dur_agg = df.groupby("interviewer_id")["duration_minutes"].mean().reset_index()
            dur_agg.columns = ["interviewer_id", "avg_duration"]
            merged = perf_df.merge(dur_agg, on="interviewer_id", how="inner")
            if not merged.empty:
                fig = scatter_chart(
                    merged, x="avg_duration", y="interview_completes",
                    color="region" if "region" in merged.columns else None,
                    title="Avg Duration vs. Completes per Interviewer",
                    size="interview_completes",
                )
                st.plotly_chart(fig, use_container_width=True, key="tim_scatter")
                st.caption("Outliers (high completes + very short duration) may indicate quality issues.")

    # Data table
    st.markdown("---")
    st.markdown("#### Raw Data")
    disp_cols = [c for c in ["instance_id", "interviewer_id", "region", "interview_date", "duration_minutes"] if c in df.columns]
    st.dataframe(df[disp_cols], use_container_width=True, height=300)
    c1, c2 = st.columns(2)
    xls = to_excel_bytes(df[disp_cols], "Timing")
    c1.download_button("Export to Excel", data=xls, file_name="timing_report.xlsx",
                       mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                       use_container_width=True)
    try:
        sav = to_sav_bytes(df[disp_cols])
        c2.download_button("Export to SAV (SPSS)", data=sav, file_name="timing_report.sav",
                           mime="application/octet-stream", use_container_width=True)
    except Exception as e:
        c2.caption(f"SAV export: {e}")
