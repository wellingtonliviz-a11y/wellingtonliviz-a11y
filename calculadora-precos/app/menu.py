"""Cardápio digital: link público, fotos dos produtos e pedido pelo WhatsApp."""
import json
import math
import re
import secrets

from flask import Blueprint, Response, abort, current_app, g, jsonify, render_template, request
from sqlalchemy import func, select

from .models import Menu, Photo, User, UserData, utcnow
from .security import login_required

bp = Blueprint("menu", __name__)

SLUG_RE = re.compile(r"^[a-z0-9](?:[a-z0-9-]{1,38}[a-z0-9])$")
RESERVED = {"admin", "api", "demo", "entrar", "sair", "conta", "esqueci", "suporte", "precifica",
            "precifica-facil", "cardapio", "webhooks", "static"}
MAX_PHOTO_BYTES = 400 * 1024
MAX_PHOTOS_PER_USER = 120
IMAGE_MAGIC = {b"\xff\xd8\xff": "image/jpeg", b"\x89PNG": "image/png", b"RIFF": "image/webp"}
UNITS = {"g": 1, "kg": 1000, "ml": 1, "L": 1000, "un": 1}


# ---------- preço (mesma conta da calculadora em app.js) ----------
def _num(v) -> float:
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        return float(v) if math.isfinite(v) else 0.0
    t = re.sub(r"r\$|%|\s", "", str(v or ""), flags=re.I)
    if "," in t:
        t = t.replace(".", "").replace(",", ".")
    try:
        n = float(t)
    except ValueError:
        return 0.0
    return n if math.isfinite(n) else 0.0


def product_price(state: dict, p: dict) -> float | None:
    """Preço mostrado no cardápio: o que a pessoa cobra hoje ou, se vazio, o sugerido."""
    current = _num(p.get("current"))
    if current > 0:
        return round(current, 2)
    s = state.get("settings") or {}
    ings = {i.get("id"): i for i in state.get("ingredients") or []}
    ing_cost = 0.0
    for it in p.get("items") or []:
        ing = ings.get(it.get("ingId"))
        if not ing:
            continue
        qty = _num(ing.get("qty")) * UNITS.get(ing.get("unit"), 1)
        if qty > 0:
            ing_cost += _num(it.get("qty")) * _num(ing.get("price")) / qty
    batch = ing_cost * (1 + _num(s.get("extras")) / 100) + _num(p.get("minutes")) / 60 * _num(s.get("hourly"))
    y = _num(p.get("yield"))
    if y <= 0:
        return None
    margin = s.get("margin") if p.get("margin") in (None, "") else p.get("margin")
    denom = 1 - _num(margin) / 100 - _num(s.get("fee")) / 100
    if denom <= 0.05:
        return None
    suggested = batch / y / denom
    step = _num(s.get("round"))
    price = math.ceil(suggested / step - 1e-9) * step if step > 0 else suggested
    return round(price, 2) if price > 0 else None


def whatsapp_digits(raw: str) -> str:
    d = re.sub(r"\D", "", raw or "")
    if len(d) in (10, 11):  # número brasileiro sem DDI
        d = "55" + d
    return d if 12 <= len(d) <= 15 else ""


def public_menu(state: dict) -> dict:
    menu = state.get("menu") or {}
    items = []
    for p in state.get("products") or []:
        pm = p.get("menu") or {}
        if pm.get("show") is False or not (p.get("name") or "").strip():
            continue
        price = product_price(state, p)
        if price is None:
            continue
        items.append({"id": p.get("id"), "name": p["name"].strip()[:120], "desc": (pm.get("desc") or "")[:300],
                      "photo": pm.get("photo") or None, "price": price})
    settings = state.get("settings") or {}
    return {"business": (settings.get("business") or "").strip(), "intro": (menu.get("intro") or "")[:500],
            "delivery": (menu.get("delivery") or "")[:300], "whatsapp": whatsapp_digits(menu.get("whatsapp")),
            "items": items}


