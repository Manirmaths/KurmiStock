from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_user, logout_user, login_required
from extensions import db
from models import User

auth_bp = Blueprint("auth", __name__, url_prefix="/auth")

@auth_bp.get("/login")
def login_form():
    return render_template("login.html")

@auth_bp.post("/login")
def login_post():
    email = request.form["email"].strip().lower()
    password = request.form["password"]
    user = User.query.filter_by(email=email).first()
    if not user or not user.check_password(password):
        flash("Invalid credentials", "danger")
        return redirect(url_for("auth.login_form"))
    login_user(user)
    return redirect(url_for("index"))

@auth_bp.get("/register")
def register_form():
    return render_template("login.html", register=True)

@auth_bp.post("/register")
def register_post():
    email = request.form["email"].strip().lower()
    password = request.form["password"]
    if User.query.filter_by(email=email).first():
        flash("Email already registered", "warning")
        return redirect(url_for("auth.register_form"))
    u = User(email=email)
    u.set_password(password)
    db.session.add(u); db.session.commit()
    login_user(u)
    return redirect(url_for("index"))

@auth_bp.post("/logout")
@login_required
def logout_post():
    logout_user()
    return redirect(url_for("auth.login_form"))
