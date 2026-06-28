"""
Quality Report page — upload, column mapping, KPI cards, and visualisations.

Required upload columns (system standard):
  INSTANCE_ID, INTERVIEWER_ID, INTERVIEW_DATE,
  INTERVIEW_START_TIME, INTERVIEW_END_TIME, DURATION_MINUTES,
  DURATION_FLAG, STRAIGHT_LINING, LONG_PAUSE,
  REGION, LOCATION, SAMPLE_POINT_ID, APPROVAL_STATUS

Optional columns (auto-detected):
  GPS_STATUS, PHONE_PRESENT, AUDIO_PRESENT,
  DURATION_VALIDATION, QC_COMMENTS
"""

import io
import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime

import database as db
from config import (
    IPSOS_NAVY, IPSOS_TEAL, IPSOS_ORANGE, IPSOS_YELLOW,
    QUALITY_REQUIRED_COLS, QUALITY_OPTIONAL_COLS, IFIELD_COLUMN_MAP,
    UPLOAD_ROLES, CHART_COLORS,
)
from utils.charts import (
    kpi_card, donut_chart, bar_chart, stacked_bar, line_chart, gauge_chart
)
from utils.exports import to_excel_bytes, to_sav_bytes


# ── Template download ──────────────────────────────────────────────────────

def _make_template() -> bytes:
    """Return an Excel template with all required + optional columns."""
    all_cols = QUALITY_REQUIRED_COLS + QUALITY_OPTIONAL_COLS
    df = pd.DataFrame(columns=all_cols)
    # Add one example row
    df.loc[0] = {
        "INSTANCE_ID": "3782322",
        "INTERVIEWER_ID": "NB0664",
        "INTERVIEW_DATE": "2025-04-15",
        "INTERVIEW_START_TIME": "09:30:00",
        "INTERVIEW_END_TIME": "10:45:00",
        "DURATION_MINUTES": "75",
        "DURATION_FLAG": "Okay",
        "STRAIGHT_LINING": "0",
        "LONG_PAUSE": "0",
        "REGION": "Nairobi",
        "LOCATION": "Pangani",
        "SAMPLE_POINT_ID": "NB18",
        "APPROVAL_STATUS": "Approved",
        "GPS_STATUS": "Present",
        "PHONE_PRESENT": "Yes",
        "AUDIO_PRESENT": "Yes",
        "DURATION_VALIDATION": "01:15:00",
        "QC_COMMENTS": "",
    }
    return to_excel_bytes(df, "Quality Report Template")


# ── Column auto-mapping ────────────────────────────────────────────────────

def _auto_map(uploaded_cols: list[str]) -> dict:
    """Map uploaded column names to standard names using known aliases."""
    mapping = {}
    # Try exact match first, then iField aliases
    remaining = list(QUALITY_REQUIRED_COLS + QUALITY_OPTIONAL_COLS)
    for uc in uploaded_cols:
        if uc in remaining:
            mapping[uc] = uc
            remaining.remove(uc)
        elif uc in IFIELD_COLUMN_MAP and IFIELD_COLUMN_MAP[uc] in remaining:
            std = IFIELD_COLUMN_MAP[uc]
            mapping[uc] = std
            remaining.remove(std)
        elif uc.strip() in IFIELD_COLUMN_MAP and IFIELD_COLUMN_MAP[uc.strip()] in remaining:
            std = IFIELD_COLUMN_MAP[uc.strip()]
            mapping[uc] = std
            remaining.remove(std)
    return mapping


# ── Data cleaning ──────────────────────────────────────────────────────────

def _clean_df(df: pd.DataFrame) -> pd.DataFrame:
    # Normalise duration
    if "DURATION_MINUTES" in df.columns:
        df["DURATION_MINUTES"] = pd.to_numeric(df["DURATION_MINUTES"], errors="coerce")

    # Normalise date
    if "INTERVIEW_DATE" in df.columns:
        df["INTERVIEW_DATE"] = pd.to_datetime(df["INTERVIEW_DATE"], errors="coerce").dt.date.astype(str)

    # Binary flag normalisation — treat '0' or blank as no-flag
    for col in ["STRAIGHT_LINING", "LONG_PAUSE"]:
        if col in df.columns:
            df[f"{col}_FLAG"] = df[col].apply(
                lambda x: False if (pd.isna(x) or str(x).strip() in ("0", "")) else True
            )

    # Ensure text columns are str
    for col in ["INSTANCE_ID", "INTERVIEWER_ID", "REGION", "LOCATION",
                "SAMPLE_POINT_ID", "APPROVAL_STATUS", "DURATION_FLAG"]:
        if col in df.columns:
            df[col] = df[col].fillna("").astype(str).str.strip()

    return df


# ── Upload panel ───────────────────────────────────────────────────────────

