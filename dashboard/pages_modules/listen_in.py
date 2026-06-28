"""
Listen-in tracking page.

Since there is no existing system data source for listen-in, this page provides:
  1. A manual entry form — log one session at a time
  2. A batch upload — Excel template with the same columns
  3. KPI cards and charts — rate vs target, type breakdown, by-interviewer trend
"""

import streamlit as st
import pandas as pd
from datetime import date

import database as db
from config import (
    IPSOS_NAVY, IPSOS_TEAL, IPSOS_ORANGE, IPSOS_YELLOW, UPLOAD_ROLES,
)
from utils.charts import kpi_card, donut_chart, bar_chart, line_chart, gauge_chart
from utils.exports import to_excel_bytes, to_sav_bytes

LISTEN_TYPES = ["Telephone", "F2F / Accompaniment", "Audio Playback"]
RESULT_OPTIONS = ["Pass", "Fail", "Partial"]


# ── Template ───────────────────────────────────────────────────────────────

def _make_template() -> bytes:
    cols = [
        "INSTANCE_ID", "INTERVIEWER_ID", "REGION",
        "LISTEN_DATE", "LISTEN_TYPE", "RESULT",
        "ISSUES_NOTED", "ACTION_TAKEN",
    ]
    df = pd.DataFrame(columns=cols)
    df.loc[0] = {
        "INSTANCE_ID": "3782322",
        "INTERVIEWER_ID": "NB0664",
        "REGION": "Nairobi",
        "LISTEN_DATE": str(date.today()),
        "LISTEN_TYPE": "Telephone",
        "RESULT": "Pass",
        "ISSUES_NOTED": "",
        "ACTION_TAKEN": "",
    }
    return to_excel_bytes(df, "Listen-in Template")


# ── Manual entry form ──────────────────────────────────────────────────────

def _manual_entry(project_id: int):
    st.markdown("#### Log a Listen-in Session")

    # Pre-populate interviewer list from quality report if available
    qr = db.get_quality_records(project_id)
    qr_interviewers = sorted({r["interviewer_id"] for r in qr if r.get("interviewer_id")})
    qr_regions = sorted({r["region"] for r in qr if r.get("region")})

    with st.form("listenin_form", clear_on_submit=True):
        c1, c2, c3 = st.columns(3)
        instance_id = c1.text_input("Instance ID (optional)", placeholder="e.g. 3782322")
        interviewer_id = c2.selectbox("Interviewer ID", ["— type manually —"] + qr_interviewers) \
            if qr_interviewers else c2.text_input("Interviewer ID")
        region = c3.selectbox("Region", ["— type manually —"] + qr_regions) \
            if qr_regions else c3.text_input("Region")

        # Allow freetext override if "type manually" selected
        if qr_interviewers and interviewer_id == "— type manually —":
            interviewer_id = st.text_input("Enter Interviewer ID manually", key="int_manual")
        if qr_regions and region == "— type manually —":
            region = st.text_input("Enter Region manually", key="reg_manual")

        c4, c5, c6 = st.columns(3)
        listen_date = c4.date_input("Listen Date", value=date.today())
        listen_type = c5.selectbox("Listen Type", LISTEN_TYPES)
        result = c6.selectbox("Result", RESULT_OPTIONS)

        issues = st.text_area("Issues Noted", placeholder="Describe any quality issues observed…", height=80)
        action = st.text_area("Action Taken", placeholder="Describe corrective actions or follow-up…", height=80)

        submitted = st.form_submit_button("Save Session", type="primary", use_container_width=True)

    if submitted:
        if not interviewer_id or interviewer_id == "— type manually —":
            st.error("Interviewer ID is required.")
        else:
            db.insert_listen_in_record(
                project_id=project_id,
                logged_by=st.session_state["user_id"],
                instance_id=instance_id or None,
                interviewer_id=interviewer_id.strip(),
                region=region if region and region != "— type manually —" else None,
                listen_date=listen_date,
                listen_type=listen_type,
                result=result,
                issues_noted=issues or None,
                action_taken=action or None,
            )
            st.success(f"Listen-in session logged for interviewer {interviewer_id}.")
            st.rerun()


# ── Batch upload ───────────────────────────────────────────────────────────

