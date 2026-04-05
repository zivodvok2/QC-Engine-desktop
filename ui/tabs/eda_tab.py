"""
ui/tabs/eda_tab.py — Exploratory Data Analysis tab

Features:
- Column pickers for X, Y, color/group variables (multiselect/selectbox)
- Chart type selector: bar, line, scatter, heatmap, histogram, box
- Summary statistics, missing value overview, distributions
"""

import streamlit as st
import pandas as pd
import numpy as np
from ui.components.drag_drop import drop_zone

try:
    import plotly.express as px
    import plotly.graph_objects as go
    PLOTLY = True
except ImportError:
    PLOTLY = False


CHART_TYPES = {
    "Bar chart":    "bar",
    "Line chart":   "line",
    "Scatter plot": "scatter",
    "Histogram":    "histogram",
    "Heatmap":      "heatmap",
    "Box plot":     "box",
}


def _plotly_chart(df, x_col, y_cols, color_col, chart_type, agg_func):
    """Build and return a Plotly figure."""
    if not PLOTLY:
        return None

    y_col = y_cols[0] if y_cols else None

    if chart_type == "heatmap":
        num_cols = ([x_col] + y_cols) if x_col else y_cols
        num_cols = [c for c in num_cols if c in df.columns and
                    pd.api.types.is_numeric_dtype(df[c])]
        if len(num_cols) < 2:
            st.warning("Heatmap needs at least 2 numeric columns.")
            return None
        corr = df[num_cols].corr().round(2)
        return px.imshow(
            corr, text_auto=True, aspect="auto",
            color_continuous_scale="RdBu_r", zmin=-1, zmax=1,
            title="Correlation heatmap",
        )

    if chart_type == "histogram":
        if not y_col:
            st.warning("Select a variable to plot.")
            return None
        return px.histogram(df, x=y_col, color=color_col or None,
                            nbins=30, title=f"Distribution of {y_col}")

    if not x_col or not y_col:
        st.warning("Select at least X and one Y variable.")
        return None

    # Aggregate if needed
    group_cols = [c for c in [x_col, color_col] if c]
    if agg_func and agg_func != "None" and group_cols:
        agg_map = {"Sum": "sum", "Mean": "mean", "Count": "count",
                   "Min": "min", "Max": "max"}
        df_plot = df.groupby(group_cols)[y_col].agg(agg_map[agg_func]).reset_index()
    else:
        df_plot = df.copy()

    if chart_type == "bar":
        fig = px.bar(df_plot, x=x_col, y=y_col, color=color_col or None,
                     barmode="group", title=f"{y_col} by {x_col}")
    elif chart_type == "line":
        fig = px.line(df_plot, x=x_col, y=y_col, color=color_col or None,
                      markers=True, title=f"{y_col} over {x_col}")
    elif chart_type == "scatter":
        if len(y_cols) > 1:
            fig = go.Figure()
            for yc in y_cols:
                if yc in df.columns:
                    fig.add_trace(go.Scatter(
                        x=df[x_col], y=df[yc], mode="markers", name=yc
                    ))
            fig.update_layout(title=f"{', '.join(y_cols)} vs {x_col}")
        else:
            fig = px.scatter(df_plot, x=x_col, y=y_col, color=color_col or None,
                             title=f"{y_col} vs {x_col}")
    elif chart_type == "box":
        fig = px.box(df, x=x_col or None, y=y_col,
                     color=color_col or None, title=f"{y_col} distribution")
    else:
        return None

    fig.update_layout(
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        font_family="DM Mono, monospace",
        font_size=12,
        margin=dict(l=40, r=20, t=50, b=40),
        legend=dict(bgcolor="rgba(0,0,0,0)"),
    )
    return fig