def _upload_section(project_id: int):
    st.markdown("#### Upload Quality Report Data")

    col_a, col_b = st.columns([2, 1])
    with col_a:
        wave_label = st.text_input(
            "Wave / Period label",
            placeholder="e.g. Wave 1, April 2025, Q2 — used for wave comparison",
            key="qr_wave",
            help="Tag this upload with a wave/period label. Leave blank to add to the running total.",
        )
    with col_b:
        upload_mode = st.selectbox(
            "Upload mode",
            ["Append (skip duplicate Instance IDs)", "Replace wave data", "Save all (allow duplicates)"],
            key="qr_upload_mode",
            help=(
                "Append: new records only — skips rows whose Instance ID already exists in this project.\n"
                "Replace wave: deletes ALL previous data for this wave label, then inserts the new file.\n"
                "Save all: inserts every row regardless of duplicates."
            ),
        )

    tpl_col, up_col = st.columns([1, 2])
    with tpl_col:
        st.download_button(
            "Download Template (.xlsx)",
            data=_make_template(),
            file_name="quality_report_template.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
        )
        st.caption("Use this template or map your iField export columns below.")

    with up_col:
        uploaded = st.file_uploader(
            "Upload Excel file (.xlsx / .xls)",
            type=["xlsx", "xls"],
            key="qr_uploader",
        )

    if not uploaded:
        return

    # Read with header detection
    try:
        raw = pd.read_excel(uploaded, header=None)
    except Exception as e:
        st.error(f"Could not read file: {e}")
        return

    # Find header row — look for INSTANCE_ID or known iField col in first 5 rows
    header_row = 0
    for i in range(min(5, len(raw))):
        row_vals = [str(v).strip() for v in raw.iloc[i]]
        if any(v in IFIELD_COLUMN_MAP or v in QUALITY_REQUIRED_COLS for v in row_vals):
            header_row = i
            break

    df = pd.read_excel(uploaded, header=header_row)
    df.columns = [str(c).strip() for c in df.columns]
    df = df.dropna(how="all")

    # Auto-map
    mapping = _auto_map(list(df.columns))

    st.markdown("##### Column Mapping")
    st.caption("Review the auto-detected mapping. Adjust if needed. Unmapped required columns are shown in red.")

    all_std = QUALITY_REQUIRED_COLS + QUALITY_OPTIONAL_COLS
    unmapped_required = [c for c in QUALITY_REQUIRED_COLS if c not in mapping.values()]

    edited_mapping = {}
    options = ["— skip —"] + list(df.columns)
    n_cols = 3
    std_items = all_std
    rows = [std_items[i:i+n_cols] for i in range(0, len(std_items), n_cols)]

    for row_group in rows:
        cols = st.columns(n_cols)
        for col_widget, std_col in zip(cols, row_group):
            is_required = std_col in QUALITY_REQUIRED_COLS
            label_color = "🔴" if (is_required and std_col in unmapped_required) else ("🟢" if is_required else "⚪")
            current = next((uc for uc, sc in mapping.items() if sc == std_col), None)
            current_idx = options.index(current) if current and current in options else 0
            selected = col_widget.selectbox(
                f"{label_color} {std_col}",
                options,
                index=current_idx,
                key=f"map_{std_col}",
            )
            if selected != "— skip —":
                edited_mapping[selected] = std_col

    # Check required columns are satisfied
    mapped_std = set(edited_mapping.values())
    still_missing = [c for c in QUALITY_REQUIRED_COLS if c not in mapped_std]

    if still_missing:
        st.error(f"Missing required columns: {', '.join(still_missing)}")

    # ── Optional: project-specific extra columns ───────────────────────────
    all_mapped_src = set(edited_mapping.keys())
    unmapped_src = [c for c in df.columns if c not in all_mapped_src]

    selected_extra = []
    if unmapped_src:
        st.markdown("##### Additional Project-Specific Columns (Optional)")
        st.caption(
            "These columns were not mapped to standard fields. "
            "Select any you want to keep — they will be stored alongside the standard data."
        )
        cols_per_row = 4
        extra_rows = [unmapped_src[i:i+cols_per_row] for i in range(0, len(unmapped_src), cols_per_row)]
        for row_group in extra_rows:
            check_cols = st.columns(cols_per_row)
            for cc, col_name in zip(check_cols, row_group):
                if cc.checkbox(col_name, key=f"extra_{col_name}"):
                    selected_extra.append(col_name)

    n_rows = len(df)
    st.info(f"{n_rows} data rows detected. Preview:")
    preview_cols = list(edited_mapping.keys())[:10] + selected_extra[:5]
    preview_cols = [c for c in preview_cols if c in df.columns]
    st.dataframe(df[preview_cols].head(5) if preview_cols else df.head(5),
                 use_container_width=True)

    if st.button("Confirm & Save Data", disabled=bool(still_missing), type="primary",
                 key="qr_save"):
        # Apply standard mapping
        df = df.rename(columns=edited_mapping)
        df = _clean_df(df)

        # Keep standard columns
        std_keep = [c for c in (QUALITY_REQUIRED_COLS + QUALITY_OPTIONAL_COLS) if c in df.columns]
        std_df = df[std_keep].copy()

        for ec in selected_extra:
            if ec in df.columns:
                std_df[ec] = df[ec].values

        records = std_df.where(pd.notna(std_df), None).to_dict("records")
        std_keys_lower = {c: c.lower() for c in QUALITY_REQUIRED_COLS + QUALITY_OPTIONAL_COLS}
        normalised = []
        for r in records:
            norm = {}
            for k, v in r.items():
                norm[std_keys_lower.get(k, k)] = v
            normalised.append(norm)

        label = wave_label.strip() or None
        mode = upload_mode

        # Handle upload mode
        if mode == "Replace wave data":
            if not label:
                st.error("A Wave/Period label is required for 'Replace wave data' mode.")
                st.stop()
            db.delete_wave_records(project_id, label, "quality_report")
            st.info(f"Previous data for wave '{label}' deleted.")

        elif mode == "Append (skip duplicate Instance IDs)":
            existing_ids = db.get_quality_instance_ids(project_id)
            before = len(normalised)
            normalised = [r for r in normalised if r.get("instance_id") not in existing_ids]
            skipped = before - len(normalised)
            if skipped:
                st.info(f"Skipped {skipped} duplicate Instance ID(s) already in the database.")

        if not normalised:
            st.warning("No new records to save after deduplication.")
            st.stop()

        uid = db.insert_quality_records(
            project_id,
            st.session_state["user_id"],
            uploaded.name,
            normalised,
            wave_label=label,
        )
        extra_msg = f" + {len(selected_extra)} extra column(s)" if selected_extra else ""
        st.success(f"Saved {len(normalised)} records{extra_msg} (upload ID: {uid[:8]}…)")
        st.rerun()


