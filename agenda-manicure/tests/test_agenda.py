from datetime import date, datetime

import pytest

from app import agenda
from app.agenda import agenda_cfg, fmt_hm, free_slots, public_services, service_price, whatsapp_digits
from app.security import RateLimiter
from tests.test_app import app, client, csrf, hotmart, login, password_from  # noqa: F401

H = {"X-Requested-With": "fetch"}
JPEG = b"\xff\xd8\xff\xe0" + b"0" * 200
NOW = datetime(2026, 11, 10, 8, 0)  # terça-feira, 08:00

WEEK = [{"on": False, "start": "09:00", "end": "18:00"}] + \
       [{"on": True, "start": "09:00", "end": "18:00"} for _ in range(5)] + [{"on": True, "start": "09:00", "end": "14:00"}]
STATE = {
    "v": 1,
    "settings": {"business": "Unhas da Ana", "margin": 40, "fee": 4, "extras": 10, "hourly": 20, "round": 1},
    "ingredients": [{"id": "es", "name": "Esmalte", "price": 7.9, "qty": 8, "unit": "ml"}],
    "products": [
        {"id": "m1", "name": "Mão", "yield": 1, "minutes": 45, "margin": None, "current": 0,
         "items": [{"ingId": "es", "qty": 0.6}], "menu": {"show": True, "desc": "Cutilagem e esmaltação", "photo": None}},
        {"id": "p1", "name": "Pé", "yield": 1, "minutes": 50, "current": 35, "items": [], "menu": {"show": True}},
        {"id": "x1", "name": "Escondido", "yield": 1, "minutes": 30, "current": 20, "items": [], "menu": {"show": False}},
    ],
    "agenda": {"whatsapp": "(11) 99999-8888", "intro": "Bem-vinda!", "address": "Rua A, 1", "week": WEEK,
               "lunch": {"on": True, "start": "12:00", "end": "13:00"}, "step": 30, "notice": 2, "daysAhead": 30,
               "autoConfirm": False, "notifyEmail": True},
}


@pytest.fixture(autouse=True)
def fixed_clock(monkeypatch):
    monkeypatch.setattr(agenda, "local_now", lambda: NOW)
    monkeypatch.setattr(agenda, "booking_limiter", RateLimiter(1000, 3600))


def _customer(app, client, email="ana@cliente.com", txn="HP123"):
    hotmart(client, "PURCHASE_APPROVED", email=email, txn=txn)
    login(client, email, password_from(app.config["MAIL_OUTBOX"]))
    assert client.put("/api/dados", json=STATE, headers=H).status_code == 200
    assert client.put("/api/agenda/link", json={"slug": "unhas-da-ana" if txn == "HP123" else "outra"}, headers=H).status_code == 200


def _book(c, day="2026-11-11", hora="10:00", servicos=("m1",), telefone="(12) 98888-7777", nome="Bruna Costa"):
    return c.post("/api/publico/unhas-da-ana/agendar", headers=H,
                  json={"servicos": list(servicos), "dia": day, "hora": hora, "nome": nome, "telefone": telefone})


# ---------- regras puras ----------
def test_price_matches_calculator():
    # 0,6 ml de esmalte (R$ 0,5925) + 10% + 45 min a R$ 20/h = 15,65 / (1 - 40% - 4%) = 27,95 -> R$ 28
    assert service_price(STATE, STATE["products"][0]) == 28.0
    assert service_price(STATE, STATE["products"][1]) == 35.0


def test_public_services_hide_unchecked():
    services = public_services(STATE)
    assert [s["name"] for s in services] == ["Mão", "Pé"]
    assert services[0]["minutes"] == 45 and services[0]["price"] == 28.0
    assert whatsapp_digits("(11) 99999-8888") == "5511999998888" and whatsapp_digits("123") == ""


def test_free_slots_respect_notice_lunch_and_busy():
    cfg = agenda_cfg(STATE)
    slots = [fmt_hm(m) for m in free_slots(cfg, date(2026, 11, 10), 45, [(14 * 60, 15 * 60 + 30)], NOW)]
    assert slots == ["10:00", "10:30", "11:00", "13:00", "15:30", "16:00", "16:30", "17:00"]
    assert free_slots(cfg, date(2026, 11, 15), 45, [], NOW) == []            # domingo: folga
    assert free_slots(cfg, date(2026, 11, 9), 45, [], NOW) == []             # ontem
    assert free_slots(cfg, date(2026, 12, 30), 45, [], NOW) == []            # além dos 30 dias
    assert fmt_hm(free_slots(cfg, date(2026, 11, 14), 45, [], NOW)[-1]) == "13:00"  # sábado até 14h


