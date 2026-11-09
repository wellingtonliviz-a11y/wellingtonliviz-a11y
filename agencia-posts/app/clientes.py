"""Cadastro dos comércios: dados, identidade visual, arquivos e link de aprovação."""
import re
from datetime import timedelta

from flask import Blueprint, abort, current_app, flash, redirect, render_template, request, url_for
from sqlalchemy import func, select

from .arquivos import flash_upload_result, save_uploads
from .models import Client, File, Post, new_token
from .security import login_required
from .util import KINDS, agora, brl, month_bounds, parse_money, start_of_day, whatsapp_link

bp = Blueprint("clientes", __name__)

COLOR_RE = re.compile(r"#[0-9a-f]{6}")


def get_client(cid: int) -> Client:
    client = current_app.db.session.get(Client, cid)
    if client is None:
        abort(404)
    return client


def fill_client(client: Client, form) -> list[str]:
    errors = []
    client.name = form.get("name", "").strip()[:120]
    if not client.name:
        errors.append("Informe o nome do comércio.")
    for field, limit in (("segment", 80), ("contact_name", 120), ("phone", 40), ("email", 255), ("fonts", 200)):
        setattr(client, field, form.get(field, "").strip()[:limit])
    client.instagram = form.get("instagram", "").strip().lstrip("@").removeprefix("https://www.instagram.com/")
    client.instagram = client.instagram.strip("/")[:80]
    client.voice = form.get("voice", "").strip()[:5000]
    client.notes = form.get("notes", "").strip()[:5000]
    for field in ("color_primary", "color_secondary"):
        value = form.get(field, "").strip().lower()
        if COLOR_RE.fullmatch(value):
            setattr(client, field, value)
        else:
            errors.append("Cor inválida: use o seletor de cor.")
    try:
        client.monthly_fee_cents = parse_money(form.get("monthly_fee", ""))
    except ValueError:
        errors.append("Valor mensal inválido. Exemplo: 450,00")
    day = form.get("payment_day", "").strip()
    if day:
        if day.isdigit() and 1 <= int(day) <= 31:
            client.payment_day = int(day)
        else:
            errors.append("Dia de pagamento deve ser de 1 a 31.")
    else:
        client.payment_day = None
    posts = form.get("posts_per_month", "").strip() or "0"
    if posts.isdigit() and int(posts) <= 300:
        client.posts_per_month = int(posts)
    else:
        errors.append("Postagens por mês deve ser um número.")
    return errors


def _money_input(client: Client) -> str:
    return brl(client.monthly_fee_cents).removeprefix("R$ ") if client.monthly_fee_cents is not None else ""


@bp.get("/clientes")
@login_required
def index():
    db = current_app.db.session
    show = request.args.get("mostrar", "ativos")
    query = select(Client).order_by(func.lower(Client.name))
    if show != "todos":
        query = query.where(Client.active.is_(True))
    clients = db.scalars(query).all()
    now = agora()
    start, end = month_bounds(now.year, now.month)
    counts = dict(db.execute(select(Post.client_id, func.count()).where(
        Post.scheduled_at >= start, Post.scheduled_at < end).group_by(Post.client_id)).all())
    return render_template("clientes.html", clients=clients, counts=counts, show=show)


@bp.route("/clientes/novo", methods=["GET", "POST"])
@login_required
def new():
    client = Client(color_primary="#7c3aed", color_secondary="#f59e0b", posts_per_month=12)
    if request.method == "POST":
        errors = fill_client(client, request.form)
        if not errors:
            db = current_app.db.session
            db.add(client)
            db.flush()
            saved, rejected = save_uploads(client.id, "logo", request.files.getlist("logo"))
            if saved:
                client.logo_id = saved[0].id
            db.commit()
            flash_upload_result([], rejected)
            flash(f"{client.name} cadastrado.", "ok")
            return redirect(url_for("clientes.detail", cid=client.id))
        for e in errors:
            flash(e, "erro")
    return render_template("cliente_form.html", client=client, money=request.form.get("monthly_fee", ""))


