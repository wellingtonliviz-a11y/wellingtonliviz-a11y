"""Painel do dono do produto: clientes, reenvio de acesso e bloqueio manual."""
from datetime import timedelta

from flask import Blueprint, current_app, flash, redirect, render_template, request, url_for
from sqlalchemy import func, or_, select

from .access import generate_password, grant_access, hash_password, normalize_email
from .mailer import send_access_email
from .models import Purchase, User, utcnow
from .security import admin_required

bp = Blueprint("admin", __name__, url_prefix="/admin")


@bp.get("")
@admin_required
def index():
    db = current_app.db.session
    q = request.args.get("q", "").strip().lower()
    stmt = select(User).order_by(User.created_at.desc()).limit(100)
    if q:
        stmt = stmt.where(or_(User.email.contains(q), func.lower(User.name).contains(q)))
    users = db.scalars(stmt).all()
    since = utcnow() - timedelta(days=30)
    stats = {
        "ativos": db.scalar(select(func.count()).select_from(User).where(User.active.is_(True))),
        "bloqueados": db.scalar(select(func.count()).select_from(User).where(User.active.is_(False))),
        "novos_30d": db.scalar(select(func.count()).select_from(User).where(User.created_at >= since)),
        "reembolsos_30d": db.scalar(select(func.count()).select_from(Purchase).where(
            Purchase.status == "revogada", Purchase.updated_at >= since)),
    }
    return render_template("admin.html", users=users, stats=stats, q=q)


def _get_user(user_id: int) -> User:
    user = current_app.db.session.get(User, user_id)
    if user is None:
        flash("Cliente não encontrado.", "erro")
    return user


@bp.post("/usuarios/<int:user_id>/reenviar")
@admin_required
def resend(user_id):
    user = _get_user(user_id)
    if user:
        password = generate_password()
        user.password_hash = hash_password(password)
        ok = send_access_email(user.name, user.email, password)
        if ok:
            user.access_email_sent_at = utcnow()
        current_app.db.session.commit()
        flash(f"Nova senha enviada para {user.email}." if ok else
              f"Não consegui enviar o e-mail. Nova senha de {user.email}: {password}", "ok" if ok else "erro")
    return redirect(url_for("admin.index", q=request.args.get("q", "")))


@bp.post("/usuarios/<int:user_id>/status")
@admin_required
def toggle(user_id):
    user = _get_user(user_id)
    if user:
        user.active = request.form.get("active") == "1"
        current_app.db.session.commit()
        flash(f"{user.email} {'liberado' if user.active else 'bloqueado'}.", "ok")
    return redirect(url_for("admin.index", q=request.args.get("q", "")))


@bp.post("/criar")
@admin_required
def create():
    email = normalize_email(request.form.get("email", ""))
    if "@" not in email:
        flash("Informe um e-mail válido.", "erro")
        return redirect(url_for("admin.index"))
    res = grant_access(current_app.db.session, "manual", f"manual:{email}", email,
                       request.form.get("name", ""), event="criado no painel")
    if res.password:
        ok = send_access_email(res.user.name, res.user.email, res.password)
        if ok:
            res.user.access_email_sent_at = utcnow()
            current_app.db.session.commit()
        flash(f"Acesso criado e enviado para {email}." if ok else
              f"Acesso criado, mas o e-mail falhou. Senha: {res.password}", "ok" if ok else "erro")
    else:
        flash(f"{email} já tinha conta e agora está liberado.", "ok")
    return redirect(url_for("admin.index", q=email))
