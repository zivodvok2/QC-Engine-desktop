import io
from datetime import datetime
import pandas as pd


def to_excel_bytes(df: pd.DataFrame, sheet_name="Data") -> bytes:
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="xlsxwriter") as writer:
        df.to_excel(writer, sheet_name=sheet_name, index=False)
        workbook = writer.book
        worksheet = writer.sheets[sheet_name]
        header_fmt = workbook.add_format({
            "bold": True, "font_color": "white",
            "bg_color": "#1F2B6C", "border": 1,
        })
        for col_num, value in enumerate(df.columns.values):
            worksheet.write(0, col_num, value, header_fmt)
            worksheet.set_column(col_num, col_num, max(len(str(value)) + 4, 14))
    return buf.getvalue()


def to_sav_bytes(df: pd.DataFrame) -> bytes:
    try:
        import pyreadstat
        import tempfile, os
        with tempfile.NamedTemporaryFile(suffix=".sav", delete=False) as f:
            tmppath = f.name
        pyreadstat.write_sav(df, tmppath)
        with open(tmppath, "rb") as f:
            data = f.read()
        os.unlink(tmppath)
        return data
    except Exception as e:
        raise RuntimeError(f"SAV export failed: {e}")


def _apply_header_fmt(writer, sheet_name: str, df: pd.DataFrame, header_fmt):
    ws = writer.sheets[sheet_name]
    for col_num, value in enumerate(df.columns.values):
        ws.write(0, col_num, value, header_fmt)
        ws.set_column(col_num, col_num, max(len(str(value)) + 4, 15))


