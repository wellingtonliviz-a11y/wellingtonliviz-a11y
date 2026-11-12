"""Acomodações, equipe e financeiro (só administradores)."""
from datetime import date

from flask import Blueprint, current_app, flash, g, redirect, render_template, request, url_for
from sqlalchemy import select

from .access import hash_password, normalize_email
from .auth import MIN_PASSWORD
from .cadastros import _get
from .models import PAY_METHODS, SIZES, SPECIES, Booking, Payment, Room, User
from .security import admin_required
from .util import parse_money, today

bp = Blueprint("gestao", __name__)


@bp.get("/acomodacoes")
@admin_required
def rooms():
    rooms = current_app.db.session.scalars(select(Room).order_by(Room.active.desc(), Room.species, Room.name)).all()
    return render_template("acomodacoes.html", rooms=rooms)


@bp.route("/acomodacoes/nova", methods=["GET", "POST"])
@bp.route("/acomodacoes/<int:room_id>/editar", methods=["GET", "POST"])
@admin_required
def room_form(room_id=None):
    db = current_app.db.session
    room = _get(Room, room_id) if room_id else Room(species="cao", max_size="G", capacity=1, active=True)
    if request.method == "POST":
        room.name = request.form.get("name", "").strip()[:60]
        room.species = request.form.get("species", "")
        room.max_size = request.form.get("max_size", "G") if room.species == "cao" else "G"
        room.capacity = max(request.form.get("capacity", 1, type=int) or 1, 1)
        rate = parse_money(request.form.get("daily_rate"))
        room.description = request.form.get("description", "").strip()[:200]
        room.active = request.form.get("active") == "1"
        if not room.name or room.species not in SPECIES or room.max_size not in SIZES or rate is None:
            flash("Preencha nome, tipo e valor da diária.", "erro")
            db.rollback()
        else:
            room.daily_rate_cents = rate
            if room.id is None:
                db.add(room)
            db.commit()
            flash("Acomodação salva.", "ok")
            return redirect(url_for("gestao.rooms"))
    return render_template("acomodacao_form.html", room=room)


@bp.route("/equipe", methods=["GET", "POST"])
@admin_required
def team():
    db = current_app.db.session
    if request.method == "POST":
        email = normalize_email(request.form.get("email", ""))
        name = request.form.get("name", "").strip()[:120]
        password = request.form.get("password", "")
        if not name or "@" not in email:
            flash("Informe nome e e-mail.", "erro")
        elif len(password) < MIN_PASSWORD:
            flash(f"A senha inicial precisa ter pelo menos {MIN_PASSWORD} caracteres.", "erro")
        elif db.scalar(select(User).where(User.email == email)):
            flash("Já existe alguém com este e-mail.", "erro")
        else:
            db.add(User(email=email, name=name, password_hash=hash_password(password),
                        is_admin=request.form.get("is_admin") == "1"))
            db.commit()
            flash(f"{name} agora tem acesso ao sistema.", "ok")
            return redirect(url_for("gestao.team"))
    return render_template("equipe.html", users=db.scalars(select(User).order_by(User.name)).all())


@bp.post("/equipe/<int:user_id>/acesso")
@admin_required
def team_toggle(user_id):
    db = current_app.db.session
    user = _get(User, user_id)
    if user.id == g.user.id:
        flash("Você não pode bloquear a si mesmo.", "erro")
    else:
        user.active = not user.active
        db.commit()
        flash(f"Acesso de {user.name} {'liberado' if user.active else 'bloqueado'}.", "ok")
    return redirect(url_for("gestao.team"))


@bp.get("/financeiro")
@admin_required
def finance():
    db = current_app.db.session
    t = today()
    try:
        year, month = (int(x) for x in request.args.get("mes", f"{t:%Y-%m}").split("-"))
        start = date(year, month, 1)
    except ValueError:
        start = date(t.year, t.month, 1)
    end = date(start.year + (start.month == 12), start.month % 12 + 1, 1)
    payments = db.scalars(select(Payment).where(Payment.paid_on >= start, Payment.paid_on < end)
                          .order_by(Payment.paid_on)).all()
    by_method = {m: sum(p.amount_cents for p in payments if p.method == m) for m in PAY_METHODS}
    month_bookings = db.scalars(select(Booking).where(Booking.check_in >= start, Booking.check_in < end,
                                                      Booking.status != "cancelada")).all()
    open_bookings = [b for b in db.scalars(select(Booking).where(Booking.status != "cancelada")
                                           .order_by(Booking.check_out)) if b.balance_cents > 0]
    nights = sum(b.nights * len(b.pets) for b in month_bookings)
    prev = date(start.year - (start.month == 1), (start.month - 2) % 12 + 1, 1)
    return render_template(
        "financeiro.html", start=start, prev=prev, next=end, payments=payments, by_method=by_method,
        received=sum(by_method.values()), billed=sum(b.total_cents for b in month_bookings),
        nights=nights, bookings_count=len(month_bookings), open_bookings=open_bookings,
        open_total=sum(b.balance_cents for b in open_bookings),
        ticket=(sum(b.total_cents for b in month_bookings) // len(month_bookings)) if month_bookings else 0)
