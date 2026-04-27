from flask import Blueprint, render_template, redirect, session, request, jsonify, flash
from models.cart_model       import Cart
from models.product_model    import Product
from models.order_model      import Order
from models.order_item_model import OrderItem
from models.user_model       import User
from models.review_model     import Review
from models.address_model    import Address
from models.notification_model import Notification
from database.db             import db
from services.dispatch_service import broadcast_shipped_order, emit_stats_update

from models.wishlist_model   import Wishlist

shop = Blueprint("shop", __name__)


# ═══════════════════════════════════════
# HOME
# ═══════════════════════════════════════
@shop.route("/")
def home():
    # ── Role guard: non-shoppers should not see the homepage ──
    # 🔥 STRONG CHECK

    if session.get("admin_id"):
        return redirect("/admin/dashboard")

    if session.get("user_role") == "delivery_boy":
        return redirect("/delivery/dashboard")

    new_arrivals = (
        Product.query
        .filter_by(is_active=True)
        .order_by(Product.created_at.desc())
        .limit(3)
        .all()
    )
    reviews = (
        Review.query
        .filter_by(is_approved=True)
        .order_by(Review.created_at.desc())
        .limit(3)
        .all()
    )
    categories = ['Shirts', 'T-Shirts', 'Jeans', 'Jackets', 'Trousers']
    category_counts = {}
    for cat in categories:
        slug  = cat.lower().replace('-', '').replace(' ', '')
        count = Product.query.filter_by(category=cat, is_active=True).count()
        category_counts[cat]  = count
        category_counts[slug] = count

    customers_k = User.query.filter_by(role="user").count()
    stats = {
        "customers": max(int(customers_k / 1000), 12),
        "products":  Product.query.filter_by(is_active=True).count() or 200,
        "orders":    Order.query.count() or 0,
    }

    return render_template(
        "home.html",
        new_arrivals    = new_arrivals,
        reviews         = reviews,
        category_counts = category_counts,
        stats           = stats,
    )


# ═══════════════════════════════════════
# SHOP PAGE
# ═══════════════════════════════════════
@shop.route("/shop")
def shop_page():
    q         = request.args.get("q", "").strip()
    category  = request.args.get("category", "")
    sort_by   = request.args.get("sort", "new")
    page      = request.args.get("page", 1, type=int)
    price_max = request.args.get("price_max", 10000, type=int)
    sel_sizes = request.args.getlist("size")    # e.g. ['M', 'L']
    sel_color = request.args.get("color", "")  # e.g. 'Navy'

    query = Product.query.filter_by(is_active=True)

    # ── Text search ──────────────────────────────────────────────
    if q:
        query = query.filter(Product.name.ilike(f"%{q}%"))

    # ── Category filter ──────────────────────────────────────────
    if category:
        query = query.filter_by(category=category)

    # ── Price filter ─────────────────────────────────────────────
    if price_max < 10000:
        query = query.filter(Product.price <= price_max)

    # ── Size filter ───────────────────────────────────────────────
    # Only runs if your Product model has a `sizes` column
    # (a comma-separated string like "S,M,L,XL").
    # If you don't have that column yet, this block is safely skipped.
    if sel_sizes:
        try:
            from sqlalchemy import or_
            query = query.filter(
                or_(*[Product.sizes.ilike(f"%{s}%") for s in sel_sizes])
            )
        except AttributeError:
            pass  # Product.sizes column doesn't exist yet — skip silently

    # ── Color filter ──────────────────────────────────────────────
    # Only runs if your Product model has a `color` column.
    if sel_color:
        try:
            query = query.filter(Product.color.ilike(f"%{sel_color}%"))
        except AttributeError:
            pass  # Product.color column doesn't exist yet — skip silently

    # ── Sort ──────────────────────────────────────────────────────
    if sort_by == "low":
        query = query.order_by(Product.price.asc())
    elif sort_by == "high":
        query = query.order_by(Product.price.desc())
    else:
        query = query.order_by(Product.created_at.desc())

    pagination = query.paginate(page=page, per_page=12, error_out=False)
    products   = pagination.items

    return render_template(
        "shop.html",
        products   = products,
        pagination = pagination,
        price_max  = price_max,
        sel_sizes  = sel_sizes,
        sel_color  = sel_color,
    )


# ═══════════════════════════════════════
# STATIC PAGES
# ═══════════════════════════════════════
@shop.route("/collections")
def collections():
    return render_template("collections.html")

