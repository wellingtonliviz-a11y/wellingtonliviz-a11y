"""Painel do dia e mapa de ocupação."""
from datetime import timedelta

from flask import Blueprint, current_app, render_template, request
from sqlalchemy import select

from .models import ACTIVE_STATUS, Booking, Room
from .security import login_required
from .util import parse_date, today

bp = Blueprint("painel", __name__)


@bp.get("/")
@login_required
def home():
    db = current_app.db.session
    t = today()
    active = list(db.scalars(select(Booking).where(Booking.status.in_(ACTIVE_STATUS)).order_by(Booking.check_in)))
    arrivals = [b for b in active if b.status == "reservada" and b.check_in <= t]
    departures = [b for b in active if b.status == "hospedado" and b.check_out <= t]
    hosted = [b for b in active if b.status == "hospedado"]
    upcoming = [b for b in active if b.status == "reservada" and t < b.check_in <= t + timedelta(days=7)]
    rooms = db.scalars(select(Room).where(Room.active.is_(True))).all()
    occupied_today = {b.room_id for b in active if b.check_in <= t < b.check_out or b.status == "hospedado"}
    vaccine_alerts, seen = [], set()
    for b in active:  # já em ordem de entrada: cada pet aparece uma vez, na próxima hospedagem
        if b.check_in <= t + timedelta(days=15):
            for p in b.pets:
                issues = p.vaccine_issues(b.check_out)
                if issues and p.id not in seen:
                    seen.add(p.id)
                    vaccine_alerts.append((b, p, issues))
    stats = {
        "pets": sum(len(b.pets) for b in hosted),
        "occupied": len(occupied_today),
        "rooms": len(rooms),
        "rate": round(100 * len(occupied_today) / len(rooms)) if rooms else 0,
        "to_receive": sum(max(b.balance_cents, 0) for b in active),
    }
    return render_template("painel.html", arrivals=arrivals, departures=departures, hosted=hosted,
                           upcoming=upcoming, stats=stats, vaccine_alerts=vaccine_alerts)


@bp.get("/ocupacao")
@login_required
def occupancy():
    db = current_app.db.session
    start = parse_date(request.args.get("inicio")) or today()
    days = [start + timedelta(days=i) for i in range(14)]
    end = days[-1] + timedelta(days=1)
    rooms = db.scalars(select(Room).where(Room.active.is_(True)).order_by(Room.species, Room.name)).all()
    bookings = db.scalars(select(Booking).where(Booking.status.in_(ACTIVE_STATUS),
                                                Booking.check_in < end, Booking.check_out > start)).all()
    grid = {r.id: [None] * len(days) for r in rooms}
    for b in bookings:
        if b.room_id not in grid:
            continue
        for i, d in enumerate(days):
            if b.check_in <= d < b.check_out:
                grid[b.room_id][i] = b
    free_per_day = [sum(1 for r in rooms if grid[r.id][i] is None) for i in range(len(days))]
    return render_template("ocupacao.html", rooms=rooms, days=days, grid=grid, start=start,
                           prev=start - timedelta(days=14), next=start + timedelta(days=14),
                           free_per_day=free_per_day, one_day=timedelta(days=1))
