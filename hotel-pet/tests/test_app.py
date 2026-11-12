import re
from datetime import timedelta

import pytest

from app import create_app
from app.demo import DEMO_EMAIL, DEMO_PASSWORD
from app.models import Booking, Pet, Room, Tutor, Vaccine
from app.security import login_limiter
from app.util import money, parse_money, wa_link

ADMIN, PASSWORD = "dono@hotel.com", "admin123"


@pytest.fixture
def app(tmp_path):
    login_limiter.reset()
    return create_app({"TESTING": True, "SECRET_KEY": "teste", "DATABASE_URL": f"sqlite:///{tmp_path / 't.db'}",
                       "ADMIN_EMAIL": ADMIN, "ADMIN_INITIAL_PASSWORD": PASSWORD, "DEMO_DATA": False})


@pytest.fixture
def client(app):
    return app.test_client()


def token(client, path="/entrar"):
    return re.search(r'name="csrf_token" value="([^"]+)"', client.get(path).get_data(as_text=True)).group(1)


def login(client, email=ADMIN, password=PASSWORD):
    return client.post("/entrar", data={"email": email, "password": password, "csrf_token": token(client)})


def post(client, path, data):
    data = dict(data, csrf_token=token(client, "/minha-senha"))
    return client.post(path, data=data)


@pytest.fixture
def logged(client):
    login(client)
    return client


@pytest.fixture
def setup(app):
    """Uma baia para cão P, um gatil e um tutor com cão e gato vacinados."""
    with app.app_context():
        from app.util import today
        t = today()
    db = app.db.session
    baia = Room(name="Baia P1", species="cao", max_size="P", capacity=2, daily_rate_cents=7000)
    gatil = Room(name="Gatil 1", species="gato", capacity=1, daily_rate_cents=5000)
    tutor = Tutor(name="Ana Souza", phone="(12) 99123-4567")
    rex = Pet(tutor=tutor, name="Rex", species="cao", size="P")
    big = Pet(tutor=tutor, name="Bidu", species="cao", size="G")
    mia = Pet(tutor=tutor, name="Mia", species="gato")
    for p in (rex, big, mia):
        p.vaccines.append(Vaccine(name="V10", valid_until=t + timedelta(days=200)))
    db.add_all([baia, gatil, tutor])
    db.commit()
    ids = dict(baia=baia.id, gatil=gatil.id, tutor=tutor.id, rex=rex.id, big=big.id, mia=mia.id, today=t)
    db.remove()
    return ids


def test_money_helpers():
    assert parse_money("1.234,56") == 123456
    assert parse_money("80") == 8000
    assert parse_money("R$ 70,5") == 7050
    assert parse_money("1.000") == 100000
    assert parse_money("abc") is None and parse_money("") is None
    assert money(123456) == "R$ 1.234,56"
    assert wa_link("(12) 99123-4567", "oi").startswith("https://wa.me/5512991234567?text=oi")


def test_login_required_and_csrf(client):
    assert client.get("/").status_code == 302
    assert client.post("/entrar", data={"email": ADMIN, "password": PASSWORD}).status_code == 400
    assert login(client, password="errada").status_code == 200
    assert login(client).status_code == 302
    assert client.get("/").status_code == 200


def test_pages_render(logged, setup):
    for path in ["/", "/ocupacao", "/reservas", "/reservas?status=todas", "/tutores", "/tutores?q=rex",
                 f"/tutores/{setup['tutor']}", f"/pets/{setup['rex']}", "/reservas/nova",
                 f"/reservas/nova?tutor={setup['tutor']}&check_in=2030-01-01&check_out=2030-01-03",
                 "/acomodacoes", "/acomodacoes/nova", "/equipe", "/financeiro", "/financeiro?mes=2030-12",
                 "/minha-senha", "/tutores/novo", f"/pets/novo?tutor={setup['tutor']}"]:
        assert logged.get(path).status_code == 200, path
    assert logged.get("/pets/novo").status_code == 404


def test_full_stay(logged, app, setup):
    t = setup["today"]
    r = post(logged, "/reservas/nova", {"tutor": setup["tutor"], "pets": [setup["rex"]], "room": setup["baia"],
                                        "check_in": t.isoformat(), "check_out": (t + timedelta(days=3)).isoformat()})
    assert r.status_code == 302
    bid = int(r.headers["Location"].rsplit("/", 1)[1])
    page = logged.get(f"/reservas/{bid}").get_data(as_text=True)
    assert "R$ 210,00" in page and "wa.me/5512991234567" in page

    post(logged, f"/reservas/{bid}/extras", {"description": "Banho", "price": "60,00"})
    post(logged, f"/reservas/{bid}/check-in", {"belongings": "caminha"})
    post(logged, f"/reservas/{bid}/diario", {"kind": "alimentacao", "text": "Comeu tudo"})
    # saída bloqueada com saldo em aberto
    post(logged, f"/reservas/{bid}/check-out", {})
    b = app.db.session.get(Booking, bid)
    assert b.status == "hospedado" and b.total_cents == 27000 and b.belongings == "caminha"
    post(logged, f"/reservas/{bid}/pagamentos", {"amount": "270,00", "method": "pix", "paid_on": t.isoformat()})
    post(logged, f"/reservas/{bid}/check-out", {})
    app.db.session.expire_all()
    b = app.db.session.get(Booking, bid)
    assert b.status == "finalizada" and b.balance_cents == 0
    assert "R$ 270,00" in logged.get("/financeiro").get_data(as_text=True)
    assert logged.get(f"/reservas/{bid}/comprovante").status_code == 200