@shop.route("/story")
def story():
    return render_template("story.html")

@shop.route("/lookbook")
def lookbook():
    products = Product.query.filter_by(is_active=True).limit(6).all()
    return render_template("lookbook.html", products=products)


# ═══════════════════════════════════════
# PRODUCT DETAIL
# ═══════════════════════════════════════
# @shop.route("/product")
# def product():
#     product_id = request.args.get("id", type=int)
#     if product_id:
#         p = Product.query.get_or_404(product_id)
#         related = (
#             Product.query
#             .filter_by(category=p.category, is_active=True)
#             .filter(Product.id != p.id)
#             .limit(3)
#             .all()
#         )
#         reviews = (
#             Review.query
#             .filter_by(product_id=p.id, is_approved=True)
#             .order_by(Review.created_at.desc())
#             .limit(10)
#             .all()
#         )
#         return render_template("shop/product-details.html", product=p, related=related, reviews=reviews)

#     name  = request.args.get("name",  "Product")
#     price = request.args.get("price", 0, type=int)
#     return render_template("product.html", product=None, name=name, price=price, related=[], reviews=[])

# ═══════════════════════════════════════════════════════════════
# REPLACE your existing /product route in shop_routes.py with this
# Adds: is_wishlisted passed to template
# ═══════════════════════════════════════════════════════════════



# @shop.route("/product")
# def product():
#     product_id = request.args.get("id", type=int)
#     if not product_id:
#         name  = request.args.get("name",  "Product")
#         price = request.args.get("price", 0, type=int)
#         return render_template("shop/product-details.html", product=None, name=name, price=price, related=[], reviews=[], is_wishlisted=False)

#     p = Product.query.get_or_404(product_id)

#     related = (
#         Product.query
#         .filter_by(category=p.category, is_active=True)
#         .filter(Product.id != p.id)
#         .limit(3)
#         .all()
#     )
#     reviews = (
#         Review.query
#         .filter_by(product_id=p.id, is_approved=True)
#         .order_by(Review.created_at.desc())
#         .limit(10)
#         .all()
#     )

#     # Check if logged-in user has wishlisted this product
#     user_id = session.get("user_id")
#     is_wishlisted = False
#     if user_id:
#         is_wishlisted = Wishlist.query.filter_by(
#             user_id=user_id, product_id=p.id
#         ).first() is not None

#     return render_template(
#         "shop/product-details.html",
#         product       = p,
#         related       = related,
#         reviews       = reviews,
#         is_wishlisted = is_wishlisted,
#     )

@shop.route("/product")
def product():
    product_id = request.args.get("id", type=int)

    if not product_id:
        return "Product not found"

    p = Product.query.get_or_404(product_id)

    related = (
        Product.query
        .filter_by(category=p.category, is_active=True)
        .filter(Product.id != p.id)
        .limit(3)
        .all()
    )

    reviews = (
        Review.query
        .filter_by(product_id=p.id, is_approved=True)
        .order_by(Review.created_at.desc())
        .limit(10)
        .all()
    )

    user_id = session.get("user_id")
    is_wishlisted = False
    can_review = False
    already_reviewed = False

    if user_id:
        # Wishlist check
        is_wishlisted = Wishlist.query.filter_by(
            user_id=user_id,
            product_id=p.id
        ).first() is not None

        # Already reviewed?
        already_reviewed = Review.query.filter_by(
            user_id=user_id,
            product_id=p.id
        ).first() is not None

        # Delivered order check ✅ FIXED
        delivered = (
            db.session.query(Order)
            .join(OrderItem, Order.id == OrderItem.order_id)
            .filter(
                Order.user_id == user_id,
                Order.status == "Delivered",
                OrderItem.product_id == p.id
            )
            .first()
        )

        can_review = (delivered is not None) and (not already_reviewed)

    return render_template(
        "shop/product-details.html",
        product=p,
        related=related,
        reviews=reviews,
        is_wishlisted=is_wishlisted,
        can_review=can_review,
        already_reviewed=already_reviewed,
    )



