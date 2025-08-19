# models.py 

from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin
from extensions import db, login_manager
import pytz

WAT = pytz.timezone("Africa/Lagos")

class Business(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(160), unique=True, nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(WAT))

class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    store_name = db.Column(db.String(120))
    password_hash = db.Column(db.String(128))
    locale = db.Column(db.String(10), default="en")
    is_admin = db.Column(db.Boolean, default=False)

    # NEW: role + business (multi-tenant)
    role = db.Column(db.String(20), default="manager")  # "manager" or "staff"
    business_id = db.Column(db.Integer, db.ForeignKey("business.id"), index=True)
    business = db.relationship("Business")

    def set_password(self, pw): self.password_hash = generate_password_hash(pw)
    def check_password(self, pw): return check_password_hash(self.password_hash, pw)

    @property
    def is_manager(self): return (self.role or "").lower() == "manager"
    @property
    def is_staff(self):   return (self.role or "").lower() == "staff"

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    # legacy scope
    user_id = db.Column(db.Integer, index=True, nullable=False)
    # NEW tenant scope
    business_id = db.Column(db.Integer, db.ForeignKey("business.id"), index=True)

    sku = db.Column(db.String(64), unique=False, nullable=False)
    name = db.Column(db.String(200), nullable=False)
    category = db.Column(db.String(120))
    unit = db.Column(db.String(20), default="unit")
    barcode = db.Column(db.String(128))
    reorder_point = db.Column(db.Integer, default=0)
    expiry_date = db.Column(db.Date, nullable=True)
    unit_price = db.Column(db.Float, default=0)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(WAT))

class StockMovement(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, index=True, nullable=False)  # legacy
    product_id = db.Column(db.Integer, db.ForeignKey("product.id"), nullable=False, index=True)
    qty = db.Column(db.Integer, nullable=False)
    type = db.Column(db.String(10), nullable=False)  # IN, OUT, ADJUST
    source = db.Column(db.String(20))
    unit_cost = db.Column(db.Float, nullable=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    product = db.relationship("Product", backref="movements")

class Supplier(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, index=True, nullable=False)  # legacy
    business_id = db.Column(db.Integer, db.ForeignKey("business.id"), index=True)  # NEW
    name = db.Column(db.String(200), nullable=False)
    phone = db.Column(db.String(50))
    location = db.Column(db.String(200))

class Purchase(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, index=True, nullable=False)  # legacy
    business_id = db.Column(db.Integer, db.ForeignKey("business.id"), index=True)  # NEW
    supplier_id = db.Column(db.Integer, db.ForeignKey("supplier.id"), nullable=True)
    total_cost = db.Column(db.Float, default=0)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    supplier = db.relationship("Supplier")

class PurchaseItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    purchase_id = db.Column(db.Integer, db.ForeignKey("purchase.id"), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey("product.id"), nullable=False)
    qty = db.Column(db.Integer, nullable=False)
    unit_cost = db.Column(db.Float, nullable=False)
    purchase = db.relationship("Purchase", backref="items")
    product = db.relationship("Product")

class Sale(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, index=True, nullable=False)  # legacy
    business_id = db.Column(db.Integer, db.ForeignKey("business.id"), index=True)  # NEW
    total_amount = db.Column(db.Float, default=0)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

class SaleItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    sale_id = db.Column(db.Integer, db.ForeignKey("sale.id"), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey("product.id"), nullable=False)
    qty = db.Column(db.Integer, nullable=False)
    unit_price = db.Column(db.Float, nullable=False)
    sale = db.relationship("Sale", backref="items")
    product = db.relationship("Product")
