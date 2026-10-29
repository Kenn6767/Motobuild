import os
from datetime import datetime
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, flash, session, abort
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import CheckConstraint, text
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "change-this-secret-before-deploying")
database_url = os.environ.get("DATABASE_URL", "sqlite:///motobuild.db")
if database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql://", 1)
app.config["SQLALCHEMY_DATABASE_URI"] = database_url
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {"pool_pre_ping": True}
db = SQLAlchemy(app)

class User(db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(160), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False, default="customer")
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    orders = db.relationship("Order", back_populates="customer")
    __table_args__ = (CheckConstraint("role IN ('customer','admin')", name="ck_user_role"),)

class Motorcycle(db.Model):
    __tablename__ = "motorcycles"
    id = db.Column(db.Integer, primary_key=True)
    brand = db.Column(db.String(80), nullable=False)
    model = db.Column(db.String(100), nullable=False)
    year_start = db.Column(db.Integer, nullable=False)
    year_end = db.Column(db.Integer, nullable=False)
    engine_cc = db.Column(db.Integer, nullable=False)
    compatibility = db.relationship("PartCompatibility", back_populates="motorcycle", cascade="all, delete-orphan")

class Part(db.Model):
    __tablename__ = "parts"
    id = db.Column(db.Integer, primary_key=True)
    sku = db.Column(db.String(40), unique=True, nullable=False)
    name = db.Column(db.String(140), nullable=False)
    category = db.Column(db.String(80), nullable=False)
    description = db.Column(db.Text, nullable=False)
    price = db.Column(db.Numeric(10,2), nullable=False)
    stock = db.Column(db.Integer, nullable=False, default=0)
    image_url = db.Column(db.String(500), nullable=False)
    active = db.Column(db.Boolean, default=True, nullable=False)
    compatibility = db.relationship("PartCompatibility", back_populates="part", cascade="all, delete-orphan")
    __table_args__ = (CheckConstraint("price >= 0", name="ck_part_price"), CheckConstraint("stock >= 0", name="ck_part_stock"),)

class PartCompatibility(db.Model):
    __tablename__ = "part_compatibility"
    id = db.Column(db.Integer, primary_key=True)
    part_id = db.Column(db.Integer, db.ForeignKey("parts.id", ondelete="CASCADE"), nullable=False)
    motorcycle_id = db.Column(db.Integer, db.ForeignKey("motorcycles.id", ondelete="CASCADE"), nullable=False)
    notes = db.Column(db.String(240), nullable=False, default="Fitment verified for demo")
    part = db.relationship("Part", back_populates="compatibility")
    motorcycle = db.relationship("Motorcycle", back_populates="compatibility")
    __table_args__ = (db.UniqueConstraint("part_id", "motorcycle_id", name="uq_part_motorcycle"),)

class Order(db.Model):
    __tablename__ = "orders"
    id = db.Column(db.Integer, primary_key=True)
    order_number = db.Column(db.String(30), unique=True, nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    status = db.Column(db.String(20), nullable=False, default="pending")
    shipping_address = db.Column(db.String(300), nullable=False)
    total = db.Column(db.Numeric(10,2), nullable=False)
    admin_note = db.Column(db.String(300))
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    customer = db.relationship("User", back_populates="orders")
    items = db.relationship("OrderItem", back_populates="order", cascade="all, delete-orphan")
    __table_args__ = (CheckConstraint("status IN ('pending','approved','rejected','shipped','completed','cancelled')", name="ck_order_status"),)

class OrderItem(db.Model):
    __tablename__ = "order_items"
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey("orders.id", ondelete="CASCADE"), nullable=False)
    part_id = db.Column(db.Integer, db.ForeignKey("parts.id"), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    unit_price = db.Column(db.Numeric(10,2), nullable=False)
    order = db.relationship("Order", back_populates="items")
    part = db.relationship("Part")
    __table_args__ = (CheckConstraint("quantity > 0", name="ck_order_item_quantity"),)

def login_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if "user_id" not in session:
            flash("Please sign in first.", "warning")
            return redirect(url_for("login", next=request.path))
        return fn(*args, **kwargs)
    return wrapper

def admin_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("login"))
        user = db.session.get(User, session["user_id"])
        if not user or user.role != "admin":
            abort(403)
        return fn(*args, **kwargs)
    return wrapper

def current_user():
    return db.session.get(User, session["user_id"]) if session.get("user_id") else None

@app.context_processor
def inject_user():
    return {"current_user": current_user()}