@shop.route("/product/<int:product_id>/review", methods=["POST"])
def submit_review(product_id):
    user_id = session.get("user_id")

    if not user_id:
        flash("Please login to submit a review.", "error")
        return redirect(f"/product?id={product_id}")

    # Delivered check ✅ FIXED
    delivered = (
        db.session.query(Order)
        .join(OrderItem, Order.id == OrderItem.order_id)
        .filter(
            Order.user_id == user_id,
            Order.status == "Delivered",
            OrderItem.product_id == product_id
        )
        .first()
    )

    if not delivered:
        flash("You can only review products you have purchased.", "error")
        return redirect(f"/product?id={product_id}")

    # Prevent duplicate
    existing = Review.query.filter_by(
        user_id=user_id,
        product_id=product_id
    ).first()

    if existing:
        flash("You have already reviewed this product.", "info")
        return redirect(f"/product?id={product_id}")

    rating = request.form.get("rating", type=int)
    title  = request.form.get("title", "").strip()
    body   = request.form.get("body", "").strip()

    if not rating or not (1 <= rating <= 5):
        flash("Please select a valid rating.", "error")
        return redirect(f"/product?id={product_id}")

    review = Review(
        user_id=user_id,
        product_id=product_id,
        rating=rating,
        title=title,
        body=body,
        is_verified=True,
        is_approved=True,
    )

    db.session.add(review)
    db.session.commit()

    flash("Review submitted successfully! ✓", "success")
    return redirect(f"/product?id={product_id}#tab-reviews")

# ═══════════════════════════════════════
# CART  ← BUG FIXED: template path was "shop/cart.html", now "cart.html"
# ═══════════════════════════════════════
@shop.route("/cart")
def cart():
    user_id = session.get("user_id")
    if not user_id:
        return redirect("/login")

    cart_items = Cart.query.filter_by(user_id=user_id).all()
    items  = []
    total  = 0

    for item in cart_items:
        p = Product.query.get(item.product_id)
        if not p:
            continue
        subtotal = p.final_price * item.quantity
        total   += subtotal
        items.append({
            "id":       item.product_id,
            "cart_id":  item.id,
            "name":     p.name,
            "price":    p.final_price,
            "qty":      item.quantity,
            "quantity": item.quantity,
            "image":    p.image,
            "subtotal": subtotal,
            "in_stock": p.in_stock,
            "product":  p,
            "size":     item.size,
            "color":    item.color,
        })

    return render_template("shop/cart.html", items=items, total=total)   # ✅ FIXED PATH


# ═══════════════════════════════════════
# ADD TO CART
# ═══════════════════════════════════════
@shop.route("/add-to-cart/<int:product_id>")
def add_to_cart(product_id):
    user_id = session.get("user_id")
    if not user_id:
        return redirect("/login")

    p = Product.query.get_or_404(product_id)
    if not p.in_stock:
        flash("Product is out of stock")
        return redirect(f"/product?id={product_id}")

    existing = Cart.query.filter_by(user_id=user_id, product_id=product_id).first()
    if existing:
        existing.quantity += 1
    else:
        db.session.add(Cart(user_id=user_id, product_id=product_id, quantity=1))

    db.session.commit()
    return redirect("/cart")


# ═══════════════════════════════════════
# UPDATE CART QUANTITY  ← NEW ROUTE (used by cart.html +/- buttons)
# ═══════════════════════════════════════
@shop.route("/update-cart/<int:cart_id>", methods=["POST"])
def update_cart(cart_id):
    user_id = session.get("user_id")
    item    = Cart.query.filter_by(id=cart_id, user_id=user_id).first()

    if item:
        action = request.form.get("action")
        if action == "increase":
            item.quantity += 1
        elif action == "decrease":
            item.quantity -= 1
            if item.quantity <= 0:
                db.session.delete(item)
        db.session.commit()

    return redirect("/cart")


# ═══════════════════════════════════════
# REMOVE FROM CART  ← supports both /remove-from-cart/<id> and /remove-cart/<id>
# ═══════════════════════════════════════
@shop.route("/remove-from-cart/<int:product_id>")
def remove_from_cart(product_id):
    user_id = session.get("user_id")
    item = Cart.query.filter_by(user_id=user_id, product_id=product_id).first()
    if item:
        db.session.delete(item)
        db.session.commit()
    return redirect("/cart")

@shop.route("/remove-cart/<int:cart_id>")
def remove_cart_item(cart_id):
    user_id = session.get("user_id")
    item = Cart.query.filter_by(id=cart_id, user_id=user_id).first()
    if item:
        db.session.delete(item)
        db.session.commit()
    return redirect("/cart")