# ── KPI cards ──────────────────────────────────────────────────────────────

def _kpi_row(df: pd.DataFrame, project: dict):
    total = len(df)
    approved = (df["approval_status"].str.lower() == "approved").sum() if "approval_status" in df.columns else 0
    pending = (df["approval_status"].str.lower() == "pending").sum() if "approval_status" in df.columns else 0
    cancelled = (df["approval_status"].str.lower() == "cancelled").sum() if "approval_status" in df.columns else 0
    flagged = (df["duration_flag"].str.lower() == "flag").sum() if "duration_flag" in df.columns else 0
    sl_flag = df.get("straight_lining_flag", pd.Series(dtype=bool)).sum()
    lp_flag = df.get("long_pause_flag", pd.Series(dtype=bool)).sum()
    error_rate = round(flagged / total * 100, 1) if total else 0

    target = project.get("sample_target") or 0
    completion_pct = round(approved / target * 100, 1) if target else 0

    avg_dur = df["duration_minutes"].mean() if "duration_minutes" in df.columns else 0
    max_dur = df["duration_minutes"].max() if "duration_minutes" in df.columns else 0
    min_dur = df["duration_minutes"].min() if "duration_minutes" in df.columns else 0

    st.markdown("#### Summary")
    c1, c2, c3, c4, c5 = st.columns(5)
    cards = [
        (c1, "Total Submitted", total, "", IPSOS_NAVY),
        (c2, "Approved", approved, "", IPSOS_TEAL),
        (c3, "Pending", pending, "", IPSOS_YELLOW),
        (c4, "Cancelled", cancelled, "", IPSOS_ORANGE),
        (c5, "Flagged (Duration)", flagged, "", IPSOS_ORANGE),
    ]
    for col, label, val, suf, color in cards:
        col.markdown(kpi_card(label, val, suffix=suf, color=color), unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)
    d1, d2, d3, d4, d5 = st.columns(5)
    d1.markdown(kpi_card("Completion", completion_pct, suffix="%", color=IPSOS_TEAL), unsafe_allow_html=True)
    d2.markdown(kpi_card("Avg Duration (min)", f"{avg_dur:.1f}", color=IPSOS_NAVY), unsafe_allow_html=True)
    d3.markdown(kpi_card("Max Duration (min)", f"{max_dur:.0f}" if max_dur else "—", color=IPSOS_NAVY), unsafe_allow_html=True)
    d4.markdown(kpi_card("Min Duration (min)", f"{min_dur:.0f}" if min_dur else "—", color=IPSOS_NAVY), unsafe_allow_html=True)
    d5.markdown(kpi_card("Error Rate", error_rate, suffix="%", color=IPSOS_ORANGE), unsafe_allow_html=True)


# ── Back-checks & Accompaniments detail block ──────────────────────────────

