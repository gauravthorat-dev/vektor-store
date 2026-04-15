from functools import wraps
from flask import Blueprint, render_template, redirect, request, session, flash
from werkzeug.security import check_password_hash, generate_password_hash
from utils.auth import admin_required, manager_required, superadmin_required

from models.order_model import Order
from models.order_item_model import OrderItem
from models.product_model import Product
from models.admin_model import Admin
from models.notification_model import Notification
from database.db import db
from models.user_model import User

admin = Blueprint("admin", __name__, url_prefix="/admin")


# ═══════════════════════════════════════
# DASHBOARD — all admins
# ═══════════════════════════════════════
@admin.route("/dashboard")
@admin_required
def dashboard():
    total_orders    = Order.query.count()
    total_revenue   = db.session.query(db.func.sum(Order.total_price)).scalar() or 0
    total_customers = User.query.filter_by(role="user").count()
    total_products  = Product.query.filter_by(is_active=True).count()
    recent_orders   = Order.query.order_by(Order.created_at.desc()).limit(5).all()
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
    return render_template(
        "admin/admin-dashboard.html",
        total_orders    = total_orders,
        total_revenue   = round(total_revenue, 2),
        total_customers = total_customers,
        total_products  = total_products,
        recent_orders   = recent_orders,
        low_stock       = low_stock,
        notifications   = notifications,
        notif_count     = len(notifications),
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
@admin.route("/delete-product/<int:id>")
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
    )


# ═══════════════════════════════════════
# UPDATE ORDER STATUS  (REPLACE existing update_order() route)
# ═══════════════════════════════════════
@admin.route("/update-order/<int:id>/<status>")
@admin_required
@manager_required
def update_order(id, status):
    allowed = ["Pending", "Confirmed", "Processing", "Shipped",
               "Out for Delivery", "Delivered", "Cancelled"]
    order = Order.query.get_or_404(id)

    if status not in allowed:
        flash("Invalid status.", "error")
        return redirect("/admin/orders")

    order.set_status(status)

    # Auto-generate OTP when order is shipped (customer receives it)
    if status == "Shipped" and not order.delivery_otp:
        otp = order.generate_otp()
        # TODO: Send OTP via SMS to order.shipping_phone using your SMS provider
        # e.g. send_sms(order.shipping_phone, f"Your VEKTOR delivery OTP is {otp}. Share only with delivery partner.")
        flash(f"Order #{id} shipped. OTP {otp} generated for customer.", "success")
    else:
        flash(f"Order #{id} marked as {status}.", "success")

    db.session.commit()
    return redirect("/admin/orders")


# ═══════════════════════════════════════
# ASSIGN DELIVERY BOY  (NEW route — add this)
# ═══════════════════════════════════════
@admin.route("/assign-delivery/<int:order_id>", methods=["POST"])
@admin_required
@manager_required
def assign_delivery(order_id):
    order           = Order.query.get_or_404(order_id)
    boy_id          = request.form.get("delivery_boy_id", type=int)
    delivery_boy    = User.query.get(boy_id) if boy_id else None

    if not delivery_boy or delivery_boy.role != "delivery_boy":
        flash("Invalid delivery boy selected.", "error")
        return redirect("/admin/orders")

    order.delivery_boy_id = boy_id

    # Auto-advance to Processing if still Pending/Confirmed
    if order.status in ("Pending", "Confirmed"):
        order.set_status("Processing")

    # Generate OTP now if not already done
    if not order.delivery_otp:
        otp = order.generate_otp()
        # TODO: SMS to customer → order.shipping_phone
        flash(f"Assigned to {delivery_boy.name}. OTP {otp} sent to customer.", "success")
    else:
        flash(f"Order reassigned to {delivery_boy.name}.", "success")

    db.session.commit()
    return redirect("/admin/orders")


