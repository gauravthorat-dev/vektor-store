"""
dispatch_service.py
───────────────────
Uber-style order dispatch engine for VEKTOR STORE.

How it works
============
1. When an order is confirmed, broadcast_order() is called.
2. It finds all ONLINE delivery boys, sorted by:
      • acceptance_rate DESC  (best boys get priority)
      • last_active_at  DESC  (most recently active first)
3. A SocketIO event "new_order_request" is emitted to each boy's
   personal room  (room = f"boy_{user_id}").
4. Each boy sees a 60-second countdown. They can ACCEPT or REJECT.
5. First ACCEPT wins — others get "order_taken" event.
6. If nobody accepts within TIMEOUT → admin gets "dispatch_failed" alert.

Rooms
=====
  boy_{id}      — personal room for each delivery boy
  admin_room    — all admins listen here for alerts
"""

from datetime import datetime
from database.db import db
from models.dispatch_model import OrderDispatch, DeliveryBoyStats
from models.order_model import Order
from models.user_model import User

DISPATCH_TIMEOUT = 60          # seconds a boy has to accept
PING_SOUND_URL   = "/static/sounds/ping.mp3"   # put a short ping.mp3 here


# ── Lazy import of socketio to avoid circular imports ─────────────────────────
def _sio():
    from app import socketio
    return socketio


# ═══════════════════════════════════════════════════════════════
# 1. BROADCAST — called right after order is confirmed by admin
# ═══════════════════════════════════════════════════════════════
def broadcast_order(order_id: int):
    """
    Find available delivery boys and emit new_order_request to each.
    Call this from admin_routes after setting order.status = 'Confirmed'.
    """
    order = Order.query.get(order_id)
    if not order:
        return

    boys = _get_ranked_boys()
    if not boys:
        # No delivery boys available — alert admin
        _sio().emit("dispatch_failed", {
            "order_id": order_id,
            "reason":   "No delivery boys online",
        }, room="admin_room")
        return

    payload = _order_payload(order)

    for boy in boys:
        # Create a dispatch record
        existing = OrderDispatch.query.filter_by(
            order_id=order_id, delivery_boy_id=boy.id
        ).first()
        if not existing:
            dispatch = OrderDispatch(
                order_id        = order_id,
                delivery_boy_id = boy.id,
                status          = "pending",
                notified_at     = datetime.utcnow(),
            )
            db.session.add(dispatch)

        # Emit to boy's personal socket room
        _sio().emit("new_order_request", payload, room=f"boy_{boy.id}")

    db.session.commit()

    # Tell admin broadcast went out
    _sio().emit("dispatch_sent", {
        "order_id":  order_id,
        "boy_count": len(boys),
    }, room="admin_room")


# ═══════════════════════════════════════════════════════════════
# 2. ACCEPT — delivery boy accepts the order
# ═══════════════════════════════════════════════════════════════
def accept_order(order_id: int, boy_id: int) -> dict:
    """
    Returns {"ok": True} or {"ok": False, "reason": "..."}
    """
    order = Order.query.get(order_id)
    if not order:
        return {"ok": False, "reason": "Order not found"}

    # Check it hasn't already been taken
    if order.delivery_boy_id and order.delivery_boy_id != boy_id:
        _mark_taken(order_id, boy_id)
        return {"ok": False, "reason": "Order already taken by another boy"}

    if order.status not in ("Pending", "Confirmed", "Processing"):
        return {"ok": False, "reason": f"Order is already {order.status}"}

    # Assign
    order.delivery_boy_id = boy_id
    order.set_status("Processing")
    otp = order.generate_otp()
    # TODO: SMS otp to order.shipping_phone

    # Update this boy's dispatch record
    _update_dispatch(order_id, boy_id, "accepted")

    # Mark all other pending dispatches as "taken"
    others = OrderDispatch.query.filter(
        OrderDispatch.order_id        == order_id,
        OrderDispatch.delivery_boy_id != boy_id,
        OrderDispatch.status          == "pending",
    ).all()
    for d in others:
        d.status       = "taken"
        d.responded_at = datetime.utcnow()

    # Update stats
    _bump_stat(boy_id, "accepted")

    db.session.commit()

    # Notify all other boys that order is taken
    boy = User.query.get(boy_id)
    for d in others:
        _sio().emit("order_taken", {
            "order_id":      order_id,
            "accepted_by":   boy.name if boy else "Someone",
        }, room=f"boy_{d.delivery_boy_id}")

    # Notify admin
    _sio().emit("order_accepted", {
        "order_id": order_id,
        "boy_id":   boy_id,
        "boy_name": boy.name if boy else "Unknown",
        "otp":      otp,
    }, room="admin_room")

    return {"ok": True, "otp": otp}