def _bc_acc_block(df: pd.DataFrame, project: dict):
    """Show a summary block of back-check and accompaniment progress against targets."""
    approved = (df["approval_status"].str.lower() == "approved").sum() if "approval_status" in df.columns else 0
    if not approved:
        return

    bc_records = db.get_backcheck_records(project["id"])
    perf_records = db.get_performance_records(project["id"])

    bc_done = len(bc_records)
    bc_target_pct = (project.get("backcheck_target") or 0.20)
    bc_target_n = round(approved * bc_target_pct)
    bc_rate = round(bc_done / approved * 100, 1)

    acc_n = sum(r.get("accompaniments", 0) or 0 for r in perf_records)
    acc_target_pct = (project.get("accompaniment_target") or 0.20)
    acc_target_n = round(approved * acc_target_pct)
    acc_rate = round(acc_n / approved * 100, 1) if approved else 0

    tel_bc = sum(r.get("backcheck_telephone_created", 0) or 0 for r in perf_records)
    f2f_bc = sum(r.get("backcheck_f2f_created", 0) or 0 for r in perf_records)
    f2f_infield = sum(r.get("backcheck_f2f_infield", 0) or 0 for r in perf_records)

    bc_icon = "✅" if bc_rate >= bc_target_pct * 100 else "⚠️"
    acc_icon = "✅" if acc_rate >= acc_target_pct * 100 else "⚠️"

    st.markdown("---")
    st.markdown(
        f'<h4 style="color:{IPSOS_NAVY};">Back-checks & Accompaniments</h4>',
        unsafe_allow_html=True,
    )
    c1, c2 = st.columns(2)
    with c1:
        rows_html = f"""
        <table style="width:100%; font-size:0.88rem; border-collapse:collapse;">
        <tr><td style="padding:4px 0; color:#666;">Back-checks Completed</td>
            <td style="font-weight:600;">{bc_done:,} / {approved:,}
                ({bc_rate}%) &nbsp; Target: {bc_target_pct*100:.0f}% &nbsp; {bc_icon}</td></tr>
        <tr><td style="padding:4px 0; color:#666;">Accompaniments</td>
            <td style="font-weight:600;">{acc_n:,} / {approved:,}
                ({acc_rate}%) &nbsp; Target: {acc_target_pct*100:.0f}% &nbsp; {acc_icon}</td></tr>
        </table>"""
        st.markdown(rows_html, unsafe_allow_html=True)
    with c2:
        if tel_bc or f2f_bc or f2f_infield:
            detail_html = f"""
            <table style="width:100%; font-size:0.88rem; border-collapse:collapse;">
            <tr><td style="padding:4px 0; color:#666;">Telephone Back-checks Created</td>
                <td style="font-weight:600;">{tel_bc:,}</td></tr>
            <tr><td style="padding:4px 0; color:#666;">F2F Back-checks Created</td>
                <td style="font-weight:600;">{f2f_bc:,}</td></tr>
            <tr><td style="padding:4px 0; color:#666;">F2F In-field</td>
                <td style="font-weight:600;">{f2f_infield:,}</td></tr>
            </table>"""
            st.markdown(detail_html, unsafe_allow_html=True)
        else:
            st.caption("Upload Performance Report to see back-check type breakdown.")


# ── Charts ─────────────────────────────────────────────────────────────────

