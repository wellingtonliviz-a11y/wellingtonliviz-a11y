"""Reservas: criar, editar, check-in, check-out, extras, pagamentos, diário e mensagens de WhatsApp."""
from flask import Blueprint, abort, current_app, flash, g, redirect, render_template, request, url_for
from sqlalchemy import select

from .cadastros import _get
from .models import (ACTIVE_STATUS, LOG_KINDS, PAY_METHODS, STATUS, Booking, Extra, LogEntry, Payment, Pet, Room,
                     Tutor, utcnow)
from .rules import booking_errors, overlapping
from .security import login_required
from .util import br_date, local_dt, money, money_input, parse_date, parse_money, today, wa_link

bp = Blueprint("reservas", __name__)
EXTRA_SUGGESTIONS = ("Banho", "Banho e tosa", "Transporte (leva e traz)", "Adaptação (meio período)",
                     "Adestramento", "Medicação extra", "Diária extra (saída após o horário)")


@bp.get("/reservas")
@login_required
def bookings():
    db = current_app.db.session
    status = request.args.get("status", "ativas")
    stmt = select(Booking)
    if status == "ativas":
        stmt = stmt.where(Booking.status.in_(ACTIVE_STATUS)).order_by(Booking.check_in)
    elif status in STATUS:
        stmt = stmt.where(Booking.status == status).order_by(Booking.check_in.desc())
    else:
        stmt = stmt.order_by(Booking.check_in.desc())
    return render_template("reservas.html", bookings=db.scalars(stmt.limit(300)).all(), status=status)


def _rooms_for_form(db, check_in, check_out, exclude_id=None):
    rooms = db.scalars(select(Room).where(Room.active.is_(True)).order_by(Room.species, Room.name)).all()
    if check_in and check_out and check_out > check_in:
        return [(r, not overlapping(db, r.id, check_in, check_out, exclude_id)) for r in rooms]
    return [(r, None) for r in rooms]


@bp.route("/reservas/nova", methods=["GET", "POST"])
@bp.route("/reservas/<int:booking_id>/editar", methods=["GET", "POST"])
@login_required
def booking_form(booking_id=None):
    db = current_app.db.session
    booking = _get(Booking, booking_id) if booking_id else None
    if booking and booking.status not in ACTIVE_STATUS:
        flash("Reservas finalizadas ou canceladas não podem ser alteradas.", "erro")
        return redirect(url_for("reservas.booking", booking_id=booking.id))
    src = request.form if request.method == "POST" else request.args

    tutor_id = src.get("tutor", type=int) or (booking.tutor_id if booking else None)
    tutor = db.get(Tutor, tutor_id) if tutor_id else None
    check_in = parse_date(src.get("check_in")) or (booking.check_in if booking else None)
    check_out = parse_date(src.get("check_out")) or (booking.check_out if booking else None)
    room_id = src.get("room", type=int) or (booking.room_id if booking else None)
    if "pets" in src or request.method == "POST":
        pet_ids = {int(x) for x in src.getlist("pets") if x.isdigit()}
    elif booking:
        pet_ids = {p.id for p in booking.pets}
    else:
        pet_ids = {p.id for p in tutor.pets} if tutor and len(tutor.pets) == 1 else set()
    rate_text = src.get("daily_rate", money_input(booking.daily_rate_cents) if booking else "")
    discount_text = src.get("discount", money_input(booking.discount_cents) if booking else "")
    notes = src.get("notes", booking.notes if booking else "")

    if request.method == "POST":
        room = db.get(Room, room_id) if room_id else None
        pets = [p for p in (db.get(Pet, i) for i in pet_ids) if p]
        errors = booking_errors(db, tutor, room, pets, check_in, check_out, booking.id if booking else None)
        rate = parse_money(rate_text)
        discount = parse_money(discount_text) or 0
        if rate_text.strip() and rate is None:
            errors.append("Valor da diária inválido.")
        if discount_text.strip() and parse_money(discount_text) is None:
            errors.append("Valor do desconto inválido.")
        if not errors:
            if booking is None:
                booking = Booking(status="reservada")
                db.add(booking)
            booking.tutor_id, booking.room_id = tutor.id, room.id
            booking.check_in, booking.check_out = check_in, check_out
            booking.pets = pets
            # campo vazio = diária padrão da acomodação
            booking.daily_rate_cents = room.daily_rate_cents if rate is None else rate
            booking.discount_cents = discount
            booking.notes = notes.strip()
            db.commit()
            flash("Reserva salva.", "ok")
            return redirect(url_for("reservas.booking", booking_id=booking.id))
        for e in errors:
            flash(e, "erro")
        db.rollback()

    tutors = db.scalars(select(Tutor).order_by(Tutor.name)).all()
    return render_template("reserva_form.html", booking=booking, tutors=tutors, tutor=tutor, pet_ids=pet_ids,
                           check_in=check_in, check_out=check_out, room_id=room_id, rate_text=rate_text,
                           discount_text=discount_text, notes=notes,
                           rooms=_rooms_for_form(db, check_in, check_out, booking.id if booking else None))


