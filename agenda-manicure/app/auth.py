"""Entrar, sair, esqueci a senha, nova senha e minha conta."""
from flask import Blueprint, current_app, flash, g, redirect, render_template, request, url_for
from sqlalchemy import select
from werkzeug.security import check_password_hash

from .access import hash_password, normalize_email
from .mailer import send_reset_email
from .models import User, utcnow
from .security import (email_limiter, login_limiter, login_required, login_user, logout_user,
                       make_reset_token, read_reset_token)

bp = Blueprint("auth", __name__)
MIN_PASSWORD = 6


@bp.route("/entrar", methods=["GET", "POST"])
def login():
    if g.get("user"):
        return redirect(url_for("main.app_page"))
    email = ""
    if request.method == "POST":
        email = normalize_email(request.form.get("email", ""))
        password = request.form.get("password", "")
        if not login_limiter.allow(request.remote_addr or "?"):
            flash("Muitas tentativas. Espere alguns minutos e tente de novo.", "erro")
            return render_template("entrar.html", email=email), 429
        user = current_app.db.session.scalar(select(User).where(User.email == email))
        if user is None or not check_password_hash(user.password_hash, password):
            flash("E-mail ou senha incorretos.", "erro")
        elif not user.active:
            support = current_app.config["SUPPORT_EMAIL"]
            flash("Seu acesso está bloqueado (reembolso ou cancelamento)."
                  + (f" Fale com {support}." if support else ""), "erro")
        else:
            user.last_login_at = utcnow()
            current_app.db.session.commit()
            login_user(user)
            return redirect(url_for("main.app_page"))
    return render_template("entrar.html", email=email)


@bp.post("/sair")
def logout():
    logout_user()
    flash("Você saiu da sua conta.", "ok")
    return redirect(url_for("auth.login"))


@bp.route("/esqueci", methods=["GET", "POST"])
def forgot():
    if request.method == "POST":
        email = normalize_email(request.form.get("email", ""))
        if email_limiter.allow(f"{request.remote_addr}:{email}"):
            user = current_app.db.session.scalar(select(User).where(User.email == email))
            if user and user.active:
                link = f"{current_app.config['APP_URL']}{url_for('auth.reset', token=make_reset_token(user))}"
                send_reset_email(user.email, link)
        # mesma resposta sempre, para ninguém descobrir quais e-mails são clientes
        flash("Se este e-mail tiver acesso, enviamos um link para criar uma nova senha. "
              "Confira também a caixa de spam.", "ok")
        return redirect(url_for("auth.login"))
    return render_template("esqueci.html")


@bp.route("/redefinir/<token>", methods=["GET", "POST"])
def reset(token):
    user = read_reset_token(token)
    if user is None:
        flash("Este link expirou ou já foi usado. Peça um novo.", "erro")
        return redirect(url_for("auth.forgot"))
    if request.method == "POST":
        pw, pw2 = request.form.get("password", ""), request.form.get("password2", "")
        if len(pw) < MIN_PASSWORD:
            flash(f"A senha precisa ter pelo menos {MIN_PASSWORD} caracteres.", "erro")
        elif pw != pw2:
            flash("As senhas não são iguais.", "erro")
        else:
            user.password_hash = hash_password(pw)
            current_app.db.session.commit()
            login_user(user)
            flash("Senha criada. Bem-vindo(a) de volta!", "ok")
            return redirect(url_for("main.app_page"))
    return render_template("redefinir.html")


@bp.route("/conta", methods=["GET", "POST"])
@login_required
def account():
    user = g.user
    if request.method == "POST":
        action = request.form.get("action")
        if action == "nome":
            user.name = request.form.get("name", "").strip()[:255]
            current_app.db.session.commit()
            flash("Nome atualizado.", "ok")
        elif action == "senha":
            current = request.form.get("current", "")
            pw, pw2 = request.form.get("password", ""), request.form.get("password2", "")
            if not check_password_hash(user.password_hash, current):
                flash("A senha atual está incorreta.", "erro")
            elif len(pw) < MIN_PASSWORD:
                flash(f"A nova senha precisa ter pelo menos {MIN_PASSWORD} caracteres.", "erro")
            elif pw != pw2:
                flash("As senhas novas não são iguais.", "erro")
            else:
                user.password_hash = hash_password(pw)
                current_app.db.session.commit()
                login_user(user)  # mantém esta sessão e derruba as outras
                flash("Senha alterada.", "ok")
        return redirect(url_for("auth.account"))
    return render_template("conta.html")
