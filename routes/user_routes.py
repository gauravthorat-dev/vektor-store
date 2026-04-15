from flask import Blueprint, render_template, request, redirect, session, flash, url_for, make_response
from werkzeug.security import generate_password_hash, check_password_hash

from models.user_model import User
from models.order_model import Order
from models.order_item_model import OrderItem
from models.product_model import Product

from database.db import db
from utils.auth import jwt_required, generate_token, decode_token

# ✅ Blueprint
user = Blueprint("user", __name__)


# ================= HELPER — check if already logged in =================
def get_logged_in_user():
    """Returns user object if logged in via session or JWT, else None."""

    # Session check (fastest)
    user_id = session.get("user_id")
    if user_id:
        u = User.query.get(user_id)
        if u and u.status != "Blocked":
            return u

    # JWT cookie fallback
    token = request.cookies.get("token")
    if token:
        data = decode_token(token)
        if data:
            u = User.query.get(data["user_id"])
            if u and u.status != "Blocked":
                return u

    return None


# ================= LOGIN =================
# ================= LOGIN =================
@user.route("/login", methods=["GET", "POST"])
def login():

    existing = get_logged_in_user()
    if existing:
        if existing.role == "delivery_boy":
            return redirect("/delivery/dashboard")
        if existing.role == "admin":
            return redirect("/admin/dashboard")
        return redirect("/")

    if request.method == "POST":
        email    = request.form["email"]
        password = request.form["password"]

        user_data = User.query.filter_by(email=email).first()

        if not user_data:
            flash("Invalid Email or Password", "error")
            return redirect("/login")

        if user_data.status == "Blocked":
            flash("Your account is blocked! Contact admin.")
            return redirect("/login")

        if check_password_hash(user_data.password, password):
            token = generate_token(user_data)

            session["user_id"]   = user_data.id
            session["user_name"] = user_data.name
            session["user_role"] = user_data.role   # ✅ role stored for SocketIO + guards

            if user_data.role == "delivery_boy":
                response = make_response(redirect("/delivery/dashboard"))
            elif user_data.role == "admin":
                response = make_response(redirect("/admin/dashboard"))
            else:
                response = make_response(redirect("/"))

            response.set_cookie("token", token, httponly=True, samesite="Lax")
            return response

        flash("Invalid Email or Password")
        return redirect("/login")

    return render_template("user/login.html")


# ================= LOGOUT =================
@user.route("/logout")
def logout():
    session.clear()

    response = make_response(redirect(url_for("user.login")))
    response.delete_cookie("token")

    # 🔥 Prevent browser from caching the page so back button doesn't restore it
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"

    return response


# ================= SIGNUP =================
@user.route("/signup", methods=["GET", "POST"])
def signup():

    # ✅ FIX — if already logged in, redirect away from signup page
    existing = get_logged_in_user()
    if existing:
        if existing.role == "admin":
            return redirect("/admin/dashboard")
        return redirect("/")

    if request.method == "POST":

        first_name = request.form.get("first_name", "").strip()
        last_name = request.form.get("last_name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")
        phone = request.form.get("phone", "").strip()

        name = f"{first_name} {last_name}".strip()

        if not first_name or not email or not password:
            flash("Please fill all required fields")
            return redirect("/signup")

        if password != confirm_password:
            flash("Passwords do not match")
            return redirect("/signup")

        existing_user = User.query.filter_by(email=email).first()
        if existing_user:
            flash("Email already registered")
            return redirect("/signup")

        hashed_password = generate_password_hash(password)

        new_user = User(
            name=name,
            email=email,
            password=hashed_password,
            phone=phone
        )

        db.session.add(new_user)
        db.session.commit()

        flash("Registration Successful 🎉 Please login")
        return redirect("/login")

    return render_template("user/signup.html")


# ================= FORGOT PASSWORD =================
@user.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():

    if request.method == 'POST':

        email = request.form['email'].strip().lower()
        user_data = User.query.filter_by(email=email).first()

        if user_data:
            session['reset_email'] = email
            return redirect(url_for('user.reset_password'))
        else:
            flash("Email not found")

    return render_template('auth/forgot-password.html')


# ================= RESET PASSWORD =================
@user.route('/reset-password', methods=['GET', 'POST'])
def reset_password():

    if 'reset_email' not in session:
        return redirect(url_for('user.forgot_password'))

    if request.method == 'POST':

        new_password = request.form['password']
        hashed_password = generate_password_hash(new_password)

        user_data = User.query.filter_by(email=session['reset_email']).first()

        if user_data:
            user_data.password = hashed_password
            db.session.commit()

        session.pop('reset_email', None)

        flash("Password updated successfully", "success")
        return redirect("/login")

    return render_template('auth/reset-password.html')