@app.route("/")
def index():
    bikes = Motorcycle.query.order_by(Motorcycle.brand, Motorcycle.model).all()
    selected_bike = request.args.get("bike", type=int)
    query = Part.query.filter_by(active=True)
    if selected_bike:
        query = query.join(PartCompatibility).filter(PartCompatibility.motorcycle_id == selected_bike)
    parts = query.order_by(Part.name).all()
    return render_template("index.html", bikes=bikes, parts=parts, selected_bike=selected_bike)

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name, email = request.form.get("name","").strip(), request.form.get("email","").strip().lower()
        password = request.form.get("password","")
        if not name or not email or len(password) < 8:
            flash("Enter your name and email; password must be at least 8 characters.", "danger")
        elif User.query.filter_by(email=email).first():
            flash("That email is already registered.", "danger")
        else:
            db.session.add(User(name=name, email=email, password_hash=generate_password_hash(password)))
            db.session.commit()
            flash("Account created. You can now sign in.", "success")
            return redirect(url_for("login"))
    return render_template("register.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email","").strip().lower()
        password = request.form.get("password","")
        user = User.query.filter_by(email=email).first()
        if user and check_password_hash(user.password_hash, password):
            session.clear()
            session["user_id"] = user.id
            flash("Welcome back!", "success")
            return redirect(url_for("admin_dashboard" if user.role == "admin" else "index"))
        flash("Invalid email or password.", "danger")
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    flash("You have signed out.", "success")
    return redirect(url_for("index"))

@app.route("/order/<int:part_id>", methods=["POST"])
@login_required
def place_order(part_id):
    part = db.session.get(Part, part_id)
    if not part or not part.active:
        abort(404)
    try:
        qty = int(request.form.get("quantity", "1"))
    except ValueError:
        qty = 0
    address = request.form.get("address","").strip()
    if qty < 1 or qty > 20 or qty > part.stock or not address:
        flash("Check quantity, stock availability, and shipping address.", "danger")
        return redirect(url_for("index"))
    # One transaction: reserve stock and create order + item together.
    try:
        with db.session.begin_nested():
            locked_part = Part.query.filter_by(id=part.id).with_for_update().first()
            if not locked_part or locked_part.stock < qty:
                raise ValueError("Not enough stock remains.")
            locked_part.stock -= qty
            order = Order(order_number=f"MB-{datetime.utcnow():%y%m%d%H%M%S}-{current_user().id}",
                          user_id=current_user().id, shipping_address=address,
                          total=locked_part.price * qty)
            db.session.add(order)
            db.session.flush()
            db.session.add(OrderItem(order_id=order.id, part_id=locked_part.id,
                                     quantity=qty, unit_price=locked_part.price))
        db.session.commit()
        flash(f"Order {order.order_number} submitted for admin approval.", "success")
    except Exception:
        db.session.rollback()
        flash("Order could not be placed. Please refresh and try again.", "danger")
    return redirect(url_for("my_orders"))

@app.route("/my-orders")
@login_required
def my_orders():
    orders = Order.query.filter_by(user_id=current_user().id).order_by(Order.created_at.desc()).all()
    return render_template("my_orders.html", orders=orders)

@app.route("/admin")
@admin_required
def admin_dashboard():
    orders = Order.query.order_by(Order.created_at.desc()).all()
    parts = Part.query.order_by(Part.name).all()
    bikes = Motorcycle.query.order_by(Motorcycle.brand).all()
    # Example readable multi-table JOIN report.
    report = db.session.execute(text("""
        SELECT o.order_number, u.name AS customer, o.status, p.name AS part_name,
               oi.quantity, oi.unit_price, o.total, o.created_at
        FROM orders o JOIN users u ON u.id=o.user_id
        JOIN order_items oi ON oi.order_id=o.id JOIN parts p ON p.id=oi.part_id
        ORDER BY o.created_at DESC
    """)).mappings().all()
    return render_template("admin.html", orders=orders, parts=parts, bikes=bikes, report=report)

@app.route("/admin/order/<int:order_id>/status", methods=["POST"])
@admin_required
def update_order_status(order_id):
    order = db.session.get(Order, order_id)
    if not order:
        abort(404)
    status = request.form.get("status")
    allowed = {"approved", "rejected", "shipped", "completed", "cancelled"}
    if status not in allowed:
        flash("Invalid order status.", "danger")
    elif order.status in {"rejected", "cancelled", "completed"}:
        flash("This order is already finalized and cannot be changed.", "warning")
    else:
        # Restore inventory on rejection/cancellation, only once.
        if status in {"rejected", "cancelled"} and order.status not in {"rejected", "cancelled"}:
            for item in order.items:
                item.part.stock += item.quantity
        order.status = status
        order.admin_note = request.form.get("admin_note","").strip()[:300]
        db.session.commit()
        flash(f"Order {order.order_number} updated to {status}.", "success")
    return redirect(url_for("admin_dashboard"))

