from functools import wraps
from datetime import datetime, timedelta
from flask import Blueprint, render_template, redirect, request, session, flash
from werkzeug.security import check_password_hash, generate_password_hash
from utils.auth import (
    admin_required,
    clear_admin_session,
    clear_login_failures,
    manager_required,
    register_login_failure,
    set_admin_session,
    superadmin_required,
    is_login_rate_limited,
)

from models.order_model import Order
from models.order_item_model import OrderItem
from models.product_model import Product
from models.admin_model import Admin
from models.notification_model import Notification
from database.db import db
from models.user_model import User
from services.dispatch_service import (
    broadcast_shipped_order,
    emit_stats_update,
    get_stats_payload,
)
from services.sms_service import send_msg91_otp

admin = Blueprint("admin", __name__, url_prefix="/admin")
ALLOWED_ADMIN_LEVELS = {"superadmin", "manager", "viewer"}


# ═══════════════════════════════════════
# DASHBOARD — all admins
# ═══════════════════════════════════════
@admin.route("/dashboard")
@admin_required
def dashboard():
    total_orders = Order.query.count()
    total_revenue = db.session.query(db.func.sum(Order.total_price)).scalar() or 0
    total_customers = User.query.filter_by(role="user").count()
    total_products = Product.query.filter_by(is_active=True).count()
    recent_orders = Order.query.order_by(Order.created_at.desc()).limit(8).all()
    low_stock = (
        Product.query
        .filter(Product.stock <= 5, Product.is_active == True)
        .order_by(Product.stock.asc())
        .limit(5).all()
    )
    notifications = (
        Notification.query
        .filter_by(is_read=False)
        .order_by(Notification.created_at.desc())
        .limit(10).all()
    )

    now = datetime.utcnow()
    today_start = datetime(now.year, now.month, now.day)
    today_orders = (
        Order.query
        .filter(Order.created_at >= today_start)
        .count()
    )
    today_revenue = (
        db.session.query(db.func.sum(Order.total_price))
        .filter(Order.created_at >= today_start)
        .scalar()
        or 0
    )
    avg_order_value = round((total_revenue / total_orders), 2) if total_orders else 0

    # Revenue: last 14 days
    daily_labels = []
    daily_revenue = []
    for i in range(13, -1, -1):
        day_start = today_start - timedelta(days=i)
        day_end = day_start + timedelta(days=1)
        rev = (
            db.session.query(db.func.sum(Order.total_price))
            .filter(Order.created_at >= day_start, Order.created_at < day_end)
            .scalar()
            or 0
        )
        daily_labels.append(day_start.strftime("%d %b"))
        daily_revenue.append(round(float(rev), 2))

    # Revenue: last 8 months
    monthly_labels = []
    monthly_revenue = []
    for i in range(7, -1, -1):
        month_anchor = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        month_start = month_anchor - timedelta(days=32 * i)
        month_start = month_start.replace(day=1)
        if month_start.month == 12:
            month_end = month_start.replace(year=month_start.year + 1, month=1, day=1)
        else:
            month_end = month_start.replace(month=month_start.month + 1, day=1)
        mrev = (
            db.session.query(db.func.sum(Order.total_price))
            .filter(Order.created_at >= month_start, Order.created_at < month_end)
            .scalar()
            or 0
        )
        monthly_labels.append(month_start.strftime("%b"))
        monthly_revenue.append(round(float(mrev), 2))

    # Status chart buckets
    pending_like = ["Pending", "Confirmed", "Processing", "Out for Delivery"]
    status_counts = {
        "Pending": Order.query.filter(Order.status.in_(pending_like)).count(),
        "Shipped": Order.query.filter_by(status="Shipped").count(),
        "Delivered": Order.query.filter_by(status="Delivered").count(),
        "Cancelled": Order.query.filter_by(status="Cancelled").count(),
    }

    # Top cities by order volume
    city_rows = (
        db.session.query(Order.shipping_city, db.func.count(Order.id))
        .filter(Order.shipping_city.isnot(None), Order.shipping_city != "")
        .group_by(Order.shipping_city)
        .order_by(db.func.count(Order.id).desc())
        .limit(5)
        .all()
    )
    city_labels = [row[0] for row in city_rows] or ["No Data"]
    city_counts = [int(row[1]) for row in city_rows] or [0]

    # Top products by revenue
    active_products = Product.query.filter_by(is_active=True).all()
    top_products = sorted(
        active_products,
        key=lambda p: p.total_revenue,
        reverse=True
    )[:5]

    return render_template(
        "admin/admin-dashboard.html",
        total_orders=total_orders,
        total_revenue=round(total_revenue, 2),
        total_customers=total_customers,
        total_products=total_products,
        recent_orders=recent_orders,
        low_stock=low_stock,
        notifications=notifications,
        notif_count=len(notifications),
        today_orders=today_orders,
        today_revenue=round(today_revenue, 2),
        avg_order_value=avg_order_value,
        daily_labels=daily_labels,
        daily_revenue=daily_revenue,
        monthly_labels=monthly_labels,
        monthly_revenue=monthly_revenue,
        status_counts=status_counts,
        city_labels=city_labels,
        city_counts=city_counts,
        top_products=top_products,
    )


