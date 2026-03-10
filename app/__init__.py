import os

from dotenv import load_dotenv
from flask import Flask, redirect, render_template, url_for
from flask_login import current_user

from .extensions import csrf, db, login_manager, migrate


@login_manager.user_loader
def load_user(user_id: str):
    from .models import User

    try:
        return db.session.get(User, int(user_id))
    except (TypeError, ValueError):
        return None


def create_app() -> Flask:
    load_dotenv()

    app = Flask(__name__)
    app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "dev-secret-key")
    app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv("DATABASE_URL", "sqlite:///app.db")
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    db.init_app(app)
    migrate.init_app(app, db)
    csrf.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = "auth_bp.login"

    from . import models
    from .auth import auth_bp
    from .admin import admin_bp
    from .daily import daily_bp
    from .dashboard import dashboard_bp

    _ = models
    app.register_blueprint(auth_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(daily_bp)
    app.register_blueprint(dashboard_bp)

    @app.route("/")
    def home():
        if current_user.is_authenticated:
            return redirect(url_for("daily_bp.index"))
        return redirect(url_for("auth_bp.login"))

    @app.errorhandler(403)
    def forbidden(error):
        return render_template("errors/403.html"), 403

    @app.errorhandler(404)
    def not_found(error):
        return render_template("errors/404.html"), 404

    return app