@app.route("/admin/parts", methods=["POST"])
@admin_required
def create_part():
    try:
        part = Part(sku=request.form["sku"].strip().upper(), name=request.form["name"].strip(),
                    category=request.form["category"].strip(), description=request.form["description"].strip(),
                    price=request.form.get("price", type=float), stock=request.form.get("stock", type=int),
                    image_url=request.form["image_url"].strip(), active=True)
        bike_ids = request.form.getlist("motorcycle_ids", type=int)
        if not part.sku or not part.name or part.price < 0 or part.stock < 0 or not bike_ids:
            raise ValueError("Complete the fields and choose at least one compatible motorcycle.")
        db.session.add(part)
        db.session.flush()
        for bike_id in bike_ids:
            if db.session.get(Motorcycle, bike_id):
                db.session.add(PartCompatibility(part_id=part.id, motorcycle_id=bike_id))
        db.session.commit()
        flash("Part created.", "success")
    except Exception as exc:
        db.session.rollback()
        flash(f"Could not create part. Check required fields and unique SKU. {exc}", "danger")
    return redirect(url_for("admin_dashboard"))

@app.route("/admin/parts/<int:part_id>/update", methods=["POST"])
@admin_required
def update_part(part_id):
    part = db.session.get(Part, part_id)
    if not part: abort(404)
    try:
        part.name = request.form["name"].strip()
        part.price = request.form.get("price", type=float)
        part.stock = request.form.get("stock", type=int)
        part.active = request.form.get("active") == "on"
        if part.price < 0 or part.stock < 0: raise ValueError()
        db.session.commit()
        flash("Part updated.", "success")
    except Exception:
        db.session.rollback()
        flash("Invalid price or stock.", "danger")
    return redirect(url_for("admin_dashboard"))

@app.route("/admin/parts/<int:part_id>/delete", methods=["POST"])
@admin_required
def delete_part(part_id):
    part = db.session.get(Part, part_id)
    if not part: abort(404)
    if OrderItem.query.filter_by(part_id=part.id).first():
        part.active = False
        flash("Part is referenced by an order, so it was archived instead of permanently deleted.", "warning")
    else:
        db.session.delete(part)
        flash("Part deleted.", "success")
    db.session.commit()
    return redirect(url_for("admin_dashboard"))

@app.route("/health")
def health():
    try:
        db.session.execute(text("SELECT 1"))
        return {"status": "ok", "database": "connected"}, 200
    except Exception:
        return {"status": "error", "database": "unavailable"}, 503

def seed_data():
    if User.query.filter_by(email="admin@motobuild.demo").first():
        return
    admin = User(name="MotoBuild Admin", email="admin@motobuild.demo",
                 password_hash=generate_password_hash(os.environ.get("DEMO_ADMIN_PASSWORD", "AdminDemo123!")),
                 role="admin")
    customer = User(name="Demo Rider", email="rider@example.com",
                    password_hash=generate_password_hash("RiderDemo123!"))
    bike1 = Motorcycle(brand="Honda", model="Click 125i", year_start=2020, year_end=2025, engine_cc=125)
    bike2 = Motorcycle(brand="Yamaha", model="Mio i 125", year_start=2018, year_end=2025, engine_cc=125)
    db.session.add_all([admin, customer, bike1, bike2])
    db.session.flush()
    p1 = Part(sku="MB-BRK-001", name="Ceramic Front Brake Pads", category="Brakes",
              description="Demo replacement brake pad set. Confirm exact model/year with a mechanic before purchase.",
              price=650, stock=12, image_url="https://pngimg.com/uploads/motorcycle/motorcycle_PNG5342.png")
    p2 = Part(sku="MB-MIR-002", name="Universal Rear-view Mirror Pair", category="Accessories",
              description="Demo mirror pair; listed as compatible with the two sample scooters for project demonstration.",
              price=480, stock=20, image_url="https://pngimg.com/uploads/motorcycle/motorcycle_PNG3177.png")
    db.session.add_all([p1,p2])
    db.session.flush()
    db.session.add_all([
        PartCompatibility(part_id=p1.id, motorcycle_id=bike1.id, notes="Demo fitment; verify before buying"),
        PartCompatibility(part_id=p2.id, motorcycle_id=bike1.id, notes="Demo fitment; verify before buying"),
        PartCompatibility(part_id=p2.id, motorcycle_id=bike2.id, notes="Demo fitment; verify before buying")
    ])
    db.session.commit()

with app.app_context():
    db.create_all()
    try:
        seed_data()
    except Exception as e:
        db.session.rollback()
        app.logger.exception("Seed data could not be loaded: %s", e)

if __name__ == "__main__":
    app.run(debug=os.environ.get("FLASK_DEBUG") == "1", host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