# ═══════════════════════════════════════
# PRODUCTS LIST — all admins
# ═══════════════════════════════════════
@admin.route("/products")
@admin_required
def products():
    q        = request.args.get("q", "")
    category = request.args.get("category", "")
    sort     = request.args.get("sort", "")
    page     = request.args.get("page", 1, type=int)

    query = Product.query
    if q:
        query = query.filter(Product.name.ilike(f"%{q}%"))
    if category:
        query = query.filter(Product.category == category)
    if sort == "low":
        query = query.order_by(Product.price.asc())
    elif sort == "high":
        query = query.order_by(Product.price.desc())
    else:
        query = query.order_by(Product.created_at.desc())

    products = query.paginate(page=page, per_page=10, error_out=False)
    return render_template("admin/admin-products.html", products=products)


# ═══════════════════════════════════════
# ADD PRODUCT — manager + superadmin only
# ═══════════════════════════════════════
@admin.route("/add-product", methods=["GET", "POST"])
@admin_required
@manager_required
def add_product():
    if request.method == "POST":
        import os, json
        from werkzeug.utils import secure_filename

        name  = request.form.get("name", "").strip()
        price = request.form.get("price", 0)

        if not name or not price:
            flash("Name and price are required")
            return redirect("/admin/add-product")

        upload_folder = os.path.join("static", "uploads")
        os.makedirs(upload_folder, exist_ok=True)

        def save_img(field, fallback=None):
            f = request.files.get(field)
            if f and f.filename:
                fname = secure_filename(f.filename)
                f.save(os.path.join(upload_folder, fname))
                return fname
            return fallback

        image   = save_img("image_1", "default.png")
        image_2 = save_img("image_2")
        image_3 = save_img("image_3")
        image_4 = save_img("image_4")

        sizes_list = request.form.getlist("sizes[]")
        colors_json = json.dumps([
            {"hex": h, "name": n}
            for h, n in zip(
                request.form.getlist("color_hex[]"),
                request.form.getlist("color_name[]")
            ) if h
        ])
        highlights_json = json.dumps([
            {"en": e, "mr": m}
            for e, m in zip(
                request.form.getlist("hl_en[]"),
                request.form.getlist("hl_mr[]")
            ) if e
        ])
        specs_json = json.dumps([
            {"key": k, "val": v}
            for k, v in zip(
                request.form.getlist("spec_key[]"),
                request.form.getlist("spec_val[]")
            ) if k
        ])
        offers_json = json.dumps([
            {"icon": i, "title": t, "desc": d}
            for i, t, d in zip(
                request.form.getlist("offer_icon[]"),
                request.form.getlist("offer_title[]"),
                request.form.getlist("offer_desc[]")
            ) if t
        ])
        delivery_json = json.dumps({
            "standard_price": request.form.get("delivery_standard", "79"),
            "express_price":  request.form.get("delivery_express", "149"),
            "free_above":     request.form.get("free_shipping_above", "999"),
            "standard_days":  request.form.get("delivery_days_standard", "3–5 Business Days"),
            "express_days":   request.form.get("delivery_days_express", "1–2 Business Days"),
            "return_window":  request.form.get("return_days", "30"),
            "refund_days":    request.form.get("refund_days", "3–5 Business Days"),
        })

        slug_val = request.form.get("slug", "").strip()
        if not slug_val:
            import re
            slug_val = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
        base_slug = slug_val
        counter = 1
        while Product.query.filter_by(slug=slug_val).first():
            slug_val = f"{base_slug}-{counter}"
            counter += 1

        new_product = Product(
            name             = name,
            price            = float(price),
            image            = image,
            image_2          = image_2,
            image_3          = image_3,
            image_4          = image_4,
            category         = request.form.get("category", "Shirts"),
            stock            = int(request.form.get("stock", 0) or 0),
            discount         = int(request.form.get("discount", 0) or 0),
            description      = request.form.get("description", "").strip(),
            brand            = request.form.get("brand", "").strip(),
            is_featured      = bool(request.form.get("is_featured")),
            is_active        = True,
            name_mr          = request.form.get("name_mr", "").strip(),
            description_mr   = request.form.get("description_mr", "").strip(),
            tagline_sk       = request.form.get("tagline_sk", "").strip(),
            collection       = request.form.get("collection", "").strip(),
            season           = request.form.get("season", "SS/26").strip(),
            sku              = request.form.get("sku", "").strip(),
            save_text        = request.form.get("save_text", "").strip(),
            tax_info         = request.form.get("tax_info", "").strip(),
            badge            = request.form.get("badge", "").strip(),
            low_stock        = int(request.form.get("low_stock", 10) or 10),
            sizes_json       = json.dumps(sizes_list),
            colors_json      = colors_json,
            highlights_json  = highlights_json,
            specs_json       = specs_json,
            offers_json      = offers_json,
            wash_care_mr     = request.form.get("care_mr", "").strip(),
            delivery_json    = delivery_json,
            meta_title       = request.form.get("meta_title", "").strip(),
            meta_description = request.form.get("meta_description", "").strip(),
            slug             = slug_val,
            tags             = request.form.get("tags", "").strip(),
            fit              = request.form.get("fit", "").strip(),
            default_size     = request.form.get("default_size", "M").strip(),
            rating_display   = float(request.form.get("rating", 4.9) or 4.9),
            review_count     = int(request.form.get("review_count", 0) or 0),
        )
        db.session.add(new_product)
        db.session.commit()

        from models.review_model import Review
        rev_names  = request.form.getlist("rev_name[]")
        rev_stars  = request.form.getlist("rev_stars[]")
        rev_titles = request.form.getlist("rev_title[]")
        rev_bodies = request.form.getlist("rev_body[]")

        for i, rev_name in enumerate(rev_names):
            if not rev_name.strip():
                continue
            stars_str   = rev_stars[i] if i < len(rev_stars) else "★★★★★"
            stars_count = stars_str.count("★") or 5
            review = Review(
                user_id     = 1,
                product_id  = new_product.id,
                rating      = stars_count,
                title       = rev_titles[i].strip() if i < len(rev_titles) else "",
                body        = rev_bodies[i].strip() if i < len(rev_bodies) else "",
                is_approved = True,
                is_verified = True,
            )
            try:
                db.session.add(review)
                db.session.commit()
            except Exception:
                db.session.rollback()

        if new_product.stock <= 5:
            db.session.add(Notification.low_stock(new_product))
            db.session.commit()

        flash("Product added successfully! · उत्पादन जोडले!", "success")
        return redirect("/admin/products")

    return render_template("admin/admin-add-product.html")


