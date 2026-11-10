"""Agenda: link público de agendamento, horários livres, agendamentos e fotos dos serviços."""
import json
import logging
import math
import re
import secrets
from datetime import date, datetime, time, timedelta, timezone

from flask import Blueprint, Response, abort, current_app, g, jsonify, render_template, request
from sqlalchemy import func, select

from .mailer import send_mail
from .models import Appointment, BookingLink, Photo, User, UserData, utcnow
from .security import RateLimiter, login_required

log = logging.getLogger(__name__)
bp = Blueprint("agenda", __name__)

SLUG_RE = re.compile(r"^[a-z0-9](?:[a-z0-9-]{1,38}[a-z0-9])$")
RESERVED = {"admin", "api", "demo", "entrar", "sair", "conta", "esqueci", "suporte", "precifica", "agenda",
            "agendar", "manicure", "precifica-facil", "webhooks", "static", "termos", "privacidade"}
MAX_PHOTO_BYTES = 400 * 1024
MAX_PHOTOS_PER_USER = 120
IMAGE_MAGIC = {b"\xff\xd8\xff": "image/jpeg", b"\x89PNG": "image/png", b"RIFF": "image/webp"}
UNITS = {"g": 1, "kg": 1000, "ml": 1, "L": 1000, "un": 1}
STATUSES = {"pendente", "confirmado", "concluido", "cancelado", "bloqueio"}
WEEKDAYS = ["dom", "seg", "ter", "qua", "qui", "sex", "sáb"]  # 0 = domingo (igual ao JavaScript)
DAY_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
MAX_RANGE_DAYS = 62
MAX_ONLINE_PER_PHONE = 3  # agendamentos futuros feitos pelo link com o mesmo telefone

booking_limiter = RateLimiter(8, 60 * 60)


# ---------- números e preço (mesma conta do app.js) ----------
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


def service_price(state: dict, p: dict) -> float | None:
    """Preço do serviço: o que a manicure cobra hoje ou, se vazio, o sugerido."""
    current = _num(p.get("current"))
    if current > 0:
        return round(current, 2)
    s = state.get("settings") or {}
    ings = {i.get("id"): i for i in state.get("ingredients") or []}
    mat_cost = 0.0
    for it in p.get("items") or []:
        ing = ings.get(it.get("ingId"))
        if not ing:
            continue
        qty = _num(ing.get("qty")) * UNITS.get(ing.get("unit"), 1)
        if qty > 0:
            mat_cost += _num(it.get("qty")) * _num(ing.get("price")) / qty
    total = mat_cost * (1 + _num(s.get("extras")) / 100) + _num(p.get("minutes")) / 60 * _num(s.get("hourly"))
    y = _num(p.get("yield")) or 1
    margin = s.get("margin") if p.get("margin") in (None, "") else p.get("margin")
    denom = 1 - _num(margin) / 100 - _num(s.get("fee")) / 100
    if denom <= 0.05:
        return None
    suggested = total / y / denom
    step = _num(s.get("round"))
    price = math.ceil(suggested / step - 1e-9) * step if step > 0 else suggested
    return round(price, 2) if price > 0 else None


def whatsapp_digits(raw: str) -> str:
    d = re.sub(r"\D", "", raw or "")
    if len(d) in (10, 11):  # número brasileiro sem DDI
        d = "55" + d
    return d if 12 <= len(d) <= 15 else ""


# ---------- horários ----------
def hm(text) -> int | None:
    m = re.fullmatch(r"(\d{1,2}):(\d{2})", str(text or "").strip())
    if not m:
        return None
    h, mi = int(m.group(1)), int(m.group(2))
    return h * 60 + mi if h < 24 and mi < 60 else None


def fmt_hm(minutes: int) -> str:
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


def _tz():
    try:
        from zoneinfo import ZoneInfo
        return ZoneInfo(current_app.config.get("TIMEZONE") or "America/Sao_Paulo")
    except Exception:  # sem base de fusos no servidor: Brasília não tem horário de verão
        return timezone(timedelta(hours=-3))


def local_now() -> datetime:
    """Agora, no horário local da agenda, sem fuso (para comparar com dia + hora)."""
    return datetime.now(_tz()).replace(tzinfo=None, second=0, microsecond=0)


