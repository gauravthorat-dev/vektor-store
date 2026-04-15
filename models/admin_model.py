from database.db import db
from datetime import datetime


class Admin(db.Model):
    """
    Separate admin accounts — independent from the users table.
    Keeps admin login secure and separate from customer accounts.
    Supports multiple admins with different permission levels.
    """

    __tablename__ = "admins"

    # ── Core ──────────────────────────────────────────────────
    id         = db.Column(db.Integer, primary_key=True)
    name       = db.Column(db.String(100), nullable=False)
    email      = db.Column(db.String(100), unique=True, nullable=False)
    password   = db.Column(db.String(200), nullable=False)   # bcrypt hashed

    # ── Permission level ──────────────────────────────────────
    # "superadmin" = full access (delete products, manage other admins)
    # "manager"    = manage orders, products, customers
    # "viewer"     = read-only analytics access
    level      = db.Column(db.String(30), default="manager")

    # ── Status ────────────────────────────────────────────────
    is_active  = db.Column(db.Boolean, default=True)

    # ── Session tracking ──────────────────────────────────────
    last_login = db.Column(db.DateTime)

    # ── Timestamps ────────────────────────────────────────────
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # ── Permission helpers ────────────────────────────────────
    @property
    def is_superadmin(self):
        return self.level == "superadmin"

    @property
    def can_delete(self):
        return self.level in ("superadmin",)

    @property
    def can_manage_products(self):
        return self.level in ("superadmin", "manager")

    @property
    def can_manage_orders(self):
        return self.level in ("superadmin", "manager")

    def record_login(self):
        """Call this on successful admin login."""
        self.last_login = datetime.utcnow()

    def __repr__(self):
        return f"<Admin {self.id} — {self.name} [{self.level}]>"