import plotly.express as px
import plotly.graph_objects as go
from config import (
    CHART_COLORS, SL_BG, SL_SURFACE, SL_SURFACE2, SL_LINE,
    SL_TX, SL_MUTED, SL_ACCENT, SL_CRITICAL, SL_WARNING,
)

_FONT = "DM Mono, ui-monospace, monospace"
_FONT_DISPLAY = "Syne, ui-sans-serif, sans-serif"

LAYOUT = dict(
    paper_bgcolor=SL_SURFACE,
    plot_bgcolor=SL_SURFACE,
    font=dict(family=_FONT, color=SL_MUTED, size=12),
    title_font=dict(family=_FONT_DISPLAY, color=SL_TX, size=14),
    margin=dict(l=30, r=30, t=48, b=30),
    legend=dict(
        orientation="h",
        yanchor="bottom", y=1.02,
        xanchor="right", x=1,
        bgcolor="rgba(0,0,0,0)",
        font=dict(color=SL_MUTED, size=11),
    ),
    xaxis=dict(
        gridcolor=SL_LINE,
        linecolor=SL_LINE,
        tickfont=dict(color=SL_MUTED, size=11),
        title_font=dict(color=SL_MUTED),
        zerolinecolor=SL_LINE,
    ),
    yaxis=dict(
        gridcolor=SL_LINE,
        linecolor=SL_LINE,
        tickfont=dict(color=SL_MUTED, size=11),
        title_font=dict(color=SL_MUTED),
        zerolinecolor=SL_LINE,
    ),
)


def _apply(fig, title=""):
    if title:
        fig.update_layout(title_text=title, title_x=0)
    fig.update_layout(**LAYOUT)
    return fig


def donut_chart(values, names, title, colors=None):
    fig = go.Figure(go.Pie(
        values=values,
        labels=names,
        hole=0.6,
        marker=dict(
            colors=colors or CHART_COLORS,
            line=dict(color=SL_SURFACE, width=2),
        ),
        textinfo="label+percent",
        textfont=dict(color=SL_TX, size=11),
        insidetextorientation="radial",
    ))
    fig.update_layout(
        paper_bgcolor=SL_SURFACE,
        plot_bgcolor=SL_SURFACE,
        font=dict(family=_FONT, color=SL_MUTED),
        title_text=title, title_x=0,
        title_font=dict(family=_FONT_DISPLAY, color=SL_TX, size=14),
        legend=dict(font=dict(color=SL_MUTED), bgcolor="rgba(0,0,0,0)"),
        margin=dict(l=20, r=20, t=48, b=20),
    )
    return fig


def bar_chart(df, x, y, color=None, title="", barmode="group", orientation="v"):
    fig = px.bar(
        df, x=x, y=y, color=color, title=title,
        barmode=barmode, orientation=orientation,
        color_discrete_sequence=CHART_COLORS,
    )
    fig.update_traces(marker_line_width=0)
    return _apply(fig, title)


def stacked_bar(df, x, y, color, title=""):
    fig = px.bar(
        df, x=x, y=y, color=color, title=title,
        barmode="stack", color_discrete_sequence=CHART_COLORS,
    )
    fig.update_traces(marker_line_width=0)
    return _apply(fig, title)


def line_chart(df, x, y, color=None, title=""):
    fig = px.line(
        df, x=x, y=y, color=color, title=title,
        markers=True, color_discrete_sequence=CHART_COLORS,
    )
    fig.update_traces(marker=dict(size=6, line=dict(width=0)))
    return _apply(fig, title)


def scatter_chart(df, x, y, color=None, title="", size=None):
    fig = px.scatter(
        df, x=x, y=y, color=color, title=title,
        size=size, color_discrete_sequence=CHART_COLORS,
    )
    return _apply(fig, title)


def histogram(df, x, title="", nbins=20):
    fig = px.histogram(
        df, x=x, title=title, nbins=nbins,
        color_discrete_sequence=[SL_ACCENT],
    )
    fig.update_traces(marker_line_width=0, opacity=0.85)
    return _apply(fig, title)


