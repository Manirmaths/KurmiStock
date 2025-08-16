from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
db = SQLAlchemy()
login_manager = LoginManager()
# extensions.py
login_manager.login_view = "auth.login_form"
