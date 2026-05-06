import os
import uuid
from datetime import datetime, timedelta
from itsdangerous import URLSafeSerializer

SECRET = os.getenv("COOKIE_SECRET", "dev-secret-change-me")
serializer = URLSafeSerializer(SECRET)

SESSION_DURATION_HOURS = 24


def create_session_token(email):
    session_id = str(uuid.uuid4())

    return session_id


def sign_session(session_id):
    return serializer.dumps(session_id)


def unsign_session(token):
    try:
        return serializer.loads(token)
    except Exception:
        return None


def session_expiry():
    return datetime.utcnow() + timedelta(hours=SESSION_DURATION_HOURS)