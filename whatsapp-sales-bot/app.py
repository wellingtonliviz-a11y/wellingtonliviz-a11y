"""Servidor do webhook do WhatsApp (Flask)."""
import logging

from flask import Flask, abort, jsonify, request

from bot.config import Config
from bot.db import Database
from bot.handlers import Outgoing, SalesBot
from bot.whatsapp import extract_messages, send_text, valid_signature

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("app")

app = Flask(__name__)
db = Database(Config.DATABASE_PATH)
bot = SalesBot(db)

MEDIA_REPLY = ("Recebi seu arquivo! 📎 Se for o comprovante de pagamento, "
               "o vendedor vai conferir em instantes.")


@app.get("/")
def health():
    return jsonify(status="ok", store=Config.STORE_NAME)


@app.get("/webhook")
def verify():
    """Verificação do webhook feita pela Meta ao cadastrar a URL."""
    if (request.args.get("hub.mode") == "subscribe"
            and request.args.get("hub.verify_token") == Config.WHATSAPP_VERIFY_TOKEN):
        return request.args.get("hub.challenge", ""), 200
    abort(403)


@app.post("/webhook")
def receive():
    if not valid_signature(request.get_data(), request.headers.get("X-Hub-Signature-256")):
        abort(401)
    payload = request.get_json(silent=True) or {}
    for msg_id, phone, name, text in extract_messages(payload):
        if msg_id and not db.mark_processed(msg_id):
            continue  # reenvio da Meta: já tratado
        try:
            outgoing = process(phone, name, text)
        except Exception:
            log.exception("Erro ao processar mensagem de %s", phone)
            outgoing = [Outgoing(phone, "Ops, tive um problema aqui. Tente de novo em instantes. 🙏")]
        for out in outgoing:
            send_text(out.to, out.text)
    return "ok", 200


def process(phone: str, name: str | None, text: str) -> list[Outgoing]:
    if text.startswith("__") and text.endswith("__"):
        # Mídia (ex: comprovante de Pix): avisa o vendedor
        customer = db.get_customer(phone, name)
        if customer["state"] == "human":
            return []
        alerts = [Outgoing(a, f"📎 {name or phone} enviou um arquivo ({text.strip('_')}). "
                              f"Veja em wa.me/{phone}") for a in Config.ADMIN_PHONES]
        return [Outgoing(phone, MEDIA_REPLY), *alerts]
    return bot.handle(phone, text, name)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
