"""
ui/tabs/eda_tab.py — Exploratory Data Analysis tab

Performance notes:
- describe() and corr() are cached with @st.cache_data so they only
  recompute when the dataframe changes, not on every widget interaction.
- Histograms are pre-aggregated in Python (numpy) before being sent to
  Plotly, reducing browser payload from N raw rows to 30 bin counts.
- Scatter plots are capped at SCATTER_SAMPLE rows to keep rendering fast.
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

SCATTER_SAMPLE = 5_000   # max rows sent to browser for scatter / raw charts
HIST_BINS      = 30


# ── Cached heavy computations ─────────────────────────────────────────────────

@st.cache_data
def _describe(df: pd.DataFrame) -> pd.DataFrame:
    num = df.select_dtypes(include="number")
    desc = num.describe().T.round(2)
    desc["missing"]   = num.isnull().sum()
    desc["missing_%"] = (num.isnull().mean() * 100).round(1)
    return desc


@st.cache_data
def _corr(df: pd.DataFrame) -> pd.DataFrame:
    return df.select_dtypes(include="number").corr().round(2)


@st.cache_data
def _missing_summary(df: pd.DataFrame) -> pd.DataFrame:
    return pd.DataFrame({
        "column":        df.columns,
        "missing_count": df.isnull().sum().values,
        "missing_%":     (df.isnull().mean() * 100).round(1).values,
    }).sort_values("missing_%", ascending=False).query("missing_count > 0")


@st.cache_data
def _hist_data(df: pd.DataFrame, col: str, nbins: int = HIST_BINS) -> pd.DataFrame:
    """Pre-aggregate histogram bins — returns a small DataFrame, not raw rows."""
    vals = df[col].dropna().to_numpy(dtype=float, na_value=np.nan)
    vals = vals[~np.isnan(vals)]
    if len(vals) == 0:
        return pd.DataFrame({"bin": [], "count": []})
    counts, edges = np.histogram(vals, bins=nbins)
    labels = [f"{edges[i]:.2g}–{edges[i+1]:.2g}" for i in range(len(counts))]
    return pd.DataFrame({"bin": labels, "count": counts,
                         "mean": vals.mean(), "std": vals.std(), "n": len(vals)})


@st.cache_data
def _cat_summary(df: pd.DataFrame, cat_cols: list) -> pd.DataFrame:
    return pd.DataFrame({
        "column":    cat_cols,
        "unique":    [df[c].nunique()       for c in cat_cols],
        "missing":   [df[c].isnull().sum()  for c in cat_cols],
        "top_value": [
            str(df[c].value_counts().index[0]) if df[c].notna().any() else "—"
            for c in cat_cols
        ],
    })


# ── Chart builder helpers ─────────────────────────────────────────────────────

def _sample(df: pd.DataFrame, n: int = SCATTER_SAMPLE) -> pd.DataFrame:
    return df.sample(n, random_state=42) if len(df) > n else df


def _fig_layout(fig):
    fig.update_layout(
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        font_family="DM Mono, monospace",
        font_size=12,
        margin=dict(l=40, r=20, t=50, b=40),
        legend=dict(bgcolor="rgba(0,0,0,0)"),
    )
    return fig


CHART_TYPES = {
    "Bar chart":    "bar",
    "Line chart":   "line",
    "Scatter plot": "scatter",
    "Histogram":    "histogram",
    "Heatmap":      "heatmap",
    "Box plot":     "box",
}


def _build_chart(df, x_col, y_cols, color_col, chart_type, agg_func):
    if not PLOTLY:
        return None

    y_col = y_cols[0] if y_cols else None

    # ── Heatmap: correlation — already cached, tiny payload ──────────────────
    if chart_type == "heatmap":
        num_cols = ([x_col] + y_cols) if x_col else y_cols
        num_cols = [c for c in num_cols if c in df.columns
                    and pd.api.types.is_numeric_dtype(df[c])]
        if len(num_cols) < 2:
            st.warning("Heatmap needs at least 2 numeric columns.")
            return None
        return _fig_layout(px.imshow(
            _corr(df[num_cols]), text_auto=True, aspect="auto",
            color_continuous_scale="RdBu_r", zmin=-1, zmax=1,
            title="Correlation heatmap",
        ))

    # ── Histogram: pre-aggregated — 30 points instead of N rows ─────────────
    if chart_type == "histogram":
        if not y_col:
            st.warning("Select a variable to plot.")
            return None
        hdata = _hist_data(df, y_col)
        if hdata.empty:
            return None
        fig = px.bar(hdata, x="bin", y="count",
                     title=f"{y_col} — mean={hdata['mean'].iloc[0]:.2f}, "
                           f"std={hdata['std'].iloc[0]:.2f}, n={hdata['n'].iloc[0]:,}")
        fig.update_xaxes(tickangle=-45)
        return _fig_layout(fig)

    if not x_col or not y_col:
        st.warning("Select at least X and one Y variable.")
        return None

    # ── Aggregate or sample ───────────────────────────────────────────────────
    group_cols = [c for c in [x_col, color_col] if c]
    if agg_func and agg_func != "None" and group_cols:
        agg_map = {"Sum": "sum", "Mean": "mean", "Count": "count",
                   "Min": "min", "Max": "max"}
        df_plot = df.groupby(group_cols)[y_col].agg(agg_map[agg_func]).reset_index()
    else:
        df_plot = _sample(df)   # cap raw rows for scatter / box

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
                if yc in df_plot.columns:
                    fig.add_trace(go.Scatter(
                        x=df_plot[x_col], y=df_plot[yc], mode="markers", name=yc
                    ))
            fig.update_layout(title=f"{', '.join(y_cols)} vs {x_col}")
        else:
            fig = px.scatter(df_plot, x=x_col, y=y_col, color=color_col or None,
                             title=f"{y_col} vs {x_col}")
    elif chart_type == "box":
        fig = px.box(df_plot, x=x_col or None, y=y_col,
                     color=color_col or None, title=f"{y_col} distribution")
    else:
        return None

    return _fig_layout(fig)


# ── Main render ───────────────────────────────────────────────────────────────

def render(df: pd.DataFrame, results: list):
    num_cols = df.select_dtypes(include="number").columns.tolist()
    cat_cols = df.select_dtypes(exclude="number").columns.tolist()
    all_cols = df.columns.tolist()

    n = len(df)
    if n > SCATTER_SAMPLE:
        st.caption(
            f"{n:,} rows loaded — charts use pre-aggregated data or a "
            f"{SCATTER_SAMPLE:,}-row sample for speed. Statistics use the full dataset."
        )

    # ── Chart builder ─────────────────────────────────────────────────────────
    st.markdown("#### Build a chart")

    if not PLOTLY:
        st.warning("Run `pip install plotly` to enable interactive charts.")

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
                                  help_text="Select numeric columns for correlation heatmap")
            x_col = color_col = agg_func = None

        elif chart_type == "histogram":
            y_cols = drop_zone("Variable", "eda_y",
                               options=all_cols, multi=False,
                               help_text="Column to plot distribution of")
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
                help="Aggregate Y values when grouping by X (avoids sending raw rows)",
            )

    with chart_col:
        if PLOTLY:
            fig = _build_chart(df, x_col, y_cols, color_col, chart_type, agg_func)
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
                    st.bar_chart(chart_df, height=300) if chart_type in ("bar", "histogram") \
                        else st.line_chart(chart_df, height=300)
                except Exception as e:
                    st.error(f"Chart error: {e}")

    st.divider()

    # ── Summary statistics (all cached) ───────────────────────────────────────
    st.markdown("#### Summary statistics")
    stat_tab, miss_tab, dist_tab = st.tabs(["Numeric", "Missing values", "Distributions"])

    with stat_tab:
        if num_cols:
            st.dataframe(_describe(df), width="stretch")
        else:
            st.info("No numeric columns found.")

        if cat_cols:
            st.markdown("##### Categorical columns")
            st.dataframe(_cat_summary(df, cat_cols), width="stretch", hide_index=True)

    with miss_tab:
        miss = _missing_summary(df)
        if miss.empty:
            st.success("No missing values found.")
        else:
            st.dataframe(miss, width="stretch", hide_index=True)
            if PLOTLY:
                fig = px.bar(miss, x="column", y="missing_%",
                             title="Missing % by column",
                             color="missing_%", color_continuous_scale="Oranges")
                fig.update_layout(
                    plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
                    font_family="DM Mono, monospace", margin=dict(l=40,r=20,t=50,b=60),
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
                options=num_cols, default=num_cols[:3], key="dist_cols",
            )
            if cols_to_plot and PLOTLY:
                for col in cols_to_plot:
                    # Pre-aggregate: sends 30 points to browser instead of N rows
                    hdata = _hist_data(df, col)
                    if not hdata.empty:
                        fig = px.bar(
                            hdata, x="bin", y="count",
                            title=f"{col} — mean={hdata['mean'].iloc[0]:.2f}, "
                                  f"std={hdata['std'].iloc[0]:.2f}, "
                                  f"n={hdata['n'].iloc[0]:,}",
                        )
                        fig.update_layout(
                            plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
                            font_family="DM Mono, monospace",
                            margin=dict(l=40, r=20, t=50, b=40),
                            showlegend=False,
                        )
                        fig.update_xaxes(tickangle=-45)
                        st.plotly_chart(fig, width="stretch")
