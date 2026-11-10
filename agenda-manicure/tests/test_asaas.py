import pytest

import app.webhooks as webhooks
from tests.test_app import app, client, login, password_from  # noqa: F401

TOKEN = "asaas-token-de-teste"
LINK = "precifica123"


@pytest.fixture(autouse=True)
def asaas_config(app, monkeypatch):
    app.config.update(ASAAS_WEBHOOK_TOKEN=TOKEN, ASAAS_API_KEY="chave", ASAAS_PAYMENT_LINK_IDS=[LINK],
                      ASAAS_BLOCK_OVERDUE=True)
    calls = []

    def fake_customer(cid):
        calls.append(cid)
        return {"id": cid, "name": "Carla Dias", "email": "carla@cliente.com"}
    monkeypatch.setattr(webhooks, "fetch_asaas_customer", fake_customer)
    return calls


def send(client, event, *, pid="pay_1", sub="sub_1", link=LINK, token=TOKEN, customer="cus_1"):
    payload = {"id": "evt_1", "event": event,
               "payment": {"object": "payment", "id": pid, "customer": customer, "subscription": sub,
                           "paymentLink": link, "value": 24.9, "billingType": "PIX"}}
    return client.post("/webhooks/asaas", json=payload, headers={"asaas-access-token": token})


def test_payment_from_precifica_link_creates_access(app, client, asaas_config):
    r = send(client, "PAYMENT_RECEIVED")
    assert r.status_code == 200 and r.json["new_user"] is True
    assert asaas_config == ["cus_1"]
    assert app.config["MAIL_OUTBOX"][-1]["to"] == "carla@cliente.com"
    assert login(client, "carla@cliente.com", password_from(app.config["MAIL_OUTBOX"])).status_code == 302


def test_monthly_renewal_keeps_access_without_new_email(app, client, asaas_config):
    send(client, "PAYMENT_CONFIRMED", pid="pay_1")
    r = send(client, "PAYMENT_RECEIVED", pid="pay_2", link=None)  # mensalidade seguinte, sem link
    assert r.status_code == 200 and r.json["new_user"] is False
    assert len(app.config["MAIL_OUTBOX"]) == 1
    assert asaas_config == ["cus_1"]  # não precisou consultar a API de novo


def test_other_business_payments_are_ignored(app, client, asaas_config):
    assert send(client, "PAYMENT_RECEIVED", sub=None, pid="pay_x", link="outro-link").json["ignored"] == "outro produto"
    assert send(client, "PAYMENT_RECEIVED", sub=None, pid="pay_y", link=None).json["ignored"] == "outro produto"
    assert "ignored" in send(client, "PAYMENT_REFUNDED", sub=None, pid="pay_z").json
    assert app.config["MAIL_OUTBOX"] == [] and asaas_config == []


def test_without_link_filter_nothing_is_released(app, client):
    app.config["ASAAS_PAYMENT_LINK_IDS"] = []
    assert "ignored" in send(client, "PAYMENT_RECEIVED").json
    assert app.config["MAIL_OUTBOX"] == []


def test_overdue_blocks_and_payment_releases_again(app, client):
    send(client, "PAYMENT_RECEIVED", pid="pay_1")
    pw = password_from(app.config["MAIL_OUTBOX"])
    assert send(client, "PAYMENT_OVERDUE", pid="pay_2", link=None).json["blocked"] is True
    assert "bloqueado" in login(client, "carla@cliente.com", pw).get_data(as_text=True)
    send(client, "PAYMENT_RECEIVED", pid="pay_2", link=None)
    assert "foi liberado" in app.config["MAIL_OUTBOX"][-1]["subject"]
    assert login(app.test_client(), "carla@cliente.com", pw).status_code == 302


def test_refund_and_subscription_cancel_block(app, client):
    send(client, "PAYMENT_RECEIVED")
    assert send(client, "PAYMENT_REFUNDED").json["blocked"] is True
    send(client, "PAYMENT_RECEIVED", pid="pay_3")
    r = client.post("/webhooks/asaas", json={"event": "SUBSCRIPTION_DELETED", "subscription": {"id": "sub_1"}},
                    headers={"asaas-access-token": TOKEN})
    assert r.json["blocked"] is True


def test_overdue_can_be_disabled(app, client):
    app.config["ASAAS_BLOCK_OVERDUE"] = False
    send(client, "PAYMENT_RECEIVED")
    assert "ignored" in send(client, "PAYMENT_OVERDUE", pid="pay_2").json


def test_wrong_token_and_api_failure(app, client, monkeypatch):
    assert send(client, "PAYMENT_RECEIVED", token="errado").status_code == 401
    monkeypatch.setattr(webhooks, "fetch_asaas_customer", lambda cid: None)
    assert send(client, "PAYMENT_RECEIVED").status_code == 503  # o Asaas tenta de novo depois


def test_irrelevant_events_return_200(client):
    r = send(client, "PAYMENT_CREATED")
    assert r.status_code == 200 and r.json["ignored"] == "PAYMENT_CREATED"


def test_legal_pages(client):
    for path, text in (("/termos", "Direito de arrependimento"), ("/privacidade", "LGPD")):
        r = client.get(path)
        assert r.status_code == 200 and text in r.get_data(as_text=True)
    assert "/termos" in client.get("/entrar").get_data(as_text=True)