@bp.route("/clientes/<int:cid>/editar", methods=["GET", "POST"])
@login_required
def edit(cid: int):
    db = current_app.db.session
    client = get_client(cid)
    if request.method == "POST":
        errors = fill_client(client, request.form)
        if not errors:
            db.commit()
            flash("Dados salvos.", "ok")
            return redirect(url_for("clientes.detail", cid=cid))
        # não salva: a sessão é descartada no fim da requisição; o formulário volta com o que foi digitado
        for e in errors:
            flash(e, "erro")
        return render_template("cliente_form.html", client=client, money=request.form.get("monthly_fee", ""))
    return render_template("cliente_form.html", client=client, money=_money_input(client))


@bp.get("/clientes/<int:cid>")
@login_required
def detail(cid: int):
    db = current_app.db.session
    client = get_client(cid)
    kind = request.args.get("tipo", "")
    files_q = select(File).where(File.client_id == cid).order_by(File.created_at.desc())
    if kind in KINDS:
        files_q = files_q.where(File.kind == kind)
    files = db.scalars(files_q).all()
    counts = dict(db.execute(select(File.kind, func.count()).where(File.client_id == cid)
                             .group_by(File.kind)).all())
    today = start_of_day(agora().date())
    upcoming = db.scalars(select(Post).where(Post.client_id == cid, Post.scheduled_at >= today)
                          .order_by(Post.scheduled_at).limit(15)).all()
    recent = db.scalars(select(Post).where(Post.client_id == cid, Post.scheduled_at < today,
                                           Post.scheduled_at >= today - timedelta(days=30))
                        .order_by(Post.scheduled_at.desc()).limit(10)).all()
    approval_url = current_app.config["APP_URL"] + url_for("aprovacao.page", token=client.approval_token)
    waiting = sum(1 for p in upcoming if p.status == "aprovacao")
    greeting = f"Olá{(' ' + client.contact_name.split()[0]) if client.contact_name else ''}!"
    wa_link = whatsapp_link(client.phone, f"{greeting} As artes estão prontas para você aprovar: {approval_url}")
    return render_template("cliente.html", client=client, files=files, kind=kind, counts=counts,
                           upcoming=upcoming, recent=recent, approval_url=approval_url,
                           waiting=waiting, wa_link=wa_link)


@bp.post("/clientes/<int:cid>/arquivos")
@login_required
def upload(cid: int):
    client = get_client(cid)
    kind = request.form.get("kind", "foto")
    if kind not in KINDS:
        kind = "outro"
    saved, rejected = save_uploads(cid, kind, request.files.getlist("arquivos"))
    if kind == "logo" and saved and not client.logo_id:
        client.logo_id = saved[0].id
    current_app.db.session.commit()
    if not saved and not rejected:
        flash("Escolha pelo menos um arquivo.", "erro")
    flash_upload_result(saved, rejected)
    return redirect(url_for("clientes.detail", cid=cid, tipo=request.form.get("voltar_tipo", "")))


@bp.post("/clientes/<int:cid>/logo/<fid>")
@login_required
def set_logo(cid: int, fid: str):
    db = current_app.db.session
    client = get_client(cid)
    f = db.get(File, fid)
    if f is None or f.client_id != cid or not f.mime.startswith("image/"):
        abort(404)
    client.logo_id = f.id
    if f.kind != "logo":
        f.kind = "logo"
    db.commit()
    flash("Logo principal atualizado.", "ok")
    return redirect(url_for("clientes.detail", cid=cid))


@bp.post("/clientes/<int:cid>/ativo")
@login_required
def toggle_active(cid: int):
    client = get_client(cid)
    client.active = not client.active
    current_app.db.session.commit()
    flash(f"{client.name} {'reativado' if client.active else 'arquivado (sai das listas e do link de aprovação)'}.", "ok")
    return redirect(url_for("clientes.detail", cid=cid))


@bp.post("/clientes/<int:cid>/novo-link")
@login_required
def new_link(cid: int):
    client = get_client(cid)
    client.approval_token = new_token()
    current_app.db.session.commit()
    flash("Link de aprovação trocado. O link antigo parou de funcionar.", "ok")
    return redirect(url_for("clientes.detail", cid=cid))
