"""Painel do dia, agenda do mês e cadastro das postagens."""
import calendar
from collections import defaultdict
from datetime import datetime, timedelta

from flask import Blueprint, abort, current_app, flash, redirect, render_template, request, url_for
from sqlalchemy import func, select

from .arquivos import flash_upload_result, save_uploads
from .models import Client, File, Post
from .security import login_required
from .util import FORMATS, MONTHS, STATUSES, agora, month_bounds, safe_next, start_of_day

bp = Blueprint("postagens", __name__)

PENDING = ("ideia", "producao", "aprovacao", "ajuste", "aprovado")


def set_status(post: Post, status: str) -> None:
    """Muda o status e mantém as datas de aprovação/publicação coerentes."""
    if status == post.status:
        return
    post.status = status
    now = agora()
    post.published_at = (post.published_at or now) if status == "publicado" else None
    post.approved_at = (post.approved_at or now) if status in ("aprovado", "publicado") else None


def get_post(pid: int) -> Post:
    post = current_app.db.session.get(Post, pid)
    if post is None:
        abort(404)
    return post


def _active_clients(include_id: int | None = None) -> list[Client]:
    query = select(Client).order_by(func.lower(Client.name))
    clients = current_app.db.session.scalars(query).all()
    return [c for c in clients if c.active or c.id == include_id]


def fill_post(post: Post, form) -> list[str]:
    errors = []
    db = current_app.db.session
    cid = form.get("client_id", "")
    client = db.get(Client, int(cid)) if cid.isdigit() else None
    if client is None:
        errors.append("Escolha o cliente.")
    else:
        post.client_id = client.id
        post.client = client
    try:
        day = datetime.strptime(form.get("date", ""), "%Y-%m-%d").date()
        hour = datetime.strptime(form.get("time", "") or "12:00", "%H:%M").time()
        post.scheduled_at = datetime.combine(day, hour)
    except ValueError:
        errors.append("Informe a data e o horário da postagem.")
    fmt = form.get("format", "feed")
    post.format = fmt if fmt in FORMATS else "feed"
    status = form.get("status", "ideia")
    set_status(post, status if status in STATUSES else "ideia")
    post.theme = form.get("theme", "").strip()[:200]
    post.caption = form.get("caption", "").strip()[:5000]
    post.hashtags = form.get("hashtags", "").strip()[:2000]
    post.notes = form.get("notes", "").strip()[:5000]
    link = form.get("link", "").strip()[:500]
    if link and not link.startswith(("https://", "http://")):
        errors.append("O link precisa começar com https://")
    post.link = link
    return errors


def _attach_arts(post: Post) -> None:
    saved, rejected = save_uploads(post.client_id, "arte", request.files.getlist("artes"), post_id=post.id)
    # artes escolhidas entre os arquivos que já estão na pasta do cliente
    db = current_app.db.session
    for fid in request.form.getlist("anexar"):
        f = db.get(File, fid)
        if f and f.client_id == post.client_id and f.post_id is None:
            f.post_id = post.id
            saved.append(f)
    for fid in request.form.getlist("desanexar"):
        f = db.get(File, fid)
        if f and f.post_id == post.id:
            f.post_id = None
    db.flush()
    db.expire(post, ["arts"])
    if rejected:
        flash_upload_result([], rejected)


def _loose_files(client_id: int | None) -> list[File]:
    if not client_id:
        return []
    return current_app.db.session.scalars(
        select(File).where(File.client_id == client_id, File.post_id.is_(None), File.mime.like("image/%"))
        .order_by(File.created_at.desc()).limit(40)).all()


@bp.get("/")
@login_required
def painel():
    db = current_app.db.session
    now = agora()
    today = start_of_day(now.date())
    tomorrow = today + timedelta(days=1)
    late = db.scalars(select(Post).where(Post.scheduled_at < today, Post.status.in_(PENDING))
                      .order_by(Post.scheduled_at)).all()
    today_posts = db.scalars(select(Post).where(Post.scheduled_at >= today, Post.scheduled_at < tomorrow)
                             .order_by(Post.scheduled_at)).all()
    week = db.scalars(select(Post).where(Post.scheduled_at >= tomorrow,
                                         Post.scheduled_at < tomorrow + timedelta(days=7))
                      .order_by(Post.scheduled_at)).all()
    waiting = db.scalars(select(Post).where(Post.status.in_(("aprovacao", "ajuste")))
                         .order_by(Post.scheduled_at)).all()
    start, end = month_bounds(now.year, now.month)
    rows = db.execute(select(Post.client_id, Post.status, func.count()).where(
        Post.scheduled_at >= start, Post.scheduled_at < end).group_by(Post.client_id, Post.status)).all()
    per_client = defaultdict(lambda: {"total": 0, "publicado": 0})
    for cid, status, n in rows:
        per_client[cid]["total"] += n
        if status == "publicado":
            per_client[cid]["publicado"] += n
    clients = db.scalars(select(Client).where(Client.active.is_(True)).order_by(func.lower(Client.name))).all()
    payments = [c for c in clients if c.payment_day and 0 <= (c.payment_day - now.day) <= 5]
    return render_template("painel.html", late=late, today_posts=today_posts, week=week, waiting=waiting,
                           clients=clients, per_client=per_client, now=now, month_name=MONTHS[now.month - 1],
                           payments=payments)