# ═══════════════════════════════════════
# CHECKOUT
# ═══════════════════════════════════════
@shop.route("/checkout")
def checkout():
    user_id = session.get("user_id")
    if not user_id:
        return redirect("/login")

    cart_items = Cart.query.filter_by(user_id=user_id).all()
    if not cart_items:
        return redirect("/cart")

    items  = []
    total  = 0
    for item in cart_items:
        p = Product.query.get(item.product_id)
        if p:
            subtotal = p.final_price * item.quantity
            total   += subtotal
            items.append({
                "name":     p.name,
                "price":    p.final_price,
                "qty":      item.quantity,
                "subtotal": subtotal,
                "image":    p.image,
            })

    # Load saved addresses for the user
    user      = User.query.get(user_id)
    addresses = Address.query.filter_by(user_id=user_id).all()

    return render_template(
        "shop/checkout.html",
        items     = items,
        total     = total,
        user      = user,
        addresses = addresses,
    )


# ═══════════════════════════════════════
# PLACE ORDER  ← BUG FIXED: now captures shipping address from form
# ═══════════════════════════════════════
@shop.route("/place-order", methods=["POST"])
def place_order():
    user_id = session.get("user_id")
    if not user_id:
        return redirect("/login")

    cart_items = Cart.query.filter_by(user_id=user_id).all()
    if not cart_items:
        flash("Your cart is empty")
        return redirect("/cart")

    # ── Calculate total ───────────────────────────────────────
    total = 0
    for item in cart_items:
        p = Product.query.get(item.product_id)
        if p:
            total += p.final_price * item.quantity

    # ── Capture shipping address from checkout form ────────────
    new_order = Order(
        user_id          = user_id,
        total_price      = round(total, 2),
        status           = "Pending",
        payment_method   = request.form.get("payment_method", "COD"),
        payment_status   = "Pending",
        shipping_name    = request.form.get("full_name", ""),
        shipping_phone   = request.form.get("phone", ""),
        shipping_address = request.form.get("address", ""),
        shipping_city    = request.form.get("city", ""),
        shipping_pincode = request.form.get("pincode", ""),
        shipping_state   = request.form.get("state", "Maharashtra"),
        shipping_country = request.form.get("country", "India"),
    )
    db.session.add(new_order)
    db.session.commit()

    # ── Create order items + reduce stock ──────────────────────
    for item in cart_items:
        p = Product.query.get(item.product_id)
        if not p:
            continue
        order_item = OrderItem(
            order_id          = new_order.id,
            product_id        = item.product_id,
            product_name      = p.name,
            quantity          = item.quantity,
            price_at_purchase = p.final_price,
        )
        db.session.add(order_item)
        if p.stock:
            p.stock = max(0, p.stock - item.quantity)
            # Trigger low stock notification
            if p.stock <= 5:
                existing = Notification.query.filter_by(
                    notif_type="stock", product_id=p.id, is_read=False
                ).first()
                if not existing:
                    db.session.add(Notification.low_stock(p))
        db.session.delete(item)

    db.session.commit()

    # ── New order notification for admin ──────────────────────
    db.session.add(Notification.new_order(new_order))

    # Auto-dispatch flow: move to Shipped immediately so delivery boys get
    # the live accept request without admin manually changing status.
    new_order.set_status("Shipped")
    db.session.commit()
    emit_stats_update()
    broadcast_shipped_order(new_order.id)

    return redirect(f"/success?order_id={new_order.id}")


# ═══════════════════════════════════════
# SUCCESS  ← BUG FIXED: now passes order object to template
# ═══════════════════════════════════════
@shop.route("/success")
def success():
    order_id = request.args.get("order_id", type=int)
    order    = Order.query.get(order_id) if order_id else None

    if not order:
        # Fallback: get user's latest order
        user_id = session.get("user_id")
        if user_id:
            order = Order.query.filter_by(user_id=user_id).order_by(Order.created_at.desc()).first()

    return render_template("shop/success.html", order=order)


# ═══════════════════════════════════════
# APPLY COUPON (stub — extend as needed)
# ═══════════════════════════════════════
@shop.route("/apply-coupon", methods=["POST"])
def apply_coupon():
    from models.coupon_model import Coupon
    code       = request.form.get("coupon", "").strip().upper()
    coupon     = Coupon.query.filter_by(code=code).first()
    user_id    = session.get("user_id")
    cart_items = Cart.query.filter_by(user_id=user_id).all()
    total      = sum(
        (Product.query.get(i.product_id).final_price * i.quantity)
        for i in cart_items
        if Product.query.get(i.product_id)
    )

    if coupon and coupon.is_valid:
        discount = coupon.calculate_discount(total)
        session["coupon_code"]     = code
        session["coupon_discount"] = discount
        flash(f"Coupon applied! You save ₹{discount:.0f}")
    else:
        flash("Invalid or expired coupon code")

    return redirect("/cart")