def _charts_section(df: pd.DataFrame, project: dict):
    st.markdown("---")
    st.markdown("#### Quality Control Charts")

    # Filters
    f1, f2, f3 = st.columns(3)
    interviewers = ["All"] + sorted(df["interviewer_id"].dropna().unique().tolist()) if "interviewer_id" in df.columns else ["All"]
    regions = ["All"] + sorted(df["region"].dropna().unique().tolist()) if "region" in df.columns else ["All"]
    statuses = ["All"] + sorted(df["approval_status"].dropna().unique().tolist()) if "approval_status" in df.columns else ["All"]

    sel_int = f1.selectbox("Interviewer", interviewers, key="qr_int")
    sel_reg = f2.selectbox("Region", regions, key="qr_reg")
    sel_sta = f3.selectbox("Status", statuses, key="qr_sta")

    fdf = df.copy()
    if sel_int != "All" and "interviewer_id" in fdf.columns:
        fdf = fdf[fdf["interviewer_id"] == sel_int]
    if sel_reg != "All" and "region" in fdf.columns:
        fdf = fdf[fdf["region"] == sel_reg]
    if sel_sta != "All" and "approval_status" in fdf.columns:
        fdf = fdf[fdf["approval_status"] == sel_sta]

    if fdf.empty:
        st.warning("No data for selected filters.")
        return

    # Row 1: Approval donut | Error type bar
    c1, c2 = st.columns(2)
    with c1:
        if "approval_status" in fdf.columns:
            status_counts = fdf["approval_status"].value_counts()
            fig = donut_chart(status_counts.values, status_counts.index,
                              "Approval Status Breakdown",
                              colors=["#00B5AD", "#D4E157", "#FF7043"])
            st.plotly_chart(fig, use_container_width=True, key="qr_approval_status")

    with c2:
        error_types = {}
        if "duration_flag" in fdf.columns:
            error_types["Duration Flag"] = (fdf["duration_flag"].str.lower() == "flag").sum()
        if "straight_lining_flag" in fdf.columns:
            error_types["Straight-lining"] = fdf["straight_lining_flag"].sum()
        if "long_pause_flag" in fdf.columns:
            error_types["Long Pause"] = fdf["long_pause_flag"].sum()
        if "gps_status" in fdf.columns:
            error_types["GPS Issue"] = (fdf["gps_status"].str.lower().isin(["missing", "duplicate"])).sum()
        if "phone_present" in fdf.columns:
            error_types["Missing Phone"] = (fdf["phone_present"].str.lower() == "no").sum()
        if "audio_present" in fdf.columns:
            error_types["Missing Audio"] = (fdf["audio_present"].str.lower() == "no").sum()

        if error_types:
            et_df = pd.DataFrame({"Error Type": list(error_types.keys()), "Count": list(error_types.values())})
            et_df = et_df[et_df["Count"] > 0].sort_values("Count", ascending=False)
            if not et_df.empty:
                fig = donut_chart(et_df["Count"], et_df["Error Type"], "Error Type Breakdown")
                st.plotly_chart(fig, use_container_width=True, key="qr_error_types")
            else:
                st.success("No quality errors detected in current selection.")

    # Row 2: Error distribution by interviewer
    if "interviewer_id" in fdf.columns:
        st.markdown("##### Error Distribution by Interviewer")
        err_rows = []
        for iid, grp in fdf.groupby("interviewer_id"):
            for etype, col, cond in [
                ("Duration Flag", "duration_flag", lambda s: s.str.lower() == "flag"),
                ("Straight-lining", "straight_lining_flag", lambda s: s),
                ("Long Pause", "long_pause_flag", lambda s: s),
            ]:
                if col in grp.columns:
                    try:
                        cnt = cond(grp[col]).sum()
                        if cnt:
                            err_rows.append({"Interviewer": iid, "Error Type": etype, "Count": int(cnt)})
                    except Exception:
                        pass

        if err_rows:
            err_df = pd.DataFrame(err_rows)
            fig = stacked_bar(err_df, x="Interviewer", y="Count", color="Error Type",
                              title="Errors by Interviewer")
            st.plotly_chart(fig, use_container_width=True, key="qr_errors_by_interviewer")

    # Row 3: Productivity trend (interviews per day) — enhanced
    if "interview_date" in fdf.columns and "interviewer_id" in fdf.columns:
        st.markdown("##### Productivity per Date per Interviewer")
        prod_df = fdf.copy()
        prod_df["interview_date"] = pd.to_datetime(prod_df["interview_date"], errors="coerce")
        prod_df = prod_df.dropna(subset=["interview_date"])

        if not prod_df.empty:
            # Date range filter for this chart
            pf1, pf2, pf3 = st.columns([2, 2, 2])
            date_min = prod_df["interview_date"].min().date()
            date_max = prod_df["interview_date"].max().date()
            with pf1:
                p_from = st.date_input("From date", value=date_min, key="prod_from",
                                       min_value=date_min, max_value=date_max)
            with pf2:
                p_to = st.date_input("To date", value=date_max, key="prod_to",
                                     min_value=date_min, max_value=date_max)
            with pf3:
                prod_view = st.radio("View", ["Daily", "Cumulative"], horizontal=True, key="prod_view")

            prod_filt = prod_df[
                (prod_df["interview_date"].dt.date >= p_from) &
                (prod_df["interview_date"].dt.date <= p_to)
            ]

            daily_prod = (
                prod_filt.groupby(["interview_date", "interviewer_id"])
                .size()
                .reset_index(name="Interviews")
            )

            if not daily_prod.empty:
                if prod_view == "Cumulative":
                    daily_prod = daily_prod.sort_values(["interviewer_id", "interview_date"])
                    daily_prod["Interviews"] = daily_prod.groupby("interviewer_id")["Interviews"].cumsum()
                    chart_title = "Cumulative Interviews per Interviewer"
                else:
                    chart_title = "Interviews per Day per Interviewer"

                fig = line_chart(daily_prod, x="interview_date", y="Interviews",
                                 color="interviewer_id", title=chart_title)
                st.plotly_chart(fig, use_container_width=True, key="qr_productivity")

                # Grouped bar: interviews per interviewer per date
                st.markdown("###### Daily Interviews by Interviewer")
                import plotly.express as px
                fig_bar = px.bar(
                    daily_prod,
                    x="interview_date", y="Interviews",
                    color="interviewer_id",
                    barmode="group",
                    title="Interviews per Day — Grouped by Interviewer",
                    labels={"interview_date": "Date", "Interviews": "Interviews", "interviewer_id": "Interviewer"},
                    color_discrete_sequence=CHART_COLORS,
                )
                fig_bar.update_layout(
                    paper_bgcolor="white", plot_bgcolor="#F5F5F5",
                    margin=dict(l=20, r=20, t=40, b=60),
                    legend=dict(orientation="h", y=-0.2),
                )
                st.plotly_chart(fig_bar, use_container_width=True, key="qr_prod_bar")

    # Row 4: Duration per interviewer
    if "duration_minutes" in fdf.columns and "interviewer_id" in fdf.columns:
        st.markdown("##### Average Interview Duration by Interviewer")
        dur_df = (
            fdf.groupby("interviewer_id")["duration_minutes"]
            .agg(["mean", "min", "max"])
            .reset_index()
        )
        dur_df.columns = ["Interviewer", "Avg Duration", "Min Duration", "Max Duration"]
        dur_df = dur_df.round(1)
        import plotly.express as px
        fig = px.bar(dur_df, x="Interviewer", y="Avg Duration",
                     error_y=dur_df["Max Duration"] - dur_df["Avg Duration"],
                     title="Avg Duration per Interviewer (min)",
                     color_discrete_sequence=["#00B5AD"])
        fig.update_layout(paper_bgcolor="white", plot_bgcolor="#F5F5F5",
                          margin=dict(l=20, r=20, t=40, b=80))
        st.plotly_chart(fig, use_container_width=True, key="qr_duration_by_interviewer")

    # Row 5: Duration by region
    if "duration_minutes" in fdf.columns and "region" in fdf.columns:
        c1, c2 = st.columns(2)
        with c1:
            reg_dur = (
                fdf.groupby("region")["duration_minutes"]
                .mean().reset_index()
            )
            reg_dur.columns = ["Region", "Avg Duration (min)"]
            fig = bar_chart(reg_dur, x="Region", y="Avg Duration (min)",
                            title="Avg Duration by Region")
            st.plotly_chart(fig, use_container_width=True, key="qr_duration_by_region")
        with c2:
            if "approval_status" in fdf.columns:
                reg_status = (
                    fdf.groupby(["region", "approval_status"])
                    .size().reset_index(name="Count")
                )
                fig = stacked_bar(reg_status, x="region", y="Count",
                                  color="approval_status",
                                  title="Approval Status by Region")
                st.plotly_chart(fig, use_container_width=True, key="qr_status_by_region")


