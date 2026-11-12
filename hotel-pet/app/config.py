"""Configurações lidas das variáveis de ambiente."""
import logging
import os
import secrets

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:  # python-dotenv é opcional
    pass

log = logging.getLogger(__name__)


def normalize_db_url(url: str) -> str:
    """Render/Railway entregam 'postgres://...'; o SQLAlchemy quer 'postgresql+psycopg://'."""
    for prefix in ("postgres://", "postgresql://"):
        if url.startswith(prefix):
            return "postgresql+psycopg://" + url[len(prefix):]
    return url


def load_config() -> dict:
    secret = os.getenv("SECRET_KEY")
    if not secret:
        log.warning("SECRET_KEY não definida: usando uma chave temporária (logins caem a cada reinício).")
        secret = secrets.token_hex(32)
    app_url = os.getenv("APP_URL", "http://localhost:5000").rstrip("/")
    return {
        "SECRET_KEY": secret,
        "DATABASE_URL": normalize_db_url(os.getenv("DATABASE_URL", "sqlite:///hotelpet.db")),
        "APP_URL": app_url,
        # Nome do hotel (aparece no topo, nas mensagens de WhatsApp e no comprovante)
        "HOTEL_NAME": os.getenv("HOTEL_NAME", "Hotel Pet"),
        "HOTEL_PHONE": os.getenv("HOTEL_PHONE", ""),
        "TIMEZONE": os.getenv("TIMEZONE", "America/Sao_Paulo"),
        # Dono do sistema: conta criada no primeiro start
        "ADMIN_EMAIL": os.getenv("ADMIN_EMAIL", "").strip().lower(),
        "ADMIN_INITIAL_PASSWORD": os.getenv("ADMIN_INITIAL_PASSWORD", ""),
        # 1 = cria dados de exemplo quando o banco está vazio (bom para apresentar ao cliente)
        "DEMO_DATA": os.getenv("DEMO_DATA", "0") == "1",
        "COMPANY_NAME": os.getenv("COMPANY_NAME", "Liviz Software"),
        "CSRF_ENABLED": True,
        "SESSION_COOKIE_SECURE": app_url.startswith("https://"),
        "SESSION_COOKIE_HTTPONLY": True,
        "SESSION_COOKIE_SAMESITE": "Lax",
        "PERMANENT_SESSION_LIFETIME": 60 * 60 * 12,  # um turno de trabalho
        "MAX_CONTENT_LENGTH": 1024 * 1024,
    }
