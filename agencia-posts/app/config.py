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


def _list(name: str) -> list[str]:
    return [x.strip().lower() for x in os.getenv(name, "").split(",") if x.strip()]


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
    max_file_mb = int(os.getenv("MAX_FILE_MB", "15"))
    return {
        "SECRET_KEY": secret,
        "DATABASE_URL": normalize_db_url(os.getenv("DATABASE_URL", "sqlite:///agencia.db")),
        "APP_URL": app_url,
        "PRODUCT_NAME": os.getenv("PRODUCT_NAME", "Agência Liviz"),
        "TIMEZONE": os.getenv("TIMEZONE", "America/Sao_Paulo"),
        "ADMIN_EMAILS": _list("ADMIN_EMAILS"),
        "ADMIN_INITIAL_PASSWORD": os.getenv("ADMIN_INITIAL_PASSWORD", ""),
        "MAX_FILE_MB": max_file_mb,
        # vários arquivos por envio
        "MAX_CONTENT_LENGTH": max_file_mb * 4 * 1024 * 1024,
        "SESSION_COOKIE_SECURE": app_url.startswith("https://"),
        "SESSION_COOKIE_HTTPONLY": True,
        "SESSION_COOKIE_SAMESITE": "Lax",
        "PERMANENT_SESSION_LIFETIME": 60 * 60 * 24 * 30,  # 30 dias logado
    }
