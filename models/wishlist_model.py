from database.db import db
from datetime import datetime


class Wishlist(db.Model):

    __tablename__ = "wishlist"

    # ── Core ──────────────────────────────────────────────────
    id         = db.Column(db.Integer, primary_key=True)
    user_id    = db.Column(db.Integer, db.ForeignKey("users.id"),    nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id"), nullable=False)

    # ── Timestamp ─────────────────────────────────────────────
    added_at   = db.Column(db.DateTime, default=datetime.utcnow)

    # ── Relationships ─────────────────────────────────────────
    # user    backref defined in User model
    # product backref defined in Product model

    def __repr__(self):
        return f"<Wishlist user={self.user_id} product={self.product_id}>"