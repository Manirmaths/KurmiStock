from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from flask_login import login_user, logout_user, login_required, current_user
from urllib.parse import urlparse, urljoin
from extensions import db
from models import User, Business

auth_bp = Blueprint("auth", __name__, url_prefix="/auth")

def _is_safe_url(target):
    # basic safety for next= redirects
    ref_url = urlparse(request.host_url)
    test_url = urlparse(urljoin(request.host_url, target))
    return (test_url.scheme in ("http", "https")
            and ref_url.netloc == test_url.netloc)

@auth_bp.get("/login")
def login_form():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard"))
    return render_template("login.html")

@auth_bp.post("/login")
def login_post():
    email = request.form.get("email", "").strip().lower()
    password = request.form.get("password", "")

    user = User.query.filter_by(email=email).first()
    if not user or not user.check_password(password):
        flash("Invalid email or password.", "danger")
        return redirect(url_for("auth.login_form"))

    login_user(user)

    next_url = request.args.get("next")
    if next_url and _is_safe_url(next_url):
        return redirect(next_url)
    return redirect(url_for("dashboard"))

@auth_bp.get("/register")
def register_form():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard"))
    return render_template("register.html")

@auth_bp.post("/register")
def register_post():
    email = request.form.get("email", "").strip().lower()
    password = request.form.get("password", "")
    confirm  = request.form.get("confirm_password", "")
    store_name = request.form.get("store_name", "").strip()

    # basic validation
    if not email or not password or not confirm or not store_name:
        flash("Please fill in all fields.", "warning")
        return redirect(url_for("auth.register_form"))
    if password != confirm:
        flash("Passwords do not match.", "danger")
        return redirect(url_for("auth.register_form"))
    if len(password) < 6:
        flash("Password must be at least 6 characters.", "warning")
        return redirect(url_for("auth.register_form"))
    if User.query.filter_by(email=email).first():
        flash("Email already registered.", "warning")
        return redirect(url_for("auth.register_form"))

    # Create Business
    biz = Business(name=store_name)
    db.session.add(biz); db.session.flush()

    # Create Manager in that business
    u = User(email=email, store_name=store_name, role="manager", business_id=biz.id)
    u.set_password(password)
    db.session.add(u)
    db.session.commit()

    login_user(u)
    return redirect(url_for("dashboard"))


@auth_bp.post("/logout")
@login_required
def logout_post():
    logout_user()
    session.clear()
    return redirect(url_for("auth.login_form"))

@auth_bp.get("/check_email")
def check_email():
    email = (request.args.get("email") or "").strip().lower()
    exists = bool(User.query.filter_by(email=email).first()) if email else False
    return {"available": (email and not exists)}
