from database.db import db
from datetime import datetime


class Product(db.Model):

    __tablename__ = "products"

    # ── Core ──────────────────────────────────────────────────
    id          = db.Column(db.Integer, primary_key=True)
    name        = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    category    = db.Column(db.String(100))

    brand = db.Column(db.String(100))
    size  = db.Column(db.String(50))
    color = db.Column(db.String(50))

    # ── Extended fields (used by admin edit form) ─────────────
    name_mr        = db.Column(db.String(200))         # Marathi product name
    description_mr = db.Column(db.Text)                # Marathi description
    tagline_sk     = db.Column(db.String(200))          # Sanskrit tagline
    collection     = db.Column(db.String(100))          # e.g. "Vasant Collection"
    season         = db.Column(db.String(50))           # e.g. "SS/26"
    sku            = db.Column(db.String(100))          # Stock keeping unit
    low_stock      = db.Column(db.Integer, default=10)  # Low stock alert threshold
    save_text      = db.Column(db.String(100))          # e.g. "SAVE ₹1,000"
    tax_info       = db.Column(db.String(150))          # e.g. "Inclusive of all taxes"
    badge          = db.Column(db.String(50))           # e.g. "New", "Bestseller", "Limited" 

    # ── Pricing ───────────────────────────────────────────────
    price       = db.Column(db.Float, nullable=False)
    discount    = db.Column(db.Integer, default=0)   # percentage e.g. 30 = 30% off

    # ── Inventory ─────────────────────────────────────────────
    stock       = db.Column(db.Integer, default=0)

    # ── Media ─────────────────────────────────────────────────
    image       = db.Column(db.String(300))          # primary image (slot 1)
    image_2     = db.Column(db.String(300))          # gallery image slot 2
    image_3     = db.Column(db.String(300))          # gallery image slot 3
    image_4     = db.Column(db.String(300))          # gallery image slot 4

    # ── Rich content (stored as JSON text) ───────────────────
    sizes_json      = db.Column(db.Text)   # e.g. '["S","M","L","XL","XXL"]'
    colors_json     = db.Column(db.Text)   # e.g. '[{"hex":"#1a2e4a","name":"Navy Blue"}]'
    highlights_json = db.Column(db.Text)   # e.g. '[{"en":"...","mr":"..."}]'
    specs_json      = db.Column(db.Text)   # e.g. '[{"key":"Material","val":"Cotton"}]'
    offers_json     = db.Column(db.Text)   # e.g. '[{"icon":"💳","title":"10% Off","desc":"..."}]'
    wash_care_mr    = db.Column(db.Text)   # Marathi wash care instructions
    delivery_json   = db.Column(db.Text)   # delivery/return settings as JSON

    # ── SEO / Meta ────────────────────────────────────────────
    meta_title      = db.Column(db.String(200))
    meta_description= db.Column(db.String(300))
    slug            = db.Column(db.String(200), unique=True)
    tags            = db.Column(db.String(300))   # comma-separated

    # ── Fit / Size defaults ───────────────────────────────────
    fit             = db.Column(db.String(50))
    default_size    = db.Column(db.String(10))

    # ── Rating display (admin-seeded, shown on product page) ──
    rating_display  = db.Column(db.Float, default=4.9)   # e.g. 4.9
    review_count    = db.Column(db.Integer, default=0)   # e.g. 412

    # ── Status ────────────────────────────────────────────────
    is_active   = db.Column(db.Boolean, default=True)   # admin can hide product
    is_featured = db.Column(db.Boolean, default=False)  # show in hero / featured section

    # ── Timestamps ────────────────────────────────────────────
    created_at  = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at  = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # ── Relationships ─────────────────────────────────────────
    order_items = db.relationship("OrderItem", backref="product", lazy=True)
    cart_items  = db.relationship("Cart",      backref="product", lazy=True)
    wishlist    = db.relationship("Wishlist",  backref="product", lazy=True)

    # ── Admin helper properties ───────────────────────────────
    @property
    def final_price(self):
        """Price after applying discount percentage."""
        if self.discount:
            return round(self.price - (self.price * self.discount / 100), 2)
        return self.price

    @property
    def in_stock(self):
        """True if stock > 0."""
        return self.stock is not None and self.stock > 0

    @property
    def total_sold(self):
        """Total units sold — used in admin analytics."""
        return sum(item.quantity for item in self.order_items if item.quantity)

    @property
    def total_revenue(self):
        """Total revenue from this product — used in admin top-products."""
        return sum(item.quantity * self.price for item in self.order_items if item.quantity)

    # ── JSON convenience helpers ──────────────────────────────
    @property
    def sizes(self):
        import json
        try: return json.loads(self.sizes_json) if self.sizes_json else []
        except: return []

    @property
    def colors(self):
        import json
        try: return json.loads(self.colors_json) if self.colors_json else []
        except: return []

    @property
    def highlights(self):
        import json
        try: return json.loads(self.highlights_json) if self.highlights_json else []
        except: return []

    @property
    def specs(self):
        import json
        try: return json.loads(self.specs_json) if self.specs_json else []
        except: return []

    @property
    def offers(self):
        import json
        try: return json.loads(self.offers_json) if self.offers_json else []
        except: return []

    @property
    def delivery(self):
        import json
        try: return json.loads(self.delivery_json) if self.delivery_json else {}
        except: return {}

    def __repr__(self):
        return f"<Product {self.id} — {self.name} ₹{self.final_price}>"