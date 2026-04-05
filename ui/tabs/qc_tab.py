"""
ui/tabs/qc_tab.py — QC Report tab
"""

import streamlit as st
import pandas as pd
import io


def sev_emoji(s): return {"critical": "🔴", "warning": "🟡", "info": "🔵"}.get(s, "⚪")
def sev_color(s): return {"critical": "var(--ds-critical)", "warning": "var(--ds-warning)", "info": "var(--ds-info)"}.get(s, "var(--ds-text2)")


def render(df: pd.DataFrame, results: list):
    total_flags = sum(r.flag_count for r in results)
    crits = sum(1 for r in results if r.severity == "critical" and r.flag_count > 0)
    warns = sum(1 for r in results if r.severity == "warning"  and r.flag_count > 0)
    infos = sum(1 for r in results if r.severity == "info"     and r.flag_count > 0)

    # Scorecards
    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("Checks run",   len(results))
    m2.metric("Total flags",  total_flags)
    m3.metric("🔴 Critical",  crits)
    m4.metric("🟡 Warnings",  warns)
    m5.metric("🔵 Info",      infos)

    st.divider()

    if total_flags == 0:
        st.success("✅ No issues detected — dataset passed all checks.")
    else:
        for sev, label in [("critical", "Critical Issues"), ("warning", "Warnings"), ("info", "Info")]:
            sev_res = [r for r in results if r.severity == sev and r.flag_count > 0]
            if not sev_res:
                continue
            st.markdown(
                f"<h4 style='color:{sev_color(sev)};margin-top:1rem;'>"
                f"{sev_emoji(sev)} {label}</h4>",
                unsafe_allow_html=True,
            )
            for r in sev_res:
                pct = r.flag_count / max(len(df), 1) * 100
                with st.expander(
                    f"{r.check_name} — **{r.flag_count:,}** rows ({pct:.1f}%)",
                    expanded=(sev == "critical"),
                ):
                    mc, dc = st.columns([2, 3])
                    with mc:
                        st.markdown("**Check metadata**")
                        st.json(r.summary(), expanded=False)
                    with dc:
                        if not r.flagged_rows.empty:
                            show = [c for c in r.flagged_rows.columns if not c.startswith("_")]
                            st.dataframe(
                                r.flagged_rows[show].head(50),
                                width="stretch",
                                hide_index=True,
                            )

    st.markdown("#### All checks summary")
    st.dataframe(
        pd.DataFrame([r.summary() for r in results]),
        width="stretch",
        hide_index=True,
    )

    # ── Sign-off workflow ─────────────────────────────────────────────────────
    flagged_results = [r for r in results if r.flag_count > 0 and not r.flagged_rows.empty]
    if not flagged_results:
        return

    st.divider()
    st.markdown("#### 📋 Review Workflow")
    st.markdown(
        "<p style='color:var(--ds-text2);font-size:13px;margin-bottom:12px;'>"
        "Mark flagged records as <strong>Accepted</strong> (valid data, no action) or "
        "<strong>Rejected</strong> (re-interview needed). Export only unreviewed flags.</p>",
        unsafe_allow_html=True,
    )

    # Build combined flagged table
    pieces = []
    for r in flagged_results:
        chunk = r.flagged_rows.copy()
        chunk["_check"] = r.check_name
        show_cols = [c for c in chunk.columns if not c.startswith("_")] + ["_check"]
        pieces.append(chunk[show_cols])

    combined = pd.concat(pieces, ignore_index=True)
    combined.insert(0, "Status", "Pending")

    # Restore saved review state
    saved = st.session_state.get("_review_state", {})
    for idx, status in saved.items():
        if idx < len(combined):
            combined.at[idx, "Status"] = status

    edited = st.data_editor(
        combined,
        column_config={
            "Status": st.column_config.SelectboxColumn(
                "Status",
                options=["Pending", "Accepted", "Rejected"],
                required=True,
                width="small",
            )
        },
        hide_index=True,
        width="stretch",
        key="review_editor",
        num_rows="fixed",
    )

    # Persist review state
    st.session_state["_review_state"] = edited["Status"].to_dict()

    pending   = (edited["Status"] == "Pending").sum()
    accepted  = (edited["Status"] == "Accepted").sum()
    rejected  = (edited["Status"] == "Rejected").sum()

    rc1, rc2, rc3 = st.columns(3)
    rc1.metric("Pending review", int(pending))
    rc2.metric("Accepted",       int(accepted))
    rc3.metric("Rejected",       int(rejected))

    unreviewed = edited[edited["Status"] == "Pending"]
    if not unreviewed.empty:
        import io
        buf = io.BytesIO()
        unreviewed.to_excel(buf, index=False)
        st.download_button(
            "↓ Export pending flags",
            data=buf.getvalue(),
            file_name="pending_flags.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