def _clamp(v, lo, hi, default):
    n = _num(v) if v not in (None, "") else default
    return int(min(hi, max(lo, n)))


DEFAULT_WEEK = [{"on": d in range(1, 7), "start": "09:00", "end": "18:00" if d < 6 else "14:00"} for d in range(7)]


def agenda_cfg(state: dict) -> dict:
    """Configuração da agenda com valores padrão e limites seguros."""
    a = state.get("agenda") or {}
    week = a.get("week") if isinstance(a.get("week"), list) and len(a.get("week")) == 7 else DEFAULT_WEEK
    days = []
    for d in week:
        d = d if isinstance(d, dict) else {}
        start, end = hm(d.get("start")), hm(d.get("end"))
        days.append((start, end) if d.get("on") and start is not None and end is not None and end > start else None)
    lunch = a.get("lunch") or {}
    ls, le = hm(lunch.get("start")), hm(lunch.get("end"))
    return {
        "days": days,
        "lunch": (ls, le) if lunch.get("on") and ls is not None and le is not None and le > ls else None,
        "step": _clamp(a.get("step"), 10, 120, 30),
        "notice": _clamp(a.get("notice"), 0, 72, 2),          # horas de antecedência
        "days_ahead": _clamp(a.get("daysAhead"), 1, 90, 30),
        "auto_confirm": bool(a.get("autoConfirm")),
        "notify_email": a.get("notifyEmail") is not False,
    }


def _overlaps(a0: int, a1: int, b0: int, b1: int) -> bool:
    return a0 < b1 and b0 < a1


def free_slots(cfg: dict, day: date, duration: int, busy: list[tuple[int, int]], now: datetime) -> list[int]:
    """Horários de início livres no dia para um atendimento de `duration` minutos."""
    window = cfg["days"][(day.weekday() + 1) % 7]
    if window is None or duration <= 0:
        return []
    today = now.date()
    if day < today or day > today + timedelta(days=cfg["days_ahead"]):
        return []
    earliest = now + timedelta(hours=cfg["notice"])
    blocks = list(busy) + ([cfg["lunch"]] if cfg["lunch"] else [])
    out = []
    for m in range(window[0], window[1] - duration + 1, cfg["step"]):
        if datetime.combine(day, time()) + timedelta(minutes=m) < earliest:
            continue
        if any(_overlaps(m, m + duration, b0, b1) for b0, b1 in blocks):
            continue
        out.append(m)
    return out


def busy_ranges(user_id: int, day: str, ignore_id: str | None = None) -> list[tuple[int, int]]:
    rows = current_app.db.session.scalars(select(Appointment).where(
        Appointment.user_id == user_id, Appointment.day == day, Appointment.status != "cancelado")).all()
    return [(r.start_min, r.start_min + r.duration) for r in rows if r.id != ignore_id]


def parse_day(text) -> date | None:
    if not DAY_RE.match(str(text or "")):
        return None
    try:
        return date.fromisoformat(text)
    except ValueError:
        return None


# ---------- serviços públicos ----------
def public_services(state: dict) -> list[dict]:
    out = []
    for p in state.get("products") or []:
        pm = p.get("menu") or {}
        if pm.get("show") is False or not (p.get("name") or "").strip():
            continue
        price = service_price(state, p)
        if price is None:
            continue
        minutes = int(_num(p.get("minutes"))) or 60
        out.append({"id": str(p.get("id")), "name": p["name"].strip()[:120], "desc": (pm.get("desc") or "")[:300],
                    "photo": pm.get("photo") or None, "price": price, "minutes": max(5, min(minutes, 600))})
    return out


def serialize(a: Appointment) -> dict:
    return {"id": a.id, "day": a.day, "time": fmt_hm(a.start_min), "end": fmt_hm(a.start_min + a.duration),
            "start": a.start_min, "duration": a.duration, "status": a.status, "source": a.source,
            "client_name": a.client_name, "client_phone": a.client_phone,
            "wa": whatsapp_digits(a.client_phone), "services": a.services,
            "price": a.price_cents / 100, "note": a.note}


def _state(user_id: int) -> dict:
    row = current_app.db.session.get(UserData, user_id)
    return json.loads(row.data) if row else {}


# ---------- link de agendamento ----------
def _link_url(slug: str) -> str:
    return f"{current_app.config['APP_URL']}/a/{slug}"