# ═══════════════════════════════════════
# EDIT PRODUCT — manager + superadmin only
# ═══════════════════════════════════════
@admin.route("/edit-product/<int:id>", methods=["GET", "POST"])
@admin_required
@manager_required
def edit_product(id):
    product = Product.query.get_or_404(id)

    if request.method == "POST":
        import os
        from werkzeug.utils import secure_filename

        product.name           = request.form.get("name", product.name).strip()
        product.price          = float(request.form.get("price", product.price) or product.price)
        product.stock          = int(request.form.get("stock", product.stock) or 0)
        product.discount       = int(request.form.get("discount", product.discount or 0) or 0)
        product.category       = request.form.get("category", product.category)
        product.description    = request.form.get("description", product.description or "")
        product.brand          = request.form.get("brand", product.brand or "")
        product.size           = request.form.get("size", product.size or "")
        product.color          = request.form.get("color", product.color or "")
        product.is_active      = bool(request.form.get("is_active"))
        product.is_featured    = bool(request.form.get("is_featured"))
        product.name_mr        = request.form.get("name_mr",        product.name_mr        or "")
        product.description_mr = request.form.get("description_mr", product.description_mr or "")
        product.tagline_sk     = request.form.get("tagline_sk",     product.tagline_sk     or "")
        product.collection     = request.form.get("collection",     product.collection     or "")
        product.season         = request.form.get("season",         product.season         or "SS/26")
        product.sku            = request.form.get("sku",            product.sku            or "")
        product.save_text      = request.form.get("save_text",      product.save_text      or "")
        product.tax_info       = request.form.get("tax_info",       product.tax_info       or "")
        product.badge          = request.form.get("badge",          product.badge          or "")
        low_stock_val          = request.form.get("low_stock", "")
        product.low_stock      = int(low_stock_val) if low_stock_val.isdigit() else (product.low_stock or 10)

        file = request.files.get("image_file")
        if file and file.filename:
            filename = secure_filename(file.filename)
            upload_folder = os.path.join("static", "uploads")
            os.makedirs(upload_folder, exist_ok=True)
            file.save(os.path.join(upload_folder, filename))
            product.image = filename
        else:
            text_img = request.form.get("image", "").strip()
            if text_img:
                product.image = os.path.basename(text_img)

        db.session.commit()

        if product.stock <= 5:
            existing = Notification.query.filter_by(
                notif_type="stock", product_id=product.id, is_read=False
            ).first()
            if not existing:
                db.session.add(Notification.low_stock(product))
                db.session.commit()

        flash("Product updated! · उत्पादन अपडेट केले!", "success")
        return redirect("/admin/products")

    return render_template("admin/admin-edit-product.html", product=product)


# ═══════════════════════════════════════
# DELETE PRODUCT — manager + superadmin only
# ═══════════════════════════════════════
@admin.route("/delete-product/<int:id>", methods=["POST"])
@admin_required
@manager_required
def delete_product(id):
    product = Product.query.get_or_404(id)
    from models.review_model import Review
    Review.query.filter_by(product_id=product.id).delete()
    db.session.delete(product)
    db.session.commit()
    flash("Product deleted.", "success")
    return redirect("/admin/products")


# ═══════════════════════════════════════════════════════════════════════════════
# PASTE THESE ROUTES INTO YOUR admin_routes.py
# REPLACE the existing  update_order()  route and ADD the two new ones below it.
# Also add this import at the top of your file (if not already present):
#   from models.user_model import User
# ═══════════════════════════════════════════════════════════════════════════════