def render(df: pd.DataFrame, results: list):
    num_cols = df.select_dtypes(include="number").columns.tolist()
    cat_cols = df.select_dtypes(exclude="number").columns.tolist()
    all_cols = df.columns.tolist()

    # ── Chart builder ─────────────────────────────────────────────────────────
    st.markdown("#### Build a chart")

    if not PLOTLY:
        st.warning("Plotly not installed. Run `pip install plotly` to enable interactive charts.")

    cfg_col, chart_col = st.columns([1, 2])

    with cfg_col:
        chart_type_label = st.selectbox(
            "Chart type", list(CHART_TYPES.keys()), key="eda_chart_type",
        )
        chart_type = CHART_TYPES[chart_type_label]
        st.markdown("---")

        if chart_type == "heatmap":
            y_cols    = drop_zone("Columns to correlate", "eda_y",
                                  options=num_cols, multi=True,
                                  help_text="Select numeric columns for the correlation heatmap")
            x_col = color_col = agg_func = None

        elif chart_type == "histogram":
            y_cols = drop_zone("Variable", "eda_y",
                               options=all_cols, multi=False,
                               help_text="Column to plot the distribution of")
            color_col_sel = drop_zone("Color / Group by (optional)", "eda_color",
                                      options=all_cols, multi=False)
            color_col = color_col_sel[0] if color_col_sel else None
            x_col = agg_func = None

        else:
            x_col_sel = drop_zone("X axis", "eda_x", options=all_cols, multi=False,
                                  help_text="Categorical or date column")
            x_col = x_col_sel[0] if x_col_sel else None

            y_cols = drop_zone("Y axis", "eda_y",
                               options=num_cols if num_cols else all_cols, multi=True,
                               help_text="Numeric column(s) to plot")

            color_col_sel = drop_zone("Color / Group by (optional)", "eda_color",
                                      options=all_cols, multi=False)
            color_col = color_col_sel[0] if color_col_sel else None

            agg_func = st.selectbox(
                "Aggregate Y by",
                ["None", "Sum", "Mean", "Count", "Min", "Max"],
                key="eda_agg",
                help="How to aggregate Y values when grouping by X",
            )

    with chart_col:
        if PLOTLY:
            fig = _plotly_chart(df, x_col, y_cols, color_col, chart_type, agg_func)
            if fig:
                st.plotly_chart(fig, width="stretch")
            else:
                st.markdown(
                    "<div style='height:300px;display:flex;align-items:center;"
                    "justify-content:center;color:var(--ds-text2);font-size:13px;'>"
                    "Configure variables on the left to build your chart.</div>",
                    unsafe_allow_html=True,
                )
        else:
            if x_col and y_cols:
                try:
                    chart_df = df.set_index(x_col)[y_cols]
                    if chart_type in ("bar", "histogram"):
                        st.bar_chart(chart_df, height=300)
                    else:
                        st.line_chart(chart_df, height=300)
                except Exception as e:
                    st.error(f"Chart error: {e}")

    st.divider()

    # ── Summary statistics ────────────────────────────────────────────────────
    st.markdown("#### Summary statistics")
    stat_tab, miss_tab, dist_tab = st.tabs(["Numeric", "Missing values", "Distributions"])

    with stat_tab:
        if num_cols:
            desc = df[num_cols].describe().T.round(2)
            desc["missing"]   = df[num_cols].isnull().sum()
            desc["missing_%"] = (df[num_cols].isnull().mean() * 100).round(1)
            st.dataframe(desc, width="stretch")
        else:
            st.info("No numeric columns found.")

        if cat_cols:
            st.markdown("##### Categorical columns")
            cat_summary = pd.DataFrame({
                "column":    cat_cols,
                "unique":    [df[c].nunique() for c in cat_cols],
                "missing":   [df[c].isnull().sum() for c in cat_cols],
                "top_value": [
                    str(df[c].value_counts().index[0]) if df[c].notna().any() else "—"
                    for c in cat_cols
                ],
            })
            st.dataframe(cat_summary, width="stretch", hide_index=True)

    with miss_tab:
        miss = pd.DataFrame({
            "column":        df.columns,
            "missing_count": df.isnull().sum().values,
            "missing_%":     (df.isnull().mean() * 100).round(1).values,
        }).sort_values("missing_%", ascending=False)
        miss = miss[miss["missing_count"] > 0]
        if miss.empty:
            st.success("No missing values found.")
        else:
            st.dataframe(miss, width="stretch", hide_index=True)
            if PLOTLY:
                fig = px.bar(miss, x="column", y="missing_%",
                             title="Missing % by column",
                             color="missing_%",
                             color_continuous_scale="Oranges")
                fig.update_layout(
                    plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
                    font_family="DM Mono, monospace",
                    margin=dict(l=40, r=20, t=50, b=60),
                )
                st.plotly_chart(fig, width="stretch")
            else:
                st.bar_chart(miss.set_index("column")["missing_%"], height=200)

    with dist_tab:
        if not num_cols:
            st.info("No numeric columns to plot.")
        else:
            cols_to_plot = st.multiselect(
                "Select columns to plot",
                options=num_cols, default=num_cols[:3],
                key="dist_cols",
            )
            if cols_to_plot and PLOTLY:
                for col in cols_to_plot:
                    vals = df[col].dropna()
                    if len(vals) > 0:
                        fig = px.histogram(
                            df, x=col, nbins=30,
                            title=f"{col} — mean={vals.mean():.2f}, std={vals.std():.2f}",
                        )
                        fig.update_layout(
                            plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
                            font_family="DM Mono, monospace",
                            margin=dict(l=40, r=20, t=50, b=40),
                            showlegend=False,
                        )
                        st.plotly_chart(fig, width="stretch")
