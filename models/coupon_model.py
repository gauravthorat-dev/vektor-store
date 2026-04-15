from database.db import db
from datetime import datetime


class Coupon(db.Model):
    """
    Discount coupon codes.
    Admin creates these from admin-settings or a future coupon management page.
    Applied at checkout to reduce order total.
    """

    __tablename__ = "coupons"

    # ── Core ──────────────────────────────────────────────────
    id          = db.Column(db.Integer, primary_key=True)
    code        = db.Column(db.String(50), unique=True, nullable=False)  # e.g. "VEKTOR40"
    description = db.Column(db.String(200))                              # e.g. "40% off flash sale"

    # ── Discount ──────────────────────────────────────────────
    # type: "percent" = percentage off | "flat" = fixed amount off
    discount_type  = db.Column(db.String(20), default="percent")         # "percent" | "flat"
    discount_value = db.Column(db.Float, nullable=False)                 # e.g. 40 (%) or 500 (₹)

    # ── Limits ────────────────────────────────────────────────
    min_order_value = db.Column(db.Float, default=0)     # minimum cart value to apply coupon
    max_discount    = db.Column(db.Float)                # cap on discount (for percent type)
    usage_limit     = db.Column(db.Integer)              # max times this coupon can be used total
    used_count      = db.Column(db.Integer, default=0)   # how many times it has been used

    # ── Validity ──────────────────────────────────────────────
    is_active   = db.Column(db.Boolean, default=True)
    valid_from  = db.Column(db.DateTime, default=datetime.utcnow)
    valid_until = db.Column(db.DateTime)                 # None = no expiry

    # ── Timestamp ─────────────────────────────────────────────
    created_at  = db.Column(db.DateTime, default=datetime.utcnow)

    # ── Admin helpers ─────────────────────────────────────────
    @property
    def is_valid(self):
        """Check if coupon is currently usable."""
        now = datetime.utcnow()
        if not self.is_active:
            return False
        if self.valid_until and now > self.valid_until:
            return False
        if self.usage_limit and self.used_count >= self.usage_limit:
            return False
        return True

    def calculate_discount(self, cart_total):
        """
        Given a cart total, return the discount amount in ₹.
        Returns 0 if coupon is invalid or minimum order not met.
        """
        if not self.is_valid:
            return 0
        if cart_total < self.min_order_value:
            return 0
        if self.discount_type == "percent":
            discount = cart_total * self.discount_value / 100
            if self.max_discount:
                discount = min(discount, self.max_discount)
            return round(discount, 2)
        elif self.discount_type == "flat":
            return min(self.discount_value, cart_total)
        return 0

    def __repr__(self):
        return f"<Coupon {self.code} — {self.discount_value}{'%' if self.discount_type=='percent' else '₹'} active={self.is_active}>"