# ── Interviewer accountability ─────────────────────────────────────────────

def _interviewer_accountability(df: pd.DataFrame, project: dict):
    """Per-interviewer flag rate table and region summary — supervisor accountability view."""
    if "interviewer_id" not in df.columns:
        return

    st.markdown("---")
    st.markdown(
        f'<h4 style="color:{IPSOS_NAVY};">Interviewer Accountability</h4>',
        unsafe_allow_html=True,
    )

    warn_thresh = float((project or {}).get("flag_warning_pct") or 5.0)
    crit_thresh = float((project or {}).get("flag_critical_pct") or 10.0)

    grp = df.groupby("interviewer_id", as_index=False).agg(
        total=("interviewer_id", "count"),
        approved=("approval_status", lambda x: (x.str.lower() == "approved").sum()
                  if "approval_status" in df.columns else 0),
        duration_flags=("duration_flag", lambda x: (x.str.lower() == "flag").sum()
                        if "duration_flag" in df.columns else 0),
    )

    if "straight_lining_flag" in df.columns:
        sl = df.groupby("interviewer_id")["straight_lining_flag"].sum().reset_index()
        sl.columns = ["interviewer_id", "sl_flags"]
        grp = grp.merge(sl, on="interviewer_id", how="left")
        grp["sl_flags"] = grp["sl_flags"].fillna(0).astype(int)
    else:
        grp["sl_flags"] = 0

    if "duration_minutes" in df.columns:
        avg_dur = df.groupby("interviewer_id")["duration_minutes"].mean().round(1).reset_index()
        avg_dur.columns = ["interviewer_id", "avg_duration"]
        grp = grp.merge(avg_dur, on="interviewer_id", how="left")
    else:
        grp["avg_duration"] = None

    if "region" in df.columns:
        region_map = (
            df.groupby("interviewer_id")["region"]
            .agg(lambda x: x.mode().iloc[0] if len(x) > 0 else "")
            .reset_index()
        )
        region_map.columns = ["interviewer_id", "region"]
        grp = grp.merge(region_map, on="interviewer_id", how="left")
    else:
        grp["region"] = "—"

    grp["total_flags"] = grp["duration_flags"] + grp["sl_flags"]
    grp["flag_rate_%"] = (grp["total_flags"] / grp["total"].clip(lower=1) * 100).round(1)
    grp = grp.sort_values("flag_rate_%", ascending=False).reset_index(drop=True)

    t1, t2 = st.tabs(["Interviewer Flag Rates", "Region Summary"])

    with t1:
        hdr_cols = ["Interviewer", "Region", "Interviews", "Approved", "Dur. Flags", "SL Flags", "Total Flags", "Flag Rate %", "Avg Duration (min)"]
        header_html = "".join(
            f'<th style="padding:6px 10px;text-align:left;font-size:0.73rem;'
            f'color:#fff;background:{IPSOS_NAVY};border-right:1px solid rgba(255,255,255,0.15);">'
            f'{h}</th>'
            for h in hdr_cols
        )
        rows_html = ""
        for _, row in grp.iterrows():
            rate = row["flag_rate_%"]
            if rate >= crit_thresh:
                bg, rate_color = "#fff0ef", "#c62828"
            elif rate >= warn_thresh:
                bg, rate_color = "#fffde7", "#e65100"
            else:
                bg, rate_color = "#f5faf5", "#2e7d32"
            avg_d = f"{row['avg_duration']:.1f}" if row.get("avg_duration") is not None and not pd.isna(row.get("avg_duration", float("nan"))) else "—"
            rows_html += (
                f'<tr style="background:{bg};border-bottom:1px solid #e8e8e8;">'
                f'<td style="padding:5px 10px;font-size:0.8rem;font-weight:600;">{row["interviewer_id"]}</td>'
                f'<td style="padding:5px 10px;font-size:0.78rem;color:#666;">{row.get("region","—")}</td>'
                f'<td style="padding:5px 10px;font-size:0.8rem;">{int(row["total"]):,}</td>'
                f'<td style="padding:5px 10px;font-size:0.8rem;">{int(row.get("approved",0)):,}</td>'
                f'<td style="padding:5px 10px;font-size:0.8rem;">{int(row["duration_flags"])}</td>'
                f'<td style="padding:5px 10px;font-size:0.8rem;">{int(row["sl_flags"])}</td>'
                f'<td style="padding:5px 10px;font-size:0.8rem;font-weight:600;">{int(row["total_flags"])}</td>'
                f'<td style="padding:5px 10px;font-size:0.85rem;font-weight:700;color:{rate_color};">{rate}%</td>'
                f'<td style="padding:5px 10px;font-size:0.8rem;color:#666;">{avg_d}</td>'
                f'</tr>'
            )
        st.markdown(
            f'<table style="width:100%;border-collapse:collapse;font-family:Arial,sans-serif;">'
            f'<thead><tr>{header_html}</tr></thead>'
            f'<tbody>{rows_html}</tbody>'
            f'</table>',
            unsafe_allow_html=True,
        )
        st.caption(
            f"Traffic-light: red = flag rate ≥ {crit_thresh}% (critical threshold), "
            f"amber = ≥ {warn_thresh}% (warning threshold), green = below warning."
        )

    with t2:
        if "region" not in df.columns:
            st.info("No region data in this dataset.")
            return

        reg = df.groupby("region", as_index=False).agg(
            total=("region", "count"),
            approved=("approval_status", lambda x: (x.str.lower() == "approved").sum()
                      if "approval_status" in df.columns else 0),
            duration_flags=("duration_flag", lambda x: (x.str.lower() == "flag").sum()
                            if "duration_flag" in df.columns else 0),
            n_interviewers=("interviewer_id", "nunique"),
        )
        if "straight_lining_flag" in df.columns:
            sl_reg = df.groupby("region")["straight_lining_flag"].sum().reset_index()
            sl_reg.columns = ["region", "sl_flags"]
            reg = reg.merge(sl_reg, on="region", how="left")
            reg["sl_flags"] = reg["sl_flags"].fillna(0).astype(int)
        else:
            reg["sl_flags"] = 0

        reg["total_flags"] = reg["duration_flags"] + reg["sl_flags"]
        reg["flag_rate_%"] = (reg["total_flags"] / reg["total"].clip(lower=1) * 100).round(1)
        reg = reg.sort_values("flag_rate_%", ascending=False)

        import plotly.express as px
        max_rate = max(reg["flag_rate_%"].max(), crit_thresh + 1)
        fig = px.bar(
            reg, x="region", y="flag_rate_%",
            color="flag_rate_%",
            color_continuous_scale=["#2e7d32", "#f9a825", "#c62828"],
            range_color=[0, max_rate],
            title="QC Flag Rate by Region",
            labels={"flag_rate_%": "Flag Rate (%)", "region": "Region"},
            height=300,
            text="flag_rate_%",
        )
        fig.add_hline(y=crit_thresh, line_dash="dash", line_color="#c62828",
                      annotation_text=f"Critical {crit_thresh}%", annotation_position="top right")
        fig.add_hline(y=warn_thresh, line_dash="dot", line_color="#e65100",
                      annotation_text=f"Warning {warn_thresh}%", annotation_position="top right")
        fig.update_traces(texttemplate="%{text}%", textposition="outside")
        fig.update_layout(
            paper_bgcolor="white", plot_bgcolor="#f9fafb",
            font=dict(family="Arial, sans-serif"),
            margin=dict(l=20, r=20, t=50, b=60),
            coloraxis_showscale=False,
        )
        st.plotly_chart(fig, use_container_width=True, key="qr_region_flag_rate")

        st.dataframe(
            reg.rename(columns={
                "region": "Region", "total": "Interviews", "approved": "Approved",
                "n_interviewers": "Interviewers", "duration_flags": "Duration Flags",
                "sl_flags": "SL Flags", "total_flags": "Total Flags", "flag_rate_%": "Flag Rate %",
            }).set_index("Region"),
            use_container_width=True,
        )


