import streamlit as st
import os
from authlib.integrations.requests_client import OAuth2Session
from streamlit_cookies_manager import EncryptedCookieManager

# -------------------------
# CONFIG
# -------------------------
CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")
REDIRECT_URI = os.getenv("GOOGLE_REDIRECT_URI", "http://localhost:8501")

COOKIE_SECRET = os.getenv("COOKIE_SECRET", "dev_secret_change_me")

AUTHORIZATION_ENDPOINT = "https://accounts.google.com/o/oauth2/auth"
TOKEN_ENDPOINT = "https://oauth2.googleapis.com/token"
USERINFO_ENDPOINT = "https://openidconnect.googleapis.com/v1/userinfo"

SCOPE = "openid email profile"
ALLOWED_DOMAIN = "ajax.systems"


# -------------------------
# COOKIE MANAGER
# -------------------------
def get_cookie_manager():
    cookies = EncryptedCookieManager(
        prefix="flyer_app_",
        password=COOKIE_SECRET
    )

    if not cookies.ready():
        st.stop()

    return cookies


# -------------------------
# LOGIN LINK
# -------------------------
def _login_link():
    oauth = OAuth2Session(
        CLIENT_ID,
        CLIENT_SECRET,
        scope=SCOPE,
        redirect_uri=REDIRECT_URI
    )

    uri, state = oauth.create_authorization_url(AUTHORIZATION_ENDPOINT)

    st.session_state["oauth_state"] = state

    st.markdown(f"""
    <a href="{uri}" target="_self"
       style="
            display:inline-block;
            padding:8px 16px;
            background:#4285F4;
            color:white;
            border-radius:6px;
            text-decoration:none;
            font-weight:500;
       ">
        Sign in with Google
    </a>
    """, unsafe_allow_html=True)


# -------------------------
# HANDLE CALLBACK
# -------------------------
def _handle_callback():
    params = st.query_params

    if "code" not in params:
        return None

    oauth = OAuth2Session(
        CLIENT_ID,
        CLIENT_SECRET,
        scope=SCOPE,
        redirect_uri=REDIRECT_URI,
        state=st.session_state.get("oauth_state")
    )

    try:
        token = oauth.fetch_token(
            TOKEN_ENDPOINT,
            code=params["code"]
        )

        resp = oauth.get(USERINFO_ENDPOINT)
        user = resp.json()

        email = user.get("email", "")

        if not email.endswith(f"@{ALLOWED_DOMAIN}"):
            return "unauthorized"

        return user

    except Exception:
        return None


# -------------------------
# MAIN AUTH ENTRY
# -------------------------
def require_login():
    """
    Call at top of app.py
    """

    # -------------------------
    # LOCAL DEV BYPASS
    # -------------------------
    if os.getenv("AUTH_DISABLED") == "true":
        if "user" not in st.session_state:
            st.session_state["user"] = {
                "email": "dev@ajax.systems",
                "name": "Local Dev",
                "picture": "https://via.placeholder.com/40"
            }

        st.sidebar.warning("Auth Disabled (Local Dev)")
        return st.session_state["user"]

    # -------------------------
    # COOKIE RESTORE
    # -------------------------
    cookies = get_cookie_manager()

    if "user" not in st.session_state:
        if "user" in cookies and cookies["user"]:
            st.session_state["user"] = cookies["user"]

    # -------------------------
    # ALREADY LOGGED IN
    # -------------------------
    if "user" in st.session_state:
        return st.session_state["user"]

    # -------------------------
    # HANDLE OAUTH CALLBACK
    # -------------------------
    result = _handle_callback()

    if result == "unauthorized":
        st.error("Access restricted to ajax.systems accounts.")
        st.stop()

    if result:
        st.session_state["user"] = result
        cookies["user"] = result
        cookies.save()

        st.query_params.clear()
        st.rerun()

    # -------------------------
    # SHOW LOGIN
    # -------------------------
    st.title("Login Required")
    _login_link()
    st.stop()


# -------------------------
# LOGOUT
# -------------------------
def logout_button():
    cookies = get_cookie_manager()

    if st.sidebar.button("Logout"):
        st.session_state.clear()
        cookies["user"] = ""
        cookies.save()
        st.rerun()