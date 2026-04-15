# ═══════════════════════════════════════════════════════════
# models/__init__.py
# Import all models here so Flask-SQLAlchemy sees them all
# when db.create_all() or flask db migrate is called.
#
# Usage in app.py / create_app():
#   from models import *
# ═══════════════════════════════════════════════════════════

from models.user_model         import User
from models.admin_model        import Admin
from models.product_model      import Product
from models.cart_model         import Cart
from models.wishlist_model     import Wishlist
from models.address_model      import Address
from models.order_model        import Order
from models.order_item_model   import OrderItem
from models.coupon_model       import Coupon
from models.payment_model      import Payment
from models.review_model       import Review
from models.notification_model import Notification

__all__ = [
    "User",
    "Admin",
    "Product",
    "Cart",
    "Wishlist",
    "Address",
    "Order",
    "OrderItem",
    "Coupon",
    "Payment",
    "Review",
    "Notification",
]