# ═══════════════════════════════════════════════════════════════
# ADD THESE TWO ROUTES to your shop_routes.py
# ═══════════════════════════════════════════════════════════════

# ── 1. ADD TO CART (POST) — replaces GET-only version ──────────
# Receives qty, size, color from the product page form.
# Add this ALONGSIDE the existing GET route (keep the old one too
# so sticky bar / related product "+ CART" links still work).
# ───────────────────────────────────────────────────────────────
@shop.route("/add-to-cart-post/<int:product_id>", methods=["POST"])
def add_to_cart_post(product_id):
    user_id = session.get("user_id")
    if not user_id:
        return redirect("/login")

    p = Product.query.get_or_404(product_id)
    if not p.in_stock:
        flash("Product is out of stock · स्टॉक संपला", "error")
        return redirect(f"/product?id={product_id}")

    qty   = int(request.form.get("qty",   1))
    size  = request.form.get("size",  "")
    color = request.form.get("color", "")
    qty   = max(1, min(10, qty))   # clamp 1–10

    existing = Cart.query.filter_by(
        user_id=user_id, product_id=product_id, size=size, color=color
    ).first()

    if existing:
        existing.quantity = min(10, existing.quantity + qty)
    else:
        db.session.add(Cart(
            user_id=user_id,
            product_id=product_id,
            quantity=qty,
            size=size,
            color=color,
        ))

    db.session.commit()
    flash(f"Added to cart! · कार्टमध्ये जोडले ✓", "success")
    return redirect("/cart")


# ── 2. WISHLIST TOGGLE (AJAX POST) ─────────────────────────────
# Called by toggleWishlist() in JS via fetch().
# Returns JSON: { "wishlisted": true/false }
# ───────────────────────────────────────────────────────────────

@shop.route("/wishlist/toggle/<int:product_id>", methods=["POST"])
def wishlist_toggle(product_id):
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"error": "login_required"}), 401

    existing = Wishlist.query.filter_by(
        user_id=user_id, product_id=product_id
    ).first()

    if existing:
        db.session.delete(existing)
        db.session.commit()
        return jsonify({"wishlisted": False})
    else:
        db.session.add(Wishlist(user_id=user_id, product_id=product_id))
        db.session.commit()
        return jsonify({"wishlisted": True})
    


# ═══════════════════════════════════════════════════════════════
# ADD THESE ROUTES to shop_routes.py
# ═══════════════════════════════════════════════════════════════

# ── WISHLIST PAGE ────────────────────────────────────────────
@shop.route("/wishlist")
def wishlist_page():
    user_id = session.get("user_id")
    if not user_id:
        flash("Please login to view your wishlist · लॉगिन करा", "error")
        return redirect("/login")

    wishlist_items = Wishlist.query.filter_by(user_id=user_id)\
                             .order_by(Wishlist.added_at.desc()).all()

    return render_template("shop/wishlist.html", wishlist_items=wishlist_items)


# ── WISHLIST REMOVE (GET — from wishlist page Remove button) ─
@shop.route("/wishlist/remove/<int:product_id>")
def wishlist_remove(product_id):
    user_id = session.get("user_id")
    if not user_id:
        return redirect("/login")

    item = Wishlist.query.filter_by(user_id=user_id, product_id=product_id).first()
    if item:
        db.session.delete(item)
        db.session.commit()
        flash("Removed from wishlist · विशलिस्टमधून काढले", "success")

    return redirect("/wishlist")


# ═══════════════════════════════════════
# CLEAR CART
# ═══════════════════════════════════════
@shop.route("/clear-cart")
def clear_cart():
    user_id = session.get("user_id")
    if not user_id:
        return redirect("/login")

    Cart.query.filter_by(user_id=user_id).delete()
    db.session.commit()
    flash("Cart cleared · कार्ट रिकामी केली", "success")
    return redirect("/cart")

@shop.route("/shop<path:extra>")
def shop_fix(extra):
    if extra.startswith("&"):
        return redirect("/shop?" + extra[1:])
    return redirect("/shop")
