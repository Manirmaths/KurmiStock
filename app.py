from flask import Flask, render_template, request
from config import Config
from extensions import db, login_manager
from models import *
from routes_auth import auth_bp
from routes_api import api_bp
from flask_login import login_required, current_user
from routes_admin import admin_bp

def create_app():
    app = Flask(__name__, static_folder="static", template_folder="templates")
    app.config.from_object(Config)

    db.init_app(app)
    login_manager.init_app(app)

    with app.app_context():
        db.create_all()

    app.register_blueprint(auth_bp)
    app.register_blueprint(api_bp)
    app.register_blueprint(admin_bp) 

    @app.route("/")
    def index():
        return render_template("index.html")

    @app.route("/dashboard")
    @login_required
    def dashboard():
        return render_template("dashboard.html")

    @app.route("/products")
    @login_required
    def products():
        return render_template("products.html")

    @app.route("/sales")
    @login_required
    def sales():
        return render_template("sales.html")

    @app.route("/purchases")
    @login_required
    def purchases():
        return render_template("purchases.html")

  
    @app.after_request
    def never_cache_private(r):
        # Never cache APIs
        if request.path.startswith('/api/'):
            r.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
            r.headers['Pragma'] = 'no-cache'
            r.headers['Expires'] = '0'
            r.headers['Vary'] = 'Cookie'
            return r

        # For HTML that depends on login state (/, /dashboard, /products, /sales, /purchases)
        if request.headers.get('Accept','').find('text/html') != -1 and request.path in (
            '/', '/dashboard', '/products', '/sales', '/purchases'
        ):
            r.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
            r.headers['Pragma'] = 'no-cache'
            r.headers['Expires'] = '0'
            r.headers['Vary'] = 'Cookie'
        return r

    
    return app


app = create_app()

if __name__ == "__main__":
    app.run(debug=True)
