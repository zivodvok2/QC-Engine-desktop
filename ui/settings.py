"""
ui/settings.py — Settings panel (rendered in sidebar expander)

Covers: theme selection, Groq API key, app version, onboarding relaunch.
"""

import json
import os
import streamlit as st
from pathlib import Path
from ui.onboarding import show_onboarding_button

VERSION_FILE = Path(__file__).parent.parent / "assets" / "app_version.json"
THEMES_FILE  = Path(__file__).parent.parent / "config"  / "themes.json"

GROQ_MODELS = [
    "llama-3.1-8b-instant",
    "llama-3.3-70b-versatile",
    "mixtral-8x7b-32768",
    "gemma2-9b-it",
]


def _load_version() -> dict:
    try:
        return json.loads(VERSION_FILE.read_text())
    except Exception:
        return {"version": "unknown", "changelog": []}


def _load_themes() -> dict:
    try:
        return json.loads(THEMES_FILE.read_text())
    except Exception:
        return {}


def init_settings():
    """Initialize settings state with defaults."""
    if "ds_theme" not in st.session_state:
        st.session_state.ds_theme = "dark"
    if "ds_groq_api_key" not in st.session_state:
        st.session_state.ds_groq_api_key = ""
    if "ds_groq_model" not in st.session_state:
        st.session_state.ds_groq_model = GROQ_MODELS[0]


def render_settings():
    """Renders the settings panel inside a sidebar expander."""
    init_settings()
    version_data = _load_version()
    themes       = _load_themes()

    with st.sidebar.expander("⚙️ Settings", expanded=False):

        # ── Theme ─────────────────────────────────────────────────────────
        st.markdown("**Theme**")
        theme_names = {k: v["name"] for k, v in themes.items()} if themes else {"dark": "Dark"}
        selected_theme = st.selectbox(
            "Theme",
            options=list(theme_names.keys()),
            format_func=lambda k: theme_names[k],
            index=list(theme_names.keys()).index(st.session_state.ds_theme)
                  if st.session_state.ds_theme in theme_names else 0,
            key="theme_select",
            label_visibility="collapsed",
        )
        if selected_theme != st.session_state.ds_theme:
            st.session_state.ds_theme = selected_theme
            st.rerun()

        st.divider()

        # ── Groq / Verbatim ───────────────────────────────────────────────
        st.markdown("**Verbatim checks (Groq AI)**")

        env_key = os.environ.get("GROQ_API_KEY", "").strip()
        if env_key:
            st.success("✓ Server key active")
            st.caption("Pre-configured via `GROQ_API_KEY` environment variable.")
        else:
            st.warning("No server key — personal key required")

        # Personal key — always shown; used as fallback when server key hits rate limit
        st.markdown(
            "<div style='font-size:11px;color:var(--ds-text2);margin:6px 0 4px;'>"
            + ("Personal key <em>(fallback when server limit is reached)</em>"
               if env_key else "Your Groq API key")
            + "</div>",
            unsafe_allow_html=True,
        )
        current_key = st.session_state.ds_groq_api_key
        new_key = st.text_input(
            "Groq API key",
            value=current_key,
            type="password",
            placeholder="gsk_…",
            key="groq_key_input",
            label_visibility="collapsed",
            help="Used when the server key hits its rate limit, or as the primary key if no server key is set.",
        )
        if new_key != current_key:
            st.session_state.ds_groq_api_key = new_key
            st.rerun()

        st.caption("Free key at [console.groq.com](https://console.groq.com)")

        st.session_state.ds_groq_model = st.selectbox(
            "Model",
            options=GROQ_MODELS,
            index=GROQ_MODELS.index(st.session_state.ds_groq_model)
                  if st.session_state.ds_groq_model in GROQ_MODELS else 0,
            key="groq_model_select",
            label_visibility="collapsed",
        )

        st.divider()

        # ── Account (placeholder) ─────────────────────────────────────────
        st.markdown("**Account**")
        st.caption("Sign-in coming soon")
        col1, col2 = st.columns(2)
        col1.button("Sign in with Google", disabled=True, use_container_width=True)
        col2.button("Sign in with email",  disabled=True, use_container_width=True)

        st.divider()

        # ── Help ──────────────────────────────────────────────────────────
        st.markdown("**Help**")
        show_onboarding_button()
        st.link_button(
            "📧 Send feedback",
            url="mailto:feedback@servalab.com?subject=Servallab Feedback",
            use_container_width=True,
        )

        st.divider()

        # ── Version ───────────────────────────────────────────────────────
        st.markdown(f"**Servallab v{version_data.get('version', '?')}**")
        st.caption(f"Released {version_data.get('release_date', '')}")
        with st.expander("Changelog"):
            for entry in version_data.get("changelog", []):
                st.caption(entry)