@bp.get("/api/agenda/link")
@login_required
def get_link():
    row = current_app.db.session.get(BookingLink, g.user.id)
    return jsonify(slug=row.slug if row else None, url=_link_url(row.slug) if row else None,
                   base=f"{current_app.config['APP_URL']}/a/")


@bp.put("/api/agenda/link")
@login_required
def set_link():
    slug = str((request.get_json(silent=True) or {}).get("slug") or "").strip().lower()
    if not SLUG_RE.match(slug) or "--" in slug:
        return jsonify(error="Use de 3 a 40 letras minúsculas, números e hífen. Ex: unhas-da-carol"), 400
    if slug in RESERVED:
        return jsonify(error="Esse nome é reservado. Escolha outro."), 400
    db = current_app.db.session
    if db.scalar(select(BookingLink).where(BookingLink.slug == slug, BookingLink.user_id != g.user.id)):
        return jsonify(error="Esse link já está em uso. Tente outro, como " + slug + "-2"), 409
    row = db.get(BookingLink, g.user.id)
    if row is None:
        db.add(BookingLink(user_id=g.user.id, slug=slug, updated_at=utcnow()))
    else:
        row.slug, row.updated_at = slug, utcnow()
    db.commit()
    return jsonify(slug=slug, url=_link_url(slug))


# ---------- agendamentos (dona da agenda) ----------
def _read_fields(body: dict, current: Appointment | None = None) -> tuple[dict | None, str]:
    """Valida os campos enviados. Retorna (campos, erro)."""
    out = {}
    if "day" in body or current is None:
        d = parse_day(body.get("day"))
        if d is None:
            return None, "Escolha a data."
        out["day"] = d.isoformat()
    if "time" in body or current is None:
        m = hm(body.get("time"))
        if m is None:
            return None, "Escolha o horário."
        out["start_min"] = m
    if "duration" in body or current is None:
        dur = int(_num(body.get("duration")))
        if not 5 <= dur <= 720:
            return None, "A duração precisa ser de 5 minutos a 12 horas."
        out["duration"] = dur
    start = out.get("start_min", current.start_min if current else 0)
    if start + out.get("duration", current.duration if current else 0) > 24 * 60:
        return None, "O horário passa da meia-noite."
    if "status" in body:
        if body["status"] not in STATUSES:
            return None, "Situação inválida."
        out["status"] = body["status"]
    for key, size in (("client_name", 120), ("services", 300), ("note", 300)):
        if key in body:
            out[key] = str(body.get(key) or "").strip()[:size]
    if "client_phone" in body:
        out["client_phone"] = re.sub(r"[^\d()+\- ]", "", str(body.get("client_phone") or ""))[:20].strip()
    if "price" in body:
        out["price_cents"] = max(0, min(int(round(_num(body.get("price")) * 100)), 10_000_000))
    return out, ""


@bp.get("/api/agendamentos")
@login_required
def list_appointments():
    start, end = parse_day(request.args.get("de")), parse_day(request.args.get("ate"))
    if start is None or end is None or end < start or (end - start).days > MAX_RANGE_DAYS:
        return jsonify(error="Período inválido."), 400
    rows = current_app.db.session.scalars(select(Appointment).where(
        Appointment.user_id == g.user.id, Appointment.day >= start.isoformat(), Appointment.day <= end.isoformat())
        .order_by(Appointment.day, Appointment.start_min)).all()
    now = local_now()
    return jsonify(items=[serialize(a) for a in rows], today=now.date().isoformat(), now=fmt_hm(now.hour * 60 + now.minute))


@bp.post("/api/agendamentos")
@login_required
def create_appointment():
    body = request.get_json(silent=True) or {}
    fields, error = _read_fields(body)
    if error:
        return jsonify(error=error), 400
    fields.setdefault("status", "confirmado")
    if fields["status"] == "bloqueio":
        fields.update(client_name="", client_phone="", price_cents=0)
    db = current_app.db.session
    if not body.get("force") and any(_overlaps(fields["start_min"], fields["start_min"] + fields["duration"], b0, b1)
                                     for b0, b1 in busy_ranges(g.user.id, fields["day"])):
        return jsonify(error="Já existe outro horário nesse período.", conflict=True), 409
    a = Appointment(id=secrets.token_hex(16), user_id=g.user.id, source="manual", **fields)
    db.add(a)
    db.commit()
    return jsonify(item=serialize(a)), 201


