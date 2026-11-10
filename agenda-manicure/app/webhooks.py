"""Webhooks da Hotmart e da Kiwify: liberam ou bloqueiam o acesso sozinhos."""
import hashlib
import hmac
import json
import logging
import urllib.error
import urllib.parse
import urllib.request

from flask import Blueprint, abort, current_app, jsonify, request

from .access import grant_access, revoke_access
from sqlalchemy import select

from .mailer import send_access_email, send_reactivated_email
from .models import Purchase, utcnow

log = logging.getLogger(__name__)
bp = Blueprint("webhooks", __name__, url_prefix="/webhooks")

HOTMART_GRANT = {"PURCHASE_APPROVED", "PURCHASE_COMPLETE"}
HOTMART_REVOKE = {"PURCHASE_REFUNDED", "PURCHASE_CHARGEBACK", "PURCHASE_CANCELED",
                  "PURCHASE_CANCELLED", "SUBSCRIPTION_CANCELLATION"}
HOTMART_STATUS_GRANT = {"APPROVED", "COMPLETE", "COMPLETED"}
HOTMART_STATUS_REVOKE = {"REFUNDED", "CHARGEBACK", "CANCELED", "CANCELLED"}

KIWIFY_GRANT = {"order_approved"}
KIWIFY_REVOKE = {"order_refunded", "chargeback", "subscription_canceled", "subscription_cancelled"}
KIWIFY_STATUS_GRANT = {"paid", "approved"}
KIWIFY_STATUS_REVOKE = {"refunded", "chargedback", "chargeback"}

ASAAS_GRANT = {"PAYMENT_CONFIRMED", "PAYMENT_RECEIVED"}
ASAAS_REVOKE = {"PAYMENT_REFUNDED", "PAYMENT_CHARGEBACK_REQUESTED", "PAYMENT_CHARGEBACK_DISPUTE",
                "SUBSCRIPTION_DELETED", "SUBSCRIPTION_INACTIVATED"}


def _get(d, *path):
    for key in path:
        if not isinstance(d, dict):
            return None
        d = d.get(key)
    return d


def _product_allowed(allowed: list[str], product_id) -> bool:
    return not allowed or str(product_id or "").lower() in allowed


def _apply(platform: str, action: str, *, transaction: str, email: str, name: str, product_id: str,
           event: str):
    db = current_app.db.session
    if action == "grant":
        if not email:
            abort(400, "compra sem e-mail do comprador")
        res = grant_access(db, platform, transaction, email, name, product_id, event)
        if res.password:
            if send_access_email(res.user.name, res.user.email, res.password):
                res.user.access_email_sent_at = utcnow()
                db.commit()
        elif res.reactivated:
            send_reactivated_email(res.user.name, res.user.email)
        log.info("%s: acesso liberado para %s (novo=%s, duplicado=%s)", platform, res.user.email,
                 bool(res.password), res.duplicate)
        return jsonify(ok=True, action="grant", new_user=bool(res.password))
    blocked = revoke_access(db, platform, transaction, email, event)
    log.info("%s: compra revogada (%s), usuário bloqueado=%s", platform, event, blocked)
    return jsonify(ok=True, action="revoke", blocked=blocked)


@bp.post("/hotmart")
def hotmart():
    cfg = current_app.config
    payload = request.get_json(silent=True) or {}
    token = request.headers.get("X-HOTMART-HOTTOK") or payload.get("hottok") or ""
    if not cfg["HOTMART_HOTTOK"] or not hmac.compare_digest(token, cfg["HOTMART_HOTTOK"]):
        abort(401)

    event = str(payload.get("event") or "").upper()
    data = payload.get("data") or {}
    status = str(_get(data, "purchase", "status") or "").upper()
    product_id = _get(data, "product", "id") or ""
    if not _product_allowed(cfg["HOTMART_PRODUCT_IDS"], product_id):
        return jsonify(ok=True, ignored="outro produto")

    if event in HOTMART_GRANT or (not event and status in HOTMART_STATUS_GRANT):
        action = "grant"
    elif event in HOTMART_REVOKE or (not event and status in HOTMART_STATUS_REVOKE):
        action = "revoke"
    else:
        return jsonify(ok=True, ignored=event or status)

    buyer = data.get("buyer") or data.get("subscriber") or _get(data, "subscription", "subscriber") or {}
    return _apply("hotmart", action,
                  transaction=str(_get(data, "purchase", "transaction") or ""),
                  email=buyer.get("email") or "", name=buyer.get("name") or "",
                  product_id=str(product_id), event=event or status)


