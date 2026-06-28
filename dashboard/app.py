import streamlit as st
import database as db
from auth import show_login_page, logout, require_login
from config import ROLES, ADMIN_ROLES, SL_ACCENT, SL_MUTED, SL_TX, SL_LINE, SL_SURFACE, SL_BG

st.set_page_config(
    page_title="Servallab — QC Dashboard",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Initialise DB once per session
if "db_init" not in st.session_state:
    db.init_db()
    import seed
    seed.run()
    st.session_state["db_init"] = True

# ── Global CSS — Servallab dark design system ──────────────────────────────
st.markdown("""
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=DM+Mono:ital,wght@0,300;0,400;0,500;1,400&family=Syne:wght@700;800&display=swap" rel="stylesheet">

<style>
/* ── Base ───────────────────────────────────────────────── */
html, body, [data-testid="stAppViewContainer"],
[data-testid="stMain"], section.main {
    background-color: #0b0c0f !important;
    color: #e8eaf2 !important;
    font-family: 'DM Mono', ui-monospace, monospace !important;
}
.main .block-container {
    background-color: #0b0c0f !important;
    padding-top: 1.5rem !important;
    max-width: 1400px !important;
}

/* ── Sidebar ───────────────────────────────────────────── */
[data-testid="stSidebar"] {
    background-color: #111318 !important;
    border-right: 1px solid #1f2330 !important;
}
[data-testid="stSidebar"] > div:first-child {
    background-color: #111318 !important;
}
[data-testid="stSidebar"] * {
    font-family: 'DM Mono', ui-monospace, monospace !important;
}
[data-testid="stSidebar"] p,
[data-testid="stSidebar"] span,
[data-testid="stSidebar"] label,
[data-testid="stSidebar"] div {
    color: #e8eaf2 !important;
}

/* Sidebar nav buttons */
[data-testid="stSidebar"] .stButton > button {
    background: transparent !important;
    color: #8b90a8 !important;
    border: 1px solid #1f2330 !important;
    border-radius: 6px !important;
    width: 100% !important;
    text-align: left !important;
    padding: 0.45rem 0.8rem !important;
    font-size: 0.82rem !important;
    font-family: 'DM Mono', monospace !important;
    transition: all 0.15s ease !important;
    margin: 2px 0 !important;
}
[data-testid="stSidebar"] .stButton > button:hover {
    background: rgba(74, 240, 160, 0.07) !important;
    border-color: #4af0a0 !important;
    color: #4af0a0 !important;
}

/* ── Headings ───────────────────────────────────────────── */
h1, h2, h3, h4 {
    font-family: 'Syne', ui-sans-serif, sans-serif !important;
    color: #e8eaf2 !important;
}

/* ── Buttons ────────────────────────────────────────────── */
.stButton > button {
    background: transparent !important;
    border: 1px solid #1f2330 !important;
    color: #8b90a8 !important;
    border-radius: 6px !important;
    font-family: 'DM Mono', monospace !important;
    font-size: 0.83rem !important;
    transition: all 0.15s ease !important;
}
.stButton > button:hover {
    border-color: #8b90a8 !important;
    color: #e8eaf2 !important;
    background: rgba(255,255,255,0.03) !important;
}
button[kind="primary"],
.stButton > button[data-testid*="primary"] {
    background: #4af0a0 !important;
    color: #0b0c0f !important;
    font-weight: 700 !important;
    border: none !important;
    font-family: 'Syne', sans-serif !important;
}
button[kind="primary"]:hover {
    background: #2ab870 !important;
}

/* ── Metrics ────────────────────────────────────────────── */
div[data-testid="metric-container"] {
    background: #111318 !important;
    border: 1px solid #1f2330 !important;
    border-radius: 8px !important;
    padding: 1rem !important;
}
div[data-testid="metric-container"] label {
    color: #8b90a8 !important;
    font-size: 0.7rem !important;
    text-transform: uppercase !important;
    letter-spacing: 0.08em !important;
    font-family: 'DM Mono', monospace !important;
}
div[data-testid="stMetricValue"] > div {
    color: #e8eaf2 !important;
    font-family: 'Syne', sans-serif !important;
    font-size: 1.7rem !important;
    font-weight: 700 !important;
}
div[data-testid="stMetricDelta"] {
    font-size: 0.78rem !important;
}

/* ── Tabs ───────────────────────────────────────────────── */
.stTabs [data-baseweb="tab-list"] {
    background: #111318 !important;
    border-bottom: 1px solid #1f2330 !important;
    gap: 0 !important;
    padding: 0 !important;
}
.stTabs [data-baseweb="tab"] {
    background: transparent !important;
    color: #8b90a8 !important;
    font-family: 'DM Mono', monospace !important;
    font-size: 0.83rem !important;
    padding: 0.7rem 1.1rem !important;
    border-radius: 0 !important;
    border-bottom: 2px solid transparent !important;
}
.stTabs [aria-selected="true"][data-baseweb="tab"] {
    color: #4af0a0 !important;
    border-bottom: 2px solid #4af0a0 !important;
    background: transparent !important;
}
.stTabs [data-baseweb="tab-highlight"] {
    display: none !important;
}
.stTabs [data-baseweb="tab-panel"] {
    background: #0b0c0f !important;
    padding-top: 1.25rem !important;
}

/* ── Inputs & selects ───────────────────────────────────── */
.stTextInput input,
.stNumberInput input,
.stTextArea textarea {
    background: #181b22 !important;
    border: 1px solid #1f2330 !important;
    color: #e8eaf2 !important;
    border-radius: 6px !important;
    font-family: 'DM Mono', monospace !important;
    font-size: 0.85rem !important;
}
.stTextInput input:focus,
.stNumberInput input:focus,
.stTextArea textarea:focus {
    border-color: #4af0a0 !important;
    box-shadow: 0 0 0 2px rgba(74,240,160,0.12) !important;
}
.stSelectbox > div > div,
.stMultiSelect > div > div {
    background: #181b22 !important;
    border: 1px solid #1f2330 !important;
    color: #e8eaf2 !important;
    border-radius: 6px !important;
}

/* ── Multiselect tags ───────────────────────────────────── */
[data-baseweb="tag"] {
    background: rgba(74,240,160,0.12) !important;
    border: 1px solid rgba(74,240,160,0.25) !important;
    border-radius: 4px !important;
}
[data-baseweb="tag"] span {
    color: #4af0a0 !important;
}

/* ── File uploader ──────────────────────────────────────── */
[data-testid="stFileUploader"] {
    background: #111318 !important;
    border: 1px dashed #1f2330 !important;
    border-radius: 8px !important;
}
[data-testid="stFileUploader"]:hover {
    border-color: #4af0a0 !important;
}

/* ── Dataframes ─────────────────────────────────────────── */
[data-testid="stDataFrame"] {
    border: 1px solid #1f2330 !important;
    border-radius: 8px !important;
    overflow: hidden !important;
}
[data-testid="stDataFrame"] th {
    background: #181b22 !important;
    color: #8b90a8 !important;
    font-size: 0.75rem !important;
    text-transform: uppercase !important;
    letter-spacing: 0.06em !important;
}
[data-testid="stDataFrame"] td {
    background: #111318 !important;
    color: #e8eaf2 !important;
    font-size: 0.83rem !important;
}

/* ── Progress bar ───────────────────────────────────────── */
[data-testid="stProgress"] > div > div {
    background: #4af0a0 !important;
}
[data-testid="stProgress"] {
    background: #1f2330 !important;
    border-radius: 4px !important;
}

/* ── Alert boxes ────────────────────────────────────────── */
div[data-testid="stAlert"] {
    border-radius: 6px !important;
    font-family: 'DM Mono', monospace !important;
    font-size: 0.85rem !important;
}

/* ── Expander ───────────────────────────────────────────── */
[data-testid="stExpander"] {
    border: 1px solid #1f2330 !important;
    border-radius: 8px !important;
    background: #111318 !important;
}
[data-testid="stExpander"] summary {
    color: #e8eaf2 !important;
    font-family: 'DM Mono', monospace !important;
}

/* ── Dividers ───────────────────────────────────────────── */
hr {
    border-color: #1f2330 !important;
    margin: 1.2rem 0 !important;
}

/* ── Caption / small text ───────────────────────────────── */
.stCaption, [data-testid="stCaption"] {
    color: #8b90a8 !important;
    font-size: 0.75rem !important;
}

/* ── Tooltips ───────────────────────────────────────────── */
[data-testid="stTooltipIcon"] {
    color: #8b90a8 !important;
}

/* ── Scrollbar ──────────────────────────────────────────── */
::-webkit-scrollbar { width: 5px; height: 5px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb { background: #1f2330; border-radius: 3px; }
::-webkit-scrollbar-thumb:hover { background: #8b90a8; }

/* ── Date inputs ────────────────────────────────────────── */
[data-testid="stDateInput"] input {
    background: #181b22 !important;
    border: 1px solid #1f2330 !important;
    color: #e8eaf2 !important;
    border-radius: 6px !important;
}
</style>
""", unsafe_allow_html=True)


# ── Sidebar ────────────────────────────────────────────────────────────────

def _nav_button(label: str, page_key: str, icon: str = ""):
    clicked = st.button(f"{icon}  {label}", key=f"nav_{page_key}", use_container_width=True)
    if clicked:
        st.session_state["page"] = page_key
        if page_key == "dashboard":
            st.session_state["project_id"] = None
        st.rerun()


def _sidebar():
    with st.sidebar:
        # ── Brand ──
        st.markdown(
            f"""<div style="padding:1.25rem 0 1.5rem; display:flex; align-items:center; gap:10px;">
                <div style="width:32px;height:32px;background:{SL_ACCENT};border-radius:6px;
                     display:flex;align-items:center;justify-content:center;flex-shrink:0;">
                    <span style="font-family:Syne,sans-serif;font-weight:800;color:#0b0c0f;
                                 font-size:0.8rem;letter-spacing:-0.5px;">SL</span>
                </div>
                <div>
                    <div style="font-family:Syne,sans-serif;font-weight:800;font-size:1rem;
                                color:{SL_TX};line-height:1;">Servallab</div>
                    <div style="font-size:0.68rem;color:{SL_MUTED};line-height:1;margin-top:2px;">
                        QC Dashboard</div>
                </div>
            </div>""",
            unsafe_allow_html=True,
        )

        # ── User chip ──
        role      = st.session_state.get("user_role", "other")
        name      = st.session_state.get("user_name", "")
        is_guest  = st.session_state.get("is_guest", False)
        role_label = ROLES.get(role, role)
        guest_tag = (
            f'<span style="background:{SL_ACCENT};color:#0b0c0f;font-size:0.6rem;'
            f'padding:1px 6px;border-radius:3px;font-weight:700;margin-left:6px;">GUEST</span>'
            if is_guest else ""
        )
        st.markdown(
            f"""<div style="background:rgba(255,255,255,0.04);border:1px solid {SL_LINE};
                 border-radius:7px;padding:0.6rem 0.75rem;margin-bottom:1.25rem;">
                <div style="font-size:0.82rem;color:{SL_TX};font-weight:500;">
                    {name}{guest_tag}</div>
                <div style="font-size:0.7rem;color:{SL_ACCENT};margin-top:2px;">{role_label}</div>
            </div>""",
            unsafe_allow_html=True,
        )

        # ── Nav ──
        st.markdown(
            f'<p style="font-size:0.65rem;color:{SL_MUTED};text-transform:uppercase;'
            f'letter-spacing:0.1em;margin-bottom:4px;">Navigation</p>',
            unsafe_allow_html=True,
        )
        _nav_button("Dashboard", "dashboard", "⬛")
        _nav_button("Interviewers", "interviewers", "◈")
        if role in ADMIN_ROLES:
            _nav_button("Admin Panel", "admin", "⚙")

        # ── Divider + sign out ──
        st.markdown(f'<hr style="border-color:{SL_LINE};margin:1rem 0;">', unsafe_allow_html=True)
        sign_out_label = "Exit Guest" if is_guest else "Sign Out"
        if st.button(f"↩  {sign_out_label}", key="nav_logout", use_container_width=True):
            logout()
            st.rerun()

        # ── Footer ──
        st.markdown(
            f"""<div style="position:fixed;bottom:1rem;left:0.75rem;right:0.75rem;
                 font-size:0.65rem;color:{SL_MUTED};text-align:center;
                 border-top:1px solid {SL_LINE};padding-top:0.6rem;">
                Servallab · QC Dashboard · Internal use only
            </div>""",
            unsafe_allow_html=True,
        )


# ── Router ─────────────────────────────────────────────────────────────────

def _route():
    page = st.session_state.get("page", "dashboard")
    if page == "dashboard":
        from pages_modules import dashboard
        dashboard.show()
    elif page == "project_detail":
        from pages_modules import project_detail
        project_detail.show()
    elif page == "interviewers":
        from pages_modules import interviewers
        interviewers.show()
    elif page == "admin":
        from pages_modules import admin
        admin.show()
    else:
        from pages_modules import dashboard
        dashboard.show()


# ── Entry ──────────────────────────────────────────────────────────────────

def main():
    if not require_login():
        show_login_page()
        return
    _sidebar()
    with st.container():
        _route()


if __name__ == "__main__":
    main()
else:
    main()
