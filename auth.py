import os
import streamlit as st
from authlib.integrations.requests_client import OAuth2Session

from db import fetch_one, execute
from session import create_session_token, sign_session, unsign_session


# =========================================================
# CONFIG
# =========================================================
CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")
REDIRECT_URI = os.getenv("GOOGLE_REDIRECT_URI")

AUTHORIZATION_ENDPOINT = "https://accounts.google.com/o/oauth2/auth"
TOKEN_ENDPOINT = "https://oauth2.googleapis.com/token"
USERINFO_ENDPOINT = "https://openidconnect.googleapis.com/v1/userinfo"

SCOPE = "openid email profile"
ALLOWED_DOMAIN = "ajax.systems"


# =========================================================
# COOKIE
# =========================================================
def get_cookie():
    if "cookie" not in st.session_state:
        st.session_state.cookie = {}
    return st.session_state.cookie


# =========================================================
# DB HELPERS
# =========================================================
def db_create_session(session_id, email):
    execute(
        "INSERT INTO sessions (session_id, user_email, expires_at) VALUES (?, ?, NULL)",
        (session_id, email)
    )


def db_get_session(session_id):
    return fetch_one(
        "SELECT * FROM sessions WHERE session_id = ?",
        (session_id,)
    )


def db_delete_session(session_id):
    execute(
        "DELETE FROM sessions WHERE session_id = ?",
        (session_id,)
    )


def get_or_create_user(user):
    existing = fetch_one(
        "SELECT * FROM users WHERE email = ?",
        (user["email"],)
    )

    if existing:
        return existing

    execute(
        "INSERT INTO users (email, name, picture_url, is_admin) VALUES (?, ?, ?, 0)",
        (user["email"], user.get("name"), user.get("picture"))
    )

    return fetch_one(
        "SELECT * FROM users WHERE email = ?",
        (user["email"],)
    )


# =========================================================
# OAUTH CALLBACK
# =========================================================
def handle_callback():
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


# =========================================================
# SESSION RESTORE
# =========================================================
def restore_session():
    cookie = get_cookie()
    signed = cookie.get("session")

    if not signed:
        return None

    session_id = unsign_session(signed)

    if not session_id:
        return None

    session = db_get_session(session_id)

    if not session:
        return None

    user = fetch_one(
        "SELECT * FROM users WHERE email = ?",
        (session["user_email"],)
    )

    if user:
        st.session_state["user"] = user
        return user

    return None


# =========================================================
# MAIN AUTH
# =========================================================
def require_login():

    # -------------------------
    # DEV MODE
    # -------------------------
    if os.getenv("AUTH_DISABLED", "false") == "true":

        dev_user = {
            "email": "dev@ajax.systems",
            "name": "Local Dev",
            "picture": "https://via.placeholder.com/40"
        }

        user = get_or_create_user(dev_user)

        session_id = create_session_token(user["email"])
        db_create_session(session_id, user["email"])

        cookie = get_cookie()
        cookie["session"] = sign_session(session_id)

        st.session_state["user"] = user

        st.sidebar.warning("DEV MODE")
        return user

    # -------------------------
    # RESTORE
    # -------------------------
    if "user" not in st.session_state:
        restored = restore_session()
        if restored:
            return restored

    if "user" in st.session_state:
        return st.session_state["user"]

    # -------------------------
    # CALLBACK
    # -------------------------
    result = handle_callback()

    if result == "unauthorized":
        st.error("Unauthorized domain")
        st.stop()

    if result:
        user = get_or_create_user(result)

        session_id = create_session_token(user["email"])
        db_create_session(session_id, user["email"])

        cookie = get_cookie()
        cookie["session"] = sign_session(session_id)

        st.session_state["user"] = user

        st.query_params.clear()
        st.rerun()

    # -------------------------
    # LOGIN
    # -------------------------
    oauth = OAuth2Session(
        CLIENT_ID,
        CLIENT_SECRET,
        scope=SCOPE,
        redirect_uri=REDIRECT_URI
    )

    uri, state = oauth.create_authorization_url(AUTHORIZATION_ENDPOINT)
    st.session_state["oauth_state"] = state

    st.markdown(f"[Login with Google]({uri})")
    st.stop()


# =========================================================
# LOGOUT / SWITCH
# =========================================================
def logout_button():

    col1, col2 = st.sidebar.columns(2)
    cookie = get_cookie()

    with col1:
        if st.button("Sign Out"):
            signed = cookie.get("session")

            if signed:
                session_id = unsign_session(signed)
                if session_id:
                    db_delete_session(session_id)

            cookie.clear()
            st.session_state.clear()
            st.rerun()

    with col2:
        if st.button("Switch User"):
            cookie.pop("session", None)
            st.session_state.pop("user", None)
            st.session_state.pop("oauth_state", None)
            st.rerun()


# =========================================================
# ADMIN CHECK
# =========================================================
def is_admin(user):
    return user.get("is_admin", 0) == 1