"""Delivery boy dashboard and action routes."""

from datetime import date, datetime, timedelta
from functools import wraps

from flask import Blueprint, jsonify, redirect, render_template, request, session, flash

from database.db import db
from models.order_model import Order
from models.user_model import User
from services.dispatch_service import emit_stats_update
from utils.auth import get_request_csrf_token, validate_csrf_token

delivery = Blueprint("delivery", __name__, url_prefix="/delivery")


def delivery_required(f):
    """Allow access only to logged-in delivery boy accounts."""

    @wraps(f)
    def decorated(*args, **kwargs):
        user_id = session.get("user_id")
        if not user_id:
            flash("Please login first.")
            return redirect("/login")
        user = User.query.get(user_id)
        if not user or user.role != "delivery_boy":
            flash("Access denied. Delivery boy account required.")
            return redirect("/")
        return f(*args, **kwargs)

    return decorated


def _is_fetch_request() -> bool:
    """Return True when request is from fetch dashboard actions."""
    return request.headers.get("X-Requested-With") == "fetch"


def _json(ok: bool, message: str, data: dict | None = None, status_code: int = 200):
    """Return standard JSON response shape."""
    body = {"ok": ok, "message": message}
    if data is not None:
        body["data"] = data
    return jsonify(body), status_code


def _delivery_stats(user_id: int) -> dict:
    """Return dashboard stats for one delivery boy."""
    delivered_today = (
        Order.query.filter_by(delivery_boy_id=user_id, status="Delivered")
        .filter(db.func.date(Order.delivered_at) == str(date.today()))
        .count()
    )
    total_delivered = Order.query.filter_by(delivery_boy_id=user_id, status="Delivered").count()
    total_assigned = Order.query.filter_by(delivery_boy_id=user_id).count()
    acceptance_rate = round((total_delivered / total_assigned * 100) if total_assigned else 0)
    active_orders = (
        Order.query.filter_by(delivery_boy_id=user_id)
        .filter(Order.status.in_(["Out for Delivery", "Shipped"]))
        .count()
    )
    return {
        "active_orders": active_orders,
        "delivered_today": delivered_today,
        "total_delivered": total_delivered,
        "acceptance_rate": acceptance_rate,
    }


def _order_payload_for_card(order: Order) -> dict:
    """Return compact order payload for real-time dashboard card rendering."""
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


def _csrf_failed_response():
    """Handle CSRF failure for fetch and non-fetch flows."""
    if _is_fetch_request():
        return _json(False, "Security check failed. Please refresh and try again.", status_code=403)
    flash("Security check failed. Please retry.", "error")
    return redirect("/delivery/dashboard")


def _ensure_csrf():
    """Validate CSRF token from form/header."""
    token = get_request_csrf_token()
    return validate_csrf_token(token)


@delivery.route("/dashboard")
@delivery_required
def dashboard():
    """Render active delivery dashboard."""
    user_id = session.get("user_id")
    active_orders = (
        Order.query.filter_by(delivery_boy_id=user_id)
        .filter(Order.status.in_(["Out for Delivery", "Shipped"]))
        .order_by(Order.updated_at.desc())
        .all()
    )

    delivered_today = (
        Order.query.filter_by(delivery_boy_id=user_id, status="Delivered")
        .filter(db.func.date(Order.delivered_at) == str(date.today()))
        .count()
    )
    total_delivered = Order.query.filter_by(delivery_boy_id=user_id, status="Delivered").count()
    total_assigned = Order.query.filter_by(delivery_boy_id=user_id).count()
    acceptance_rate = round((total_delivered / total_assigned * 100) if total_assigned else 0)

    return render_template(
        "delivery/delivery-dashboard.html",
        active_orders=active_orders,
        delivered_today=delivered_today,
        total_delivered=total_delivered,
        acceptance_rate=acceptance_rate,
        boy_name=session.get("user_name", "Delivery Boy"),
    )


@delivery.route("/pickup/<int:order_id>", methods=["POST"])
@delivery_required
def pickup(order_id):
    """Mark shipped order as out for delivery."""
    if not _ensure_csrf():
        return _csrf_failed_response()

    user_id = session.get("user_id")
    order = Order.query.get_or_404(order_id)

    if order.delivery_boy_id != user_id:
        message = "This order is not assigned to you."
        if _is_fetch_request():
            return _json(False, message, status_code=403)
        flash(message, "error")
        return redirect("/delivery/dashboard")

    if order.status != "Shipped":
        message = "Order must be in Shipped status to pick up."
        if _is_fetch_request():
            return _json(False, message, status_code=400)
        flash(message, "error")
        return redirect("/delivery/dashboard")

    try:
        order.set_status("Out for Delivery")
        db.session.commit()
        emit_stats_update()
    except Exception:
        db.session.rollback()
        message = "Could not update order status. Please retry."
        if _is_fetch_request():
            return _json(False, message, status_code=500)
        flash(message, "error")
        return redirect("/delivery/dashboard")

    message = f"Order #VK{order.id} marked as Out for Delivery."
    if _is_fetch_request():
        return _json(
            True,
            message,
            data={"order_id": order.id, "stats": _delivery_stats(user_id), "order": _order_payload_for_card(order)},
        )
    flash(message, "success")
    return redirect("/delivery/dashboard")