def _batch_upload(project_id: int):
    st.markdown("#### Batch Upload")

    wave_label = st.text_input("Wave / Period label", placeholder="e.g. Wave 1, April 2025",
                                key="li_wave", help="Tag this upload for wave comparison.")

    c1, c2 = st.columns([1, 2])
    with c1:
        st.download_button(
            "Download Template",
            data=_make_template(),
            file_name="listen_in_template.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
        )
    with c2:
        uploaded = st.file_uploader("Upload Excel (.xlsx / .xls)", type=["xlsx", "xls"],
                                    key="li_uploader")

    if not uploaded:
        return

    try:
        df = pd.read_excel(uploaded)
    except Exception as e:
        st.error(f"Read error: {e}")
        return

    df.columns = [str(c).strip().lower() for c in df.columns]
    rename = {
        "instance id": "instance_id", "interviewer id": "interviewer_id",
        "listen date": "listen_date", "listen type": "listen_type",
        "issues noted": "issues_noted", "action taken": "action_taken",
    }
    df = df.rename(columns=rename)
    df = df.dropna(how="all")

    if "listen_date" in df.columns:
        df["listen_date"] = pd.to_datetime(df["listen_date"], errors="coerce").dt.date.astype(str)

    st.info(f"{len(df)} rows. Preview:")
    st.dataframe(df.head(5), use_container_width=True)

    if st.button("Save Batch", type="primary", key="li_save"):
        records = df.where(pd.notna(df), None).to_dict("records")
        uid = db.insert_listen_in_batch(
            project_id, st.session_state["user_id"], uploaded.name, records,
            wave_label=wave_label.strip() or None,
        )
        st.success(f"Saved {len(records)} listen-in records.")
        st.rerun()


# ── KPI + charts ───────────────────────────────────────────────────────────