# ═══════════════════════════════════════
# REGENERATE OTP  (NEW route — add this)
# In case customer didn't receive OTP
# ═══════════════════════════════════════
@admin.route("/regenerate-otp/<int:order_id>", methods=["POST"])
@admin_required
@manager_required
def regenerate_otp(order_id):
    order = Order.query.get_or_404(order_id)
    otp   = order.generate_otp()
    db.session.commit()
    # TODO: Resend SMS to order.shipping_phone
    flash(f"New OTP {otp} generated for Order #{order_id}.", "success")
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
@admin.route("/toggle-customer/<int:id>")
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
    total_revenue   = db.session.query(func.sum(Order.total_price)).scalar() or 0
    total_orders    = Order.query.count()
    total_customers = User.query.filter_by(role="user").count()
    avg_order_value = round(total_revenue / total_orders, 2) if total_orders else 0
    top_products = sorted(
        Product.query.filter_by(is_active=True).all(),
        key=lambda p: p.total_revenue,
        reverse=True
    )[:5]
    return render_template(
        "admin/admin-analytics.html",
        total_revenue   = round(total_revenue, 2),
        total_orders    = total_orders,
        total_customers = total_customers,
        avg_order_value = avg_order_value,
        top_products    = top_products,
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
    admin_user = Admin.query.filter_by(email=u.email, is_active=True).first()

    if not admin_user:
        flash("No admin account found.")
        return redirect("/")

    if request.method == "POST":
        password   = request.form.get("password", "")
        admin_user = Admin.query.filter_by(email=u.email, is_active=True).first()

        if admin_user and check_password_hash(admin_user.password, password):
            session["admin_id"]    = admin_user.id
            session["admin_name"]  = admin_user.name
            session["admin_level"] = admin_user.level

            # 🔥 ADD THESE ALSO
            session["user_role"] = "admin"
            session["user_id"]   = admin_user.id
            
            admin_user.record_login()
            db.session.commit()
            return redirect("/admin/dashboard")

        flash("Wrong admin password. Access denied.")
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
        email    = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        admin_user = Admin.query.filter_by(email=email, is_active=True).first()
        if admin_user and check_password_hash(admin_user.password, password):
            session["admin_id"]    = admin_user.id
            session["admin_name"]  = admin_user.name
            session["admin_level"] = admin_user.level

            # 🔥 ADD THESE 2 LINES
            session["user_role"] = "admin"
            session["user_id"]   = admin_user.id

            admin_user.record_login()
            db.session.commit()
            return redirect("/admin/dashboard")

        flash("Invalid email or password.", "error")
        return redirect("/admin/login")

    # GET — template uses get_flashed_messages() directly
    return render_template("admin/admin-login.html")


# ═══════════════════════════════════════
# ADMIN LOGOUT
# ═══════════════════════════════════════
@admin.route("/logout")
def admin_logout():
    session.pop("admin_id",    None)
    session.pop("admin_name",  None)
    session.pop("admin_level", None)
    session.pop("user_id",     None)
    session.pop("user_name",   None)
    from flask import make_response
    response = make_response(redirect("/"))
    response.delete_cookie("token")
    return response


# ═══════════════════════════════════════
# NOTIFICATIONS — mark as read
# ═══════════════════════════════════════
@admin.route("/notifications/read/<int:id>")
@admin_required
def mark_notif_read(id):
    n = Notification.query.get_or_404(id)
    n.is_read = True
    db.session.commit()
    return redirect(n.link or "/admin/dashboard")


# ═══════════════════════════════════════
# SWITCH ADMIN ACCOUNT
# ═══════════════════════════════════════
@admin.route("/switch")
def admin_switch():
    session.pop("admin_id",    None)
    session.pop("admin_name",  None)
    session.pop("admin_level", None)
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
        level     = request.form.get("level", "manager")
        is_super  = bool(request.form.get("is_superadmin"))

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
            is_superadmin = is_super,
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
    level    = request.form.get("level", target.level)
    password = request.form.get("password", "").strip()

    EMAIL_RE = re.compile(r'^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$')

    if not name or len(name) < 2:
        flash("Name must be at least 2 characters.", "error")
        return redirect("/admin/manage-admins")
    if not EMAIL_RE.match(email):
        flash("Enter a valid email address.", "error")
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