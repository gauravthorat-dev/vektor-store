from database.db import db
from datetime import datetime


class Notification(db.Model):
    """
    Admin notification system.
    Replaces the fake JS notification bell in admin-dashboard.
    Triggers: new order, low stock, new user registered, order status change.
    """

    __tablename__ = "notifications"

    # ── Core ──────────────────────────────────────────────────
    id         = db.Column(db.Integer, primary_key=True)

    # ── Content ───────────────────────────────────────────────
    title      = db.Column(db.String(150), nullable=False)  # short headline
    message    = db.Column(db.Text)                         # full message
    icon       = db.Column(db.String(10), default="📦")     # emoji icon for UI

    # ── Type ──────────────────────────────────────────────────
    # "order"   = new order placed
    # "stock"   = low stock warning
    # "user"    = new user registered
    # "payment" = payment received
    # "system"  = general system alert
    notif_type = db.Column(db.String(30), default="order")

    # ── Link ──────────────────────────────────────────────────
    link       = db.Column(db.String(200))   # e.g. "/admin/orders/42" — click to go there

    # ── Related records (optional) ────────────────────────────
    order_id   = db.Column(db.Integer, db.ForeignKey("orders.id"),   nullable=True)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id"), nullable=True)
    user_id    = db.Column(db.Integer, db.ForeignKey("users.id"),    nullable=True)

    # ── Read status ───────────────────────────────────────────
    is_read    = db.Column(db.Boolean, default=False)

    # ── Timestamp ─────────────────────────────────────────────
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # ── Relationships ─────────────────────────────────────────
    order   = db.relationship("Order",   backref="notifications", foreign_keys=[order_id])
    product = db.relationship("Product", backref="notifications", foreign_keys=[product_id])
    user    = db.relationship("User",    backref="notifications", foreign_keys=[user_id])

    # ── Class methods for creating standard notifications ─────

    @classmethod
    def new_order(cls, order):
        """Call this when a new order is placed."""
        return cls(
            title      = f"New Order #VK{order.id}",
            message    = f"{order.customer} placed an order for ₹{order.total_price}",
            icon       = "📦",
            notif_type = "order",
            link       = f"/admin/orders",
            order_id   = order.id,
            user_id    = order.user_id
        )

    @classmethod
    def low_stock(cls, product):
        """Call this when a product stock drops below threshold."""
        return cls(
            title      = f"Low Stock: {product.name}",
            message    = f"Only {product.stock} units left. Restock soon.",
            icon       = "⚠",
            notif_type = "stock",
            link       = f"/admin/edit-product/{product.id}",
            product_id = product.id
        )

    @classmethod
    def new_user(cls, user):
        """Call this when a new user registers."""
        return cls(
            title      = f"New Customer: {user.name}",
            message    = f"{user.email} just registered.",
            icon       = "👤",
            notif_type = "user",
            link       = f"/admin/customers",
            user_id    = user.id
        )

    def __repr__(self):
        return f"<Notification [{self.notif_type}] {self.title} read={self.is_read}>"