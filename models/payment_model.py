from database.db import db
from datetime import datetime


class Payment(db.Model):
    """
    Payment transaction records.
    One record per payment attempt — separate from Order so
    refunds, retries and gateway responses are tracked cleanly.
    Ready for Razorpay / PhonePe / UPI integration.
    """

    __tablename__ = "payments"

    # ── Core ──────────────────────────────────────────────────
    id       = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey("orders.id"), nullable=False)
    user_id  = db.Column(db.Integer, db.ForeignKey("users.id"),  nullable=False)

    # ── Amount ────────────────────────────────────────────────
    amount   = db.Column(db.Float, nullable=False)
    currency = db.Column(db.String(10), default="INR")

    # ── Method ────────────────────────────────────────────────
    # "COD" | "UPI" | "Razorpay" | "PhonePe" | "Card" | "NetBanking"
    method   = db.Column(db.String(50), default="COD")

    # ── Status ────────────────────────────────────────────────
    # "Pending" | "Paid" | "Failed" | "Refunded"
    status   = db.Column(db.String(30), default="Pending")

    # ── Gateway fields (for online payments) ──────────────────
    gateway_order_id    = db.Column(db.String(200))  # Razorpay order_id
    gateway_payment_id  = db.Column(db.String(200))  # Razorpay payment_id
    gateway_signature   = db.Column(db.String(400))  # Razorpay signature for verification
    gateway_response    = db.Column(db.Text)          # Full JSON response stored as text

    payment_date = db.Column(db.DateTime)
    # ── Refund tracking ───────────────────────────────────────
    refund_id     = db.Column(db.String(200))
    refund_amount = db.Column(db.Float)
    refunded_at   = db.Column(db.DateTime)

    # ── Timestamps ────────────────────────────────────────────
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # ── Relationships ─────────────────────────────────────────
    order = db.relationship("Order", backref="payments")
    user  = db.relationship("User",  backref="payments")

    # ── Admin helpers ─────────────────────────────────────────
    @property
    def is_paid(self):
        return self.status == "Paid"

    @property
    def is_cod(self):
        return self.method == "COD"

    def __repr__(self):
        return f"<Payment order={self.order_id} ₹{self.amount} [{self.method}] {self.status}>"