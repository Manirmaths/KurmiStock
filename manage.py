# manage.py
import getpass
from flask.cli import FlaskGroup
from app import create_app
from extensions import db
from models import User

app = create_app()
cli = FlaskGroup(app)

@cli.command("create-user")
def create_user():
    """Create a new user (prompts for email, store, password)."""
    email = input("Email: ").strip().lower()
    store_name = input("Store name: ").strip()
    # hide password input on Windows too
    password = getpass.getpass("Password: ")

    if User.query.filter_by(email=email).first():
        print("❌ User already exists.")
        return

    u = User(email=email, store_name=store_name)
    # set admin if the model supports it
    if hasattr(User, "is_admin"):
        setattr(u, "is_admin", True)

    u.set_password(password)
    db.session.add(u)
    db.session.commit()
    print(f"✅ Created user {email} for store {store_name}")

@cli.command("set-password")
def set_password():
    """Reset password for an existing user."""
    email = input("Email: ").strip().lower()
    user = User.query.filter_by(email=email).first()
    if not user:
        print("❌ No such user.")
        return
    new_pw = getpass.getpass("New password: ")
    user.set_password(new_pw)
    db.session.commit()
    print("🔑 Password updated successfully.")

if __name__ == "__main__":
    cli()
