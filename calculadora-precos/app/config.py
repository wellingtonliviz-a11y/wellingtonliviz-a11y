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
    return {
        "SECRET_KEY": secret,
        "DATABASE_URL": normalize_db_url(os.getenv("DATABASE_URL", "sqlite:///precifica.db")),
        "APP_URL": app_url,
        "PRODUCT_NAME": os.getenv("PRODUCT_NAME", "Precifica Fácil"),
        "SUPPORT_EMAIL": os.getenv("SUPPORT_EMAIL", ""),
        "CHECKOUT_URL": os.getenv("CHECKOUT_URL", ""),
        "DEMO_ENABLED": os.getenv("DEMO_ENABLED", "1") != "0",
        # E-mail (qualquer SMTP: Brevo, Resend, Gmail com senha de app...)
        "SMTP_HOST": os.getenv("SMTP_HOST", ""),
        "SMTP_PORT": int(os.getenv("SMTP_PORT", "587")),
        "SMTP_USER": os.getenv("SMTP_USER", ""),
        "SMTP_PASSWORD": os.getenv("SMTP_PASSWORD", ""),
        "MAIL_FROM": os.getenv("MAIL_FROM", ""),
        # Plataformas de venda
        "HOTMART_HOTTOK": os.getenv("HOTMART_HOTTOK", ""),
        "HOTMART_PRODUCT_IDS": _list("HOTMART_PRODUCT_IDS"),
        "KIWIFY_TOKEN": os.getenv("KIWIFY_TOKEN", ""),
        "KIWIFY_PRODUCT_IDS": _list("KIWIFY_PRODUCT_IDS"),
        # Administração
        "ADMIN_EMAILS": _list("ADMIN_EMAILS"),
        "ADMIN_INITIAL_PASSWORD": os.getenv("ADMIN_INITIAL_PASSWORD", ""),
        # Cookies
        "SESSION_COOKIE_SECURE": app_url.startswith("https://"),
        "SESSION_COOKIE_HTTPONLY": True,
        "SESSION_COOKIE_SAMESITE": "Lax",
        "PERMANENT_SESSION_LIFETIME": 60 * 60 * 24 * 30,  # 30 dias logado
        "MAX_CONTENT_LENGTH": 1024 * 1024,  # 1 MB por requisição
    }
