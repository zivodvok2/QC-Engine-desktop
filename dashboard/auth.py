import bcrypt
import streamlit as st
import database as db
from config import ROLES, SL_ACCENT, SL_MUTED, SL_TX, SL_LINE, SL_SURFACE, SL_BG, SL_CRITICAL


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode(), hashed.encode())
    except Exception:
        return False


def login(email: str, password: str):
    user = db.get_user_by_email(email.strip().lower())
    if not user:
        return False, "Invalid email or password."
    if not verify_password(password, user["password_hash"]):
        return False, "Invalid email or password."
    st.session_state["logged_in"]    = True
    st.session_state["user_id"]      = user["id"]
    st.session_state["user_email"]   = user["email"]
    st.session_state["user_name"]    = user["full_name"]
    st.session_state["user_role"]    = user["role"]
    st.session_state["page"]         = "dashboard"
    st.session_state["project_id"]   = None
    st.session_state["project_tab"]  = "quality_report"
    return True, None


def logout():
    for key in list(st.session_state.keys()):
        del st.session_state[key]


def guest_login():
    st.session_state["logged_in"]    = True
    st.session_state["user_id"]      = None
    st.session_state["user_email"]   = None
    st.session_state["user_name"]    = "Guest"
    st.session_state["user_role"]    = "qc_executive"
    st.session_state["is_guest"]     = True
    st.session_state["page"]         = "dashboard"
    st.session_state["project_id"]   = None
    st.session_state["project_tab"]  = "quality_report"


def require_login() -> bool:
    return st.session_state.get("logged_in", False)


def require_role(*roles) -> bool:
    return st.session_state.get("user_role") in roles


def show_login_page():
    _, col, _ = st.columns([1, 1, 1])
    with col:
        # ── Brand mark ──
        st.markdown(
            f"""<div style="text-align:center;padding:2.5rem 0 2rem;">
                <div style="display:inline-flex;align-items:center;gap:12px;margin-bottom:0.5rem;">
                    <div style="width:40px;height:40px;background:{SL_ACCENT};border-radius:8px;
                         display:flex;align-items:center;justify-content:center;">
                        <span style="font-family:Syne,sans-serif;font-weight:800;color:#0b0c0f;
                                     font-size:0.9rem;">SL</span>
                    </div>
                    <span style="font-family:Syne,sans-serif;font-weight:800;font-size:1.8rem;
                                 color:{SL_TX};">Servallab</span>
                </div>
                <p style="font-family:DM Mono,monospace;font-size:0.82rem;color:{SL_MUTED};
                           margin:0;">QC Dashboard &nbsp;·&nbsp; Internal use only</p>
            </div>""",
            unsafe_allow_html=True,
        )

        # ── Card container ──
        st.markdown(
            f"""<div style="background:{SL_SURFACE};border:1px solid {SL_LINE};
                 border-radius:10px;padding:1.75rem 1.5rem 1.25rem;">""",
            unsafe_allow_html=True,
        )

        tab_login, tab_register = st.tabs(["Sign In", "Register"])

        with tab_login:
            with st.form("login_form"):
                email    = st.text_input("Email", placeholder="you@example.com")
                password = st.text_input("Password", type="password", placeholder="••••••••")
                submitted = st.form_submit_button(
                    "Sign In", use_container_width=True, type="primary"
                )
            if submitted:
                ok, err = login(email, password)
                if ok:
                    st.rerun()
                else:
                    st.markdown(
                        f'<div style="background:rgba(240,74,106,0.1);border:1px solid rgba(240,74,106,0.3);'
                        f'border-radius:6px;padding:0.6rem 0.8rem;font-size:0.82rem;color:{SL_CRITICAL};'
                        f'font-family:DM Mono,monospace;margin-top:0.5rem;">{err}</div>',
                        unsafe_allow_html=True,
                    )

        with tab_register:
            with st.form("register_form"):
                r_name  = st.text_input("Full Name")
                r_email = st.text_input("Email", placeholder="you@example.com")
                r_pass  = st.text_input("Password", type="password", placeholder="Min. 8 characters")
                r_pass2 = st.text_input("Confirm Password", type="password")
                submitted2 = st.form_submit_button(
                    "Create Account", use_container_width=True, type="primary"
                )
            if submitted2:
                if not r_name or not r_email or not r_pass:
                    st.error("All fields are required.")
                elif r_pass != r_pass2:
                    st.error("Passwords do not match.")
                elif len(r_pass) < 8:
                    st.error("Password must be at least 8 characters.")
                else:
                    ok, err = db.create_user(
                        r_email.strip().lower(),
                        hash_password(r_pass),
                        r_name.strip(),
                        "other",
                    )
                    if ok:
                        st.markdown(
                            f'<div style="background:rgba(74,240,160,0.1);border:1px solid rgba(74,240,160,0.25);'
                            f'border-radius:6px;padding:0.6rem 0.8rem;font-size:0.82rem;color:{SL_ACCENT};'
                            f'font-family:DM Mono,monospace;margin-top:0.5rem;">'
                            f'Account created. Sign in — your role will be set by an admin.</div>',
                            unsafe_allow_html=True,
                        )
                    else:
                        st.error(err)

        st.markdown("</div>", unsafe_allow_html=True)

        # ── Guest access ──
        st.markdown(
            f'<p style="text-align:center;font-size:0.75rem;color:{SL_MUTED};'
            f'font-family:DM Mono,monospace;margin-top:1rem;">No account?</p>',
            unsafe_allow_html=True,
        )
        if st.button("Continue as Guest", use_container_width=True):
            guest_login()
            st.rerun()
