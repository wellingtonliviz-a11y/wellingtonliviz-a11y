import hashlib
import hmac
import json
import re

import pytest

from app import create_app
from app.models import User
from app.security import email_limiter, login_limiter

HOTTOK = "hottok-de-teste"
KIWI = "kiwify-token-de-teste"
ADMIN = "dono@loja.com"


@pytest.fixture
def app(tmp_path):
    login_limiter.reset()
    email_limiter.reset()
    app = create_app({
        "TESTING": True,
        "SECRET_KEY": "teste",
        "DATABASE_URL": f"sqlite:///{tmp_path / 'test.db'}",
        "APP_URL": "https://precifica.test",
        "HOTMART_HOTTOK": HOTTOK,
        "HOTMART_PRODUCT_IDS": [],
        "KIWIFY_TOKEN": KIWI,
        "KIWIFY_PRODUCT_IDS": [],
        "ADMIN_EMAILS": [ADMIN],
        "ADMIN_INITIAL_PASSWORD": "admin123",
        "MAIL_OUTBOX": [],
    })
    return app


@pytest.fixture
def client(app):
    return app.test_client()


def csrf(client, path):
    html = client.get(path).get_data(as_text=True)
    return re.search(r'name="csrf" value="([^"]+)"', html).group(1)


def login(client, email, password):
    return client.post("/entrar", data={"email": email, "password": password,
                                        "csrf": csrf(client, "/entrar")})


def hotmart(client, event, email="ana@cliente.com", txn="HP123", product=111, token=HOTTOK):
    payload = {"event": event, "version": "2.0.0", "data": {
        "product": {"id": product, "name": "Precifica Fácil"},
        "buyer": {"email": email, "name": "Ana Souza"},
        "purchase": {"transaction": txn, "status": "APPROVED"}}}
    return client.post("/webhooks/hotmart", json=payload, headers={"X-HOTMART-HOTTOK": token})


def kiwify(client, event, email="bia@cliente.com", order="ord_1", token=KIWI):
    body = json.dumps({"order_id": order, "order_status": "paid", "webhook_event_type": event,
                       "Product": {"product_id": "prod_1", "product_name": "Precifica"},
                       "Customer": {"email": email, "full_name": "Bia Lima"}}).encode()
    sig = hmac.new(token.encode(), body, hashlib.sha1).hexdigest()
    return client.post(f"/webhooks/kiwify?signature={sig}", data=body, content_type="application/json")


def password_from(outbox):
    return re.search(r"Senha: (\S+)", outbox[-1]["text"]).group(1)


def test_hotmart_purchase_creates_user_and_emails_password(app, client):
    r = hotmart(client, "PURCHASE_APPROVED")
    assert r.status_code == 200 and r.json["new_user"] is True
    mail = app.config["MAIL_OUTBOX"][-1]
    assert mail["to"] == "ana@cliente.com"
    assert "https://precifica.test/entrar" in mail["text"]

    r = login(client, "Ana@Cliente.com ", password_from(app.config["MAIL_OUTBOX"]))
    assert r.status_code == 302 and r.headers["Location"] == "/"
    assert "Produtos" in client.get("/").get_data(as_text=True)


def test_duplicate_webhook_does_not_send_twice(app, client):
    hotmart(client, "PURCHASE_APPROVED")
    hotmart(client, "PURCHASE_APPROVED")
    hotmart(client, "PURCHASE_COMPLETE")
    assert len(app.config["MAIL_OUTBOX"]) == 1


def test_wrong_token_is_rejected(app, client):
    assert hotmart(client, "PURCHASE_APPROVED", token="errado").status_code == 401
    assert kiwify(client, "order_approved", token="errado").status_code == 401
    assert app.config["MAIL_OUTBOX"] == []


def test_refund_blocks_and_new_purchase_unblocks(app, client):
    hotmart(client, "PURCHASE_APPROVED")
    pw = password_from(app.config["MAIL_OUTBOX"])
    login(client, "ana@cliente.com", pw)
    assert client.get("/").status_code == 200

    assert hotmart(client, "PURCHASE_REFUNDED").json["blocked"] is True
    assert client.get("/").status_code == 302  # sessão derrubada
    r = login(client, "ana@cliente.com", pw)
    assert "bloqueado" in r.get_data(as_text=True)

    hotmart(client, "PURCHASE_APPROVED", txn="HP999")
    assert "foi liberado" in app.config["MAIL_OUTBOX"][-1]["subject"]
    assert login(client, "ana@cliente.com", pw).status_code == 302


def test_other_product_is_ignored(app, client):
    app.config["HOTMART_PRODUCT_IDS"] = ["111"]
    assert hotmart(client, "PURCHASE_APPROVED", product=222).json["ignored"] == "outro produto"
    assert hotmart(client, "PURCHASE_APPROVED", product=111).json["new_user"] is True


def test_irrelevant_events_are_ignored(client):
    assert "ignored" in hotmart(client, "PURCHASE_BILLET_PRINTED").json


def test_kiwify_flow(app, client):
    assert kiwify(client, "order_approved").json["new_user"] is True
    assert app.config["MAIL_OUTBOX"][-1]["to"] == "bia@cliente.com"
    assert kiwify(client, "order_refunded").json["blocked"] is True
    assert "ignored" in kiwify(client, "billet_created", order="ord_2").json


