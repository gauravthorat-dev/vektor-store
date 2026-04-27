from database.db import db
from datetime import datetime
import secrets


class Order(db.Model):

    __tablename__ = "orders"

    # ── Core ──────────────────────────────────────────────────
    id          = db.Column(db.Integer, primary_key=True)
    user_id     = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    total_price = db.Column(db.Float, nullable=False)

    # ── Status ────────────────────────────────────────────────
    # Values: "Pending" | "Confirmed" | "Processing" | "Shipped" | "Out for Delivery" | "Delivered" | "Cancelled"
    status      = db.Column(db.String(50), default="Pending")

    # ── Payment ───────────────────────────────────────────────
    payment_method = db.Column(db.String(50), default="COD")
    payment_status = db.Column(db.String(50), default="Pending")  # "Pending" | "Paid" | "Refunded"

    # ── Shipping Address (snapshot at order time) ─────────────
    shipping_name    = db.Column(db.String(100))
    shipping_phone   = db.Column(db.String(20))
    shipping_address = db.Column(db.Text)
    shipping_city    = db.Column(db.String(100))
    shipping_pincode = db.Column(db.String(10))
    shipping_state   = db.Column(db.String(100))
    shipping_country = db.Column(db.String(50))

    # ── Coupon ────────────────────────────────────────────────
    coupon_id       = db.Column(db.Integer, db.ForeignKey("coupons.id"))
    discount_amount = db.Column(db.Float, default=0)

    # ── Delivery Boy ──────────────────────────────────────────
    delivery_boy_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    delivery_otp    = db.Column(db.String(6), nullable=True)   # 6-digit OTP for delivery confirmation
    otp_verified    = db.Column(db.Boolean, default=False)
    otp_attempts    = db.Column(db.Integer, default=0)
    otp_locked_at   = db.Column(db.DateTime, nullable=True)

    # ── Stage Timestamps ──────────────────────────────────────
    confirmed_at        = db.Column(db.DateTime, nullable=True)
    processing_at       = db.Column(db.DateTime, nullable=True)
    shipped_at          = db.Column(db.DateTime, nullable=True)
    out_for_delivery_at = db.Column(db.DateTime, nullable=True)
    delivered_at        = db.Column(db.DateTime, nullable=True)
    cancelled_at        = db.Column(db.DateTime, nullable=True)

    # ── Cancellation ─────────────────────────────────────────
    cancel_reason = db.Column(db.String(255), nullable=True)

    # ── Timestamps ────────────────────────────────────────────
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # ── Relationships ─────────────────────────────────────────
    items = db.relationship("OrderItem", backref="order", lazy=True, cascade="all, delete-orphan")

    # Primary user relationship — must specify foreign_keys because two FK paths exist
    user = db.relationship(
        "User",
        foreign_keys=[user_id],
        backref=db.backref("orders", lazy=True),
    )

    # Delivery boy relationship — separate FK path, no conflicting backref
    delivery_boy = db.relationship(
        "User",
        foreign_keys=[delivery_boy_id],
        backref=db.backref("assigned_orders", lazy=True),
    )

    # ── OTP Helper ───────────────────────────────────────────
    def generate_otp(self):
        """Generate a fresh 6-digit OTP and save to model (call db.session.commit() after)."""
        self.delivery_otp = f"{secrets.randbelow(1_000_000):06d}"
        self.otp_verified = False
        self.otp_attempts = 0
        self.otp_locked_at = None
        return self.delivery_otp

    # ── Status Transition Helper ─────────────────────────────
    def set_status(self, new_status):
        """
        Transition order to new_status and stamp the matching timestamp.
        Call db.session.commit() after.
        """
        now = datetime.utcnow()
        self.status = new_status

        stamp_map = {
            "Confirmed":        "confirmed_at",
            "Processing":       "processing_at",
            "Shipped":          "shipped_at",
            "Out for Delivery":  "out_for_delivery_at",
            "Delivered":        "delivered_at",
            "Cancelled":        "cancelled_at",
        }
        attr = stamp_map.get(new_status)
        if attr:
            setattr(self, attr, now)

    # ── Admin helper properties ───────────────────────────────
    @property
    def customer(self):
        return self.user.name if self.user else "Unknown"

    @property
    def date(self):
        return self.created_at

    @property
    def total(self):
        return self.total_price

    @property
    def products(self):
        result = []
        for item in self.items:
            product = item.product
            if product:
                result.append({
                    "name":  product.name,
                    "qty":   item.quantity,
                    "price": product.final_price * item.quantity,
                })
        return result

    @property
    def status_timeline(self):
        """
        Returns ordered list of status stages with timestamps.
        Used for timeline UI in admin and buyer views.
        """
        stages = [
            ("Pending",          self.created_at),
            ("Confirmed",        self.confirmed_at),
            ("Processing",       self.processing_at),
            ("Shipped",          self.shipped_at),
            ("Out for Delivery", self.out_for_delivery_at),
            ("Delivered",        self.delivered_at),
        ]
        # Cancelled replaces everything after it
        if self.status == "Cancelled":
            stages.append(("Cancelled", self.cancelled_at))

        result = []
        for label, ts in stages:
            result.append({
                "label":     label,
                "timestamp": ts,
                "done":      ts is not None or label == "Pending",
                "active":    label == self.status,
            })
        return result

    def __repr__(self):
        return f"<Order {self.id} — ₹{self.total_price} [{self.status}]>"
