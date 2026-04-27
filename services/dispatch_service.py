"""Dispatch and live delivery utilities for VEKTOR."""

from datetime import datetime, timedelta

from flask import current_app
from sqlalchemy import select

from database.db import db
from models.dispatch_model import DeliveryBoyStats, OrderDispatch
from models.order_model import Order
from models.user_model import User
from services.sms_service import send_msg91_otp

DISPATCH_TIMEOUT_SECONDS = 90
ONLINE_STALE_SECONDS = 90


def _sio():
    """Lazy import to avoid circular imports."""
    from app import socketio
    return socketio


def get_stats_payload() -> dict:
    """Build admin counters payload."""
    return {
        "total": Order.query.count(),
        "active": Order.query.filter(
            Order.status.in_(["Pending", "Confirmed", "Processing", "Shipped", "Out for Delivery"])
        ).count(),
        "out_for_delivery": Order.query.filter_by(status="Out for Delivery").count(),
        "delivered": Order.query.filter_by(status="Delivered").count(),
        "cancelled": Order.query.filter_by(status="Cancelled").count(),
    }


def emit_stats_update():
    """Emit global order counters to admin listeners."""
    _sio().emit("stats_update", get_stats_payload(), room="admin_room")


def mark_stale_delivery_boys_offline():
    """Mark delivery boys offline if heartbeat is stale."""
    try:
        cutoff = datetime.utcnow() - timedelta(seconds=ONLINE_STALE_SECONDS)
        stale_boys = User.query.filter(
            User.role == "delivery_boy",
            User.is_online.is_(True),
            ((User.last_heartbeat.is_(None)) | (User.last_heartbeat < cutoff)),
        ).all()
        for boy in stale_boys:
            boy.is_online = False
        if stale_boys:
            db.session.commit()
    except Exception:
        db.session.rollback()


def set_delivery_boy_presence(user_id: int, is_online: bool):
    """Set delivery boy online state and heartbeat."""
    try:
        boy = User.query.get(user_id)
        if not boy or boy.role != "delivery_boy":
            return
        boy.is_online = is_online
        boy.last_heartbeat = datetime.utcnow()
        db.session.commit()
    except Exception:
        db.session.rollback()


def touch_delivery_boy_heartbeat(user_id: int):
    """Refresh delivery boy heartbeat and online status."""
    try:
        mark_stale_delivery_boys_offline()
        boy = User.query.get(user_id)
        if not boy or boy.role != "delivery_boy":
            return
        boy.is_online = True
        boy.last_heartbeat = datetime.utcnow()
        db.session.commit()
    except Exception:
        db.session.rollback()


def _order_payload(order: Order) -> dict:
    """Create socket payload for delivery request card."""
    return {
        "order_id": order.id,
        "customer_name": order.shipping_name or "",
        "address": f"{order.shipping_address or ''}, {order.shipping_city or ''} - {order.shipping_pincode or ''}",
        "total": order.total_price,
        "payment_method": order.payment_method,
        "items_count": len(order.items),
        "timeout": DISPATCH_TIMEOUT_SECONDS,
        "created_at": order.created_at.isoformat() if order.created_at else "",
    }


def _assigned_order_payload(order: Order) -> dict:
    """Create payload for active-order card after assignment."""
    return {
        "id": order.id,
        "status": order.status,
        "total_price": float(order.total_price or 0),
        "payment_method": order.payment_method or "COD",
        "shipping_name": order.shipping_name or "",
        "shipping_phone": order.shipping_phone or "",
        "shipping_address": order.shipping_address or "",
        "shipping_city": order.shipping_city or "",
        "shipping_pincode": order.shipping_pincode or "",
    }


def _upsert_dispatch_records(order_id: int, boys: list[User]):
    """Create pending dispatch rows for online recipients."""
    for boy in boys:
        existing = OrderDispatch.query.filter_by(order_id=order_id, delivery_boy_id=boy.id).first()
        if existing:
            existing.status = "pending"
            existing.notified_at = datetime.utcnow()
            existing.responded_at = None
            continue
        db.session.add(
            OrderDispatch(
                order_id=order_id,
                delivery_boy_id=boy.id,
                status="pending",
                notified_at=datetime.utcnow(),
            )
        )


def _send_or_keep_otp(order: Order) -> tuple[str, bool, str]:
    """Generate OTP when missing and send SMS, without raising."""
    otp = order.delivery_otp or order.generate_otp()
    ok, msg = send_msg91_otp(order.shipping_phone or "", otp)
    return otp, ok, msg