# ═══════════════════════════════════════
# ORDERS — all admins  (REPLACE existing orders() route)
# ═══════════════════════════════════════
@admin.route("/orders")
@admin_required
def orders():
    """Render admin orders table with live counters."""
    status_filter = request.args.get("status", "")
    page          = request.args.get("page", 1, type=int)

    query = Order.query.order_by(Order.created_at.desc())
    if status_filter:
        query = query.filter(Order.status == status_filter)

    pagination = query.paginate(page=page, per_page=15, error_out=False)
    all_orders = pagination.items

    # Fetch all delivery boys for the assign dropdown
    delivery_boys = User.query.filter_by(role="delivery_boy", status="Active").all()

    order_data = []
    for order in all_orders:
        user  = User.query.get(order.user_id)
        items = OrderItem.query.filter_by(order_id=order.id).all()
        product_list = []
        for item in items:
            p = Product.query.get(item.product_id)
            if p:
                product_list.append({
                    "name":  p.name,
                    "qty":   item.quantity,
                    "price": item.price_at_purchase or p.price,
                })

        boy = User.query.get(order.delivery_boy_id) if order.delivery_boy_id else None

        order_data.append({
            "id":                   order.id,
            "customer":             user.name  if user else "Unknown",
            "email":                user.email if user else "",
            "phone":                user.phone if user else "",
            "date":                 order.created_at,
            "total":                order.total_price,
            "status":               order.status,
            "payment_method":       order.payment_method,
            "payment_status":       order.payment_status,
            "shipping_address":     order.shipping_address or "",
            "shipping_city":        order.shipping_city    or "",
            "shipping_pincode":     order.shipping_pincode or "",
            "products":             product_list,
            "delivery_boy_id":      order.delivery_boy_id,
            "delivery_boy_name":    boy.name if boy else None,
            "delivery_otp":         order.delivery_otp,
            "otp_verified":         order.otp_verified,
            # Stage timestamps
            "confirmed_at":         order.confirmed_at,
            "processing_at":        order.processing_at,
            "shipped_at":           order.shipped_at,
            "out_for_delivery_at":  order.out_for_delivery_at,
            "delivered_at":         order.delivered_at,
            "cancelled_at":         order.cancelled_at,
        })

    return render_template(
        "admin/admin-manage-orders.html",
        orders        = order_data,
        pagination    = pagination,
        delivery_boys = delivery_boys,
        stats         = get_stats_payload(),
    )


# ═══════════════════════════════════════
# UPDATE ORDER STATUS  (REPLACE existing update_order() route)
# ═══════════════════════════════════════
@admin.route("/update-order/<int:id>", methods=["POST"])
@admin_required
@manager_required
def update_order(id):
    """Update order status and trigger dispatch/stats side effects."""
    status = request.form.get("status", "").strip()
    allowed = ["Pending", "Confirmed", "Processing", "Shipped",
               "Out for Delivery", "Delivered", "Cancelled"]
    order = Order.query.get_or_404(id)

    if status not in allowed:
        flash("Invalid status.", "error")
        return redirect("/admin/orders")

    try:
        order.set_status(status)
        db.session.commit()
    except Exception:
        db.session.rollback()
        flash("Could not update order status. Please retry.", "error")
        return redirect("/admin/orders")

    emit_stats_update()
    if status == "Shipped":
        broadcast_shipped_order(order.id)
        flash(f"Order #{id} marked as Shipped. Live dispatch started for delivery boys.", "success")
    else:
        flash(f"Order #{id} marked as {status}.", "success")
    return redirect("/admin/orders")


# ═══════════════════════════════════════
# ASSIGN DELIVERY BOY  (NEW route — add this)
# ═══════════════════════════════════════
@admin.route("/assign-delivery/<int:order_id>", methods=["POST"])
@admin_required
@manager_required
def assign_delivery(order_id):
    """Manually assign delivery boy and send OTP SMS."""
    order           = Order.query.get_or_404(order_id)
    boy_id          = request.form.get("delivery_boy_id", type=int)
    delivery_boy    = User.query.get(boy_id) if boy_id else None

    if not delivery_boy or delivery_boy.role != "delivery_boy":
        flash("Invalid delivery boy selected.", "error")
        return redirect("/admin/orders")

    sms_ok = True
    sms_msg = "OTP SMS sent."
    try:
        order.delivery_boy_id = boy_id
        if not order.delivery_otp:
            order.generate_otp()
        sms_ok, sms_msg = send_msg91_otp(order.shipping_phone or "", order.delivery_otp or "")
        db.session.commit()
    except Exception:
        db.session.rollback()
        flash("Could not assign delivery boy right now.", "error")
        return redirect("/admin/orders")

    if sms_ok:
        flash(f"Assigned to {delivery_boy.name}. OTP sent to customer.", "success")
    else:
        flash(f"Assigned to {delivery_boy.name}, but OTP SMS failed: {sms_msg}", "error")
    return redirect("/admin/orders")


