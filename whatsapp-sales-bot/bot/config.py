"""Configurações lidas de variáveis de ambiente (arquivo .env)."""
import os

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:  # python-dotenv é opcional
    pass


def _list(name: str) -> list[str]:
    raw = os.getenv(name, "")
    return [only_digits(p) for p in raw.split(",") if only_digits(p)]


def only_digits(value: str) -> str:
    return "".join(ch for ch in value if ch.isdigit())


class Config:
    # WhatsApp Cloud API (Meta)
    WHATSAPP_TOKEN = os.getenv("WHATSAPP_TOKEN", "")
    WHATSAPP_PHONE_NUMBER_ID = os.getenv("WHATSAPP_PHONE_NUMBER_ID", "")
    WHATSAPP_VERIFY_TOKEN = os.getenv("WHATSAPP_VERIFY_TOKEN", "meu-token-secreto")
    WHATSAPP_APP_SECRET = os.getenv("WHATSAPP_APP_SECRET", "")
    GRAPH_API_VERSION = os.getenv("GRAPH_API_VERSION", "v21.0")

    # Loja
    STORE_NAME = os.getenv("STORE_NAME", "Minha Loja")
    PIX_KEY = os.getenv("PIX_KEY", "")
    BUSINESS_HOURS = os.getenv("BUSINESS_HOURS", "Seg a Sex, 9h às 18h")
    DELIVERY_FEE_CENTS = int(os.getenv("DELIVERY_FEE_CENTS", "0"))

    # Números dos vendedores (com DDI e DDD, ex: 5511999998888), separados por vírgula
    ADMIN_PHONES = _list("ADMIN_PHONES")

    DATABASE_PATH = os.getenv("DATABASE_PATH", "vendas.db")
