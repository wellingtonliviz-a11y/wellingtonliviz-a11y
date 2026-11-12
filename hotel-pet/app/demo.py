"""Dados de exemplo para apresentar o sistema ao cliente."""
from datetime import datetime, time, timedelta, timezone

from sqlalchemy import select

from .access import hash_password
from .models import Booking, Extra, LogEntry, Payment, Pet, Room, Tutor, User, Vaccine, utcnow
from .util import today, tz

DEMO_EMAIL, DEMO_PASSWORD = "demo@hotelpet.com", "demo123"


def seed(db) -> str:
    if db.scalar(select(Room).limit(1)) is not None:
        return "O banco já tem dados; nada foi criado."
    t = today()
    d = lambda n: t + timedelta(days=n)  # noqa: E731

    if db.scalar(select(User).where(User.email == DEMO_EMAIL)) is None:
        db.add(User(email=DEMO_EMAIL, name="Equipe Demo", password_hash=hash_password(DEMO_PASSWORD), is_admin=True))

    rooms = [Room(name=f"Baia P{i}", species="cao", max_size="P", capacity=2, daily_rate_cents=7000,
                  description="Para cães pequenos, com caminha e área coberta") for i in (1, 2, 3)]
    rooms += [Room(name=f"Baia M{i}", species="cao", max_size="M", capacity=2, daily_rate_cents=8500,
                   description="Cães até porte médio") for i in (1, 2)]
    rooms += [Room(name="Suíte G1", species="cao", max_size="G", capacity=3, daily_rate_cents=11000,
                   description="Espaçosa, com solário — cabe a família inteira"),
              Room(name="Gatil 1", species="gato", capacity=2, daily_rate_cents=6000,
                   description="Ambiente só de gatos, com prateleiras e arranhador"),
              Room(name="Gatil 2", species="gato", capacity=3, daily_rate_cents=6000,
                   description="Ambiente só de gatos, com janela telada")]
    db.add_all(rooms)
    r = {x.name: x for x in rooms}

    def tutor(name, phone, **kw):
        obj = Tutor(name=name, phone=phone, **kw)
        db.add(obj)
        return obj

    ana = tutor("Ana Paula Souza", "(12) 99123-4567", email="ana@exemplo.com",
                emergency_contact="Marcos (marido) (12) 99876-1111")
    carlos = tutor("Carlos Henrique Lima", "(12) 98111-2233")
    bea = tutor("Beatriz Martins", "(12) 99777-8899", notes="Prefere receber fotos à tarde.")
    joao = tutor("João Pedro Alves", "(11) 97654-3210")

    def pet(owner, name, species, vaccines, **kw):
        obj = Pet(tutor=owner, name=name, species=species, **kw)
        for vname, valid in vaccines:
            obj.vaccines.append(Vaccine(name=vname, valid_until=valid, applied_on=valid - timedelta(days=365)))
        db.add(obj)
        return obj

    thor = pet(ana, "Thor", "cao", [("V10", d(200)), ("Antirrábica", d(120)), ("Gripe", d(90))],
               breed="Golden Retriever", size="G", sex="M", weight_kg="32", neutered=True,
               food="Premier Golden 350 g, 2x ao dia (8h e 18h)", behavior="Muito sociável, adora bolinha")
    luna = pet(ana, "Luna", "cao", [("V10", d(150)), ("Antirrábica", d(150))],
               breed="Shih Tzu", size="P", sex="F", weight_kg="6", food="Ração úmida 1 sachê às 12h",
               allergies="Frango")
    mel = pet(carlos, "Mel", "cao", [("V10", d(3)), ("Antirrábica", d(-10))],
              breed="SRD", size="M", sex="F", weight_kg="14", medications="Apoquel 1/2 comprimido às 8h",
              behavior="Medrosa com barulho; não dividir espaço com machos")
    mingau = pet(bea, "Mingau", "gato", [("V4", d(300)), ("Antirrábica", d(300))],
                 breed="Persa", sex="M", neutered=True, food="Golden Gatos castrados, à vontade")
    nina = pet(bea, "Nina", "gato", [("V4", d(240)), ("Antirrábica", d(240))], breed="SRD", sex="F",
               neutered=True)
    bob = pet(joao, "Bob", "cao", [], breed="Bulldog Francês", size="P", sex="M", weight_kg="11",
              notes="Braquicefálico: evitar passeios no calor")
    db.flush()

    def booking(owner, room, pets, ci, co, status, paid=0, method="pix", extras=()):
        b = Booking(tutor=owner, room=room, pets=pets, check_in=ci, check_out=co, status=status,
                    daily_rate_cents=room.daily_rate_cents)
        if status in ("hospedado", "finalizada"):
            b.checked_in_at = datetime.combine(ci, time(9, 30), tz()).astimezone(timezone.utc)
        if status == "finalizada":
            b.checked_out_at = datetime.combine(co, time(17, 0), tz()).astimezone(timezone.utc)
        for desc, price in extras:
            b.extras.append(Extra(description=desc, price_cents=price))
        if paid:
            b.payments.append(Payment(amount_cents=paid, method=method, paid_on=min(ci, t)))
        db.add(b)
        return b

    stay = booking(ana, r["Suíte G1"], [thor, luna], d(-2), d(3), "hospedado", paid=50000,
                   extras=[("Banho", 6000)])
    booking(bea, r["Gatil 2"], [mingau, nina], d(-1), d(0), "hospedado", paid=12000, method="credito")
    booking(carlos, r["Baia M1"], [mel], d(0), d(4), "reservada")
    booking(joao, r["Baia P1"], [bob], d(2), d(6), "reservada", paid=14000)
    booking(bea, r["Gatil 1"], [mingau], d(-30), d(-25), "finalizada", paid=30000, method="dinheiro")
    booking(ana, r["Baia P2"], [luna], d(-15), d(-12), "finalizada", paid=21000)
    booking(carlos, r["Baia M2"], [mel], d(10), d(12), "reservada")

    now = utcnow()
    for hours, kind, text, p in [(5, "alimentacao", "Comeu toda a ração da manhã", thor),
                                 (5, "alimentacao", "Comeu metade, ficou com o resto para depois", luna),
                                 (3, "passeio", "Recreação no solário com outros cães, 40 min", thor),
                                 (1, "banho", "Banho tomado, ficou cheirosa!", luna)]:
        stay.logs.append(LogEntry(pet=p, kind=kind, text=text, user_name="Equipe Demo",
                                  created_at=now - timedelta(hours=hours)))
    db.commit()
    return f"Dados de exemplo criados. Entre com {DEMO_EMAIL} / {DEMO_PASSWORD}."