def _messages(b: Booking) -> dict:
    cfg = current_app.config
    hotel = cfg["HOTEL_NAME"]
    first = b.tutor.name.split()[0] if b.tutor.name else ""
    nights = f"{b.nights} diária{'s' if b.nights > 1 else ''}"
    msgs = {
        "confirmacao": (f"Olá, {first}! 🐾 Confirmamos a hospedagem de {b.pet_names} no {hotel}.\n"
                        f"Entrada: {br_date(b.check_in)}\nSaída: {br_date(b.check_out)} ({nights})\n"
                        f"Valor: {money(b.total_cents)}\n\nPor favor, traga a carteira de vacinação, a ração "
                        f"e os remédios de uso contínuo. Qualquer dúvida, é só chamar!"),
    }
    t = today()
    todays = [e for e in reversed(b.logs) if local_dt(e.created_at).date() == t]
    if todays:
        lines = "\n".join(f"• {local_dt(e.created_at):%H:%M} {LOG_KINDS.get(e.kind, '')}"
                          f"{' (' + e.pet.name + ')' if e.pet and len(b.pets) > 1 else ''}: {e.text}"
                          for e in todays)
        msgs["novidades"] = f"Olá, {first}! Notícias de {b.pet_names} hoje no {hotel} 🐾\n\n{lines}"
    if b.balance_cents > 0:
        msgs["cobranca"] = (f"Olá, {first}! Segue o resumo da hospedagem de {b.pet_names} no {hotel}:\n"
                            f"Total: {money(b.total_cents)}\nPago: {money(b.paid_cents)}\n"
                            f"Falta pagar: {money(b.balance_cents)}")
    return {k: wa_link(b.tutor.phone, v) for k, v in msgs.items()}


@bp.get("/reservas/<int:booking_id>")
@login_required
def booking(booking_id):
    b = _get(Booking, booking_id)
    vaccine_issues = {p.id: p.vaccine_issues(b.check_out) for p in b.pets}
    return render_template("reserva.html", b=b, vaccine_issues=vaccine_issues,
                           has_vaccine_issues=any(vaccine_issues.values()), messages=_messages(b),
                           extra_suggestions=EXTRA_SUGGESTIONS)


@bp.get("/reservas/<int:booking_id>/comprovante")
@login_required
def receipt(booking_id):
    return render_template("comprovante.html", b=_get(Booking, booking_id))


def _back(b: Booking, anchor: str = ""):
    return redirect(url_for("reservas.booking", booking_id=b.id) + anchor)


@bp.post("/reservas/<int:booking_id>/check-in")
@login_required
def check_in(booking_id):
    db = current_app.db.session
    b = _get(Booking, booking_id)
    if b.status != "reservada":
        flash("Esta reserva não está aguardando entrada.", "erro")
        return _back(b)
    if any(p.vaccine_issues(b.check_out) for p in b.pets) and request.form.get("vacinas_ok") != "1":
        flash("Há vacinas vencidas ou não cadastradas. Confira a carteira e marque a confirmação.", "erro")
        return _back(b, "#entrada")
    b.status, b.checked_in_at = "hospedado", utcnow()
    b.belongings = request.form.get("belongings", "").strip()[:300]
    db.add(LogEntry(booking_id=b.id, kind="observacao", user_name=g.user.name,
                    text="Entrada realizada." + (f" Pertences: {b.belongings}." if b.belongings else "")))
    db.commit()
    flash(f"Entrada de {b.pet_names} registrada. Boa hospedagem! 🐾", "ok")
    return _back(b)