def test_default_config_is_safe():
    cfg = agenda_cfg({})
    assert cfg["days"][0] is None and cfg["days"][1] == (540, 1080)
    assert cfg["step"] == 30 and cfg["notice"] == 2 and not cfg["auto_confirm"]
    bad = agenda_cfg({"agenda": {"step": 1, "daysAhead": 9999, "week": [{"on": True, "start": "18:00", "end": "09:00"}] * 7}})
    assert bad["step"] == 10 and bad["days_ahead"] == 90 and bad["days"] == [None] * 7


# ---------- página pública e agendamento ----------
def test_public_booking_flow(app, client):
    _customer(app, client)
    public = app.test_client()
    page = public.get("/a/unhas-da-ana")
    html = page.get_data(as_text=True)
    assert page.status_code == 200
    assert "Unhas da Ana" in html and "Mão" in html and "Escondido" not in html and "Rua A, 1" in html

    slots = public.get("/api/publico/unhas-da-ana/horarios?dia=2026-11-11&servicos=m1,p1").json
    assert slots["duration"] == 95 and slots["slots"][0] == "09:00"
    assert public.get("/api/publico/unhas-da-ana/horarios?dia=2026-11-11&servicos=x1").status_code == 400

    r = _book(public, servicos=("m1", "p1"))
    assert r.status_code == 201
    item = r.json["item"]
    assert item["status"] == "pendente" and item["end"] == "11:35" and item["price"] == 63.0
    assert item["services"] == "Mão + Pé" and item["whatsapp"] == "5511999998888"
    mail = app.config["MAIL_OUTBOX"][-1]
    assert mail["to"] == "ana@cliente.com" and "Bruna Costa" in mail["text"] and "R$ 63,00" in mail["text"]

    after = public.get("/api/publico/unhas-da-ana/horarios?dia=2026-11-11&servicos=m1").json["slots"]
    assert "09:00" in after and "09:30" not in after and "10:00" not in after and "11:00" not in after and "11:30" not in after
    assert "13:00" in after
    taken = _book(public, hora="10:30", telefone="(12) 97777-0000")
    assert taken.status_code == 409 and taken.json["taken"]

    listed = client.get("/api/agendamentos?de=2026-11-10&ate=2026-11-20").json["items"]
    assert len(listed) == 1 and listed[0]["source"] == "online" and listed[0]["wa"] == "5512988887777"


def test_booking_validation(app, client):
    _customer(app, client)
    public = app.test_client()
    assert _book(public, servicos=("x1",)).status_code == 400                 # serviço escondido
    assert _book(public, telefone="123").status_code == 400
    assert _book(public, nome="").status_code == 400
    assert _book(public, day="2026-11-15").status_code == 409                 # domingo
    assert _book(public, day="2026-11-10", hora="09:00").status_code == 409   # sem antecedência
    assert _book(public, hora="09:10").status_code == 409                     # fora da grade
    no_header = public.post("/api/publico/unhas-da-ana/agendar", json={})
    assert no_header.status_code == 403


def test_limit_per_phone_and_auto_confirm(app, client):
    state = {**STATE, "agenda": {**STATE["agenda"], "autoConfirm": True, "notifyEmail": False}}
    _customer(app, client)
    client.put("/api/dados", json=state, headers=H)
    public = app.test_client()
    sent = len(app.config["MAIL_OUTBOX"])
    for hora in ("09:00", "10:00", "11:00"):
        r = _book(public, hora=hora)
        assert r.status_code == 201 and r.json["item"]["status"] == "confirmado"
    assert _book(public, hora="14:00").status_code == 409
    assert _book(public, hora="14:00", telefone="(12) 91111-2222").status_code == 201
    assert len(app.config["MAIL_OUTBOX"]) == sent


