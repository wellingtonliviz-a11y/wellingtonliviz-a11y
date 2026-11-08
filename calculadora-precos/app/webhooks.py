"""Webhooks da Hotmart e da Kiwify: liberam ou bloqueiam o acesso sozinhos."""
import hashlib
import hmac
import logging

from flask import Blueprint, abort, current_app, jsonify, request

from .access import grant_access, revoke_access
from .mailer import send_access_email, send_reactivated_email
from .models import utcnow

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