# ═══════════════════════════════════════════════════════════════
# 3. REJECT — delivery boy rejects the order
# ═══════════════════════════════════════════════════════════════
def reject_order(order_id: int, boy_id: int):
    _update_dispatch(order_id, boy_id, "rejected")
    _bump_stat(boy_id, "rejected")
    db.session.commit()

    # Check if anyone is still pending
    pending = OrderDispatch.query.filter_by(
        order_id=order_id, status="pending"
    ).count()

    if pending == 0:
        # Everyone rejected — alert admin
        _sio().emit("dispatch_failed", {
            "order_id": order_id,
            "reason":   "All delivery boys rejected the order",
        }, room="admin_room")


# ═══════════════════════════════════════════════════════════════
# 4. EXPIRE — called by a background job after DISPATCH_TIMEOUT
# ═══════════════════════════════════════════════════════════════
def expire_dispatch(order_id: int, boy_id: int):
    dispatch = OrderDispatch.query.filter_by(
        order_id=order_id, delivery_boy_id=boy_id, status="pending"
    ).first()
    if not dispatch:
        return

    dispatch.status       = "expired"
    dispatch.responded_at = datetime.utcnow()
    _bump_stat(boy_id, "expired")
    db.session.commit()

    # Check if everyone expired/rejected
    pending = OrderDispatch.query.filter_by(
        order_id=order_id, status="pending"
    ).count()
    if pending == 0:
        _sio().emit("dispatch_failed", {
            "order_id": order_id,
            "reason":   "All delivery boys timed out",
        }, room="admin_room")


# ═══════════════════════════════════════════════════════════════
# HELPERS
# ═══════════════════════════════════════════════════════════════
def _get_ranked_boys():
    """
    Return active delivery boys sorted by acceptance_rate DESC,
    then last_active_at DESC.
    """
    boys = User.query.filter_by(role="delivery_boy", status="Active").all()

    def rank(boy):
        stats = boy.stats  # via backref on DeliveryBoyStats
        rate  = stats.acceptance_rate if stats else 1.0
        last  = stats.last_active_at  if stats else datetime.min
        return (-rate, -(last.timestamp() if last else 0))

    return sorted(boys, key=rank)


def _order_payload(order: Order) -> dict:
    return {
        "order_id":         order.id,
        "customer_name":    order.shipping_name or "",
        "address":          f"{order.shipping_address}, {order.shipping_city} — {order.shipping_pincode}",
        "total":            order.total_price,
        "payment_method":   order.payment_method,
        "items_count":      len(order.items),
        "timeout":          DISPATCH_TIMEOUT,
        "created_at":       order.created_at.isoformat() if order.created_at else "",
    }


def _update_dispatch(order_id, boy_id, status):
    d = OrderDispatch.query.filter_by(
        order_id=order_id, delivery_boy_id=boy_id
    ).first()
    if d:
        d.status       = status
        d.responded_at = datetime.utcnow()


def _mark_taken(order_id, boy_id):
    _update_dispatch(order_id, boy_id, "taken")
    db.session.commit()


def _bump_stat(boy_id, field):
    stats = DeliveryBoyStats.query.filter_by(delivery_boy_id=boy_id).first()
    if not stats:
        stats = DeliveryBoyStats(delivery_boy_id=boy_id)
        db.session.add(stats)
    stats.total_notified += 1
    setattr(stats, f"total_{field}", getattr(stats, f"total_{field}") + 1)
    stats.last_active_at = datetime.utcnow()
    stats.recalculate()