import os
from datetime import timedelta

from flask import Flask, flash, redirect, request, session
from flask_socketio import SocketIO
from flask_migrate import Migrate
from flask_mail import Mail

# Blueprints
from routes.shop_routes  import shop
from routes.user_routes  import user
from routes.admin_routes import admin
from routes.tryon_routes import tryon
from routes.delivery_boy_routes import delivery

# Database
from database.db import db

# Models (import ALL so Flask-SQLAlchemy registers them)
from models import *
from utils.auth import get_csrf_token, get_request_csrf_token, validate_csrf_token

app = Flask(__name__)

# ── Secret key ────────────────────────────────────────────────
app.secret_key = os.environ.get("VEKTOR_SECRET_KEY", "VEKTOR_secret")

# ── Mail ──────────────────────────────────────────────────────
app.config['MAIL_SERVER']   = 'smtp.gmail.com'
app.config['MAIL_PORT']     = 587
app.config['MAIL_USE_TLS']  = True
app.config['MAIL_USERNAME'] = 'your_email@gmail.com'
app.config['MAIL_PASSWORD'] = 'your_app_password'
mail = Mail(app)

# ── Database ──────────────────────────────────────────────────
app.config["SQLALCHEMY_DATABASE_URI"]        = "mysql+pymysql://root:kaalx@localhost/VEKTOR"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

# ── Session cookies ───────────────────────────────────────────
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SECURE"]   = os.environ.get("VEKTOR_COOKIE_SECURE", "0") == "1"
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(hours=8)

# ── Init extensions ───────────────────────────────────────────
db.init_app(app)
migrate  = Migrate(app, db)
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="threading")

# ── Register blueprints ───────────────────────────────────────
app.register_blueprint(shop)
app.register_blueprint(user)
app.register_blueprint(admin)
app.register_blueprint(tryon)
app.register_blueprint(delivery)

# ── Register SocketIO events ──────────────────────────────────
from socketio_events import register_events
register_events(socketio)


@app.before_request
def protect_admin_csrf():
    if request.method not in ("POST", "PUT", "PATCH", "DELETE"):
        return None
    if not request.path.startswith("/admin"):
        return None
    token = get_request_csrf_token()
    if validate_csrf_token(token):
        return None
    flash("Security check failed. Please retry.", "error")
    if request.endpoint in ("admin.admin_login", "admin.admin_verify"):
        return redirect("/admin/login")
    return redirect(request.referrer or "/admin/dashboard")

# ── CART COUNT — injected into every template ─────────────────
@app.context_processor
def inject_cart_count():
    count = 0
    minicart_items = []
    minicart_total = 0
    if session.get("user_id"):
        from models.cart_model import Cart
        rows = Cart.query.filter_by(user_id=session["user_id"]).all()
        count = sum((r.quantity or 0) for r in rows)

        for r in rows:
            p = r.product
            if not p:
                continue
            qty = int(r.quantity or 0)
            line_total = int(round((p.final_price or 0) * qty))
            minicart_total += line_total
            minicart_items.append({
                "product_id": p.id,
                "name": p.name,
                "name_mr": p.name_mr,
                "image": p.image,
                "qty": qty,
                "size": r.size,
                "line_total": line_total,
            })

    return dict(
        cart_count=count,
        minicart_items=minicart_items,
        minicart_total=minicart_total,
    )

# ── CURRENT USER — injected into every template ───────────────
@app.context_processor
def inject_user():
    from utils.auth import decode_token

    user_id = session.get("user_id")
    if user_id:
        from models.user_model import User
        user_obj = User.query.get(user_id)
        if user_obj and user_obj.status != "Blocked":
            return dict(current_user=user_obj)

    token = request.cookies.get("token")
    if token:
        data = decode_token(token)
        if data:
            from models.user_model import User
            user_obj = User.query.get(data["user_id"])
            if user_obj and user_obj.status != "Blocked":
                return dict(current_user=user_obj)

    return dict(current_user=None)


@app.context_processor
def inject_csrf_token():
    return dict(csrf_token=get_csrf_token)

# ── Run ───────────────────────────────────────────────────────
if __name__ == "__main__":
    socketio.run(app, debug=True)   # ← use socketio.run, NOT app.run