# ---------- link do cardápio ----------
def _menu_url(slug: str) -> str:
    return f"{current_app.config['APP_URL']}/c/{slug}"


@bp.get("/api/cardapio")
@login_required
def get_menu_link():
    row = current_app.db.session.get(Menu, g.user.id)
    return jsonify(slug=row.slug if row else None, url=_menu_url(row.slug) if row else None,
                   base=f"{current_app.config['APP_URL']}/c/")


@bp.put("/api/cardapio")
@login_required
def set_menu_link():
    slug = str((request.get_json(silent=True) or {}).get("slug") or "").strip().lower()
    if not SLUG_RE.match(slug) or "--" in slug:
        return jsonify(error="Use de 3 a 40 letras minúsculas, números e hífen. Ex: doces-da-ana"), 400
    if slug in RESERVED:
        return jsonify(error="Esse nome é reservado. Escolha outro."), 400
    db = current_app.db.session
    taken = db.scalar(select(Menu).where(Menu.slug == slug, Menu.user_id != g.user.id))
    if taken:
        return jsonify(error="Esse link já está em uso. Tente outro, como " + slug + "-2"), 409
    row = db.get(Menu, g.user.id)
    if row is None:
        db.add(Menu(user_id=g.user.id, slug=slug, updated_at=utcnow()))
    else:
        row.slug, row.updated_at = slug, utcnow()
    db.commit()
    return jsonify(slug=slug, url=_menu_url(slug))


# ---------- fotos ----------
@bp.post("/api/fotos")
@login_required
def upload_photo():
    data = request.get_data()
    if not data or len(data) > MAX_PHOTO_BYTES:
        return jsonify(error="A foto precisa ter até 400 KB."), 413
    mime = next((m for magic, m in IMAGE_MAGIC.items() if data.startswith(magic)), None)
    if mime is None or (mime == "image/webp" and data[8:12] != b"WEBP"):
        return jsonify(error="Envie uma imagem JPG, PNG ou WebP."), 400
    db = current_app.db.session
    count = db.scalar(select(func.count()).select_from(Photo).where(Photo.user_id == g.user.id))
    if count >= MAX_PHOTOS_PER_USER:
        return jsonify(error="Limite de fotos atingido. Remova fotos antigas."), 400
    photo = Photo(id=secrets.token_hex(16), user_id=g.user.id, mime=mime, data=data, created_at=utcnow())
    db.add(photo)
    db.commit()
    return jsonify(id=photo.id, url=f"/f/{photo.id}")


@bp.delete("/api/fotos/<photo_id>")
@login_required
def delete_photo(photo_id):
    db = current_app.db.session
    photo = db.get(Photo, photo_id)
    if photo and photo.user_id == g.user.id:
        db.delete(photo)
        db.commit()
    return jsonify(ok=True)


@bp.get("/f/<photo_id>")
def photo(photo_id):
    row = current_app.db.session.get(Photo, photo_id) if re.fullmatch(r"[0-9a-f]{32}", photo_id) else None
    if row is None:
        abort(404)
    resp = Response(row.data, mimetype=row.mime)
    resp.headers["Cache-Control"] = "public, max-age=31536000, immutable"
    return resp


# ---------- página pública ----------
@bp.get("/c/<slug>")
def public_page(slug):
    db = current_app.db.session
    row = db.scalar(select(Menu).where(Menu.slug == slug.lower()))
    user = db.get(User, row.user_id) if row else None
    if user is None or not user.active:
        abort(404)
    data = db.get(UserData, user.id)
    state = json.loads(data.data) if data else {}
    menu = public_menu(state)
    if not menu["business"]:
        menu["business"] = user.name or "Cardápio"
    cfg = current_app.config
    promo = cfg["CHECKOUT_URL"] or f"{cfg['APP_URL']}/demo"
    first_photo = next((i["photo"] for i in menu["items"] if i["photo"]), None)
    return render_template("cardapio_publico.html", menu=menu, promo_url=promo,
                           page_url=_menu_url(row.slug),
                           og_image=f"{cfg['APP_URL']}/f/{first_photo}" if first_photo else None)
