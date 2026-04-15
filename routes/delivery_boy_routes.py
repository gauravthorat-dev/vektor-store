from flask import Blueprint, render_template, redirect, request, session, flash, jsonify
from models.order_model import Order
from models.user_model import User
from models.notification_model import Notification
from database.db import db

delivery = Blueprint("delivery", __name__, url_prefix="/delivery")


# ── Guard: only delivery boys ─────────────────────────────────────────────────
def delivery_required(f):
    from functools import wraps
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


# ═══════════════════════════════════════
# DELIVERY BOY — DASHBOARD / ORDER LIST
# ═══════════════════════════════════════
@delivery.route("/dashboard")
@delivery_required
def dashboard():
    user_id = session.get("user_id")

    # Orders assigned to this delivery boy that are active
    active_orders = (
        Order.query
        .filter_by(delivery_boy_id=user_id)
        .filter(Order.status.in_(["Out for Delivery", "Shipped"]))
        .order_by(Order.updated_at.desc())
        .all()
    )

    # Completed today
    from datetime import date
    delivered_today = (
        Order.query
        .filter_by(delivery_boy_id=user_id, status="Delivered")
        .filter(db.func.date(Order.delivered_at) == str(date.today()))
        .count()
    )

    total_delivered = Order.query.filter_by(
        delivery_boy_id=user_id, status="Delivered"
    ).count()

    # ── FIX: calculate acceptance_rate ──────────────────────────────────────
    # Count all orders ever assigned (any status except unassigned)
    total_assigned = Order.query.filter_by(delivery_boy_id=user_id).count()
    acceptance_rate = round((total_delivered / total_assigned * 100) if total_assigned else 0)
    # ────────────────────────────────────────────────────────────────────────

    return render_template(
        "delivery/delivery-dashboard.html",
        active_orders   = active_orders,
        delivered_today = delivered_today,
        total_delivered = total_delivered,
        acceptance_rate = acceptance_rate,   # ← was missing before
        boy_name        = session.get("user_name", "Delivery Boy"),
    )


# ═══════════════════════════════════════
# MARK — OUT FOR DELIVERY
# Called by delivery boy when they pick up the order
# ═══════════════════════════════════════
@delivery.route("/pickup/<int:order_id>", methods=["POST"])
@delivery_required
def pickup(order_id):
    user_id = session.get("user_id")
    order   = Order.query.get_or_404(order_id)

    if order.delivery_boy_id != user_id:
        flash("This order is not assigned to you.", "error")
        return redirect("/delivery/dashboard")

    if order.status != "Shipped":
        flash("Order must be in Shipped status to pick up.", "error")
        return redirect("/delivery/dashboard")

    order.set_status("Out for Delivery")
    db.session.commit()

    flash(f"Order #VK{order.id} marked as Out for Delivery!", "success")
    return redirect("/delivery/dashboard")


# ═══════════════════════════════════════
# DELIVER — OTP VERIFICATION
# Delivery boy enters OTP given by customer
# ═══════════════════════════════════════
@delivery.route("/deliver/<int:order_id>", methods=["POST"])
@delivery_required
def deliver(order_id):
    user_id     = session.get("user_id")
    order       = Order.query.get_or_404(order_id)
    entered_otp = request.form.get("otp", "").strip()

    if order.delivery_boy_id != user_id:
        flash("This order is not assigned to you.", "error")
        return redirect("/delivery/dashboard")

    if order.status != "Out for Delivery":
        flash("Order must be Out for Delivery to confirm delivery.", "error")
        return redirect("/delivery/dashboard")

    if not order.delivery_otp:
        flash("No OTP generated for this order. Contact admin.", "error")
        return redirect("/delivery/dashboard")

    # ── FIX: validate OTP length before comparing ────────────────────────────
    if len(entered_otp) != 6 or not entered_otp.isdigit():
        flash("❌ Invalid OTP format. Enter the 6-digit code from the customer.", "error")
        return redirect("/delivery/dashboard")
    # ────────────────────────────────────────────────────────────────────────

    if entered_otp != order.delivery_otp:
        flash("❌ Wrong OTP. Ask the customer for the correct OTP.", "error")
        return redirect("/delivery/dashboard")

    # OTP correct — mark delivered
    order.set_status("Delivered")
    order.otp_verified   = True
    order.payment_status = "Paid" if order.payment_method == "COD" else order.payment_status

    db.session.commit()

    flash(f"✅ Order #VK{order.id} delivered successfully!", "success")
    return redirect("/delivery/dashboard")


# ═══════════════════════════════════════
# HISTORY — all completed orders
# ═══════════════════════════════════════
@delivery.route("/history")
@delivery_required
def history():
    user_id = session.get("user_id")
    delivered = (
        Order.query
        .filter_by(delivery_boy_id=user_id, status="Delivered")
        .order_by(Order.delivered_at.desc())
        .all()
    )

    total_delivered = len(delivered)

    # ── FIX: acceptance_rate for history view too ────────────────────────────
    total_assigned  = Order.query.filter_by(delivery_boy_id=user_id).count()
    acceptance_rate = round((total_delivered / total_assigned * 100) if total_assigned else 0)
    # ────────────────────────────────────────────────────────────────────────

    return render_template(
        "delivery/delivery-dashboard.html",
        active_orders   = [],
        history_orders  = delivered,
        show_history    = True,
        delivered_today = 0,
        total_delivered = total_delivered,
        acceptance_rate = acceptance_rate,   # ← was missing before
        boy_name        = session.get("user_name", "Delivery Boy"),
    )