# ── Data table ─────────────────────────────────────────────────────────────

def _data_table(df: pd.DataFrame):
    st.markdown("---")
    st.markdown("#### Raw Data")

    std_display = [c for c in [
        "instance_id", "interviewer_id", "interview_date",
        "start_time", "end_time", "duration_minutes", "duration_flag",
        "straight_lining", "long_pause", "gps_status",
        "region", "location", "sample_point_id", "approval_status",
    ] if c in df.columns]

    # Expand extra_data JSON into columns for display
    disp_df = df[std_display].copy()
    if "extra_data" in df.columns:
        import json
        extra_rows = []
        for val in df["extra_data"]:
            try:
                extra_rows.append(json.loads(val) if val else {})
            except Exception:
                extra_rows.append({})
        extra_df = pd.DataFrame(extra_rows, index=df.index)
        if not extra_df.empty and extra_df.columns.tolist():
            disp_df = pd.concat([disp_df, extra_df], axis=1)

    st.dataframe(disp_df, use_container_width=True, height=300)

    c1, c2 = st.columns(2)
    xls = to_excel_bytes(disp_df, "Quality Report")
    c1.download_button("Export to Excel", data=xls, file_name="quality_report.xlsx",
                       mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                       use_container_width=True)
    try:
        sav = to_sav_bytes(disp_df)
        c2.download_button("Export to SAV (SPSS)", data=sav, file_name="quality_report.sav",
                           mime="application/octet-stream", use_container_width=True)
    except Exception as e:
        c2.caption(f"SAV export error: {e}")


# ── Quality Queries & Mitigation ──────────────────────────────────────────

