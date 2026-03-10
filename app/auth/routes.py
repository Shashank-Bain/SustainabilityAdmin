from flask import Blueprint, flash, redirect, render_template
from flask_login import current_user, login_required, login_user, logout_user

from app.models import User

from .forms import LoginForm


auth_bp = Blueprint("auth_bp", __name__, url_prefix="")


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect("/admin")

    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data.strip().lower()).first()

        if user and user.active and user.check_password(form.password.data):
            login_user(user)
            return redirect("/admin")

        flash("Invalid credentials or inactive account.", "danger")

    return render_template("login.html", form=form)


@auth_bp.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect("/login")