# ═══════════════════════════════════════
# REGENERATE OTP  (NEW route — add this)
# In case customer didn't receive OTP
# ═══════════════════════════════════════
@admin.route("/regenerate-otp/<int:order_id>", methods=["POST"])
@admin_required
@manager_required
def regenerate_otp(order_id):
    """Backward-compatible OTP resend endpoint."""
    return resend_otp(order_id)


@admin.route("/resend-otp/", methods=["POST"])
@admin.route("/resend-otp/<int:order_id>", methods=["POST"])
@admin_required
@manager_required
def resend_otp(order_id=None):
    """Regenerate and resend customer OTP SMS."""
    if order_id is None:
        order_id = request.form.get("order_id", type=int)
    if not order_id:
        flash("Order ID missing for OTP resend.", "error")
        return redirect("/admin/orders")

    order = Order.query.get_or_404(order_id)
    try:
        otp = order.generate_otp()
        sms_ok, sms_msg = send_msg91_otp(order.shipping_phone or "", otp)
        db.session.commit()
    except Exception:
        db.session.rollback()
        flash("Could not regenerate OTP right now.", "error")
        return redirect("/admin/orders")

    if sms_ok:
        flash(f"New OTP sent for Order #{order_id}.", "success")
    else:
        flash(f"OTP regenerated but SMS failed: {sms_msg}", "error")
    return redirect("/admin/orders")


# ═══════════════════════════════════════
# CUSTOMERS — all admins
# ═══════════════════════════════════════
@admin.route("/customers")
@admin_required
def customers():
    q    = request.args.get("q", "").strip()
    page = request.args.get("page", 1, type=int)

    query = User.query.filter_by(role="user")
    if q:
        query = query.filter(
            User.name.ilike(f"%{q}%") | User.email.ilike(f"%{q}%")
        )

    pagination    = query.paginate(page=page, per_page=15, error_out=False)
    users         = pagination.items
    customer_data = []

    for u in users:
        orders_list  = Order.query.filter_by(user_id=u.id).order_by(Order.created_at.desc()).all()
        total_orders = len(orders_list)
        total_spent  = sum(o.total_price or 0 for o in orders_list)
        last_order   = orders_list[0].created_at if orders_list else None
        default_addr = next((a for a in u.addresses if a.is_default), None)
        if not default_addr and u.addresses:
            default_addr = u.addresses[0]
        address_str = default_addr.full_address if default_addr else "N/A"
        customer_data.append({
            "id":         u.id,
            "name":       u.name,
            "email":      u.email,
            "phone":      u.phone or "N/A",
            "address":    address_str,
            "status":     u.status,
            "orders":     total_orders,
            "spent":      total_spent,
            "last_order": last_order,
            "joined":     u.created_at,
        })

    return render_template(
        "admin/customers.html",
        customers  = customer_data,
        pagination = pagination,
    )


# ═══════════════════════════════════════
# TOGGLE CUSTOMER — manager + superadmin only
# ═══════════════════════════════════════
@admin.route("/toggle-customer/<int:id>", methods=["POST"])
@admin_required
@manager_required
def toggle_customer(id):
    u = User.query.get_or_404(id)
    u.status = "Blocked" if u.status == "Active" else "Active"
    db.session.commit()
    flash(f"Customer {u.name} is now {u.status}.", "success")
    return redirect("/admin/customers")


