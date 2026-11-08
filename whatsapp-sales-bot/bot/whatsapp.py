"""Cliente da WhatsApp Cloud API (oficial da Meta)."""
import hashlib
import hmac
import logging

import requests

from .config import Config

log = logging.getLogger(__name__)


def send_text(to: str, text: str, config: type[Config] = Config) -> bool:
    """Envia uma mensagem de texto. Retorna True em caso de sucesso."""
    if not config.WHATSAPP_TOKEN or not config.WHATSAPP_PHONE_NUMBER_ID:
        log.warning("WhatsApp não configurado; mensagem para %s:\n%s", to, text)
        return False
    url = (f"https://graph.facebook.com/{config.GRAPH_API_VERSION}/"
           f"{config.WHATSAPP_PHONE_NUMBER_ID}/messages")
    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "text",
        "text": {"body": text[:4096], "preview_url": False},
    }
    try:
        resp = requests.post(
            url, json=payload, timeout=15,
            headers={"Authorization": f"Bearer {config.WHATSAPP_TOKEN}"},
        )
    except requests.RequestException as exc:
        log.error("Falha ao enviar mensagem para %s: %s", to, exc)
        return False
    if resp.status_code >= 400:
        log.error("Erro da API do WhatsApp (%s): %s", resp.status_code, resp.text)
        return False
    return True


def valid_signature(body: bytes, header: str | None, config: type[Config] = Config) -> bool:
    """Valida o cabeçalho X-Hub-Signature-256 enviado pela Meta."""
    if not config.WHATSAPP_APP_SECRET:
        return True  # validação desativada (apenas para desenvolvimento)
    if not header or not header.startswith("sha256="):
        return False
    expected = hmac.new(config.WHATSAPP_APP_SECRET.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, header.removeprefix("sha256="))


def extract_messages(payload: dict):
    """Extrai (id, telefone, nome, texto) das mensagens recebidas no webhook."""
    for entry in payload.get("entry", []):
        for change in entry.get("changes", []):
            value = change.get("value", {})
            names = {c.get("wa_id"): c.get("profile", {}).get("name")
                     for c in value.get("contacts", [])}
            for msg in value.get("messages", []):
                sender = msg.get("from", "")
                mtype = msg.get("type")
                if mtype == "text":
                    text = msg["text"].get("body", "")
                elif mtype == "button":
                    text = msg["button"].get("text", "")
                elif mtype == "interactive":
                    inter = msg["interactive"]
                    reply = inter.get("button_reply") or inter.get("list_reply") or {}
                    text = reply.get("id") or reply.get("title", "")
                else:
                    text = f"__{mtype}__"  # imagem, áudio, documento...
                yield msg.get("id", ""), sender, names.get(sender), text
