import streamlit as st
import os
import json
from authlib.integrations.requests_client import OAuth2Session
from streamlit_cookies_manager import EncryptedCookieManager

# -------------------------
# CONFIG
# -------------------------
CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")
REDIRECT_URI = os.getenv("GOOGLE_REDIRECT_URI")
COOKIE_SECRET = os.getenv("COOKIE_SECRET")

AUTHORIZATION_ENDPOINT = "https://accounts.google.com/o/oauth2/auth"
TOKEN_ENDPOINT = "https://oauth2.googleapis.com/token"
USERINFO_ENDPOINT = "https://openidconnect.googleapis.com/v1/userinfo"

SCOPE = "openid email profile"
ALLOWED_DOMAIN = "ajax.systems"


# -------------------------
# COOKIE MANAGER (SESSION-BASED)
# -------------------------
def get_cookie_manager():
    if "cookie_manager" not in st.session_state:
        st.session_state["cookie_manager"] = EncryptedCookieManager(
            prefix="flyer_app_",
            password=COOKIE_SECRET
        )
    return st.session_state["cookie_manager"]


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
                "picture": "https://via.placeholder.com/40"
            }

        st.sidebar.warning("Auth Disabled (Local Dev)")
        return st.session_state["user"]

    # -------------------------
    # INIT COOKIE MANAGER
    # -------------------------
    cookies = get_cookie_manager()

    if not cookies.ready():
        st.markdown("Loading session...")
        st.session_state["_cookie_init"] = True
        st.rerun()

    # -------------------------
    # RESTORE FROM COOKIE
    # -------------------------
    if "user" not in st.session_state:
        if "user" in cookies and cookies["user"]:
            try:
                st.session_state["user"] = json.loads(cookies["user"])
            except Exception:
                pass

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
        cookies["user"] = json.dumps(result)
        cookies.save()

        st.query_params.clear()
        st.rerun()

    # -------------------------
    # AUTO-LOGIN (redirect)
    # -------------------------
    oauth = OAuth2Session(
        CLIENT_ID,
        CLIENT_SECRET,
        scope=SCOPE,
        redirect_uri=REDIRECT_URI
    )

    uri, state = oauth.create_authorization_url(
        AUTHORIZATION_ENDPOINT,
        prompt="consent"
    )

    st.session_state["oauth_state"] = state

    # prevent infinite redirect loop
    if "auth_redirected" not in st.session_state:
        st.session_state["auth_redirected"] = True

        st.markdown(
            f'<meta http-equiv="refresh" content="0; url={uri}">',
            unsafe_allow_html=True
        )

        st.markdown("Redirecting to login...")
        st.markdown(f"[Click here if not redirected]({uri})")

        st.stop()
    else:
        st.error("Login redirect failed. Please click below to continue.")
        st.markdown(f"[Continue to login]({uri})")
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