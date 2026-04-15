from database.db import db


class Cart(db.Model):

    __tablename__ = "cart"

    # ── Core ──────────────────────────────────────────────────
    id         = db.Column(db.Integer, primary_key=True)
    user_id    = db.Column(db.Integer, db.ForeignKey("users.id"),    nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id"), nullable=False)
    quantity   = db.Column(db.Integer, default=1, nullable=False)

    size = db.Column(db.String(20))
    color = db.Column(db.String(20))

    # ── Relationships ─────────────────────────────────────────
    # user    backref defined in User model
    # product backref defined in Product model

    # ── Admin helper property ─────────────────────────────────
    @property
    def subtotal(self):
        """Line total for cart summary."""
        if self.product:
            return round(self.product.final_price * self.quantity, 2)
        return 0

    def __repr__(self):
        return f"<Cart user={self.user_id} product={self.product_id} qty={self.quantity}>"