from database.db import db
from datetime import datetime


class Review(db.Model):
    """
    Product reviews and star ratings.
    Used on the product detail page to show real ratings.
    Admin can see/moderate reviews.
    One user can only review the same product once.
    """

    __tablename__ = "reviews"

    # ── Core ──────────────────────────────────────────────────
    id         = db.Column(db.Integer, primary_key=True)
    user_id    = db.Column(db.Integer, db.ForeignKey("users.id"),    nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id"), nullable=False)

    # ── Review Content ────────────────────────────────────────
    rating     = db.Column(db.Integer, nullable=False)   # 1 to 5
    title      = db.Column(db.String(150))               # short headline
    body       = db.Column(db.Text)                      # full review text

    # ── Moderation ────────────────────────────────────────────
    is_approved = db.Column(db.Boolean, default=True)    # admin can hide a review

    # ── Verified Purchase ─────────────────────────────────────
    is_verified = db.Column(db.Boolean, default=False)   # True if user actually bought it

    # ── Timestamp ─────────────────────────────────────────────
    created_at  = db.Column(db.DateTime, default=datetime.utcnow)

    # ── Relationships ─────────────────────────────────────────
    user    = db.relationship("User",    backref="reviews")
    product = db.relationship("Product", backref="reviews")

    # ── Unique constraint: one review per user per product ────
    __table_args__ = (
        db.UniqueConstraint("user_id", "product_id", name="uq_user_product_review"),
    )

    # ── Admin helpers ─────────────────────────────────────────
    @property
    def reviewer_name(self):
        return self.user.name if self.user else "Anonymous"

    @property
    def stars(self):
        """Returns star string like ★★★★☆ for display."""
        return "★" * self.rating + "☆" * (5 - self.rating)

    def __repr__(self):
        return f"<Review product={self.product_id} user={self.user_id} rating={self.rating}>"