# ═══════════════════════════════════════
# ANALYTICS — all admins
# ═══════════════════════════════════════
@admin.route("/analytics")
@admin_required
def analytics():
    from sqlalchemy import func

    allowed_ranges = {
        "7d": 7,
        "30d": 30,
        "90d": 90,
        "365d": 365,
    }
    range_key = request.args.get("range", "30d")
    if range_key not in allowed_ranges:
        range_key = "30d"
    range_days = allowed_ranges[range_key]

    now = datetime.utcnow()
    today_start = datetime(now.year, now.month, now.day)
    range_start = today_start - timedelta(days=range_days - 1)
    range_end = today_start + timedelta(days=1)
    prev_start = range_start - timedelta(days=range_days)
    prev_end = range_start

    total_revenue = db.session.query(func.sum(Order.total_price)).scalar() or 0
    total_orders = Order.query.count()
    total_customers = User.query.filter_by(role="user").count()
    total_products = Product.query.filter_by(is_active=True).count()

    period_revenue = (
        db.session.query(func.sum(Order.total_price))
        .filter(Order.created_at >= range_start, Order.created_at < range_end)
        .scalar()
        or 0
    )
    period_orders = (
        Order.query
        .filter(Order.created_at >= range_start, Order.created_at < range_end)
        .count()
    )
    prev_period_revenue = (
        db.session.query(func.sum(Order.total_price))
        .filter(Order.created_at >= prev_start, Order.created_at < prev_end)
        .scalar()
        or 0
    )
    prev_period_orders = (
        Order.query
        .filter(Order.created_at >= prev_start, Order.created_at < prev_end)
        .count()
    )

    def pct_change(current, previous):
        if previous == 0:
            return 100.0 if current > 0 else 0.0
        return round(((current - previous) / previous) * 100, 1)

    revenue_growth = pct_change(float(period_revenue), float(prev_period_revenue))
    orders_growth = pct_change(float(period_orders), float(prev_period_orders))
    avg_order_value = round((period_revenue / period_orders), 2) if period_orders else 0

    period_orders_list = (
        Order.query
        .filter(Order.created_at >= range_start, Order.created_at < range_end)
        .order_by(Order.created_at.asc())
        .all()
    )

    revenue_map = {}
    orders_map = {}
    for i in range(range_days):
        day = range_start + timedelta(days=i)
        key = day.strftime("%Y-%m-%d")
        revenue_map[key] = 0.0
        orders_map[key] = 0

    pending_like = {"Pending", "Confirmed", "Processing", "Out for Delivery"}
    status_counts = {"Pending": 0, "Shipped": 0, "Delivered": 0, "Cancelled": 0}
    city_map = {}

    for order in period_orders_list:
        day_key = order.created_at.strftime("%Y-%m-%d")
        if day_key in revenue_map:
            revenue_map[day_key] += float(order.total_price or 0)
            orders_map[day_key] += 1

        order_status = (order.status or "Pending").strip()
        if order_status in pending_like:
            status_counts["Pending"] += 1
        elif order_status == "Shipped":
            status_counts["Shipped"] += 1
        elif order_status == "Delivered":
            status_counts["Delivered"] += 1
        elif order_status == "Cancelled":
            status_counts["Cancelled"] += 1
        else:
            status_counts["Pending"] += 1

        city = (order.shipping_city or "").strip()
        if city:
            city_map[city] = city_map.get(city, 0) + 1

    trend_labels = []
    trend_revenue = []
    trend_orders = []
    for i in range(range_days):
        day = range_start + timedelta(days=i)
        key = day.strftime("%Y-%m-%d")
        trend_labels.append(day.strftime("%d %b"))
        trend_revenue.append(round(revenue_map.get(key, 0), 2))
        trend_orders.append(int(orders_map.get(key, 0)))

    top_cities = sorted(city_map.items(), key=lambda x: x[1], reverse=True)[:5]
    city_labels = [c[0] for c in top_cities] or ["No Data"]
    city_counts = [c[1] for c in top_cities] or [0]

    price_expr = func.coalesce(OrderItem.price_at_purchase, Product.price)
    category_rows = (
        db.session.query(
            Product.category,
            func.sum(OrderItem.quantity),
            func.sum(OrderItem.quantity * price_expr),
        )
        .join(OrderItem, OrderItem.product_id == Product.id)
        .join(Order, Order.id == OrderItem.order_id)
        .filter(Order.created_at >= range_start, Order.created_at < range_end)
        .group_by(Product.category)
        .order_by(func.sum(OrderItem.quantity).desc())
        .limit(6)
        .all()
    )

    category_labels = []
    category_units = []
    category_revenue = []
    for row in category_rows:
        category_labels.append((row[0] or "Uncategorized").strip())
        category_units.append(int(row[1] or 0))
        category_revenue.append(round(float(row[2] or 0), 2))

    if not category_labels:
        category_labels = ["No Data"]
        category_units = [0]
        category_revenue = [0]

    top_product_rows = (
        db.session.query(
            Product.id,
            Product.name,
            Product.category,
            func.sum(OrderItem.quantity).label("units"),
            func.sum(OrderItem.quantity * price_expr).label("revenue"),
        )
        .join(OrderItem, OrderItem.product_id == Product.id)
        .join(Order, Order.id == OrderItem.order_id)
        .filter(Order.created_at >= range_start, Order.created_at < range_end)
        .group_by(Product.id, Product.name, Product.category)
        .order_by(func.sum(OrderItem.quantity * price_expr).desc())
        .limit(8)
        .all()
    )

    top_products = [
        {
            "id": row[0],
            "name": row[1],
            "category": row[2] or "General",
            "sold": int(row[3] or 0),
            "revenue": round(float(row[4] or 0), 2),
        }
        for row in top_product_rows
    ]

    range_labels = {
        "7d": "Last 7 Days",
        "30d": "Last 30 Days",
        "90d": "Last 90 Days",
        "365d": "Last 365 Days",
    }

    return render_template(
        "admin/admin-analytics.html",
        selected_range=range_key,
        range_days=range_days,
        range_label=range_labels.get(range_key, "Last 30 Days"),
        total_revenue=round(float(total_revenue), 2),
        total_orders=total_orders,
        total_customers=total_customers,
        total_products=total_products,
        period_revenue=round(float(period_revenue), 2),
        period_orders=period_orders,
        prev_period_revenue=round(float(prev_period_revenue), 2),
        prev_period_orders=prev_period_orders,
        revenue_growth=revenue_growth,
        orders_growth=orders_growth,
        avg_order_value=avg_order_value,
        trend_labels=trend_labels,
        trend_revenue=trend_revenue,
        trend_orders=trend_orders,
        status_counts=status_counts,
        city_labels=city_labels,
        city_counts=city_counts,
        category_labels=category_labels,
        category_units=category_units,
        category_revenue=category_revenue,
        top_products=top_products,
    )


