"""Envio, visualização e exclusão de logos, fotos e artes."""
import io
import os
import re

from flask import Blueprint, abort, current_app, flash, redirect, request, send_file, url_for
from werkzeug.datastructures import FileStorage

from .models import Client, File
from .security import login_required
from .util import safe_next

bp = Blueprint("arquivos", __name__)

EXTENSIONS = {"image/png": ".png", "image/jpeg": ".jpg", "image/gif": ".gif", "image/webp": ".webp",
              "application/pdf": ".pdf", "video/mp4": ".mp4"}
INLINE = {"image/png", "image/jpeg", "image/gif", "image/webp", "video/mp4"}


def sniff(data: bytes) -> str | None:
    """Descobre o tipo pelo conteúdo (não confia no nome do arquivo)."""
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if data.startswith((b"GIF87a", b"GIF89a")):
        return "image/gif"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    if data.startswith(b"%PDF-"):
        return "application/pdf"
    if data[4:8] == b"ftyp":
        return "video/mp4"
    return None


def _clean_name(filename: str) -> str:
    name = os.path.basename(filename.replace("\\", "/"))
    name = re.sub(r"[\x00-\x1f\x7f]", "", name).strip()
    return name[:200] or "arquivo"


def save_uploads(client_id: int, kind: str, storages: list[FileStorage],
                 post_id: int | None = None) -> tuple[list[File], list[str]]:
    """Guarda os arquivos válidos; devolve (salvos, mensagens dos recusados)."""
    db = current_app.db.session
    max_mb = current_app.config["MAX_FILE_MB"]
    limit = max_mb * 1024 * 1024
    saved, rejected = [], []
    for fs in storages:
        if not fs or not fs.filename:
            continue
        name = _clean_name(fs.filename)
        data = fs.read(limit + 1)
        if len(data) > limit:
            rejected.append(f"{name} (maior que {max_mb} MB)")
            continue
        mime = sniff(data)
        if mime is None:
            rejected.append(f"{name} (use PNG, JPG, WEBP, GIF, PDF ou MP4)")
            continue
        f = File(client_id=client_id, post_id=post_id, kind=kind, name=name, mime=mime,
                 size=len(data), data=data)
        db.add(f)
        saved.append(f)
    db.flush()
    return saved, rejected


def flash_upload_result(saved: list[File], rejected: list[str]) -> None:
    if saved:
        flash(f"{len(saved)} arquivo(s) enviado(s).", "ok")
    if rejected:
        flash("Não foram aceitos: " + "; ".join(rejected), "erro")


def send_stored(f: File):
    download = request.args.get("baixar") == "1" or f.mime not in INLINE
    name = f.name
    ext = EXTENSIONS.get(f.mime, "")
    if ext and not name.lower().endswith((ext, ".jpeg") if ext == ".jpg" else ext):
        name += ext
    resp = send_file(io.BytesIO(f.data), mimetype=f.mime, as_attachment=download, download_name=name)
    resp.headers["Cache-Control"] = "private, max-age=86400"
    return resp


@bp.get("/arquivos/<fid>")
@login_required
def show(fid: str):
    f = current_app.db.session.get(File, fid)
    if f is None:
        abort(404)
    return send_stored(f)


@bp.post("/arquivos/<fid>/excluir")
@login_required
def delete(fid: str):
    db = current_app.db.session
    f = db.get(File, fid)
    if f is None:
        abort(404)
    client = db.get(Client, f.client_id)
    if client and client.logo_id == f.id:
        client.logo_id = None
    db.delete(f)
    db.commit()
    flash("Arquivo excluído.", "ok")
    return redirect(safe_next(request.form.get("voltar"), url_for("clientes.detail", cid=f.client_id)))
