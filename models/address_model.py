from database.db import db
from datetime import datetime


class Address(db.Model):
    """
    Saved delivery addresses for a user.
    Users can save multiple addresses and pick one at checkout.
    Admin can see address in customer detail popup.
    """

    __tablename__ = "addresses"

    # ── Core ──────────────────────────────────────────────────
    id         = db.Column(db.Integer, primary_key=True)
    user_id    = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)

    # ── Address Fields ────────────────────────────────────────
    full_name  = db.Column(db.String(100), nullable=False)
    phone      = db.Column(db.String(20),  nullable=False)
    line1      = db.Column(db.String(200), nullable=False)   # House / Flat / Building
    line2      = db.Column(db.String(200))                   # Street / Area (optional)
    city       = db.Column(db.String(100), nullable=False)
    state      = db.Column(db.String(100), default="Maharashtra")
    pincode    = db.Column(db.String(10),  nullable=False)
    country    = db.Column(db.String(50),  default="India")

    # ── Default flag ──────────────────────────────────────────
    is_default = db.Column(db.Boolean, default=False)

    # ── Timestamp ─────────────────────────────────────────────
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # ── Relationship ──────────────────────────────────────────
    user = db.relationship("User", backref="addresses")

    # ── Helper ────────────────────────────────────────────────
    @property
    def full_address(self):
        """Single-line address string for display."""
        parts = [self.line1]
        if self.line2:
            parts.append(self.line2)
        parts += [self.city, self.state, self.pincode, self.country]
        return ", ".join(parts)

    def __repr__(self):
        return f"<Address user={self.user_id} city={self.city} pincode={self.pincode}>"