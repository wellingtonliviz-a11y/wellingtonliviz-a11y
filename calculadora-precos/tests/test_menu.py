import re

from app.menu import product_price, public_menu, whatsapp_digits
from tests.test_app import app, client, csrf, hotmart, login, password_from  # noqa: F401

H = {"X-Requested-With": "fetch"}
JPEG = b"\xff\xd8\xff\xe0" + b"0" * 200

# mesmo exemplo de brigadeiro da calculadora (app.js)
STATE = {
    "v": 1,
    "settings": {"business": "Doces da Ana", "margin": 40, "fee": 4, "extras": 10, "hourly": 15, "round": 0.5},
    "ingredients": [
        {"id": "lc", "name": "Leite condensado", "price": 6.49, "qty": 395, "unit": "g"},
        {"id": "ch", "name": "Chocolate", "price": 9.9, "qty": 200, "unit": "g"},
        {"id": "mt", "name": "Manteiga", "price": 11.9, "qty": 200, "unit": "g"},
        {"id": "gr", "name": "Granulado", "price": 7.5, "qty": 500, "unit": "g"},
        {"id": "fm", "name": "Forminha", "price": 6.0, "qty": 100, "unit": "un"},
    ],
    "products": [
        {"id": "b1", "name": "Brigadeiro", "yield": 30, "minutes": 50, "margin": None, "current": 0,
         "items": [{"ingId": "lc", "qty": 395}, {"ingId": "ch", "qty": 40}, {"ingId": "mt", "qty": 15},
                   {"ingId": "gr", "qty": 120}, {"ingId": "fm", "qty": 30}],
         "menu": {"show": True, "desc": "Feito com chocolate 50%", "photo": None}},
        {"id": "b2", "name": "Bolo de pote", "yield": 8, "minutes": 0, "margin": None, "current": 12,
         "items": [], "menu": {"show": True}},
        {"id": "b3", "name": "Escondido", "yield": 1, "current": 5, "items": [], "menu": {"show": False}},
    ],
    "menu": {"whatsapp": "(11) 99999-8888", "intro": "Doces artesanais", "delivery": "Entrega no centro"},
}


def test_price_matches_calculator():
    assert product_price(STATE, STATE["products"][0]) == 2.0     # sugerido (igual ao app.js)
    assert product_price(STATE, STATE["products"][1]) == 12.0    # preço que já cobra


def test_public_menu_filters_hidden_and_formats_whatsapp():
    menu = public_menu(STATE)
    assert [i["name"] for i in menu["items"]] == ["Brigadeiro", "Bolo de pote"]
    assert menu["whatsapp"] == "5511999998888"
    assert whatsapp_digits("123") == ""


def _customer(app, client):
    hotmart(client, "PURCHASE_APPROVED")
    login(client, "ana@cliente.com", password_from(app.config["MAIL_OUTBOX"]))
    client.put("/api/dados", json=STATE, headers=H)


def test_menu_link_photo_and_public_page(app, client):
    _customer(app, client)
    assert client.get("/api/cardapio").json["slug"] is None
    assert client.put("/api/cardapio", json={"slug": "Admin"}, headers=H).status_code == 400
    assert client.put("/api/cardapio", json={"slug": "a b"}, headers=H).status_code == 400
    r = client.put("/api/cardapio", json={"slug": "doces-da-ana"}, headers=H)
    assert r.json["url"] == "https://precifica.test/c/doces-da-ana"

    photo = client.post("/api/fotos", data=JPEG, headers=H, content_type="image/jpeg").json
    assert client.post("/api/fotos", data=b"<svg>", headers=H, content_type="image/svg+xml").status_code == 400
    assert client.get(photo["url"]).data == JPEG

    page = app.test_client().get("/c/doces-da-ana")
    html = page.get_data(as_text=True)
    assert page.status_code == 200
    assert "Doces da Ana" in html and "Brigadeiro" in html and "Escondido" not in html
    assert '"whatsapp": "5511999998888"' in html
    assert "Feito com chocolate 50%" in html and "Precifica Fácil" in html


def test_slug_is_unique_between_customers(app, client):
    _customer(app, client)
    client.put("/api/cardapio", json={"slug": "doces"}, headers=H)
    hotmart(client, "PURCHASE_APPROVED", email="outra@x.com", txn="T2")
    other = app.test_client()
    login(other, "outra@x.com", password_from(app.config["MAIL_OUTBOX"]))
    assert other.put("/api/cardapio", json={"slug": "doces"}, headers=H).status_code == 409


def test_photo_belongs_to_owner(app, client):
    _customer(app, client)
    pid = client.post("/api/fotos", data=JPEG, headers=H, content_type="image/jpeg").json["id"]
    hotmart(client, "PURCHASE_APPROVED", email="outra@x.com", txn="T2")
    other = app.test_client()
    login(other, "outra@x.com", password_from(app.config["MAIL_OUTBOX"]))
    other.delete(f"/api/fotos/{pid}", headers=H)
    assert client.get(f"/f/{pid}").status_code == 200


def test_blocked_customer_menu_goes_offline(app, client):
    _customer(app, client)
    client.put("/api/cardapio", json={"slug": "doces-da-ana"}, headers=H)
    hotmart(client, "PURCHASE_REFUNDED")
    assert app.test_client().get("/c/doces-da-ana").status_code == 404
    assert app.test_client().get("/c/nao-existe").status_code == 404