# ═══════════════════════════════════════
# SETTINGS — all admins
# ═══════════════════════════════════════
@admin.route("/settings")
@admin_required
def settings():
    admin_id   = session.get("admin_id")
    admin_user = Admin.query.get(admin_id) if admin_id else None
    return render_template("admin/admin-settings.html", admin=admin_user)


# ═══════════════════════════════════════
# ADMIN VERIFY — 2-step login flow
# ═══════════════════════════════════════
@admin.route("/verify", methods=["GET", "POST"])
def admin_verify():
    user_id = session.get("user_id")
    if not user_id:
        flash("Please login to your account first.")
        return redirect("/login")

    if session.get("admin_id"):
        return redirect("/admin/dashboard")

    u = User.query.get(user_id)
    if not u or u.status == "Blocked":
        flash("Your account session is invalid. Please login again.", "error")
        return redirect("/login")
    admin_user = Admin.query.filter_by(email=u.email, is_active=True).first()

    if not admin_user:
        flash("No admin account found.")
        return redirect("/")

    if request.method == "POST":
        locked, remaining = is_login_rate_limited(scope="admin_verify")
        if locked:
            wait_mins = max(1, remaining // 60)
            flash(f"Too many failed attempts. Try again in {wait_mins} minute(s).", "error")
            return redirect("/admin/verify")

        password = request.form.get("password", "")
        admin_user = Admin.query.filter_by(email=u.email, is_active=True).first()

        if admin_user and check_password_hash(admin_user.password, password):
            set_admin_session(admin_user)
            session.permanent = True
            clear_login_failures(scope="admin_verify")

            # 🔥 ADD THESE ALSO

            
            admin_user.record_login()
            db.session.commit()
            return redirect("/admin/dashboard")

        register_login_failure(scope="admin_verify")
        flash("Wrong admin password. Access denied.", "error")
        return redirect("/admin/verify")

    return render_template("admin/admin-verify.html", user=u)


# ═══════════════════════════════════════
# ADMIN LOGIN — direct login (Admin table only)
# ═══════════════════════════════════════
@admin.route("/login", methods=["GET", "POST"])
def admin_login():
    if session.get("admin_id"):
        return redirect("/admin/dashboard")

    if request.method == "POST":
        locked, remaining = is_login_rate_limited(scope="admin_login")
        if locked:
            wait_mins = max(1, remaining // 60)
            flash(f"Too many failed attempts. Try again in {wait_mins} minute(s).", "error")
            return redirect("/admin/login")

        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        admin_user = Admin.query.filter_by(email=email, is_active=True).first()
        if admin_user and check_password_hash(admin_user.password, password):
            set_admin_session(admin_user)
            session.permanent = True
            clear_login_failures(scope="admin_login")

            # 🔥 ADD THESE 2 LINES


            admin_user.record_login()
            db.session.commit()
            return redirect("/admin/dashboard")

        register_login_failure(scope="admin_login")
        flash("Invalid email or password.", "error")
        return redirect("/admin/login")

    # GET — template uses get_flashed_messages() directly
    return render_template("admin/admin-login.html")


# ═══════════════════════════════════════
# ADMIN LOGOUT
# ═══════════════════════════════════════
@admin.route("/logout", methods=["POST"])
def admin_logout():
    clear_admin_session()
    clear_login_failures(scope="admin_login")
    clear_login_failures(scope="admin_verify")
    from flask import make_response
    response = make_response(redirect("/"))
    response.delete_cookie("token")
    return response


# ═══════════════════════════════════════
# NOTIFICATIONS — mark as read
# ═══════════════════════════════════════
@admin.route("/notifications/read/<int:id>", methods=["POST"])
@admin_required
def mark_notif_read(id):
    n = Notification.query.get_or_404(id)
    n.is_read = True
    db.session.commit()
    return redirect(n.link or "/admin/dashboard")


# ═══════════════════════════════════════
# SWITCH ADMIN ACCOUNT
# ═══════════════════════════════════════
@admin.route("/switch", methods=["POST"])
def admin_switch():
    clear_admin_session()
    return redirect("/admin/login")


# ═══════════════════════════════════════════════════════════
# ADMIN MANAGEMENT — superadmin only
# All routes below require superadmin_required
# ═══════════════════════════════════════════════════════════

# ── LIST ───────────────────────────────────────────────────
@admin.route("/manage-admins")
@admin_required
@superadmin_required
def manage_admins():
    admins = Admin.query.order_by(Admin.created_at.desc()).all()
    return render_template("admin/admin-management.html", admins=admins)


# ── CREATE ─────────────────────────────────────────────────
@admin.route("/create-admin", methods=["GET", "POST"])
@admin_required
@superadmin_required
def create_admin():
    if request.method == "POST":
        import re

        name      = request.form.get("name", "").strip()
        email     = request.form.get("email", "").strip().lower()
        password  = request.form.get("password", "")
        level     = request.form.get("level", "manager").strip().lower()

        EMAIL_RE = re.compile(r'^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$')

        # ── Server-side validation ─────────────────────────
        if not name or len(name) < 2:
            flash("Name must be at least 2 characters.", "error")
            return redirect("/admin/manage-admins")
        if not EMAIL_RE.match(email):
            flash("Enter a valid email address.", "error")
            return redirect("/admin/manage-admins")
        if len(password) < 8:
            flash("Password must be at least 8 characters.", "error")
            return redirect("/admin/manage-admins")
        if not re.search(r'[A-Z]', password):
            flash("Password must contain at least one uppercase letter.", "error")
            return redirect("/admin/manage-admins")
        if not re.search(r'[0-9]', password):
            flash("Password must contain at least one number.", "error")
            return redirect("/admin/manage-admins")
        if not re.search(r'[^A-Za-z0-9]', password):
            flash("Password must contain at least one symbol.", "error")
            return redirect("/admin/manage-admins")
        if level not in ALLOWED_ADMIN_LEVELS:
            flash("Invalid admin role selected.", "error")
            return redirect("/admin/manage-admins")

        existing = Admin.query.filter_by(email=email).first()
        if existing:
            flash(f"An admin with email '{email}' already exists.", "error")
            return redirect("/admin/manage-admins")

        hashed = generate_password_hash(password)

        new_admin = Admin(
            name          = name,
            email         = email,
            password      = hashed,
            level         = level,
            is_active     = True,
        )
        db.session.add(new_admin)

        # Auto-create matching User account for 2-step login flow
        existing_user = User.query.filter_by(email=email).first()
        if not existing_user:
            new_user = User(
                name     = name,
                email    = email,
                password = hashed,
                role     = "admin",
                status   = "Active",
            )
            db.session.add(new_user)

        db.session.commit()
        flash(f"Admin '{name}' created successfully!", "success")
        return redirect("/admin/manage-admins")

    # GET — redirect to management hub
    return redirect("/admin/manage-admins")


# ── EDIT ───────────────────────────────────────────────────
@admin.route("/edit-admin/<int:id>", methods=["POST"])
@admin_required
@superadmin_required
def edit_admin(id):
    import re
    target = Admin.query.get_or_404(id)

    name     = request.form.get("name", "").strip()
    email    = request.form.get("email", "").strip().lower()
    level    = request.form.get("level", target.level).strip().lower()
    password = request.form.get("password", "").strip()

    EMAIL_RE = re.compile(r'^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$')

    if not name or len(name) < 2:
        flash("Name must be at least 2 characters.", "error")
        return redirect("/admin/manage-admins")
    if not EMAIL_RE.match(email):
        flash("Enter a valid email address.", "error")
        return redirect("/admin/manage-admins")
    if level not in ALLOWED_ADMIN_LEVELS:
        flash("Invalid admin role selected.", "error")
        return redirect("/admin/manage-admins")

    # Email uniqueness — exclude self
    conflict = Admin.query.filter(Admin.email == email, Admin.id != id).first()
    if conflict:
        flash(f"Email '{email}' is already used by another admin.", "error")
        return redirect("/admin/manage-admins")

    target.name  = name
    target.email = email
    target.level = level

    if password:
        if len(password) < 8:
            flash("New password must be at least 8 characters.", "error")
            return redirect("/admin/manage-admins")
        hashed = generate_password_hash(password)
        target.password = hashed
        # Sync password in matching User account
        u = User.query.filter_by(email=email).first()
        if u:
            u.password = hashed

    db.session.commit()
    flash(f"Admin '{name}' updated successfully!", "success")
    return redirect("/admin/manage-admins")


# ── BLOCK / UNBLOCK ────────────────────────────────────────
@admin.route("/toggle-admin/<int:id>", methods=["POST"])
@admin_required
@superadmin_required
def toggle_admin(id):
    current_id = session.get("admin_id")
    target     = Admin.query.get_or_404(id)

    if target.id == current_id:
        flash("You cannot block your own account.", "error")
        return redirect("/admin/manage-admins")
    if target.is_superadmin:
        flash("Superadmin accounts cannot be blocked.", "error")
        return redirect("/admin/manage-admins")

    target.is_active = not target.is_active
    action = "unblocked" if target.is_active else "blocked"
    db.session.commit()
    flash(f"Admin '{target.name}' has been {action}.", "success")
    return redirect("/admin/manage-admins")


# ── DELETE ─────────────────────────────────────────────────
@admin.route("/delete-admin/<int:id>", methods=["POST"])
@admin_required
@superadmin_required
def delete_admin(id):
    current_id = session.get("admin_id")
    target     = Admin.query.get_or_404(id)

    if target.id == current_id:
        flash("You cannot delete your own account.", "error")
        return redirect("/admin/manage-admins")
    if target.is_superadmin:
        flash("Superadmin accounts cannot be deleted.", "error")
        return redirect("/admin/manage-admins")

    # Name confirmation check (sent from delete modal)
    confirm_name = request.form.get("confirm_name", "").strip()
    if confirm_name != target.name:
        flash("Name confirmation did not match. Admin not deleted.", "error")
        return redirect("/admin/manage-admins")

    name = target.name
    db.session.delete(target)
    db.session.commit()
    flash(f"Admin '{name}' has been permanently deleted.", "success")
    return redirect("/admin/manage-admins")
