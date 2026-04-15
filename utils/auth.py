import jwt
import datetime
from functools import wraps
from flask import request, redirect, url_for, flash, make_response, session

from models.user_model import User
from models.admin_model import Admin

SECRET_KEY = "VEKTOR_secret"


# ═══════════════════════════════════════
# TOKEN HELPERS
# ═══════════════════════════════════════
def generate_token(user):
    payload = {
        "user_id": user.id,
        "exp": datetime.datetime.utcnow() + datetime.timedelta(hours=24),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm="HS256")


def decode_token(token):
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
    except Exception:
        return None


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
            session.pop("admin_id", None)
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