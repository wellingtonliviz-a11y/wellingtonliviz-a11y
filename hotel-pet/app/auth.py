"""Entrar, sair e trocar a própria senha."""
from flask import Blueprint, current_app, flash, g, redirect, render_template, request, url_for
from sqlalchemy import select
from werkzeug.security import check_password_hash

from .access import hash_password, normalize_email
from .models import User
from .security import login_limiter, login_required, login_user, logout_user

bp = Blueprint("auth", __name__)
MIN_PASSWORD = 6


def _safe_next(target: str | None) -> str:
    return target if target and target.startswith("/") and not target.startswith("//") else url_for("painel.home")


@bp.route("/entrar", methods=["GET", "POST"])
def login():
    if g.get("user"):
        return redirect(url_for("painel.home"))
    email = ""
    if request.method == "POST":
        email = normalize_email(request.form.get("email", ""))
        if not login_limiter.allow(request.remote_addr or "?"):
            flash("Muitas tentativas. Espere alguns minutos e tente de novo.", "erro")
            return render_template("entrar.html", email=email), 429
        user = current_app.db.session.scalar(select(User).where(User.email == email))
        if user and user.active and check_password_hash(user.password_hash, request.form.get("password", "")):
            login_user(user)
            return redirect(_safe_next(request.args.get("next")))
        flash("E-mail ou senha incorretos.", "erro")
    return render_template("entrar.html", email=email)


@bp.post("/sair")
def logout():
    logout_user()
    flash("Você saiu do sistema.", "ok")
    return redirect(url_for("auth.login"))


@bp.route("/minha-senha", methods=["GET", "POST"])
@login_required
def password():
    if request.method == "POST":
        current, new, new2 = (request.form.get(k, "") for k in ("current", "password", "password2"))
        if not check_password_hash(g.user.password_hash, current):
            flash("A senha atual está errada.", "erro")
        elif len(new) < MIN_PASSWORD:
            flash(f"A nova senha precisa ter pelo menos {MIN_PASSWORD} caracteres.", "erro")
        elif new != new2:
            flash("As senhas novas não são iguais.", "erro")
        else:
            g.user.password_hash = hash_password(new)
            current_app.db.session.commit()
            flash("Senha alterada.", "ok")
            return redirect(url_for("painel.home"))
    return render_template("senha.html")