# ================= PROFILE =================
@user.route("/profile")
@jwt_required
def profile():
    return render_template("user/profile.html")


# ================= EDIT PROFILE =================
@user.route("/edit-profile")
@jwt_required
def edit_profile():
    return render_template("user/edit-profile.html")


# ================= MY ORDERS =================
@user.route("/my-orders")
@jwt_required
def my_orders():

    token = request.cookies.get("token")
    data = decode_token(token)

    if not data:
        return redirect("/login")

    user_id = data["user_id"]

    orders = Order.query.filter_by(user_id=user_id)\
                        .order_by(Order.id.desc())\
                        .all()

    order_data = []

    for order in orders:

        items = OrderItem.query.filter_by(order_id=order.id).all()
        product_list = []

        for item in items:
            product = Product.query.get(item.product_id)
            if product:
                image_url = f"/static/uploads/{product.image}" if product.image else None
                product_list.append({
                    "name":  product.name,
                    "price": (item.price_at_purchase or product.final_price) * item.quantity,
                    "qty":   item.quantity,
                    "image": image_url,
                })

        order_data.append({
            "id":               order.id,
            "total":            order.total_price,
            "status":           order.status,
            "date":             order.created_at.strftime("%d %b %Y"),
            "products":         product_list,
            "discount_amount":  order.discount_amount or 0,
            "payment_method":   order.payment_method  or "COD",
            "payment_status":   order.payment_status  or "Pending",
            "shipping_name":    order.shipping_name    or "",
            "shipping_phone":   order.shipping_phone   or "",
            "shipping_address": order.shipping_address or "",
            "shipping_city":    order.shipping_city    or "",
            "shipping_pincode": order.shipping_pincode or "",
            "shipping_state":   order.shipping_state   or "Maharashtra",
            "shipping_country": order.shipping_country or "India",
        })

    return render_template("user/my-orders.html", orders=order_data)


# ================= PLACE ORDER =================
@user.route("/place-order", methods=["POST"])
@jwt_required
def place_order():

    token = request.cookies.get("token")
    data = decode_token(token)

    if not data:
        return redirect("/login")

    user_id = data["user_id"]

    from models.cart_model import Cart
    cart_items = Cart.query.filter_by(user_id=user_id).all()

    if not cart_items:
        flash("Cart is empty")
        return redirect("/cart")

    total_price = sum(item.product.final_price * item.quantity for item in cart_items)

    new_order = Order(
        user_id=user_id,
        total_price=total_price,
        status="Pending"
    )

    db.session.add(new_order)
    db.session.commit()

    for item in cart_items:
        order_item = OrderItem(
            order_id=new_order.id,
            product_id=item.product_id,
            quantity=item.quantity
        )
        db.session.add(order_item)

    db.session.commit()

    Cart.query.filter_by(user_id=user_id).delete()
    db.session.commit()

    flash("Order placed successfully 🎉")
    return redirect("/my-orders")


# ================= ORDER DETAILS =================
# Supports both /order-details?id=1  and  /order-details/1
@user.route("/order-details", methods=["GET"])
@user.route("/order-details/<int:order_id>", methods=["GET"])
@jwt_required
def order_details(order_id=None):

    token = request.cookies.get("token")
    data = decode_token(token)

    if not data:
        return redirect("/login")

    user_id = data["user_id"]

    # Accept ?id= query param OR /<int:order_id> path param
    if order_id is None:
        order_id = request.args.get("id", type=int)

    if not order_id:
        return redirect("/my-orders")

    order = Order.query.get(order_id)

    if not order:
        flash("Order not found")
        return redirect("/my-orders")

    if order.user_id != user_id:
        return redirect("/my-orders")

    items = OrderItem.query.filter_by(order_id=order.id).all()
    product_list = []

    for item in items:
        product = Product.query.get(item.product_id)
        if product:
            image_url = f"/static/uploads/{product.image}" if product.image else None
            product_list.append({
                "name":  product.name,
                "price": (item.price_at_purchase or product.final_price) * item.quantity,
                "qty":   item.quantity,
                "image": image_url,
            })

    order_data = {
        "id":               order.id,
        "total":            order.total_price,
        "status":           order.status,
        "date":             order.created_at.strftime("%d %b %Y"),
        "products":         product_list,
        "discount_amount":  order.discount_amount or 0,
        "payment_method":   order.payment_method  or "COD",
        "payment_status":   order.payment_status  or "Pending",
        "shipping_name":    order.shipping_name    or "",
        "shipping_phone":   order.shipping_phone   or "",
        "shipping_address": order.shipping_address or "",
        "shipping_city":    order.shipping_city    or "",
        "shipping_pincode": order.shipping_pincode or "",
        "shipping_state":   order.shipping_state   or "Maharashtra",
        "shipping_country": order.shipping_country or "India",
    }

    return render_template("user/order-details.html", order=order_data)