def get_theme_css(theme_key: str = "dark") -> str:
    """
    Returns comprehensive CSS variable definitions and component overrides
    for the selected theme. Uses !important to win over Streamlit's defaults.
    """
    themes = _load_themes()
    t = themes.get(theme_key, themes.get("dark", {}))
    if not t:
        return ""

    bg       = t.get("bg",       "#0b0c0f")
    surface  = t.get("surface",  "#111318")
    surface2 = t.get("surface2", "#181b22")
    border   = t.get("border",   "#1f2330")
    accent   = t.get("accent",   "#4af0a0")
    text     = t.get("text",     "#e8eaf2")
    text2    = t.get("text2",    "#8b90a8")
    critical = t.get("critical", "#f04a6a")
    warning  = t.get("warning",  "#f0c04a")
    info     = t.get("info",     "#4a9ef0")

    return f"""
    <style>
    /* ── CSS variables ────────────────────────────────────────────────── */
    :root {{
        --ds-bg:       {bg};
        --ds-surface:  {surface};
        --ds-surface2: {surface2};
        --ds-border:   {border};
        --ds-accent:   {accent};
        --ds-text:     {text};
        --ds-text2:    {text2};
        --ds-critical: {critical};
        --ds-warning:  {warning};
        --ds-info:     {info};
    }}

    /* ── Page background ──────────────────────────────────────────────── */
    .stApp,
    [data-testid="stAppViewContainer"],
    [data-testid="stMain"],
    [data-testid="stAppViewBlockContainer"],
    .main .block-container {{
        background-color: {bg} !important;
    }}

    /* ── Sidebar ──────────────────────────────────────────────────────── */
    section[data-testid="stSidebar"],
    section[data-testid="stSidebar"] > div:first-child {{
        background-color: {surface} !important;
        border-right: 1px solid {border} !important;
    }}

    /* ── Text ─────────────────────────────────────────────────────────── */
    .stMarkdown p, .stMarkdown li, .stMarkdown span,
    .stMarkdown h1, .stMarkdown h2, .stMarkdown h3, .stMarkdown h4,
    [data-testid="stText"] p,
    [data-testid="stHeadingWithActionElements"] h1,
    [data-testid="stHeadingWithActionElements"] h2,
    [data-testid="stHeadingWithActionElements"] h3 {{
        color: {text} !important;
    }}
    [data-testid="stCaptionContainer"] p,
    .stCaption p {{
        color: {text2} !important;
    }}

    /* ── Metric cards ─────────────────────────────────────────────────── */
    [data-testid="metric-container"] {{
        background:    {surface} !important;
        border:        1px solid {border} !important;
        border-radius: 6px !important;
        padding:       12px 16px !important;
    }}
    [data-testid="metric-container"] label {{
        color:           {text2} !important;
        font-size:       10px !important;
        letter-spacing:  0.1em !important;
        text-transform:  uppercase !important;
    }}
    [data-testid="metric-container"] [data-testid="stMetricValue"] {{
        color:       {text} !important;
        font-weight: 800 !important;
        font-size:   2rem !important;
    }}

    /* ── Expanders ────────────────────────────────────────────────────── */
    div[data-testid="stExpander"] {{
        border:           1px solid {border} !important;
        border-radius:    6px !important;
        background-color: {surface} !important;
    }}
    div[data-testid="stExpander"] summary {{
        color: {text} !important;
    }}

    /* ── DataFrames ───────────────────────────────────────────────────── */
    [data-testid="stDataFrame"] {{
        border:        1px solid {border} !important;
        border-radius: 6px !important;
    }}

    /* ── Inputs ───────────────────────────────────────────────────────── */
    [data-testid="stTextInput"] input,
    [data-testid="stNumberInput"] input {{
        background-color: {surface2} !important;
        color:            {text}    !important;
        border-color:     {border}  !important;
    }}

    /* ── Dividers ─────────────────────────────────────────────────────── */
    hr {{
        border-color: {border} !important;
    }}

    /* ── Tab buttons ──────────────────────────────────────────────────── */
    button[data-baseweb="tab"] {{
        color: {text2} !important;
    }}
    button[data-baseweb="tab"][aria-selected="true"] {{
        color:        {text}   !important;
        border-color: {accent} !important;
    }}
    </style>
    """