def _rank_fallback_boy() -> User | None:
    """Pick fallback by fewest active orders, then highest acceptance rate."""
    boys = User.query.filter_by(role="delivery_boy", status="Active").all()
    if not boys:
        return None

    candidates = []
    for boy in boys:
        active_count = Order.query.filter(
            Order.delivery_boy_id == boy.id,
            Order.status.in_(["Shipped", "Out for Delivery"]),
        ).count()
        rate = boy.stats.acceptance_rate if boy.stats else 0.0
        candidates.append((active_count, -float(rate), boy))
    candidates.sort(key=lambda item: (item[0], item[1], item[2].id))
    return candidates[0][2] if candidates else None


def broadcast_shipped_order(order_id: int):
    """Broadcast shipped order to all currently online delivery boys."""
    try:
        mark_stale_delivery_boys_offline()
        order = Order.query.get(order_id)
        if not order or order.status != "Shipped":
            return

        online_boys = User.query.filter_by(role="delivery_boy", status="Active", is_online=True).all()
        payload = _order_payload(order)

        _upsert_dispatch_records(order.id, online_boys)
        db.session.commit()

        if online_boys:
            _sio().emit("new_order_request", payload, room="delivery_boys")
            _sio().emit(
                "dispatch_sent",
                {"order_id": order.id, "boy_count": len(online_boys), "timeout": DISPATCH_TIMEOUT_SECONDS},
                room="admin_room",
            )
        else:
            _sio().emit(
                "dispatch_failed",
                {"order_id": order.id, "reason": "No delivery boys online"},
                room="admin_room",
            )

        schedule_auto_assign(order.id, timeout_seconds=DISPATCH_TIMEOUT_SECONDS)
    except Exception:
        db.session.rollback()


def schedule_auto_assign(order_id: int, timeout_seconds: int = DISPATCH_TIMEOUT_SECONDS):
    """Start background fallback assignment timer."""
    app = current_app._get_current_object()

    def _job(target_order_id: int):
        from time import sleep

        sleep(timeout_seconds)
        with app.app_context():
            auto_assign_if_unclaimed(target_order_id)

    _sio().start_background_task(_job, order_id)


def auto_assign_if_unclaimed(order_id: int) -> dict:
    """Auto-assign an unclaimed shipped order after timeout."""
    try:
        order = db.session.execute(
            select(Order).where(Order.id == order_id).with_for_update()
        ).scalar_one_or_none()
        if not order:
            return {"ok": False, "message": "Order not found."}
        if order.status != "Shipped":
            return {"ok": False, "message": f"Order is {order.status}."}
        if order.delivery_boy_id:
            return {"ok": False, "message": "Order already claimed."}

        boy = _rank_fallback_boy()
        if not boy:
            db.session.commit()
            _sio().emit(
                "dispatch_failed",
                {"order_id": order_id, "reason": "No eligible delivery boy for fallback"},
                room="admin_room",
            )
            return {"ok": False, "message": "No eligible delivery boy."}

        order.delivery_boy_id = boy.id
        otp, sms_ok, sms_msg = _send_or_keep_otp(order)
        db.session.commit()

        _sio().emit(
            "order_taken",
            {"order_id": order.id, "accepted_by": boy.name, "accepted_by_id": boy.id},
            room="delivery_boys",
        )
        _sio().emit(
            "order_auto_assigned",
            {
                "order_id": order.id,
                "boy_id": boy.id,
                "boy_name": boy.name,
                "sms_ok": sms_ok,
                "sms_message": sms_msg,
                "otp": otp,
            },
            room="admin_room",
        )
        _sio().emit(
            "order_assigned",
            {"order": _assigned_order_payload(order), "source": "auto_assign"},
            room=f"boy_{boy.id}",
        )
        return {
            "ok": True,
            "message": "Order auto-assigned.",
            "boy_id": boy.id,
            "boy_name": boy.name,
            "sms_ok": sms_ok,
            "sms_message": sms_msg,
        }
    except Exception as exc:
        db.session.rollback()
        return {"ok": False, "message": f"Auto-assign failed: {exc}"}