def generate_project_report(project_id: int) -> bytes:
    """
    Generate a comprehensive multi-sheet Excel report for a project,
    formatted in the Ipsos QC style.
    """
    import database as db
    from config import BACKCHECK_ERRORS

    project = db.get_project(project_id)
    if not project:
        raise ValueError("Project not found")

    qr_records = db.get_quality_records(project_id)
    bc_records = db.get_backcheck_records(project_id)
    perf_records = db.get_performance_records(project_id)
    timing_records = db.get_timing_records(project_id)
    cancelled_records = db.get_cancelled_records(project_id)
    listen_records = db.get_listen_in_records(project_id)
    wave_data = db.get_wave_comparison_data(project_id)
    upload_log = db.get_upload_log(project_id)

    qr_df = pd.DataFrame(qr_records) if qr_records else pd.DataFrame()
    bc_df = pd.DataFrame(bc_records) if bc_records else pd.DataFrame()
    perf_df = pd.DataFrame(perf_records) if perf_records else pd.DataFrame()
    timing_df = pd.DataFrame(timing_records) if timing_records else pd.DataFrame()
    cancelled_df = pd.DataFrame(cancelled_records) if cancelled_records else pd.DataFrame()
    listen_df = pd.DataFrame(listen_records) if listen_records else pd.DataFrame()

    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="xlsxwriter") as writer:
        wb = writer.book

        # ── Shared formats ────────────────────────────────────────────────
        navy_hdr = wb.add_format({
            "bold": True, "font_color": "white", "bg_color": "#1F2B6C",
            "border": 1, "align": "center", "valign": "vcenter",
        })
        teal_hdr = wb.add_format({
            "bold": True, "font_color": "white", "bg_color": "#00B5AD",
            "border": 1, "align": "center", "valign": "vcenter",
        })
        orange_hdr = wb.add_format({
            "bold": True, "font_color": "white", "bg_color": "#FF7043",
            "border": 1, "align": "center", "valign": "vcenter",
        })
        title_fmt = wb.add_format({
            "bold": True, "font_size": 16, "font_color": "#1F2B6C",
            "align": "center", "valign": "vcenter",
        })
        section_fmt = wb.add_format({
            "bold": True, "font_size": 11, "font_color": "white",
            "bg_color": "#1F2B6C", "border": 1,
        })
        label_fmt = wb.add_format({"bold": True, "font_color": "#1F2B6C"})
        value_fmt = wb.add_format({"font_color": "#333333"})
        good_fmt = wb.add_format({"font_color": "#2E7D32", "bold": True})
        warn_fmt = wb.add_format({"font_color": "#E65100", "bold": True})
        pct_label_fmt = wb.add_format({"bold": True, "font_color": "#1F2B6C", "num_format": "0.0%"})

        # ── Compute summary metrics ───────────────────────────────────────
        if not qr_df.empty and "approval_status" in qr_df.columns:
            approved = int((qr_df["approval_status"].str.lower() == "approved").sum())
            total_submitted = len(qr_df)
            cancelled_qr = int((qr_df["approval_status"].str.lower() == "cancelled").sum())
            pending_qr = int((qr_df["approval_status"].str.lower() == "pending").sum())
            flagged = int((qr_df.get("duration_flag", pd.Series(dtype=str)).str.lower() == "flag").sum())
            sl_flagged = int(qr_df.get("straight_lining", pd.Series(dtype=str)).apply(
                lambda x: str(x).strip() not in ("0", "", "None", "nan")).sum())
            lp_flagged = int(qr_df.get("long_pause", pd.Series(dtype=str)).apply(
                lambda x: str(x).strip() not in ("0", "", "None", "nan")).sum())
            gps_issue = int((qr_df.get("gps_status", pd.Series(dtype=str)).str.lower().isin(["missing", "duplicate"])).sum())
            phone_miss = int((qr_df.get("phone_present", pd.Series(dtype=str)).str.lower() == "no").sum())
            audio_miss = int((qr_df.get("audio_present", pd.Series(dtype=str)).str.lower() == "no").sum())
            avg_dur = float(qr_df["duration_minutes"].mean()) if "duration_minutes" in qr_df.columns else 0.0
            max_dur = float(qr_df["duration_minutes"].max()) if "duration_minutes" in qr_df.columns else 0.0
            min_dur = float(qr_df["duration_minutes"].min()) if "duration_minutes" in qr_df.columns else 0.0
        else:
            approved = total_submitted = cancelled_qr = pending_qr = flagged = 0
            sl_flagged = lp_flagged = gps_issue = phone_miss = audio_miss = 0
            avg_dur = max_dur = min_dur = 0.0

        target = int(project.get("sample_target") or 0)
        completion_pct = round(approved / target * 100, 1) if target else 0.0
        error_rate = round(flagged / total_submitted * 100, 1) if total_submitted else 0.0

        bc_count = len(bc_df)
        bc_rate = round(bc_count / approved * 100, 1) if approved else 0.0
        bc_target_pct = round((project.get("backcheck_target") or 0.20) * 100, 1)

        li_count = len(listen_df)
        li_rate = round(li_count / approved * 100, 1) if approved else 0.0
        li_target_pct = round((project.get("listenin_target") or 0.10) * 100, 1)

        acc_n = int(sum(r.get("accompaniments", 0) or 0 for r in perf_records))
        completes_n = int(sum(r.get("interview_completes", 0) or 0 for r in perf_records))
        acc_rate = round(acc_n / completes_n * 100, 1) if completes_n else 0.0
        acc_target_pct = round((project.get("accompaniment_target") or 0.20) * 100, 1)

        # ── SUMMARY sheet ─────────────────────────────────────────────────
        ws = wb.add_worksheet("SUMMARY")
        ws.set_column("A:A", 3)
        ws.set_column("B:B", 32)
        ws.set_column("C:C", 22)
        ws.set_column("D:D", 18)
        ws.set_column("E:E", 18)
        ws.set_column("F:F", 18)
        ws.set_row(1, 30)

        ws.merge_range("B2:F2", "IPSOS KENYA — QC DASHBOARD REPORT", title_fmt)
        ws.merge_range("B3:F3", f"Generated: {datetime.now().strftime('%d %B %Y, %H:%M')}", value_fmt)

        r = 4
        ws.merge_range(r, 1, r, 5, "PROJECT INFORMATION", section_fmt)
        r += 1
        info = [
            ("Project Name", project.get("name", "")),
            ("Job Number", project.get("job_number") or "—"),
            ("Client / Study", project.get("client") or "—"),
            ("Start Date", str(project.get("start_date") or "—")),
            ("End Date", str(project.get("end_date") or "—")),
            ("Status", str(project.get("status", "")).upper()),
        ]
        for lbl, val in info:
            ws.write(r, 1, lbl, label_fmt)
            ws.write(r, 2, val, value_fmt)
            r += 1

        r += 1
        ws.merge_range(r, 1, r, 5, "KEY PERFORMANCE INDICATORS", section_fmt)
        r += 1
        ws.write(r, 1, "Metric", navy_hdr)
        ws.write(r, 2, "Value", navy_hdr)
        ws.write(r, 3, "Target", navy_hdr)
        ws.write(r, 4, "Status", navy_hdr)
        r += 1

        def _icon(actual, target_val, higher_is_better=True):
            if higher_is_better:
                return "✅ On track" if actual >= target_val else "⚠️ Below target"
            return "✅ On track" if actual <= target_val else "⚠️ Above target"

        kpi_rows = [
            ("Sample Target", target, "—", "—"),
            ("Approved Interviews", approved, target, _icon(approved, target)),
            ("Completion %", f"{completion_pct}%", f"{target}", _icon(completion_pct, 100)),
            ("Total Submitted", total_submitted, "—", "—"),
            ("Pending", pending_qr, "—", "—"),
            ("Cancelled", cancelled_qr, "—", "—"),
            ("Duration-flagged Records", flagged, "—", "—"),
            ("Error Rate %", f"{error_rate}%", f"{project.get('flag_warning_pct') or 5}%", _icon(error_rate, project.get("flag_warning_pct") or 5, False)),
            ("Avg Interview Duration (min)", f"{avg_dur:.1f}", "—", "—"),
            ("Max Duration (min)", f"{max_dur:.0f}", "—", "—"),
            ("Min Duration (min)", f"{min_dur:.0f}", "—", "—"),
            ("Back-check Rate %", f"{bc_rate}%", f"{bc_target_pct}%", _icon(bc_rate, bc_target_pct)),
            ("Listen-in Rate %", f"{li_rate}%", f"{li_target_pct}%", _icon(li_rate, li_target_pct)),
            ("Accompaniment Rate %", f"{acc_rate}%", f"{acc_target_pct}%", _icon(acc_rate, acc_target_pct)),
        ]
        for lbl, val, tgt, status in kpi_rows:
            ws.write(r, 1, lbl, label_fmt)
            ws.write(r, 2, str(val), value_fmt)
            ws.write(r, 3, str(tgt), value_fmt)
            fmt = good_fmt if "✅" in str(status) else (warn_fmt if "⚠️" in str(status) else value_fmt)
            ws.write(r, 4, str(status), fmt)
            r += 1

        r += 1
        ws.merge_range(r, 1, r, 5, "QUALITY QUERIES SUMMARY", section_fmt)
        r += 1
        issues = [
            ("Straight-lining detected", sl_flagged),
            ("Long pauses detected", lp_flagged),
            ("GPS issues (missing/duplicate)", gps_issue),
            ("Missing telephone numbers", phone_miss),
            ("Missing audio recordings", audio_miss),
            ("Duration-flagged (short LOI)", flagged),
            ("Cancelled / invalid interviews", cancelled_qr),
        ]
        ws.write(r, 1, "Issue", navy_hdr)
        ws.write(r, 2, "Count", navy_hdr)
        ws.write(r, 3, "% of Total", navy_hdr)
        r += 1
        for issue_lbl, cnt in issues:
            pct = round(cnt / total_submitted * 100, 1) if total_submitted else 0
            ws.write(r, 1, issue_lbl, label_fmt)
            ws.write(r, 2, cnt, value_fmt)
            ws.write(r, 3, f"{pct}%", value_fmt)
            r += 1

        r += 2
        ws.merge_range(r, 1, r, 5, "UPLOAD HISTORY", section_fmt)
        r += 1
        ws.write(r, 1, "Date", navy_hdr)
        ws.write(r, 2, "Report Type", navy_hdr)
        ws.write(r, 3, "File", navy_hdr)
        ws.write(r, 4, "Rows", navy_hdr)
        ws.write(r, 5, "Uploader", navy_hdr) if False else None
        r += 1
        for log in upload_log:
            ws.write(r, 1, str(log.get("upload_date", ""))[:16], value_fmt)
            ws.write(r, 2, str(log.get("report_type", "")), value_fmt)
            ws.write(r, 3, str(log.get("filename", "")), value_fmt)
            ws.write(r, 4, int(log.get("row_count", 0)), value_fmt)
            r += 1

        # ── QUALITY REPORT sheet ──────────────────────────────────────────
        if not qr_df.empty:
            qr_cols = [c for c in [
                "instance_id", "interviewer_id", "interview_date", "start_time", "end_time",
                "duration_minutes", "duration_flag", "straight_lining", "long_pause",
                "gps_status", "phone_present", "audio_present",
                "region", "location", "sample_point_id", "approval_status", "qc_comments",
            ] if c in qr_df.columns]
            qr_export = qr_df[qr_cols].copy()
            qr_export.columns = [c.replace("_", " ").title() for c in qr_cols]
            qr_export.to_excel(writer, sheet_name="QUALITY REPORT", index=False)
            _apply_header_fmt(writer, "QUALITY REPORT", qr_export, teal_hdr)

            # DATA QUALITY FLAGS — flagged records only
            flag_mask = pd.Series([False] * len(qr_df))
            if "duration_flag" in qr_df.columns:
                flag_mask |= qr_df["duration_flag"].str.lower() == "flag"
            if "straight_lining" in qr_df.columns:
                flag_mask |= qr_df["straight_lining"].apply(
                    lambda x: str(x).strip() not in ("0", "", "None", "nan"))
            if "long_pause" in qr_df.columns:
                flag_mask |= qr_df["long_pause"].apply(
                    lambda x: str(x).strip() not in ("0", "", "None", "nan"))
            flags_df = qr_df[flag_mask][qr_cols].copy() if flag_mask.any() else pd.DataFrame(columns=qr_cols)
            if not flags_df.empty:
                flags_df.columns = [c.replace("_", " ").title() for c in qr_cols]
                flags_df.to_excel(writer, sheet_name="DATA QUALITY FLAGS", index=False)
                _apply_header_fmt(writer, "DATA QUALITY FLAGS", flags_df, orange_hdr)

        # ── BACK-CHECK INFO sheet ─────────────────────────────────────────
        if not bc_df.empty:
            bc_cols = [c for c in [
                "bc_instance_id", "original_instance_id", "interview_status",
                "region", "location", "sample_point_id", "backchecker_id",
                "interviewer_id", "script_name", "interview_date", "backcheck_date",
            ] + [f"error_{i:02d}" for i in range(1, 14)] if c in bc_df.columns]
            bc_export = bc_df[bc_cols].copy()
            # Rename error columns to readable descriptions
            err_rename = {k: f"E{k[-2:]}: {v[:30]}" for k, v in BACKCHECK_ERRORS.items()}
            bc_export.rename(columns={
                **{c: c.replace("_", " ").title() for c in bc_cols},
                **{k: v for k, v in err_rename.items() if k in bc_cols},
            }, inplace=True)
            bc_export.to_excel(writer, sheet_name="BACK-CHECK INFO", index=False)
            _apply_header_fmt(writer, "BACK-CHECK INFO", bc_export, teal_hdr)

        # ── PERFORMANCE REPORT sheet ──────────────────────────────────────
        if not perf_df.empty:
            perf_cols = [c for c in [
                "interviewer_id", "region", "first_interview", "last_interview",
                "interview_completes", "followup_completes", "ecs_completes",
                "work_summary", "accompaniments", "cancelled_interviews",
                "backcheck_telephone_created", "backcheck_f2f_created",
                "backcheck_f2f_infield", "backcheck_total", "backcheck_completed",
            ] if c in perf_df.columns]
            perf_export = perf_df[perf_cols].copy()
            perf_export.columns = [c.replace("_", " ").title() for c in perf_cols]
            perf_export.to_excel(writer, sheet_name="PERFORMANCE REPORT", index=False)
            _apply_header_fmt(writer, "PERFORMANCE REPORT", perf_export, teal_hdr)

        # ── TIMING REPORT sheet ───────────────────────────────────────────
        if not timing_df.empty:
            timing_cols = [c for c in [
                "instance_id", "interviewer_id", "region", "interview_date", "duration_minutes",
            ] if c in timing_df.columns]
            timing_export = timing_df[timing_cols].copy()
            timing_export.columns = [c.replace("_", " ").title() for c in timing_cols]
            timing_export.to_excel(writer, sheet_name="TIMING REPORT", index=False)
            _apply_header_fmt(writer, "TIMING REPORT", timing_export, teal_hdr)

        # ── CANCELLED INTERVIEWS sheet ────────────────────────────────────
        if not cancelled_df.empty:
            canc_cols = [c for c in [
                "instance_id", "interviewer_id", "region", "location",
                "interview_date", "start_time", "end_time", "interview_length",
                "active_length", "idle_time", "gap_to_last", "same_day_finish",
                "qf_a", "qf_b", "qf_c", "qf_d", "qf_e", "qf_f",
                "interviewer_performance", "backcheck_result_telephone",
                "backcheck_result_f2f", "backcheck_result_independent",
            ] if c in cancelled_df.columns]
            canc_export = cancelled_df[canc_cols].copy()
            canc_export.columns = [c.replace("_", " ").title() for c in canc_cols]
            canc_export.to_excel(writer, sheet_name="CANCELLED INTERVIEWS", index=False)
            _apply_header_fmt(writer, "CANCELLED INTERVIEWS", canc_export, orange_hdr)

        # ── LISTEN-IN REPORT sheet ────────────────────────────────────────
        if not listen_df.empty:
            li_cols = [c for c in [
                "instance_id", "interviewer_id", "region", "listen_date",
                "listen_type", "result", "issues_noted", "action_taken",
            ] if c in listen_df.columns]
            li_export = listen_df[li_cols].copy()
            li_export.columns = [c.replace("_", " ").title() for c in li_cols]
            li_export.to_excel(writer, sheet_name="LISTEN-IN REPORT", index=False)
            _apply_header_fmt(writer, "LISTEN-IN REPORT", li_export, teal_hdr)

        # ── WAVE COMPARISON sheet ─────────────────────────────────────────
        if wave_data:
            wave_df = pd.DataFrame(wave_data)
            wave_df.columns = [c.replace("_", " ").title() for c in wave_df.columns]
            wave_df.to_excel(writer, sheet_name="WAVE COMPARISON", index=False)
            _apply_header_fmt(writer, "WAVE COMPARISON", wave_df, navy_hdr)

        # ── PRODUCTIVITY SUMMARY sheet ────────────────────────────────────
        if not qr_df.empty and "interview_date" in qr_df.columns and "interviewer_id" in qr_df.columns:
            prod_df = (
                qr_df.groupby(["interview_date", "interviewer_id"])
                .size()
                .reset_index(name="Interviews")
            )
            prod_df.columns = ["Interview Date", "Interviewer ID", "Interviews"]
            prod_pivot = prod_df.pivot_table(
                index="Interview Date", columns="Interviewer ID",
                values="Interviews", fill_value=0,
            ).reset_index()
            prod_pivot.to_excel(writer, sheet_name="PRODUCTIVITY", index=False)
            _apply_header_fmt(writer, "PRODUCTIVITY", prod_pivot, teal_hdr)

    return buf.getvalue()