@bp.post("/reservas/<int:booking_id>/check-out")
@login_required
def check_out(booking_id):
    db = current_app.db.session
    b = _get(Booking, booking_id)
    if b.status != "hospedado":
        flash("Só dá para dar saída em um pet hospedado.", "erro")
        return _back(b)
    if b.balance_cents > 0 and request.form.get("saldo_ok") != "1":
        flash(f"Ainda faltam {money(b.balance_cents)}. Registre o pagamento ou confirme a saída com saldo.", "erro")
        return _back(b, "#saida")
    b.status, b.checked_out_at = "finalizada", utcnow()
    db.add(LogEntry(booking_id=b.id, kind="observacao", user_name=g.user.name, text="Saída realizada."))
    db.commit()
    flash(f"Saída de {b.pet_names} registrada.", "ok")
    return _back(b)


@bp.post("/reservas/<int:booking_id>/cancelar")
@login_required
def cancel(booking_id):
    db = current_app.db.session
    b = _get(Booking, booking_id)
    if b.status != "reservada":
        flash("Só reservas que ainda não deram entrada podem ser canceladas.", "erro")
    else:
        b.status = "cancelada"
        db.commit()
        flash("Reserva cancelada. A acomodação ficou livre.", "ok")
    return _back(b)


@bp.post("/reservas/<int:booking_id>/extras")
@login_required
def extra_add(booking_id):
    db = current_app.db.session
    b = _get(Booking, booking_id)
    desc = request.form.get("description", "").strip()[:120]
    price = parse_money(request.form.get("price"))
    if b.status == "cancelada":
        flash("Reserva cancelada.", "erro")
    elif not desc or price is None:
        flash("Informe o serviço e o valor.", "erro")
    else:
        db.add(Extra(booking_id=b.id, description=desc, price_cents=price))
        db.commit()
        flash(f"{desc} adicionado.", "ok")
    return _back(b, "#valores")


@bp.post("/extras/<int:extra_id>/excluir")
@login_required
def extra_delete(extra_id):
    db = current_app.db.session
    e = _get(Extra, extra_id)
    b = db.get(Booking, e.booking_id)
    db.delete(e)
    db.commit()
    flash("Serviço removido.", "ok")
    return _back(b, "#valores")


@bp.post("/reservas/<int:booking_id>/pagamentos")
@login_required
def payment_add(booking_id):
    db = current_app.db.session
    b = _get(Booking, booking_id)
    amount = parse_money(request.form.get("amount"))
    method = request.form.get("method", "")
    if not amount or method not in PAY_METHODS:
        flash("Informe o valor e a forma de pagamento.", "erro")
    else:
        db.add(Payment(booking_id=b.id, amount_cents=amount, method=method,
                       paid_on=parse_date(request.form.get("paid_on")) or today(),
                       note=request.form.get("note", "").strip()[:120]))
        db.commit()
        flash(f"Pagamento de {money(amount)} registrado.", "ok")
    return _back(b, "#valores")


@bp.post("/pagamentos/<int:payment_id>/excluir")
@login_required
def payment_delete(payment_id):
    db = current_app.db.session
    p = _get(Payment, payment_id)
    b = db.get(Booking, p.booking_id)
    db.delete(p)
    db.commit()
    flash("Pagamento removido.", "ok")
    return _back(b, "#valores")


@bp.post("/reservas/<int:booking_id>/diario")
@login_required
def log_add(booking_id):
    db = current_app.db.session
    b = _get(Booking, booking_id)
    kind = request.form.get("kind", "")
    text = request.form.get("text", "").strip()[:500]
    pet_id = request.form.get("pet", type=int)
    if kind not in LOG_KINDS or not text:
        flash("Escolha o tipo e escreva o que aconteceu.", "erro")
    elif pet_id and pet_id not in {p.id for p in b.pets}:
        abort(400)
    else:
        db.add(LogEntry(booking_id=b.id, pet_id=pet_id, kind=kind, text=text, user_name=g.user.name))
        db.commit()
        flash("Registro adicionado ao diário.", "ok")
    return _back(b, "#diario")