def _quality_queries_section(df: pd.DataFrame, project: dict = None):
    st.markdown("---")
    c_left, c_right = st.columns(2)

    # Calibration thresholds
    loi_pct = float((project or {}).get("loi_pct_threshold") or 0.50)
    loi_min = float((project or {}).get("loi_min_minutes") or 0)

    with c_left:
        st.markdown(
            f'<h4 style="color:{IPSOS_NAVY};">Quality Queries</h4>',
            unsafe_allow_html=True,
        )
        st.caption(
            "As a standard procedure, all submitted interviews were subjected to "
            "validation on key metrics. Queries were shared with the field coordinator "
            "for review and feedback."
        )

        issues = []
        total = len(df)

        if "straight_lining_flag" in df.columns:
            n = int(df["straight_lining_flag"].sum())
            if n:
                issues.append(f"Self-administration / straight-lining detected ({n} records, {round(n/total*100,1)}%)")
        if "long_pause" in df.columns:
            n = int((df["long_pause"].apply(lambda x: str(x).strip() not in ("0", "", "None"))).sum())
            if n:
                issues.append(f"Long pauses detected during interview ({n} records)")
        if "gps_status" in df.columns:
            dup = int((df["gps_status"].str.lower() == "duplicate").sum())
            miss = int((df["gps_status"].str.lower() == "missing").sum())
            if dup or miss:
                issues.append(f"Duplicate or missing GPS co-ordinates ({dup + miss} records: {dup} duplicate, {miss} missing)")
        if "phone_present" in df.columns:
            n = int((df["phone_present"].str.lower() == "no").sum())
            if n:
                issues.append(f"Missing telephone numbers ({n} records)")
        if "audio_present" in df.columns:
            n = int((df["audio_present"].str.lower() == "no").sum())
            if n:
                issues.append(f"Missing audio recordings ({n} records)")

        # LOI flagging — project-calibrated
        if "duration_flag" in df.columns:
            n_ifield = int((df["duration_flag"].str.lower() == "flag").sum())
            if n_ifield:
                issues.append(f"Short LOI flagged by iField ({n_ifield} records)")

        if "duration_minutes" in df.columns:
            avg_dur = df["duration_minutes"].mean()
            # Calibrated threshold: max(absolute min, pct of avg)
            threshold = max(loi_min, avg_dur * loi_pct) if avg_dur else loi_min
            if threshold > 0:
                n_short = int((df["duration_minutes"] < threshold).sum())
                if n_short:
                    issues.append(
                        f"Short LOI by project threshold (< {threshold:.1f} min = "
                        f"{int(loi_pct*100)}% of avg {avg_dur:.1f} min): {n_short} records"
                    )

        if "approval_status" in df.columns:
            n = int((df["approval_status"].str.lower() == "cancelled").sum())
            if n:
                issues.append(f"Cancelled / invalid interviews ({n} records)")

        if issues:
            for issue in issues:
                st.markdown(f"- ⚠️ {issue}")
        else:
            st.success("No quality queries flagged for this dataset.")

    with c_right:
        st.markdown(
            f'<h4 style="color:{IPSOS_NAVY};">Mitigation Measures</h4>',
            unsafe_allow_html=True,
        )
        mitigations = [
            "Held debrief sessions and checked improvements with field team.",
            "Listened in to audio-recorded interviews to verify conduct.",
            "Interviewers with major issues were accompanied by the QC team.",
            "Telephonic back-checks were done to affirm interviews were conducted.",
            "Queries shared with field coordinator for review and feedback.",
        ]
        for m in mitigations:
            st.markdown(f"- {m}")


# ── Upload history ─────────────────────────────────────────────────────────

def _upload_history(project_id: int):
    logs = db.get_upload_log(project_id)
    logs = [l for l in logs if l["report_type"] == "quality_report"]
    if not logs:
        return
    st.markdown("##### Upload History")
    for log in logs:
        c1, c2, c3 = st.columns([3, 2, 1])
        c1.write(f"📂 {log['filename']} — {log['row_count']} rows")
        c2.caption(f"Uploaded by {log.get('uploader_name', '?')} on {log['upload_date'][:16]}")
        if st.session_state["user_role"] in ("qc_executive", "operations_manager"):
            if c3.button("Delete", key=f"del_qr_{log['upload_id']}", type="secondary"):
                db.delete_upload(log["upload_id"], "quality_report")
                st.rerun()


# ── Main entry point ───────────────────────────────────────────────────────

def show(project_id: int):
    project = db.get_project(project_id)
    if not project:
        st.error("Project not found.")
        return

    st.markdown(
        f'<h3 style="color:{IPSOS_NAVY};">Quality Report — {project["name"]}</h3>',
        unsafe_allow_html=True,
    )

    role = st.session_state["user_role"]
    can_upload = role in UPLOAD_ROLES

    records = db.get_quality_records(project_id)

    if can_upload:
        with st.expander("Upload New Data", expanded=True):
            _upload_section(project_id)
        _upload_history(project_id)
        st.markdown("---")

    if not records:
        st.info("No Quality Report data yet. Upload an Excel file above.")
        return

    df = pd.DataFrame(records)

    # Derive flag columns if not already present
    for col in ["straight_lining", "long_pause"]:
        flag_col = f"{col}_flag"
        if col in df.columns and flag_col not in df.columns:
            df[flag_col] = df[col].apply(
                lambda x: False if (pd.isna(x) or str(x).strip() in ("0", "", "None")) else True
            )

    _kpi_row(df, project)
    _bc_acc_block(df, project)
    _charts_section(df, project)
    _interviewer_accountability(df, project)
    _data_table(df)
    _quality_queries_section(df, project)
