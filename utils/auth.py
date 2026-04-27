import datetime
import hmac
import os
import secrets
from functools import wraps

import jwt
from flask import flash, redirect, request, session, url_for

from models.admin_model import Admin
from models.user_model import User

SECRET_KEY = os.environ.get("VEKTOR_SECRET_KEY", "VEKTOR_secret")
JWT_HOURS = int(os.environ.get("VEKTOR_JWT_HOURS", "24"))
CSRF_SESSION_KEY = "_csrf_token"


# ═══════════════════════════════════════
# TOKEN HELPERS
# ═══════════════════════════════════════
def generate_token(user):
    payload = {
        "user_id": user.id,
        "exp": datetime.datetime.utcnow() + datetime.timedelta(hours=JWT_HOURS),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm="HS256")


def decode_token(token):
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
    except Exception:
        return None


# CSRF HELPERS
def get_csrf_token():
    token = session.get(CSRF_SESSION_KEY)
    if not token:
        token = secrets.token_urlsafe(32)
        session[CSRF_SESSION_KEY] = token
    return token


def reset_csrf_token():
    session.pop(CSRF_SESSION_KEY, None)


def validate_csrf_token(token):
    if not token:
        return False
    expected = session.get(CSRF_SESSION_KEY)
    if not expected:
        return False
    return hmac.compare_digest(token, expected)


def get_request_csrf_token():
    return (
        request.form.get("csrf_token")
        or request.headers.get("X-CSRF-Token")
        or request.headers.get("X-CSRFToken")
    )


def is_login_rate_limited(scope="admin_login", max_failures=5, lock_minutes=10):
    fail_key = f"{scope}_failures"
    lock_key = f"{scope}_lock_until"
    now = datetime.datetime.utcnow()
    lock_until_iso = session.get(lock_key)
    if lock_until_iso:
        try:
            lock_until = datetime.datetime.fromisoformat(lock_until_iso)
            if now < lock_until:
                remaining = int((lock_until - now).total_seconds())
                return True, remaining
        except ValueError:
            pass
        session.pop(lock_key, None)
    failures = int(session.get(fail_key, 0))
    return failures >= max_failures, 0


def register_login_failure(scope="admin_login", max_failures=5, lock_minutes=10):
    fail_key = f"{scope}_failures"
    lock_key = f"{scope}_lock_until"
    failures = int(session.get(fail_key, 0)) + 1
    session[fail_key] = failures
    if failures >= max_failures:
        lock_until = datetime.datetime.utcnow() + datetime.timedelta(minutes=lock_minutes)
        session[lock_key] = lock_until.isoformat()
        return True
    return False


def clear_login_failures(scope="admin_login"):
    session.pop(f"{scope}_failures", None)
    session.pop(f"{scope}_lock_until", None)


def set_admin_session(admin_user):
    session["admin_id"] = admin_user.id
    session["admin_name"] = admin_user.name
    session["admin_level"] = admin_user.level
    session["admin_logged_in_at"] = datetime.datetime.utcnow().isoformat()


def clear_admin_session():
    session.pop("admin_id", None)
    session.pop("admin_name", None)
    session.pop("admin_level", None)
    session.pop("admin_logged_in_at", None)


# ═══════════════════════════════════════
# USER AUTH (JWT + SESSION)
# ═══════════════════════════════════════
def jwt_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):

        # Session check
        if session.get("user_id"):
            user = User.query.get(session["user_id"])
            if user and user.status != "Blocked":
                return f(*args, **kwargs)

        # JWT check
        token = request.cookies.get("token")
        if not token:
            return redirect(url_for("user.login"))

        data = decode_token(token)
        if not data:
            return redirect(url_for("user.login"))

        user = User.query.get(data["user_id"])
        if not user or user.status == "Blocked":
            flash("Account blocked or invalid")
            return redirect(url_for("user.login"))

        # Restore session
        session["user_id"]   = user.id
        session["user_name"] = user.name
        session["user_role"] = user.role   # ✅ needed for SocketIO room routing

        return f(*args, **kwargs)

    return wrapper


# ═══════════════════════════════════════
# ADMIN LOGIN REQUIRED (ONLY ADMIN TABLE)
# ═══════════════════════════════════════
def admin_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):

        admin_id = session.get("admin_id")

        if not admin_id:
            flash("Please login as admin", "error")
            return redirect(url_for("admin.admin_login"))

        admin = Admin.query.get(admin_id)

        if not admin or not admin.is_active:
            clear_admin_session()
            flash("Invalid admin session", "error")
            return redirect(url_for("admin.admin_login"))

        return f(*args, **kwargs)

    return wrapper


# ═══════════════════════════════════════
# MANAGER ACCESS (SUPERADMIN + MANAGER)
# ═══════════════════════════════════════
def manager_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):

        admin_id = session.get("admin_id")
        if not admin_id:
            return redirect(url_for("admin.admin_login"))

        admin = Admin.query.get(admin_id)

        if not admin or admin.level not in ("superadmin", "manager"):
            flash("Access denied — Manager required", "error")
            return redirect(url_for("admin.dashboard"))

        return f(*args, **kwargs)

    return wrapper


# ═══════════════════════════════════════
# SUPERADMIN ONLY
# ═══════════════════════════════════════
def superadmin_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):

        admin_id = session.get("admin_id")
        if not admin_id:
            return redirect(url_for("admin.admin_login"))

        admin = Admin.query.get(admin_id)

        if not admin or admin.level != "superadmin":
            flash("Access denied — Superadmin only", "error")
            return redirect(url_for("admin.dashboard"))

        return f(*args, **kwargs)

    return wrapper