def accept_order_atomic(order_id: int, boy_id: int) -> dict:
    """Atomically accept an order from socket accept click."""
    try:
        order = db.session.execute(
            select(Order).where(Order.id == order_id).with_for_update()
        ).scalar_one_or_none()
        if not order:
            return {"ok": False, "message": "Order not found."}
        if order.status != "Shipped":
            return {"ok": False, "message": f"Order is {order.status}."}
        if order.delivery_boy_id and order.delivery_boy_id != boy_id:
            return {"ok": False, "message": "Order already accepted by another delivery boy."}

        order.delivery_boy_id = boy_id
        otp, sms_ok, sms_msg = _send_or_keep_otp(order)

        chosen = OrderDispatch.query.filter_by(order_id=order_id, delivery_boy_id=boy_id).first()
        if chosen:
            chosen.status = "accepted"
            chosen.responded_at = datetime.utcnow()

        others = OrderDispatch.query.filter(
            OrderDispatch.order_id == order_id,
            OrderDispatch.delivery_boy_id != boy_id,
            OrderDispatch.status == "pending",
        ).all()
        for row in others:
            row.status = "taken"
            row.responded_at = datetime.utcnow()

        stats = DeliveryBoyStats.query.filter_by(delivery_boy_id=boy_id).first()
        if not stats:
            stats = DeliveryBoyStats(delivery_boy_id=boy_id)
            db.session.add(stats)
        stats.total_notified = int(stats.total_notified or 0) + 1
        stats.total_accepted = int(stats.total_accepted or 0) + 1
        stats.last_active_at = datetime.utcnow()
        stats.recalculate()

        db.session.commit()

        boy = User.query.get(boy_id)
        _sio().emit(
            "order_taken",
            {"order_id": order_id, "accepted_by": boy.name if boy else "Delivery Boy", "accepted_by_id": boy_id},
            room="delivery_boys",
        )
        _sio().emit(
            "order_accepted",
            {
                "order_id": order_id,
                "boy_id": boy_id,
                "boy_name": boy.name if boy else "Delivery Boy",
                "otp": otp,
                "sms_ok": sms_ok,
                "sms_message": sms_msg,
            },
            room="admin_room",
        )
        _sio().emit(
            "order_assigned",
            {"order": _assigned_order_payload(order), "source": "accepted"},
            room=f"boy_{boy_id}",
        )
        return {
            "ok": True,
            "message": "Order accepted.",
            "data": {
                "order_id": order_id,
                "otp": otp,
                "sms_ok": sms_ok,
                "sms_message": sms_msg,
                "order": _assigned_order_payload(order),
            },
        }
    except Exception as exc:
        db.session.rollback()
        return {"ok": False, "message": f"Accept failed: {exc}"}


def reject_order(order_id: int, boy_id: int):
    """Mark this boy as rejected for dispatch telemetry."""
    try:
        row = OrderDispatch.query.filter_by(order_id=order_id, delivery_boy_id=boy_id).first()
        if row:
            row.status = "rejected"
            row.responded_at = datetime.utcnow()
        stats = DeliveryBoyStats.query.filter_by(delivery_boy_id=boy_id).first()
        if not stats:
            stats = DeliveryBoyStats(delivery_boy_id=boy_id)
            db.session.add(stats)
        stats.total_notified = int(stats.total_notified or 0) + 1
        stats.total_rejected = int(stats.total_rejected or 0) + 1
        stats.last_active_at = datetime.utcnow()
        stats.recalculate()
        db.session.commit()
    except Exception:
        db.session.rollback()


def expire_dispatch(order_id: int, boy_id: int):
    """Mark timeout in dispatch telemetry."""
    try:
        row = OrderDispatch.query.filter_by(order_id=order_id, delivery_boy_id=boy_id).first()
        if row and row.status == "pending":
            row.status = "expired"
            row.responded_at = datetime.utcnow()
        stats = DeliveryBoyStats.query.filter_by(delivery_boy_id=boy_id).first()
        if not stats:
            stats = DeliveryBoyStats(delivery_boy_id=boy_id)
            db.session.add(stats)
        stats.total_notified = int(stats.total_notified or 0) + 1
        stats.total_expired = int(stats.total_expired or 0) + 1
        stats.last_active_at = datetime.utcnow()
        stats.recalculate()
        db.session.commit()
    except Exception:
        db.session.rollback()


def resend_order_otp(order: Order) -> tuple[bool, str, str]:
    """Regenerate and resend OTP for an order."""
    otp = order.generate_otp()
    ok, msg = send_msg91_otp(order.shipping_phone or "", otp)
    return ok, msg, otp
