"""
ui/tabs/compare_tab.py — Multi-file Wave Comparison

Upload two waves of the same survey and diff them:
  - New records (in wave 2, not wave 1)
  - Removed records (in wave 1, not wave 2)
  - Changed records (same ID, values differ)
  - Interviewer stats shift between waves
"""

import streamlit as st
import pandas as pd
from core.loader import DataLoader


def render(df: pd.DataFrame):
    st.markdown("#### Wave Comparison")
    st.markdown(
        "<p style='color:var(--ds-text2);font-size:13px;margin-bottom:16px;'>"
        "Upload a second wave of the same survey to compare records, detect changes, "
        "and track interviewer stat shifts.</p>",
        unsafe_allow_html=True,
    )

    # ── Upload second file ────────────────────────────────────────────────────
    uploaded2 = st.file_uploader(
        "Upload wave 2 file (CSV or Excel)",
        type=["csv", "xlsx", "xls"],
        key="compare_upload",
    )

    if uploaded2:
        try:
            df2 = DataLoader().load_from_buffer(uploaded2)
            st.session_state["_compare_df"] = df2
            st.session_state["_compare_name"] = uploaded2.name
            st.success(f"✓ Wave 2 loaded: {len(df2):,} rows · {len(df2.columns)} columns")
        except Exception as e:
            st.error(f"Error loading file: {e}")
            return

    df2 = st.session_state.get("_compare_df")
    if df2 is None:
        st.info("Upload a second file above to start comparison.")
        return

    st.caption(
        f"Wave 1: **{st.session_state.get('filename', 'current')}** · {len(df):,} rows  |  "
        f"Wave 2: **{st.session_state.get('_compare_name', 'wave2')}** · {len(df2):,} rows"
    )

    st.divider()

    # ── ID column ─────────────────────────────────────────────────────────────
    common_cols = [c for c in df.columns if c in df2.columns]
    id_col_sel = st.selectbox(
        "Unique ID column (to match records across waves)",
        options=["— select —"] + common_cols,
        key="cmp_id_col",
    )
    if id_col_sel == "— select —":
        st.info("Select the ID column to match records.")
        return
    id_col = id_col_sel

    # ── Diff ──────────────────────────────────────────────────────────────────
    ids1 = set(df[id_col].dropna().astype(str))
    ids2 = set(df2[id_col].dropna().astype(str))

    new_ids     = ids2 - ids1
    removed_ids = ids1 - ids2
    common_ids  = ids1 & ids2

    c1, c2, c3 = st.columns(3)
    c1.metric("New records (wave 2 only)",      len(new_ids))
    c2.metric("Removed records (wave 1 only)",  len(removed_ids))
    c3.metric("Matching records",               len(common_ids))

    st.divider()

    tab_new, tab_removed, tab_changed, tab_interviewers = st.tabs([
        f"New ({len(new_ids)})", f"Removed ({len(removed_ids)})", "Changed values", "Interviewer shifts",
    ])

    with tab_new:
        if new_ids:
            new_rows = df2[df2[id_col].astype(str).isin(new_ids)]
            st.dataframe(new_rows.head(200), width="stretch", hide_index=True)
        else:
            st.success("No new records in wave 2.")

    with tab_removed:
        if removed_ids:
            removed_rows = df[df[id_col].astype(str).isin(removed_ids)]
            st.dataframe(removed_rows.head(200), width="stretch", hide_index=True)
        else:
            st.success("No records removed in wave 2.")

    with tab_changed:
        compare_cols = st.multiselect(
            "Columns to compare",
            options=common_cols,
            default=[c for c in common_cols if c != id_col][:10],
            key="cmp_cols",
        )
        if compare_cols and common_ids:
            w1 = df[df[id_col].astype(str).isin(common_ids)].set_index(id_col)[compare_cols]
            w2 = df2[df2[id_col].astype(str).isin(common_ids)].set_index(id_col)[compare_cols]
            w1.index = w1.index.astype(str)
            w2.index = w2.index.astype(str)

            # Align on common index
            common_idx = w1.index.intersection(w2.index)
            w1 = w1.loc[common_idx]
            w2 = w2.loc[common_idx]

            diff_mask = w1.astype(str) != w2.astype(str)
            changed_ids = diff_mask.any(axis=1)
            n_changed = changed_ids.sum()

            st.metric("Records with changed values", int(n_changed))

            if n_changed > 0:
                changed_w1 = w1[changed_ids].copy()
                changed_w2 = w2[changed_ids].copy()
                changed_w1.columns = [f"{c} (wave1)" for c in compare_cols]
                changed_w2.columns = [f"{c} (wave2)" for c in compare_cols]
                combined = pd.concat([changed_w1, changed_w2], axis=1)
                # interleave wave1/wave2 columns for easy reading
                ordered = []
                for c in compare_cols:
                    ordered += [f"{c} (wave1)", f"{c} (wave2)"]
                st.dataframe(combined[ordered].head(200), width="stretch")
        else:
            st.info("Select columns to compare above.")

    with tab_interviewers:
        int_col_sel = st.selectbox(
            "Interviewer column",
            options=["— select —"] + common_cols,
            key="cmp_int_col",
        )
        if int_col_sel == "— select —":
            st.info("Select interviewer column to compare stats.")
        else:
            int_col = int_col_sel
            s1 = df[int_col].value_counts().rename("wave1_count")
            s2 = df2[int_col].value_counts().rename("wave2_count")
            comp = pd.concat([s1, s2], axis=1).fillna(0).astype(int)
            comp["change"] = comp["wave2_count"] - comp["wave1_count"]
            comp["change_%"] = (
                (comp["change"] / comp["wave1_count"].replace(0, 1)) * 100
            ).round(1)
            comp = comp.reset_index().rename(columns={"index": int_col})
            comp = comp.sort_values("change", ascending=False)

            st.dataframe(
                comp,
                width="stretch",
                hide_index=True,
                column_config={
                    "change": st.column_config.NumberColumn("Change", format="%+d"),
                    "change_%": st.column_config.NumberColumn("Change %", format="%+.1f%%"),
                },
            )