def test_data_is_saved_per_user(app, client):
    hotmart(client, "PURCHASE_APPROVED", email="a@x.com", txn="1")
    pw_a = password_from(app.config["MAIL_OUTBOX"])
    hotmart(client, "PURCHASE_APPROVED", email="b@x.com", txn="2")
    pw_b = password_from(app.config["MAIL_OUTBOX"])

    login(client, "a@x.com", pw_a)
    assert client.get("/api/dados").json == {"data": None}
    state = {"v": 1, "settings": {"margin": 40}, "ingredients": [], "products": [{"name": "Coxinha"}]}
    h = {"X-Requested-With": "fetch"}
    assert client.put("/api/dados", json=state, headers=h).status_code == 200
    assert client.put("/api/dados", json=state).status_code == 403          # sem cabeçalho: bloqueado
    assert client.put("/api/dados", json={"v": 2}, headers=h).status_code == 400
    assert client.get("/api/dados").json["data"]["products"][0]["name"] == "Coxinha"

    other = app.test_client()
    login(other, "b@x.com", pw_b)
    assert other.get("/api/dados").json == {"data": None}
    assert app.test_client().get("/api/dados").status_code == 401


def test_forgot_and_reset_password(app, client):
    hotmart(client, "PURCHASE_APPROVED")
    old = password_from(app.config["MAIL_OUTBOX"])
    client.post("/esqueci", data={"email": "ana@cliente.com", "csrf": csrf(client, "/esqueci")})
    link = re.search(r"https://precifica.test(/redefinir/\S+)", app.config["MAIL_OUTBOX"][-1]["text"]).group(1)

    # e-mail desconhecido: mesma resposta, nenhum e-mail enviado
    n = len(app.config["MAIL_OUTBOX"])
    client.post("/esqueci", data={"email": "ninguem@x.com", "csrf": csrf(client, "/esqueci")})
    assert len(app.config["MAIL_OUTBOX"]) == n

    token = csrf(client, link)
    r = client.post(link, data={"password": "novasenha", "password2": "novasenha", "csrf": token})
    assert r.status_code == 302
    assert client.get(link).status_code == 302  # link já usado
    fresh = app.test_client()
    assert "incorretos" in login(fresh, "ana@cliente.com", old).get_data(as_text=True)
    assert login(fresh, "ana@cliente.com", "novasenha").status_code == 302


def test_change_password_in_account(app, client):
    hotmart(client, "PURCHASE_APPROVED")
    pw = password_from(app.config["MAIL_OUTBOX"])
    login(client, "ana@cliente.com", pw)
    token = csrf(client, "/conta")
    client.post("/conta", data={"action": "senha", "current": pw, "password": "minha123",
                                "password2": "minha123", "csrf": token})
    assert client.get("/").status_code == 200  # esta sessão continua
    assert login(app.test_client(), "ana@cliente.com", "minha123").status_code == 302


def test_forms_require_csrf(client):
    r = client.post("/entrar", data={"email": "x@x.com", "password": "x"})
    assert r.status_code == 400


def test_login_rate_limit(client):
    for _ in range(10):
        login(client, "x@x.com", "errada")
    assert login(client, "x@x.com", "errada").status_code == 429


def test_admin_panel(app, client):
    hotmart(client, "PURCHASE_APPROVED")
    assert client.get("/admin").status_code == 302
    login(client, ADMIN, "admin123")
    html = client.get("/admin").get_data(as_text=True)
    assert "ana@cliente.com" in html

    with app.app_context():
        uid = app.db.session.query(User).filter_by(email="ana@cliente.com").one().id
    token = csrf(client, "/admin")
    client.post(f"/admin/usuarios/{uid}/status", data={"active": "0", "csrf": token})
    with app.app_context():
        assert app.db.session.get(User, uid).active is False
    client.post(f"/admin/usuarios/{uid}/reenviar", data={"csrf": token})
    assert app.config["MAIL_OUTBOX"][-1]["to"] == "ana@cliente.com"
    client.post("/admin/criar", data={"email": "cortesia@x.com", "name": "Parceira", "csrf": token})
    assert app.config["MAIL_OUTBOX"][-1]["to"] == "cortesia@x.com"

    # cliente comum não vê o painel
    other = app.test_client()
    login(other, "cortesia@x.com", password_from(app.config["MAIL_OUTBOX"]))
    assert other.get("/admin").status_code == 404


def test_demo_page_is_public(client):
    html = client.get("/demo").get_data(as_text=True)
    assert "Demonstração" in html and '"mode": "demo"' in html


def test_access_email_capitalizes_first_name(app):
    from app.mailer import send_access_email
    with app.app_context():
        send_access_email("wellington liviz", "w@x.com", "abc")
    assert app.config["MAIL_OUTBOX"][-1]["text"].startswith("Olá, Wellington!")


def test_format_name():
    from app.access import format_name
    assert format_name("wellington felipe liviz da fonseca") == "Wellington Felipe Liviz da Fonseca"
    assert format_name("  MARIA  DOS SANTOS ") == "Maria dos Santos"
    assert format_name("") == ""