@bp.post("/kiwify")
def kiwify():
    cfg = current_app.config
    raw = request.get_data()
    signature = request.args.get("signature", "")
    expected = hmac.new(cfg["KIWIFY_TOKEN"].encode(), raw, hashlib.sha1).hexdigest()
    if not cfg["KIWIFY_TOKEN"] or not hmac.compare_digest(signature, expected):
        abort(401)

    payload = request.get_json(silent=True) or {}
    event = str(payload.get("webhook_event_type") or "").lower()
    status = str(payload.get("order_status") or "").lower()
    product = payload.get("Product") or {}
    product_id = product.get("product_id") or ""
    if not _product_allowed(cfg["KIWIFY_PRODUCT_IDS"], product_id):
        return jsonify(ok=True, ignored="outro produto")

    if event in KIWIFY_GRANT or (not event and status in KIWIFY_STATUS_GRANT):
        action = "grant"
    elif event in KIWIFY_REVOKE or (not event and status in KIWIFY_STATUS_REVOKE):
        action = "revoke"
    else:
        return jsonify(ok=True, ignored=event or status)

    customer = payload.get("Customer") or {}
    return _apply("kiwify", action,
                  transaction=str(payload.get("order_id") or ""),
                  email=customer.get("email") or "",
                  name=customer.get("full_name") or customer.get("first_name") or "",
                  product_id=str(product_id), event=event or status)


def fetch_asaas_customer(customer_id: str) -> dict | None:
    """O aviso do Asaas traz só o código do cliente; nome e e-mail vêm da API."""
    cfg = current_app.config
    if not customer_id or not cfg["ASAAS_API_KEY"]:
        log.error("asaas: ASAAS_API_KEY não configurada; não consigo buscar o cliente %s", customer_id)
        return None
    url = f"{cfg['ASAAS_API_URL']}/customers/{urllib.parse.quote(customer_id)}"
    req = urllib.request.Request(url, headers={"access_token": cfg["ASAAS_API_KEY"], "Accept": "application/json",
                                               "User-Agent": "agendamento-inteligente"})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.load(resp)
    except (urllib.error.URLError, TimeoutError, ValueError) as exc:
        log.error("asaas: falha ao buscar o cliente %s: %s", customer_id, exc)
        return None


@bp.post("/asaas")
def asaas():
    cfg = current_app.config
    token = request.headers.get("asaas-access-token", "")
    if not cfg["ASAAS_WEBHOOK_TOKEN"] or not hmac.compare_digest(token, cfg["ASAAS_WEBHOOK_TOKEN"]):
        abort(401)

    payload = request.get_json(silent=True) or {}
    event = str(payload.get("event") or "").upper()
    payment = payload.get("payment") or {}
    subscription = payload.get("subscription") or {}
    # numa assinatura, todas as mensalidades contam como a mesma compra
    transaction = str(payment.get("subscription") or subscription.get("id") or payment.get("id") or "")

    if event in ASAAS_GRANT:
        action = "grant"
    elif event in ASAAS_REVOKE or (event == "PAYMENT_OVERDUE" and cfg["ASAAS_BLOCK_OVERDUE"]):
        action = "revoke"
    else:
        return jsonify(ok=True, ignored=event)  # sempre 200, senão o Asaas pausa a fila de avisos

    db = current_app.db.session
    known = db.scalar(select(Purchase).where(Purchase.platform == "asaas",
                                             Purchase.transaction_id == transaction)) if transaction else None
    if action == "revoke":
        if known is None:
            return jsonify(ok=True, ignored="compra que não é deste produto")
        return _apply("asaas", "revoke", transaction=transaction, email=known.email, name="",
                      product_id=known.product_id, event=event)

    allowed = cfg["ASAAS_PAYMENT_LINK_IDS"]
    link = str(payment.get("paymentLink") or "")
    if known is None:
        if not allowed:
            log.warning("asaas: configure ASAAS_PAYMENT_LINK_IDS para liberar acesso pelos links deste produto")
            return jsonify(ok=True, ignored="ASAAS_PAYMENT_LINK_IDS não configurado")
        if link.lower() not in allowed:
            return jsonify(ok=True, ignored="outro produto")
        customer = fetch_asaas_customer(str(payment.get("customer") or ""))
        if customer is None:
            return jsonify(ok=False, error="não consegui buscar o cliente no Asaas"), 503  # o Asaas tenta de novo
        email, name = customer.get("email") or "", customer.get("name") or ""
    else:
        email, name = known.email, ""
    return _apply("asaas", "grant", transaction=transaction, email=email, name=name,
                  product_id=link or (known.product_id if known else ""), event=event)
