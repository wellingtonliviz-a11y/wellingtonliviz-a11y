import hashlib
import hmac
import json

import pytest

from bot.config import Config
from bot.db import Database
from bot.handlers import SalesBot, money, parse_money

CLIENT = "5511900000001"
SELLER = "5511900000099"


class Cfg(Config):
    ADMIN_PHONES = [SELLER]
    PIX_KEY = "pix@loja.com"
    DELIVERY_FEE_CENTS = 500
    STORE_NAME = "Loja Teste"


@pytest.fixture
def bot():
    db = Database(":memory:")
    db.upsert_product("P01", "Bolo de pote", 1290, 3)
    db.upsert_product("P02", "Brigadeiro", 300, None)
    return SalesBot(db, Cfg)


def texts(outs, to):
    return "\n".join(o.text for o in outs if o.to == to)


def test_money_and_parse():
    assert money(123456) == "R$ 1.234,56"
    assert money(990) == "R$ 9,90"
    assert parse_money("12,90") == 1290
    assert parse_money("12.90") == 1290
    assert parse_money("R$ 1.234,56") == 123456
    assert parse_money("1.234") == 123400
    assert parse_money("abc") is None


def test_menu_and_catalog(bot):
    assert "Catálogo" not in texts(bot.handle(CLIENT, "oi", "Maria Silva"), CLIENT)
    assert "Olá, Maria" in texts(bot.handle(CLIENT, "Olá", "Maria Silva"), CLIENT)
    cat = texts(bot.handle(CLIENT, "1"), CLIENT)
    assert "P01" in cat and "R$ 12,90" in cat and "últimas 3" in cat


def test_full_purchase_flow(bot):
    assert "Adicionado" in texts(bot.handle(CLIENT, "add p01 2"), CLIENT)
    assert "Adicionado" in texts(bot.handle(CLIENT, "3x P02"), CLIENT)
    cart = texts(bot.handle(CLIENT, "carrinho"), CLIENT)
    assert "R$ 34,80" in cart  # 2*12,90 + 3*3,00

    assert "endereço" in texts(bot.handle(CLIENT, "3"), CLIENT)
    outs = bot.handle(CLIENT, "Rua das Flores, 123 - Centro", "Maria")
    client_msg, seller_msg = texts(outs, CLIENT), texts(outs, SELLER)
    assert "Pedido *#1*" in client_msg and "R$ 39,80" in client_msg  # + entrega
    assert "pix@loja.com" in client_msg
    assert "Novo pedido #1" in seller_msg and "Rua das Flores" in seller_msg

    # estoque baixou e carrinho esvaziou
    assert bot.db.get_product("P01")["stock"] == 1
    assert bot.db.get_cart(CLIENT) == []

    # vendedor atualiza o status e o cliente é avisado
    outs = bot.handle(SELLER, "#status 1 enviado")
    assert "saiu para entrega" in texts(outs, CLIENT)
    assert "Saiu para entrega" in texts(bot.handle(CLIENT, "4"), CLIENT)


def test_pickup_has_no_delivery_fee(bot):
    bot.handle(CLIENT, "P02")
    bot.handle(CLIENT, "finalizar")
    outs = bot.handle(CLIENT, "retirada")
    assert "R$ 3,00" in texts(outs, CLIENT)


def test_stock_limit(bot):
    assert "apenas 3" in texts(bot.handle(CLIENT, "add P01 4"), CLIENT)
    bot.handle(CLIENT, "add P01 3")
    assert "apenas 3" in texts(bot.handle(CLIENT, "add P01 1"), CLIENT)


def test_cancel_returns_stock(bot):
    bot.handle(CLIENT, "add P01 2")
    bot.handle(CLIENT, "3")
    bot.handle(CLIENT, "retirada")
    assert bot.db.get_product("P01")["stock"] == 1
    bot.handle(SELLER, "#status 1 cancelado")
    bot.handle(SELLER, "#status 1 cancelado")  # repetido não devolve de novo
    assert bot.db.get_product("P01")["stock"] == 3


def test_human_handoff(bot):
    outs = bot.handle(CLIENT, "5", "Maria")
    assert "atendimento humano" in texts(outs, SELLER)
    assert bot.handle(CLIENT, "quanto custa o frete?") == []  # robô fica quieto
    outs = bot.handle(SELLER, f"#responder {CLIENT} Olá! O frete é grátis.")
    assert "frete é grátis" in texts(outs, CLIENT)
    bot.handle(SELLER, f"#bot {CLIENT}")
    assert "Catálogo" in texts(bot.handle(CLIENT, "1"), CLIENT)


def test_admin_product_management(bot):
    out = texts(bot.handle(SELLER, "#produto bolo2 | Bolo de cenoura | 15,50 | 8"), SELLER)
    assert "BOLO2" in out and "R$ 15,50" in out
    assert "Bolo de cenoura" in texts(bot.handle(CLIENT, "1"), CLIENT)
    bot.handle(SELLER, "#estoque BOLO2 0")
    assert "esgotado" in texts(bot.handle(CLIENT, "add bolo2"), CLIENT)
    bot.handle(SELLER, "#remover BOLO2")
    assert "Bolo de cenoura" not in texts(bot.handle(CLIENT, "1"), CLIENT)
    assert "Use:" in texts(bot.handle(SELLER, "#produto P9 | sem preço"), SELLER)


def test_admin_summary(bot):
    bot.handle(CLIENT, "add P01 1")
    bot.handle(CLIENT, "3")
    bot.handle(CLIENT, "retirada")
    out = texts(bot.handle(SELLER, "#resumo"), SELLER)
    assert "Pedidos: 1" in out and "R$ 12,90" in out and "Estoque baixo" in out


def test_non_admin_cannot_use_admin_commands(bot):
    out = texts(bot.handle(CLIENT, "#status 1 entregue"), CLIENT)
    assert "Não entendi" in out


def test_webhook(monkeypatch, tmp_path):
    monkeypatch.setattr(Config, "DATABASE_PATH", str(tmp_path / "t.db"))
    monkeypatch.setattr(Config, "WHATSAPP_APP_SECRET", "segredo")
    import importlib

    import app as app_module
    importlib.reload(app_module)
    sent = []
    monkeypatch.setattr(app_module, "send_text", lambda to, text: sent.append((to, text)))
    client = app_module.app.test_client()

    r = client.get("/webhook?hub.mode=subscribe&hub.verify_token="
                   f"{Config.WHATSAPP_VERIFY_TOKEN}&hub.challenge=42")
    assert r.status_code == 200 and r.data == b"42"
    assert client.get("/webhook?hub.mode=subscribe&hub.verify_token=x").status_code == 403

    payload = {"entry": [{"changes": [{"value": {
        "contacts": [{"wa_id": CLIENT, "profile": {"name": "Ana"}}],
        "messages": [{"id": "wamid.1", "from": CLIENT, "type": "text", "text": {"body": "oi"}}],
    }}]}]}
    body = json.dumps(payload).encode()
    sig = "sha256=" + hmac.new(b"segredo", body, hashlib.sha256).hexdigest()

    assert client.post("/webhook", data=body, headers={"X-Hub-Signature-256": "sha256=bad"},
                       content_type="application/json").status_code == 401
    for _ in range(2):  # segundo envio é duplicado e deve ser ignorado
        r = client.post("/webhook", data=body, headers={"X-Hub-Signature-256": sig},
                        content_type="application/json")
        assert r.status_code == 200
    assert len(sent) == 1 and "Olá, Ana" in sent[0][1]
