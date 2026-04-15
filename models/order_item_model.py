from database.db import db


class OrderItem(db.Model):

    __tablename__ = "order_items"

    # ── Core ──────────────────────────────────────────────────
    id         = db.Column(db.Integer, primary_key=True)
    product_name = db.Column(db.String(200))
    order_id   = db.Column(db.Integer, db.ForeignKey("orders.id"),   nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id"), nullable=False)
    quantity   = db.Column(db.Integer, nullable=False, default=1)

    # ── Price snapshot at time of order ───────────────────────
    # Store price at purchase time so price changes don't affect old orders
    price_at_purchase = db.Column(db.Float)

    # ── Relationships ─────────────────────────────────────────
    # order   backref defined in Order model
    # product backref defined in Product model

    # ── Admin helper property ─────────────────────────────────
    @property
    def subtotal(self):
        """Line item total = quantity × price at purchase."""
        if self.price_at_purchase:
            return round(self.price_at_purchase * self.quantity, 2)
        if self.product:
            return round(self.product.final_price * self.quantity, 2)
        return 0

    def __repr__(self):
        return f"<OrderItem order={self.order_id} product={self.product_id} qty={self.quantity}>"