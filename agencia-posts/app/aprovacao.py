"""Página pública (link secreto) onde o comerciante vê as artes e aprova ou pede ajuste."""
from flask import Blueprint, abort, current_app, flash, redirect, render_template, request, url_for
from sqlalchemy import select

from .arquivos import send_stored
from .models import Client, File, Post
from .postagens import set_status
from .security import RateLimiter
from .util import agora, start_of_day

bp = Blueprint("aprovacao", __name__)
answer_limiter = RateLimiter(limit=60, window=600)


def _client(token: str) -> Client:
    client = current_app.db.session.scalar(
        select(Client).where(Client.approval_token == token, Client.active.is_(True)))
    if client is None:
        abort(404)
    return client


@bp.get("/aprovar/<token>")
def page(token: str):
    db = current_app.db.session
    client = _client(token)
    pending = db.scalars(select(Post).where(Post.client_id == client.id, Post.status == "aprovacao")
                         .order_by(Post.scheduled_at)).all()
    today = start_of_day(agora().date())
    others = db.scalars(select(Post).where(Post.client_id == client.id, Post.scheduled_at >= today,
                                           Post.status.in_(("ajuste", "aprovado", "publicado")))
                        .order_by(Post.scheduled_at).limit(30)).all()
    return render_template("aprovacao.html", client=client, pending=pending, others=others, public=True)


@bp.post("/aprovar/<token>/<int:pid>")
def answer(token: str, pid: int):
    db = current_app.db.session
    client = _client(token)
    post = db.get(Post, pid)
    if post is None or post.client_id != client.id:
        abort(404)
    if not answer_limiter.allow(request.remote_addr or "?"):
        flash("Muitas respostas seguidas. Espere alguns minutos.", "erro")
        return redirect(url_for("aprovacao.page", token=token))
    if post.status != "aprovacao":
        flash("Esta arte já foi respondida.", "ok")
        return redirect(url_for("aprovacao.page", token=token))
    action = request.form.get("acao")
    comment = request.form.get("comentario", "").strip()[:2000]
    stamp = agora().strftime("%d/%m %H:%M")
    if action == "aprovar":
        set_status(post, "aprovado")
        if comment:
            post.feedback = (post.feedback + "\n" if post.feedback else "") + f"[{stamp}] Aprovado: {comment}"
        flash("Arte aprovada. Obrigado!", "ok")
    elif action == "ajuste":
        if not comment:
            flash("Escreva o que você quer mudar na arte.", "erro")
            return redirect(url_for("aprovacao.page", token=token) + f"#post-{pid}")
        set_status(post, "ajuste")
        post.feedback = (post.feedback + "\n" if post.feedback else "") + f"[{stamp}] Ajuste: {comment}"
        flash("Pedido de ajuste enviado. Já vamos mexer na arte.", "ok")
    else:
        abort(400)
    db.commit()
    return redirect(url_for("aprovacao.page", token=token))


@bp.get("/aprovar/<token>/arquivo/<fid>")
def file(token: str, fid: str):
    client = _client(token)
    f = current_app.db.session.get(File, fid)
    # só o logo e as artes ligadas a postagens; fotos e arquivos internos não aparecem
    if f is None or f.client_id != client.id or (f.post_id is None and f.id != client.logo_id):
        abort(404)
    return send_stored(f)
