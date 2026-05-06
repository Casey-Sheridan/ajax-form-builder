import streamlit as st
import os
from authlib.integrations.requests_client import OAuth2Session

# -------------------------
# CONFIG
# -------------------------
CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")
REDIRECT_URI = os.getenv("GOOGLE_REDIRECT_URI")

AUTHORIZATION_ENDPOINT = "https://accounts.google.com/o/oauth2/auth"
TOKEN_ENDPOINT = "https://oauth2.googleapis.com/token"
USERINFO_ENDPOINT = "https://openidconnect.googleapis.com/v1/userinfo"

SCOPE = "openid email profile"
ALLOWED_DOMAIN = "ajax.systems"


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
        state=st.session_state.get("oauth_state"),
    )

    try:
        oauth.fetch_token(TOKEN_ENDPOINT, code=params["code"])
        user = oauth.get(USERINFO_ENDPOINT).json()

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

    # -------------------------
    # LOCAL DEV BYPASS
    # -------------------------
    if os.getenv("AUTH_DISABLED") == "true":
        if "user" not in st.session_state:
            st.session_state["user"] = {
                "email": "dev@ajax.systems",
                "name": "Local Dev",
                "picture": "https://via.placeholder.com/40",
            }

        st.sidebar.warning("Auth Disabled (Local Dev)")
        return st.session_state["user"]

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

        # clean URL
        st.query_params.clear()
        st.rerun()

    # -------------------------
    # AUTO-LOGIN (redirect once)
    # -------------------------
    oauth = OAuth2Session(
        CLIENT_ID,
        CLIENT_SECRET,
        scope=SCOPE,
        redirect_uri=REDIRECT_URI,
    )

    prompt = None
    if st.session_state.get("force_account_select"):
        prompt = "select_account"
        st.session_state.pop("force_account_select")

    if prompt:
        uri, state = oauth.create_authorization_url(
            AUTHORIZATION_ENDPOINT,
            prompt=prompt
        )
    else:
        uri, state = oauth.create_authorization_url(
            AUTHORIZATION_ENDPOINT
        )

    st.session_state["oauth_state"] = state

    # prevent infinite redirect loop
    if not st.session_state.get("auth_redirected"):
        st.session_state["auth_redirected"] = True

        st.markdown(
            f'<meta http-equiv="refresh" content="0; url={uri}">',
            unsafe_allow_html=True,
        )

        st.markdown("Redirecting to login...")
        st.markdown(f"[Click here if not redirected]({uri})")
        st.stop()

    # fallback if redirect fails
    st.error("Login redirect failed. Please click below.")
    st.markdown(f"[Continue to login]({uri})")
    st.stop()


# -------------------------
# LOGOUT
# -------------------------
def logout_button():

    col1, col2 = st.sidebar.columns(2)

    with col1:
        if st.button("Sign Out"):
            st.session_state.clear()
            st.session_state["force_account_select"] = True
            st.rerun()

    with col2:
        if st.button("Switch User"):
            # keep session but force account picker
            st.session_state.pop("user", None)
            st.session_state["force_account_select"] = True
            st.session_state.pop("auth_redirected", None)
            st.rerun()