# ================= CANCEL ORDER =================
@user.route("/cancel-order/<int:order_id>")
@jwt_required
def cancel_order(order_id):

    token = request.cookies.get("token")
    data = decode_token(token)

    if not data:
        return redirect("/login")

    user_id = data["user_id"]
    order = Order.query.get(order_id)

    if not order:
        flash("Order not found")
        return redirect("/my-orders")

    if order.user_id != user_id:
        return redirect("/my-orders")

    if order.status in ["Delivered", "Cancelled"]:
        flash(f"Order cannot be cancelled — it is already {order.status}.")
        return redirect(f"/order-details/{order_id}")

    order.status = "Cancelled"
    db.session.commit()

    flash(f"Order #VK{order_id} cancelled successfully.")
    return redirect("/my-orders")


# ================= WISHLIST =================
@user.route("/wishlist")
@jwt_required
def wishlist():

    token = request.cookies.get("token")
    data = decode_token(token)
    if not data:
        return redirect("/login")

    user_id = data["user_id"]

    from models.wishlist_model import Wishlist
    items = Wishlist.query.filter_by(user_id=user_id).order_by(Wishlist.added_at.desc()).all()

    return render_template("user/wishlist.html", wishlist_items=items)


# ================= ADD TO WISHLIST =================
@user.route("/wishlist/add/<int:product_id>")
@jwt_required
def wishlist_add(product_id):

    token = request.cookies.get("token")
    data = decode_token(token)
    if not data:
        return redirect("/login")

    user_id = data["user_id"]

    from models.wishlist_model import Wishlist
    existing = Wishlist.query.filter_by(user_id=user_id, product_id=product_id).first()

    if not existing:
        db.session.add(Wishlist(user_id=user_id, product_id=product_id))
        db.session.commit()
        flash("Added to Wishlist 💖")

    # Redirect back to wherever the user came from
    return redirect(request.referrer or "/wishlist")


# ================= REMOVE FROM WISHLIST =================
@user.route("/wishlist/remove/<int:product_id>")
@jwt_required
def wishlist_remove(product_id):

    token = request.cookies.get("token")
    data = decode_token(token)
    if not data:
        return redirect("/login")

    user_id = data["user_id"]

    from models.wishlist_model import Wishlist
    item = Wishlist.query.filter_by(user_id=user_id, product_id=product_id).first()

    if item:
        db.session.delete(item)
        db.session.commit()
        flash("Removed from Wishlist")

    return redirect(request.referrer or "/wishlist")


# ================= ADDRESSES =================
@user.route("/addresses")
@jwt_required
def addresses():

    token = request.cookies.get("token")
    data = decode_token(token)

    if not data:
        return redirect("/login")

    user_id = data["user_id"]

    from models.address_model import Address
    addresses = Address.query.filter_by(user_id=user_id).all()

    return render_template("user/addresses.html", addresses=addresses)


from models.address_model import Address

# ================= ADD ADDRESS =================
@user.route("/add-address", methods=["POST"])
@jwt_required
def add_address():

    token = request.cookies.get("token")
    data = decode_token(token)

    if not data:
        return redirect("/login")

    user_id = data["user_id"]

    if request.form.get("is_default"):
        Address.query.filter_by(user_id=user_id).update({"is_default": False})

    new_address = Address(
        user_id=user_id,
        full_name=request.form.get("full_name"),
        phone=request.form.get("phone"),
        line1=request.form.get("line1"),
        line2=request.form.get("line2"),
        city=request.form.get("city"),
        state=request.form.get("state"),
        pincode=request.form.get("pincode"),
        is_default=True if request.form.get("is_default") else False
    )

    db.session.add(new_address)
    db.session.commit()

    return redirect("/addresses")