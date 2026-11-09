"""Entrar, sair e minha conta."""
from flask import Blueprint, current_app, flash, g, redirect, render_template, request, url_for
from sqlalchemy import select
from werkzeug.security import check_password_hash, generate_password_hash

from .models import User
from .security import login_limiter, login_required, login_user, logout_user
from .util import safe_next

bp = Blueprint("auth", __name__)
MIN_PASSWORD = 8


@bp.route("/entrar", methods=["GET", "POST"])
def login():
    next_url = safe_next(request.values.get("next"), url_for("postagens.painel"))
    if g.get("user"):
        return redirect(next_url)
    email = ""
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        if not login_limiter.allow(request.remote_addr or "?"):
            flash("Muitas tentativas. Espere alguns minutos e tente de novo.", "erro")
            return render_template("entrar.html", email=email, next_url=next_url, public=True), 429
        user = current_app.db.session.scalar(select(User).where(User.email == email))
        if user is None or not user.active or not check_password_hash(user.password_hash, password):
            flash("E-mail ou senha incorretos.", "erro")
        else:
            login_user(user)
            return redirect(next_url)
    return render_template("entrar.html", email=email, next_url=next_url, public=True)


@bp.post("/sair")
def logout():
    logout_user()
    flash("Você saiu.", "ok")
    return redirect(url_for("auth.login"))


@bp.route("/conta", methods=["GET", "POST"])
@login_required
def account():
    user = g.user
    if request.method == "POST":
        user.name = request.form.get("name", "").strip()[:120]
        current = request.form.get("current_password", "")
        new = request.form.get("new_password", "")
        if new:
            if not check_password_hash(user.password_hash, current):
                flash("A senha atual não confere.", "erro")
                return render_template("conta.html")
            if len(new) < MIN_PASSWORD:
                flash(f"A nova senha precisa ter pelo menos {MIN_PASSWORD} caracteres.", "erro")
                return render_template("conta.html")
            user.password_hash = generate_password_hash(new)
        current_app.db.session.commit()
        if new:
            login_user(user)  # a sessão atual continua valendo com a senha nova
        flash("Dados salvos.", "ok")
        return redirect(url_for("auth.account"))
    return render_template("conta.html")
