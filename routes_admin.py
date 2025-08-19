# routes_admin.py
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import current_user
from models import User, db
from utils import role_required

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")

def manager_required(view):
    return role_required("manager")(view)

@admin_bp.get("/users")
@manager_required
def users_list():
    users = User.query.filter_by(business_id=current_user.business_id).order_by(User.email).all()
    return render_template("admin_users.html", users=users)

@admin_bp.get("/users/new")
@manager_required
def users_new_form():
    return render_template("admin_user_new.html")

@admin_bp.post("/users")
@manager_required
def users_create():
    email = (request.form.get("email") or "").strip().lower()
    password = request.form.get("password") or ""
    role = (request.form.get("role") or "staff").lower()  # staff by default

    if not email or not password:
        flash("Email and password are required", "warning")
        return redirect(url_for("admin.users_new_form"))
    if User.query.filter_by(email=email).first():
        flash("Email already exists", "warning")
        return redirect(url_for("admin.users_new_form"))

    u = User(
        email=email,
        store_name=current_user.store_name,
        role=("manager" if role == "manager" else "staff"),
        business_id=current_user.business_id
    )
    u.set_password(password)
    db.session.add(u)
    db.session.commit()
    flash(f"Created {u.role} {email}", "success")
    return redirect(url_for("admin.users_list"))
