from database.db import db
from datetime import datetime


class User(db.Model):

    __tablename__ = "users"

    # ── Core ──────────────────────────────────────────────────
    id          = db.Column(db.Integer, primary_key=True)
    name        = db.Column(db.String(100), nullable=False)
    email       = db.Column(db.String(100), unique=True, nullable=False)
    password    = db.Column(db.String(200), nullable=False)
    phone       = db.Column(db.String(20))
    is_verified = db.Column(db.Boolean, default=False)

    # ── Role & Status ─────────────────────────────────────────
    # "user" | "admin" | "delivery_boy"
    role   = db.Column(db.String(20), default="user")
    status = db.Column(db.String(20), default="Active")  # "Active" | "Blocked"
    is_online = db.Column(db.Boolean, default=False)
    last_heartbeat = db.Column(db.DateTime, nullable=True)

    # ── Timestamps ────────────────────────────────────────────
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # ── Relationships ─────────────────────────────────────────
    # NOTE: `orders` and `assigned_orders` backrefs are defined in order_model.py
    # via foreign_keys to avoid AmbiguousForeignKeysError (two FK paths: user_id & delivery_boy_id)
    cart     = db.relationship("Cart",     backref="user", lazy=True, cascade="all, delete-orphan")
    wishlist = db.relationship("Wishlist", backref="user", lazy=True, cascade="all, delete-orphan")
    # addresses backref is defined in address_model.py

    # ── Admin helper properties ───────────────────────────────
    @property
    def total_orders(self):
        return len(self.orders)

    @property
    def total_spent(self):
        return sum(o.total_price for o in self.orders if o.total_price)

    @property
    def last_order(self):
        if not self.orders:
            return None
        return max(o.created_at for o in self.orders if o.created_at)

    def __repr__(self):
        return f"<User {self.id} — {self.name} ({self.role})>"