def _own(appt_id: str) -> Appointment:
    a = current_app.db.session.get(Appointment, appt_id) if re.fullmatch(r"[0-9a-f]{32}", appt_id) else None
    if a is None or a.user_id != g.user.id:
        abort(404)
    return a


@bp.patch("/api/agendamentos/<appt_id>")
@login_required
def update_appointment(appt_id):
    a = _own(appt_id)
    body = request.get_json(silent=True) or {}
    fields, error = _read_fields(body, a)
    if error:
        return jsonify(error=error), 400
    day = fields.get("day", a.day)
    start, dur = fields.get("start_min", a.start_min), fields.get("duration", a.duration)
    # só confere conflito se o horário mudou ou se um cancelado voltou para a agenda
    changed = any(k in fields for k in ("day", "start_min", "duration")) or a.status == "cancelado"
    if fields.get("status", a.status) != "cancelado" and changed and not body.get("force") and \
            any(_overlaps(start, start + dur, b0, b1) for b0, b1 in busy_ranges(g.user.id, day, ignore_id=a.id)):
        return jsonify(error="Já existe outro horário nesse período.", conflict=True), 409
    for k, v in fields.items():
        setattr(a, k, v)
    a.updated_at = utcnow()
    current_app.db.session.commit()
    return jsonify(item=serialize(a))


@bp.delete("/api/agendamentos/<appt_id>")
@login_required
def delete_appointment(appt_id):
    a = _own(appt_id)
    current_app.db.session.delete(a)
    current_app.db.session.commit()
    return jsonify(ok=True)


# ---------- fotos dos serviços ----------
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


# ---------- página pública de agendamento ----------
def _owner_by_slug(slug: str) -> tuple[User, BookingLink]:
    db = current_app.db.session
    row = db.scalar(select(BookingLink).where(BookingLink.slug == slug.lower()))
    user = db.get(User, row.user_id) if row else None
    if user is None or not user.active:
        abort(404)
    return user, row


def _public_info(user: User, state: dict) -> dict:
    a = state.get("agenda") or {}
    business = ((state.get("settings") or {}).get("business") or "").strip() or user.name or "Agenda"
    return {"business": business[:80], "intro": str(a.get("intro") or "")[:500],
            "address": str(a.get("address") or "")[:300], "whatsapp": whatsapp_digits(a.get("whatsapp"))}


@bp.get("/a/<slug>")
def public_page(slug):
    user, row = _owner_by_slug(slug)
    state = _state(user.id)
    cfg = agenda_cfg(state)
    now = local_now()
    days = []
    for i in range(cfg["days_ahead"] + 1):
        d = now.date() + timedelta(days=i)
        days.append({"day": d.isoformat(), "wd": "Hoje" if i == 0 else "Amanhã" if i == 1 else WEEKDAYS[(d.weekday() + 1) % 7],
                     "dm": d.strftime("%d/%m"), "open": cfg["days"][(d.weekday() + 1) % 7] is not None})
    services = public_services(state)
    info = _public_info(user, state)
    app_cfg = current_app.config
    first_photo = next((s["photo"] for s in services if s["photo"]), None)
    return render_template("agendar.html", info=info, services=services, days=days, slug=row.slug,
                           page_url=_link_url(row.slug), promo_url=app_cfg["CHECKOUT_URL"] or f"{app_cfg['APP_URL']}/demo",
                           timezone=app_cfg.get("TIMEZONE") or "America/Sao_Paulo",
                           og_image=f"{app_cfg['APP_URL']}/f/{first_photo}" if first_photo else None)


def _chosen(state: dict, ids) -> list[dict]:
    if isinstance(ids, str):
        ids = ids.split(",")
    by_id = {s["id"]: s for s in public_services(state)}
    seen, out = set(), []
    for i in ids if isinstance(ids, list) else []:
        i = str(i)
        if i in by_id and i not in seen:
            seen.add(i)
            out.append(by_id[i])
    return out[:6]


