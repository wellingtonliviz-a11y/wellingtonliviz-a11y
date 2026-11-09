"""Criador de artes com modelos prontos (desenhadas no navegador, salvas como PNG na pasta do cliente)."""
from flask import Blueprint, abort, current_app, jsonify, render_template, request, url_for
from sqlalchemy import select

from .arquivos import save_uploads
from .clientes import get_client
from .models import File, Post
from .security import login_required

bp = Blueprint("artes", __name__)


def _post_of(client_id: int, raw: str | None) -> Post | None:
    if not raw or not raw.isdigit():
        return None
    post = current_app.db.session.get(Post, int(raw))
    return post if post and post.client_id == client_id else None


@bp.get("/clientes/<int:cid>/criar-arte")
@login_required
def editor(cid: int):
    client = get_client(cid)
    post = _post_of(cid, request.args.get("post"))
    images = current_app.db.session.scalars(
        select(File).where(File.client_id == cid, File.mime.like("image/%"))
        .order_by(File.created_at.desc()).limit(60)).all()
    fmt = "story" if post and post.format in ("story", "reels") else request.args.get("formato", "feed")
    return render_template("criar_arte.html", client=client, post=post, images=images,
                           fmt=fmt if fmt in ("feed", "story") else "feed")


@bp.post("/clientes/<int:cid>/criar-arte")
@login_required
def save(cid: int):
    get_client(cid)
    post = _post_of(cid, request.form.get("post_id"))
    fs = request.files.get("arte")
    if fs is None:
        abort(400)
    saved, rejected = save_uploads(cid, "arte", [fs], post_id=post.id if post else None)
    if not saved or saved[0].mime != "image/png":
        current_app.db.session.rollback()
        return jsonify(ok=False, erro="; ".join(rejected) or "A arte precisa ser PNG."), 400
    current_app.db.session.commit()
    f = saved[0]
    return jsonify(ok=True, id=f.id, url=url_for("arquivos.show", fid=f.id),
                   voltar=url_for("postagens.edit", pid=post.id) if post else url_for("clientes.detail", cid=cid, tipo="arte"))