def test_booking_rules(logged, app, setup):
    t = setup["today"]
    base = {"tutor": setup["tutor"], "room": setup["baia"], "check_in": t.isoformat(),
            "check_out": (t + timedelta(days=2)).isoformat()}

    def count():
        app.db.session.expire_all()
        return len(app.db.session.query(Booking).all())

    post(logged, "/reservas/nova", dict(base, pets=[setup["mia"]]))  # gato na baia de cão
    post(logged, "/reservas/nova", dict(base, pets=[setup["big"]]))  # porte G em baia P
    post(logged, "/reservas/nova", dict(base, pets=[setup["rex"]], check_out=t.isoformat()))  # zero diárias
    assert count() == 0
    post(logged, "/reservas/nova", dict(base, pets=[setup["rex"]]))
    assert count() == 1
    # mesma baia, datas cruzando: recusada; começando no dia da saída: aceita
    post(logged, "/reservas/nova", dict(base, pets=[setup["rex"]], check_in=(t + timedelta(days=1)).isoformat(),
                                        check_out=(t + timedelta(days=4)).isoformat()))
    assert count() == 1
    post(logged, "/reservas/nova", dict(base, pets=[setup["rex"]], check_in=(t + timedelta(days=2)).isoformat(),
                                        check_out=(t + timedelta(days=4)).isoformat()))
    assert count() == 2


def test_vaccine_blocks_check_in(logged, app, setup):
    t = setup["today"]
    db = app.db.session
    db.query(Vaccine).filter_by(pet_id=setup["mia"]).update({"valid_until": t - timedelta(days=1)})
    db.commit()
    r = post(logged, "/reservas/nova", {"tutor": setup["tutor"], "pets": [setup["mia"]], "room": setup["gatil"],
                                        "check_in": t.isoformat(), "check_out": (t + timedelta(days=1)).isoformat()})
    bid = int(r.headers["Location"].rsplit("/", 1)[1])
    assert "Vacinas para conferir" in logged.get("/").get_data(as_text=True)
    post(logged, f"/reservas/{bid}/check-in", {})
    db.expire_all()
    assert db.get(Booking, bid).status == "reservada"
    post(logged, f"/reservas/{bid}/check-in", {"vacinas_ok": "1"})
    db.expire_all()
    assert db.get(Booking, bid).status == "hospedado"


def test_cancel_frees_room(logged, app, setup):
    t = setup["today"]
    data = {"tutor": setup["tutor"], "pets": [setup["mia"]], "room": setup["gatil"],
            "check_in": t.isoformat(), "check_out": (t + timedelta(days=2)).isoformat()}
    bid = int(post(logged, "/reservas/nova", data).headers["Location"].rsplit("/", 1)[1])
    post(logged, f"/reservas/{bid}/cancelar", {})
    assert post(logged, "/reservas/nova", data).status_code == 302


def test_staff_cannot_see_admin_pages(logged, app):
    post(logged, "/equipe", {"name": "Joana", "email": "joana@hotel.com", "password": "123456"})
    other = app.test_client()
    login(other, "joana@hotel.com", "123456")
    assert other.get("/").status_code == 200
    assert other.get("/financeiro").status_code == 403


def test_create_tutor_pet_vaccine(logged, app):
    r = post(logged, "/tutores/novo", {"name": "Carlos", "phone": "12 98888-7777"})
    assert "/pets/novo" in r.headers["Location"]
    tid = app.db.session.query(Tutor).filter_by(name="Carlos").one().id
    r = post(logged, f"/pets/novo?tutor={tid}", {"name": "Toby", "species": "cao", "size": "M"})
    pid = int(r.headers["Location"].rsplit("/", 1)[1])
    post(logged, f"/pets/{pid}/vacinas", {"name": "V10", "valid_until": "2099-01-01"})
    assert "V10" in logged.get(f"/pets/{pid}").get_data(as_text=True)


def test_demo_seed(tmp_path):
    app = create_app({"TESTING": True, "SECRET_KEY": "x", "DATABASE_URL": f"sqlite:///{tmp_path / 'd.db'}",
                      "DEMO_DATA": True, "ADMIN_EMAIL": ""})
    c = app.test_client()
    login(c, DEMO_EMAIL, DEMO_PASSWORD)
    for path in ["/", "/ocupacao", "/reservas", "/financeiro", "/tutores"] + [f"/reservas/{i}" for i in range(1, 8)]:
        assert c.get(path).status_code == 200, path
    assert "Thor" in c.get("/").get_data(as_text=True)