def _kpi_and_charts(df: pd.DataFrame, project: dict):
    qr = db.get_quality_records(project["id"])
    approved = sum(1 for r in qr if str(r.get("approval_status", "")).lower() == "approved")
    li_target = project.get("listenin_target", 0.10)
    total_li = len(df)
    li_rate = round(total_li / approved * 100, 1) if approved else 0

    passes = (df["result"] == "Pass").sum() if "result" in df.columns else 0
    fails = (df["result"] == "Fail").sum() if "result" in df.columns else 0
    partials = (df["result"] == "Partial").sum() if "result" in df.columns else 0

    # KPI cards
    st.markdown("#### Summary")
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.markdown(kpi_card("Approved Interviews", f"{approved:,}", color=IPSOS_NAVY), unsafe_allow_html=True)
    c2.markdown(kpi_card("Listen-in Sessions", f"{total_li:,}", color=IPSOS_TEAL), unsafe_allow_html=True)
    c3.markdown(kpi_card("Listen-in Rate", li_rate, suffix="%",
                         color=IPSOS_TEAL if li_rate >= li_target * 100 else IPSOS_ORANGE),
                unsafe_allow_html=True)
    c4.markdown(kpi_card("Target", f"{li_target*100:.0f}", suffix="%", color=IPSOS_NAVY), unsafe_allow_html=True)
    c5.markdown(kpi_card("Pass Rate",
                         f"{round(passes/total_li*100,1)}" if total_li else "—",
                         suffix="%" if total_li else "",
                         color=IPSOS_TEAL), unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # Row 1: gauge + result donut
    c1, c2 = st.columns(2)
    with c1:
        fig = gauge_chart(li_rate, li_target, "Listen-in Rate vs Target")
        st.plotly_chart(fig, use_container_width=True, key="li_gauge")
    with c2:
        if total_li:
            fig = donut_chart(
                [passes, fails, partials],
                ["Pass", "Fail", "Partial"],
                "Result Breakdown",
                colors=["#00B5AD", "#FF7043", "#D4E157"],
            )
            st.plotly_chart(fig, use_container_width=True, key="li_results")

    # Listen type breakdown
    if "listen_type" in df.columns:
        c1, c2 = st.columns(2)
        with c1:
            type_counts = df["listen_type"].value_counts().reset_index()
            type_counts.columns = ["Listen Type", "Count"]
            fig = donut_chart(type_counts["Count"], type_counts["Listen Type"],
                              "Listen Type Breakdown")
            st.plotly_chart(fig, use_container_width=True, key="li_type_breakdown")
        with c2:
            if "interviewer_id" in df.columns:
                by_int = df["interviewer_id"].value_counts().reset_index()
                by_int.columns = ["Interviewer", "Sessions"]
                by_int = by_int.head(15)
                fig = bar_chart(by_int, x="Interviewer", y="Sessions",
                                title="Listen-in Sessions by Interviewer")
                st.plotly_chart(fig, use_container_width=True, key="li_by_interviewer")

    # Trend over time
    if "listen_date" in df.columns:
        st.markdown("##### Listen-in Trend Over Time")
        df["listen_date"] = pd.to_datetime(df["listen_date"], errors="coerce")
        trend = df.dropna(subset=["listen_date"])
        if not trend.empty:
            if "listen_type" in trend.columns:
                daily = trend.groupby(["listen_date", "listen_type"]).size().reset_index(name="Count")
                fig = line_chart(daily, x="listen_date", y="Count", color="listen_type",
                                 title="Daily Listen-in Sessions by Type")
            else:
                daily = trend.groupby("listen_date").size().reset_index(name="Count")
                fig = line_chart(daily, x="listen_date", y="Count",
                                 title="Daily Listen-in Sessions")
            st.plotly_chart(fig, use_container_width=True, key="li_trend")

    # Issues table
    issues_df = df[df["issues_noted"].notna() & (df["issues_noted"] != "")].copy() \
        if "issues_noted" in df.columns else pd.DataFrame()
    if not issues_df.empty:
        st.markdown("##### Sessions with Issues Noted")
        show_cols = [c for c in ["listen_date", "interviewer_id", "listen_type",
                                  "result", "issues_noted", "action_taken"] if c in issues_df.columns]
        st.dataframe(issues_df[show_cols].reset_index(drop=True),
                     use_container_width=True, height=250)


# ── Log history + delete ───────────────────────────────────────────────────

def _session_log(df: pd.DataFrame, project_id: int):
    st.markdown("---")
    st.markdown("#### All Listen-in Sessions")

    role = st.session_state["user_role"]
    show_cols = [c for c in [
        "id", "listen_date", "interviewer_id", "region",
        "listen_type", "result", "issues_noted", "action_taken",
    ] if c in df.columns]

    st.dataframe(df[show_cols].reset_index(drop=True),
                 use_container_width=True, height=300)

    c1, c2, c3 = st.columns(3)
    xls = to_excel_bytes(df[show_cols], "Listen-in")
    c1.download_button("Export to Excel", data=xls, file_name="listen_in_sessions.xlsx",
                       mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                       use_container_width=True)
    try:
        sav = to_sav_bytes(df[show_cols])
        c2.download_button("Export to SAV (SPSS)", data=sav, file_name="listen_in_sessions.sav",
                           mime="application/octet-stream", use_container_width=True)
    except Exception as e:
        c2.caption(f"SAV export: {e}")

    if role in ("qc_executive", "operations_manager", "qc_officer") and "id" in df.columns:
        with c3:
            with st.expander("Delete a record"):
                rec_ids = df["id"].tolist()
                sel_id = st.selectbox("Select record ID", rec_ids, key="li_del_id")
                if st.button("Delete", key="li_del_btn", type="secondary"):
                    db.delete_listen_in_record(sel_id)
                    st.success("Record deleted.")
                    st.rerun()


# ── Main ───────────────────────────────────────────────────────────────────

def show(project_id: int):
    project = db.get_project(project_id)
    st.markdown(
        f'<h3 style="color:{IPSOS_NAVY};">Listen-in Tracking — {project["name"]}</h3>',
        unsafe_allow_html=True,
    )
    st.caption(
        "Listen-in sessions are logged manually here. "
        "Use the form below to record individual sessions, or upload a batch Excel file."
    )

    role = st.session_state["user_role"]
    can_log = role in UPLOAD_ROLES

    if can_log:
        entry_tab, batch_tab = st.tabs(["Log Single Session", "Batch Upload"])
        with entry_tab:
            _manual_entry(project_id)
        with batch_tab:
            _batch_upload(project_id)
        st.markdown("---")

    records = db.get_listen_in_records(project_id)
    if not records:
        st.info("No listen-in sessions recorded yet.")
        return

    df = pd.DataFrame(records)
    _kpi_and_charts(df, project)
    _session_log(df, project_id)