@bp.get("/agenda")
@login_required
def agenda():
    db = current_app.db.session
    now = agora()
    try:
        first = datetime.strptime(request.args.get("mes", ""), "%Y-%m").date()
    except ValueError:
        first = now.date().replace(day=1)
    cid = request.args.get("cliente", "")
    client_id = int(cid) if cid.isdigit() else None
    weeks = calendar.Calendar(firstweekday=6).monthdatescalendar(first.year, first.month)
    start = start_of_day(weeks[0][0])
    end = start_of_day(weeks[-1][-1]) + timedelta(days=1)
    query = select(Post).where(Post.scheduled_at >= start, Post.scheduled_at < end).order_by(Post.scheduled_at)
    if client_id:
        query = query.where(Post.client_id == client_id)
    by_day = defaultdict(list)
    for p in db.scalars(query):
        by_day[p.scheduled_at.date()].append(p)
    prev_month = (first - timedelta(days=1)).replace(day=1)
    next_month = (first + timedelta(days=32)).replace(day=1)
    return render_template("agenda.html", weeks=weeks, by_day=by_day, first=first, today=now.date(),
                           month_name=MONTHS[first.month - 1], prev_month=prev_month, next_month=next_month,
                           clients=_active_clients(client_id), client_id=client_id)


@bp.route("/postagens/nova", methods=["GET", "POST"])
@login_required
def new():
    db = current_app.db.session
    post = Post(status="ideia", format="feed")
    if request.method == "POST":
        errors = fill_post(post, request.form)
        if not errors:
            db.add(post)
            db.flush()
            _attach_arts(post)
            db.commit()
            flash("Postagem criada.", "ok")
            if request.form.get("depois") == "outra":
                return redirect(url_for("postagens.new", cliente=post.client_id))
            return redirect(url_for("postagens.edit", pid=post.id))
        for e in errors:
            flash(e, "erro")
    else:
        cid = request.args.get("cliente", "")
        if cid.isdigit() and db.get(Client, int(cid)):
            post.client_id = int(cid)
            post.client = db.get(Client, int(cid))
        try:
            day = datetime.strptime(request.args.get("data", ""), "%Y-%m-%d").date()
        except ValueError:
            day = agora().date() + timedelta(days=1)
        post.scheduled_at = datetime.combine(day, datetime.strptime("12:00", "%H:%M").time())
    return render_template("postagem_form.html", post=post, clients=_active_clients(post.client_id),
                           loose=_loose_files(post.client_id))


@bp.route("/postagens/<int:pid>", methods=["GET", "POST"])
@login_required
def edit(pid: int):
    db = current_app.db.session
    post = get_post(pid)
    if request.method == "POST":
        old_client = post.client_id
        errors = fill_post(post, request.form)
        if not errors:
            if post.client_id != old_client:  # artes ficam com o cliente certo
                for f in post.arts:
                    f.client_id = post.client_id
            _attach_arts(post)
            db.commit()
            flash("Postagem salva.", "ok")
            return redirect(safe_next(request.form.get("voltar"), url_for("postagens.edit", pid=pid)))
        for e in errors:
            flash(e, "erro")
    return render_template("postagem_form.html", post=post, clients=_active_clients(post.client_id),
                           loose=_loose_files(post.client_id), voltar=request.values.get("voltar", ""))


@bp.post("/postagens/<int:pid>/status")
@login_required
def change_status(pid: int):
    post = get_post(pid)
    status = request.form.get("status", "")
    if status not in STATUSES:
        abort(400)
    set_status(post, status)
    current_app.db.session.commit()
    flash(f"“{post.theme or post.client.name}” agora está: {STATUSES[status]}.", "ok")
    return redirect(safe_next(request.form.get("voltar"), url_for("postagens.painel")))


@bp.post("/postagens/<int:pid>/duplicar")
@login_required
def duplicate(pid: int):
    db = current_app.db.session
    post = get_post(pid)
    copy = Post(client_id=post.client_id, scheduled_at=post.scheduled_at + timedelta(days=7), format=post.format,
                status="ideia", theme=post.theme, caption=post.caption, hashtags=post.hashtags, notes=post.notes)
    db.add(copy)
    db.commit()
    flash("Cópia criada para a semana seguinte (sem as artes).", "ok")
    return redirect(url_for("postagens.edit", pid=copy.id))


@bp.post("/postagens/<int:pid>/excluir")
@login_required
def delete(pid: int):
    db = current_app.db.session
    post = get_post(pid)
    for f in post.arts:  # as artes continuam na pasta do cliente
        f.post_id = None
    month = post.scheduled_at.strftime("%Y-%m")
    db.delete(post)
    db.commit()
    flash("Postagem excluída. As artes continuam na pasta do cliente.", "ok")
    return redirect(url_for("postagens.agenda", mes=month))