@delivery.route("/deliver/<int:order_id>", methods=["POST"])
@delivery_required
def deliver(order_id):
    """Verify customer OTP and mark order delivered."""
    if not _ensure_csrf():
        return _csrf_failed_response()

    user_id = session.get("user_id")
    order = Order.query.get_or_404(order_id)
    entered_otp = request.form.get("otp", "").strip()

    if order.delivery_boy_id != user_id:
        message = "This order is not assigned to you."
        if _is_fetch_request():
            return _json(False, message, status_code=403)
        flash(message, "error")
        return redirect("/delivery/dashboard")

    if order.status != "Out for Delivery":
        message = "Order must be Out for Delivery to confirm delivery."
        if _is_fetch_request():
            return _json(False, message, status_code=400)
        flash(message, "error")
        return redirect("/delivery/dashboard")

    if not order.delivery_otp:
        message = "No OTP generated for this order. Contact admin."
        if _is_fetch_request():
            return _json(False, message, status_code=400)
        flash(message, "error")
        return redirect("/delivery/dashboard")

    if len(entered_otp) != 6 or not entered_otp.isdigit():
        message = "Invalid OTP format. Enter the 6-digit code from the customer."
        if _is_fetch_request():
            return _json(False, message, status_code=400)
        flash(message, "error")
        return redirect("/delivery/dashboard")

    if order.otp_attempts >= 3 and order.otp_locked_at:
        lock_expires = order.otp_locked_at + timedelta(minutes=10)
        if datetime.utcnow() < lock_expires:
            message = "Too many attempts. Wait 10 minutes."
            if _is_fetch_request():
                return _json(False, message, status_code=429)
            flash(message, "error")
            return redirect("/delivery/dashboard")

    if entered_otp != order.delivery_otp:
        try:
            order.otp_attempts = int(order.otp_attempts or 0) + 1
            if order.otp_attempts >= 3:
                order.otp_locked_at = datetime.utcnow()
            db.session.commit()
        except Exception:
            db.session.rollback()
            if _is_fetch_request():
                return _json(False, "Could not record OTP attempt. Try again.", status_code=500)
            flash("Could not record OTP attempt. Try again.", "error")
            return redirect("/delivery/dashboard")

        message = "Wrong OTP. Ask the customer for the correct OTP."
        if _is_fetch_request():
            return _json(
                False,
                message,
                data={"attempts_left": max(0, 3 - int(order.otp_attempts or 0))},
                status_code=400,
            )
        flash(message, "error")
        return redirect("/delivery/dashboard")

    try:
        order.set_status("Delivered")
        order.otp_verified = True
        order.otp_attempts = 0
        order.otp_locked_at = None
        if order.payment_method == "COD":
            order.payment_status = "Paid"
        db.session.commit()
        emit_stats_update()
    except Exception:
        db.session.rollback()
        message = "Could not complete delivery confirmation."
        if _is_fetch_request():
            return _json(False, message, status_code=500)
        flash(message, "error")
        return redirect("/delivery/dashboard")

    message = f"Order #VK{order.id} delivered successfully."
    if _is_fetch_request():
        return _json(True, message, data={"order_id": order.id, "stats": _delivery_stats(user_id)})
    flash(message, "success")
    return redirect("/delivery/dashboard")


@delivery.route("/history")
@delivery_required
def history():
    """Render delivered-order history."""
    user_id = session.get("user_id")
    delivered = (
        Order.query.filter_by(delivery_boy_id=user_id, status="Delivered")
        .order_by(Order.delivered_at.desc())
        .all()
    )

    total_delivered = len(delivered)
    total_assigned = Order.query.filter_by(delivery_boy_id=user_id).count()
    acceptance_rate = round((total_delivered / total_assigned * 100) if total_assigned else 0)

    return render_template(
        "delivery/delivery-dashboard.html",
        active_orders=[],
        history_orders=delivered,
        show_history=True,
        delivered_today=0,
        total_delivered=total_delivered,
        acceptance_rate=acceptance_rate,
        boy_name=session.get("user_name", "Delivery Boy"),
    )
