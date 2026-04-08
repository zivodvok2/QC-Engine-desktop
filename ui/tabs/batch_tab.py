"""
ui/tabs/batch_tab.py — Batch Processing

Upload multiple survey files, run QC on each using current settings,
view a combined summary table, and download a single combined Excel report.
"""

import io
from datetime import datetime

import streamlit as st
import pandas as pd

from core.loader import DataLoader
from core.cleaner import DataCleaner
from core.rule_engine import RuleEngine


def _run_one(uploaded_file, cfg: dict, aliases: dict) -> dict:
    """Run the full pipeline on a single uploaded file."""
    df_raw = DataLoader().load_from_buffer(uploaded_file)
    df_clean = DataCleaner().clean(df_raw)
    if aliases:
        df_clean = df_clean.rename(columns=aliases)
    cfg_copy = dict(cfg)
    cfg_copy["logic_rules"] = cfg_copy.get("logic_rules", []) + st.session_state.get("custom_logic_rules", [])
    results = RuleEngine(config=cfg_copy).run(df_clean)
    total_flags = sum(r.flag_count for r in results)
    crits = sum(1 for r in results if r.severity == "critical" and r.flag_count > 0)
    warns = sum(1 for r in results if r.severity == "warning"  and r.flag_count > 0)
    return {
        "filename": uploaded_file.name,
        "rows": len(df_clean),
        "columns": len(df_clean.columns),
        "checks_run": len(results),
        "total_flags": total_flags,
        "flag_rate_pct": round(total_flags / max(len(df_clean), 1) * 100, 1),
        "critical": crits,
        "warnings": warns,
        "status": "🔴 Issues" if crits > 0 else ("🟡 Warnings" if warns > 0 else "✅ Clean"),
        "_df": df_clean,
        "_results": results,
    }


def _build_combined_excel(batch_results: list) -> bytes:
    out = io.BytesIO()
    with pd.ExcelWriter(out, engine="openpyxl") as writer:
        summary_rows = [{
            "File":        b["filename"],
            "Rows":        b["rows"],
            "Checks Run":  b["checks_run"],
            "Total Flags": b["total_flags"],
            "Flag Rate":   f"{b['flag_rate_pct']:.1f}%",
            "Critical":    b["critical"],
            "Warnings":    b["warnings"],
            "Status":      b["status"],
        } for b in batch_results]
        pd.DataFrame(summary_rows).to_excel(writer, sheet_name="Batch Summary", index=False)

        for b in batch_results:
            frames = [
                r.flagged_rows.assign(_qc_check=r.check_name, _severity=r.severity)
                for r in b["_results"] if r.flag_count > 0
            ]
            if frames:
                safe_name = b["filename"][:28].replace("/", "_").replace("\\", "_")
                pd.concat(frames, ignore_index=True).to_excel(
                    writer, sheet_name=safe_name, index=False
                )

    out.seek(0)
    return out.read()


def render(df: pd.DataFrame, results: list):
    st.caption(
        "Use the 📁 Batch QC expander in the sidebar to upload files and run batch processing. "
        "Results appear here."
    )

    batch_results = st.session_state.get("_batch_results", [])

    if not batch_results:
        st.info("No batch results yet. Open the 📁 Batch QC section in the sidebar, upload files, and click ▶ Run batch QC.")
        return

    st.divider()

    bc1, bc2, bc3, bc4 = st.columns(4)
    bc1.metric("Files processed",   len(batch_results))
    bc2.metric("Total rows",        f"{sum(b['rows'] for b in batch_results):,}")
    bc3.metric("Total flags",       f"{sum(b['total_flags'] for b in batch_results):,}")
    bc4.metric("Files with issues", sum(1 for b in batch_results if b["critical"] > 0))

    summary = pd.DataFrame([{
        "File":        b["filename"],
        "Rows":        b["rows"],
        "Total Flags": b["total_flags"],
        "Flag Rate":   f"{b['flag_rate_pct']:.1f}%",
        "Critical":    b["critical"],
        "Warnings":    b["warnings"],
        "Status":      b["status"],
    } for b in batch_results])
    st.dataframe(summary, hide_index=True, use_container_width=True)

    combined_xlsx = _build_combined_excel(batch_results)
    st.download_button(
        "↓ Download combined report",
        data=combined_xlsx,
        file_name=f"Batch_QC_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        type="primary",
    )

    # Per-file expandable detail
    st.divider()
    st.markdown("##### Per-file details")
    for b in batch_results:
        with st.expander(f"{b['status']}  {b['filename']}  —  {b['total_flags']:,} flags"):
            check_rows = [{
                "Check":    r.check_name,
                "Severity": r.severity,
                "Flags":    r.flag_count,
                "Rate":     f"{r.flag_count / max(b['rows'], 1) * 100:.1f}%",
            } for r in b["_results"]]
            st.dataframe(pd.DataFrame(check_rows), hide_index=True, use_container_width=True)