@bp.get("/api/publico/<slug>/horarios")
def public_slots(slug):
    user, _ = _owner_by_slug(slug)
    state = _state(user.id)
    chosen = _chosen(state, request.args.get("servicos", ""))
    d = parse_day(request.args.get("dia"))
    if not chosen or d is None:
        return jsonify(error="Escolha o serviço e o dia."), 400
    duration = sum(s["minutes"] for s in chosen)
    slots = free_slots(agenda_cfg(state), d, duration, busy_ranges(user.id, d.isoformat()), local_now())
    return jsonify(slots=[fmt_hm(m) for m in slots], duration=duration)


@bp.post("/api/publico/<slug>/agendar")
def public_book(slug):
    user, _ = _owner_by_slug(slug)
    if not booking_limiter.allow(f"{request.remote_addr}:{slug}"):
        return jsonify(error="Muitas tentativas. Espere um pouco e tente de novo."), 429
    body = request.get_json(silent=True) or {}
    state = _state(user.id)
    cfg = agenda_cfg(state)
    chosen = _chosen(state, body.get("servicos"))
    d, start = parse_day(body.get("dia")), hm(body.get("hora"))
    name = " ".join(str(body.get("nome") or "").split())[:120]
    phone_digits = re.sub(r"\D", "", str(body.get("telefone") or ""))
    if not chosen:
        return jsonify(error="Escolha pelo menos um serviço."), 400
    if d is None or start is None:
        return jsonify(error="Escolha o dia e o horário."), 400
    if len(name) < 2:
        return jsonify(error="Informe seu nome."), 400
    if not 10 <= len(phone_digits) <= 13:
        return jsonify(error="Informe seu WhatsApp com DDD."), 400
    duration = sum(s["minutes"] for s in chosen)
    db = current_app.db.session
    today = local_now().date().isoformat()
    open_count = db.scalar(select(func.count()).select_from(Appointment).where(
        Appointment.user_id == user.id, Appointment.source == "online", Appointment.day >= today,
        Appointment.status.in_(("pendente", "confirmado")), Appointment.client_phone == phone_digits))
    if open_count >= MAX_ONLINE_PER_PHONE:
        return jsonify(error="Você já tem horários marcados. Fale com o salão pelo WhatsApp para marcar mais."), 409
    if start not in free_slots(cfg, d, duration, busy_ranges(user.id, d.isoformat()), local_now()):
        return jsonify(error="Esse horário acabou de ser ocupado. Escolha outro.", taken=True), 409
    price = round(sum(s["price"] for s in chosen), 2)
    a = Appointment(id=secrets.token_hex(16), user_id=user.id, day=d.isoformat(), start_min=start, duration=duration,
                    status="confirmado" if cfg["auto_confirm"] else "pendente", source="online",
                    client_name=name, client_phone=phone_digits, services=" + ".join(s["name"] for s in chosen)[:300],
                    price_cents=int(round(price * 100)), note=str(body.get("obs") or "").strip()[:300])
    db.add(a)
    db.commit()
    if cfg["notify_email"]:
        _notify_owner(user, a)
    info = _public_info(user, state)
    return jsonify(ok=True, item={"day": a.day, "time": fmt_hm(a.start_min), "end": fmt_hm(a.start_min + a.duration),
                                  "status": a.status, "services": a.services, "price": price,
                                  "business": info["business"], "whatsapp": info["whatsapp"]}), 201


def _notify_owner(user: User, a: Appointment) -> None:
    cfg = current_app.config
    d = date.fromisoformat(a.day)
    when = f"{WEEKDAYS[(d.weekday() + 1) % 7]}, {d.strftime('%d/%m')} às {fmt_hm(a.start_min)}"
    value = f"R$ {a.price_cents / 100:.2f}".replace(".", ",")
    text = (f"Olá!\n\nVocê recebeu um novo agendamento pelo seu link:\n\n"
            f"Cliente: {a.client_name}\nWhatsApp: {a.client_phone}\nServiço: {a.services}\n"
            f"Quando: {when} ({a.duration} min)\nValor: {value}"
            + (f"\nObservação: {a.note}" if a.note else "")
            + ("\n\nO horário está aguardando a sua confirmação." if a.status == "pendente" else "")
            + f"\n\nVeja a sua agenda: {cfg['APP_URL']}/\n\n—\n{cfg['PRODUCT_NAME']}")
    try:
        send_mail(user.email, f"Novo agendamento: {a.client_name}, {when}", text)
    except Exception:  # o agendamento não pode falhar por causa do e-mail
        log.exception("falha ao avisar novo agendamento")
