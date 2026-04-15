from database.db import db
from datetime import datetime


class OrderDispatch(db.Model):
    """
    Tracks each delivery boy's response to an order broadcast.
    One row per (order, delivery_boy) pair.

    Status flow:
      "pending"  → boy was notified, hasn't responded yet
      "accepted" → boy accepted (order assigned to him)
      "rejected" → boy rejected (order goes to next available boy)
      "expired"  → boy didn't respond within TIMEOUT seconds
      "taken"    → another boy accepted first
    """
    __tablename__ = "order_dispatches"

    id              = db.Column(db.Integer, primary_key=True)
    order_id        = db.Column(db.Integer, db.ForeignKey("orders.id", ondelete="CASCADE"), nullable=False)
    delivery_boy_id = db.Column(db.Integer, db.ForeignKey("users.id",  ondelete="CASCADE"), nullable=False)

    status          = db.Column(db.String(20), default="pending")  # pending | accepted | rejected | expired | taken
    notified_at     = db.Column(db.DateTime, default=datetime.utcnow)
    responded_at    = db.Column(db.DateTime, nullable=True)

    # ── Relationships ─────────────────────────────────────────
    order        = db.relationship("Order", backref=db.backref("dispatches", lazy=True))
    delivery_boy = db.relationship("User",  foreign_keys=[delivery_boy_id])

    def __repr__(self):
        return f"<Dispatch order={self.order_id} boy={self.delivery_boy_id} [{self.status}]>"


class DeliveryBoyStats(db.Model):
    """
    Running stats per delivery boy — updated after every dispatch event.
    Used for ranking (best acceptance rate gets orders first).
    """
    __tablename__ = "delivery_boy_stats"

    id              = db.Column(db.Integer, primary_key=True)
    delivery_boy_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)

    total_notified  = db.Column(db.Integer, default=0)
    total_accepted  = db.Column(db.Integer, default=0)
    total_rejected  = db.Column(db.Integer, default=0)
    total_expired   = db.Column(db.Integer, default=0)
    total_delivered = db.Column(db.Integer, default=0)

    # Cached acceptance rate (0.0 – 1.0)
    acceptance_rate = db.Column(db.Float, default=1.0)

    last_active_at  = db.Column(db.DateTime, nullable=True)

    delivery_boy = db.relationship("User", foreign_keys=[delivery_boy_id],
                                   backref=db.backref("stats", uselist=False))

    def recalculate(self):
        """Recompute acceptance_rate from counters."""
        responded = self.total_accepted + self.total_rejected + self.total_expired
        self.acceptance_rate = (self.total_accepted / responded) if responded else 1.0

    def __repr__(self):
        return f"<Stats boy={self.delivery_boy_id} rate={self.acceptance_rate:.0%}>"