def gauge_chart(value, target, title, suffix="%"):
    on_target = value >= target * 100
    bar_color = SL_ACCENT if on_target else SL_CRITICAL
    fig = go.Figure(go.Indicator(
        mode="gauge+number+delta",
        value=value,
        delta={"reference": target * 100, "suffix": suffix,
               "increasing": {"color": SL_ACCENT},
               "decreasing": {"color": SL_CRITICAL}},
        number={"suffix": suffix, "font": {"color": SL_TX, "family": _FONT_DISPLAY, "size": 28}},
        title={"text": title, "font": {"size": 13, "color": SL_MUTED, "family": _FONT}},
        gauge={
            "axis": {"range": [0, 100], "tickfont": {"color": SL_MUTED}, "tickcolor": SL_LINE},
            "bar": {"color": bar_color},
            "bgcolor": SL_SURFACE2,
            "borderwidth": 0,
            "steps": [
                {"range": [0, target * 80],          "color": "rgba(240,74,106,0.1)"},
                {"range": [target * 80, target * 100], "color": "rgba(240,192,74,0.1)"},
                {"range": [target * 100, 100],        "color": "rgba(74,240,160,0.1)"},
            ],
            "threshold": {
                "line": {"color": SL_TX, "width": 2},
                "thickness": 0.75,
                "value": target * 100,
            },
        },
    ))
    fig.update_layout(
        height=220,
        margin=dict(l=10, r=10, t=50, b=10),
        paper_bgcolor=SL_SURFACE,
        font=dict(family=_FONT, color=SL_MUTED),
    )
    return fig


def kpi_card(label, value, delta=None, delta_label="", suffix="", color=None):
    if color is None:
        color = SL_ACCENT
    delta_html = ""
    if delta is not None:
        arrow = "▲" if delta >= 0 else "▼"
        d_color = SL_ACCENT if delta >= 0 else SL_CRITICAL
        delta_html = (
            f'<div style="color:{d_color};font-size:0.78rem;margin-top:2px;">'
            f'{arrow} {abs(delta)}{suffix} {delta_label}</div>'
        )
    return f"""
<div style="
    background:{SL_SURFACE};
    border:1px solid {SL_LINE};
    border-top:2px solid {color};
    border-radius:8px;
    padding:1.1rem 1rem 0.9rem;
    text-align:center;
    min-height:100px;
    font-family:DM Mono,ui-monospace,monospace;
">
    <div style="
        color:{SL_MUTED};
        font-size:0.68rem;
        text-transform:uppercase;
        letter-spacing:0.1em;
        margin-bottom:0.4rem;
    ">{label}</div>
    <div style="
        color:{SL_TX};
        font-size:1.9rem;
        font-weight:700;
        font-family:Syne,ui-sans-serif,sans-serif;
        line-height:1;
    ">{value}{suffix}</div>
    {delta_html}
</div>"""


def section_header(title: str, muted: str = ""):
    """Render a Servallab-styled section heading."""
    sub = f'<span style="color:{SL_MUTED};font-size:0.8rem;font-family:DM Mono,monospace;"> — {muted}</span>' if muted else ""
    return (
        f'<h3 style="font-family:Syne,sans-serif;font-weight:700;font-size:1.05rem;'
        f'color:{SL_TX};border-bottom:1px solid {SL_LINE};padding-bottom:0.5rem;'
        f'margin-bottom:1rem;">{title}{sub}</h3>'
    )


def status_badge(status: str) -> str:
    """Return an inline HTML badge matching Servallab severity colours."""
    cfg = {
        "active":    (SL_ACCENT,    "rgba(74,240,160,0.12)"),
        "completed": (SL_INFO,      "rgba(74,158,240,0.12)"),
        "paused":    (SL_WARNING,   "rgba(240,192,74,0.12)"),
        "critical":  (SL_CRITICAL,  "rgba(240,74,106,0.12)"),
        "warning":   (SL_WARNING,   "rgba(240,192,74,0.12)"),
        "info":      (SL_INFO,      "rgba(74,158,240,0.12)"),
    }
    color, bg = cfg.get(status.lower(), (SL_MUTED, SL_SURFACE2))
    return (
        f'<span style="background:{bg};color:{color};border:1px solid {color}33;'
        f'border-radius:4px;padding:1px 8px;font-size:0.7rem;font-weight:600;'
        f'font-family:DM Mono,monospace;letter-spacing:0.05em;">'
        f'{status.upper()}</span>'
    )
