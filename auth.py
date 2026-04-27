import streamlit as st
from authlib.integrations.requests_client import OAuth2Session

from dotenv import load_dotenv
import os

load_dotenv()

CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")

REDIRECT_URI = "https://ajaxflyers.rotecode.com"

AUTHORIZATION_ENDPOINT = "https://accounts.google.com/o/oauth2/auth"
TOKEN_ENDPOINT = "https://oauth2.googleapis.com/token"
USERINFO_ENDPOINT = "https://openidconnect.googleapis.com/v1/userinfo"

SCOPE = "openid email profile"
ALLOWED_DOMAIN = "ajax.systems"


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

        # Domain restriction
        email = user.get("email", "")
        if not email.endswith(f"@{ALLOWED_DOMAIN}"):
            return "unauthorized"

        return user

    except Exception as e:
        return None


# -------------------------
# MAIN ENTRY
# -------------------------
def require_login():
    """
    Call this at the TOP of your app.
    Blocks execution until user is authenticated.
    """

    # Already logged in
    if "user" in st.session_state:
        return st.session_state["user"]

    # Try handling OAuth callback
    result = _handle_callback()

    if result == "unauthorized":
        st.error("Access restricted to ajax.systems accounts.")
        st.stop()

    if result:
        st.session_state["user"] = result
        st.query_params.clear()
        st.rerun()

    # Not logged in yet → show login
    st.title("Login Required")
    _login_link()
    st.stop()


# -------------------------
# LOGOUT
# -------------------------
def logout_button():
    if st.sidebar.button("Logout"):
        st.session_state.clear()
        st.rerun()