def test_owner_manages_appointments(app, client):
    _customer(app, client)
    body = {"day": "2026-11-12", "time": "09:00", "duration": 60, "client_name": "Lia", "client_phone": "11 98888-0000",
            "services": "Pé e mão", "price": "60,00"}
    a = client.post("/api/agendamentos", json=body, headers=H)
    assert a.status_code == 201 and a.json["item"]["price"] == 60.0 and a.json["item"]["status"] == "confirmado"
    clash = client.post("/api/agendamentos", json={**body, "time": "09:30"}, headers=H)
    assert clash.status_code == 409 and clash.json["conflict"]
    assert client.post("/api/agendamentos", json={**body, "time": "09:30", "force": True}, headers=H).status_code == 201
    block = client.post("/api/agendamentos", json={"day": "2026-11-12", "time": "15:00", "duration": 120,
                                                   "status": "bloqueio", "client_name": "x", "note": "Médico"}, headers=H)
    assert block.status_code == 201 and block.json["item"]["client_name"] == ""
    assert client.post("/api/agendamentos", json={**body, "time": "25:00"}, headers=H).status_code == 400

    # o bloqueio some do link
    slots = app.test_client().get("/api/publico/unhas-da-ana/horarios?dia=2026-11-12&servicos=m1").json["slots"]
    assert "15:00" not in slots and "16:00" not in slots and "17:00" in slots and "09:00" not in slots

    aid = a.json["item"]["id"]
    assert client.patch(f"/api/agendamentos/{aid}", json={"status": "cancelado"}, headers=H).json["item"]["status"] == "cancelado"
    # reabrir conflita com o encaixe das 09:30
    assert client.patch(f"/api/agendamentos/{aid}", json={"status": "confirmado"}, headers=H).status_code == 409
    assert client.patch(f"/api/agendamentos/{aid}", json={"status": "confirmado", "time": "13:00"}, headers=H).status_code == 200
    assert client.patch(f"/api/agendamentos/{aid}", json={"status": "concluido"}, headers=H).status_code == 200
    assert client.get("/api/agendamentos?de=2026-11-01&ate=2027-02-01").status_code == 400
    items = client.get("/api/agendamentos?de=2026-11-12&ate=2026-11-12").json["items"]
    assert [i["time"] for i in items] == ["09:30", "13:00", "15:00"]
    assert client.delete(f"/api/agendamentos/{aid}", headers=H).json["ok"]


def test_appointments_are_private(app, client):
    _customer(app, client)
    aid = client.post("/api/agendamentos", json={"day": "2026-11-12", "time": "09:00", "duration": 60,
                                                 "client_name": "Lia"}, headers=H).json["item"]["id"]
    other = app.test_client()
    _customer(app, other, email="outra@x.com", txn="T2")
    assert other.patch(f"/api/agendamentos/{aid}", json={"status": "cancelado"}, headers=H).status_code == 404
    assert other.delete(f"/api/agendamentos/{aid}", headers=H).status_code == 404
    assert other.get("/api/agendamentos?de=2026-11-01&ate=2026-11-30").json["items"] == []
    assert app.test_client().get("/api/agendamentos?de=2026-11-01&ate=2026-11-30").status_code == 401


def test_link_rules_and_blocked_customer(app, client):
    _customer(app, client)
    assert client.put("/api/agenda/link", json={"slug": "Admin"}, headers=H).status_code == 400
    assert client.put("/api/agenda/link", json={"slug": "a b"}, headers=H).status_code == 400
    assert client.get("/api/agenda/link").json["url"] == "https://precifica.test/a/unhas-da-ana"
    other = app.test_client()
    hotmart(client, "PURCHASE_APPROVED", email="outra@x.com", txn="T2")
    login(other, "outra@x.com", password_from(app.config["MAIL_OUTBOX"]))
    assert other.put("/api/agenda/link", json={"slug": "unhas-da-ana"}, headers=H).status_code == 409
    hotmart(client, "PURCHASE_REFUNDED")
    assert app.test_client().get("/a/unhas-da-ana").status_code == 404
    assert app.test_client().get("/api/publico/unhas-da-ana/horarios?dia=2026-11-11&servicos=m1").status_code == 404
    assert app.test_client().get("/a/nao-existe").status_code == 404


def test_photo_upload_and_owner(app, client):
    _customer(app, client)
    photo = client.post("/api/fotos", data=JPEG, headers=H, content_type="image/jpeg").json
    assert client.post("/api/fotos", data=b"<svg>", headers=H, content_type="image/svg+xml").status_code == 400
    assert client.get(photo["url"]).data == JPEG
    other = app.test_client()
    _customer(app, other, email="outra@x.com", txn="T2")
    other.delete(f"/api/fotos/{photo['id']}", headers=H)
    assert client.get(photo["url"]).status_code == 200
    assert client.get("/f/ex-brigadeiro").status_code == 404


def test_demo_and_app_pages(app, client):
    html = client.get("/demo").get_data(as_text=True)
    assert "Agenda" in html and "Materiais" in html and '"mode": "demo"' in html
