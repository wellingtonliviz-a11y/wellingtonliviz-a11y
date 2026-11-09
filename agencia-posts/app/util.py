"""Listas fixas e funções pequenas usadas em vários lugares."""
import re
from datetime import date, datetime, time
from decimal import Decimal, InvalidOperation
from urllib.parse import quote
from zoneinfo import ZoneInfo

from flask import current_app

STATUSES = {
    "ideia": "Ideia",
    "producao": "Em produção",
    "aprovacao": "Aguardando aprovação",
    "ajuste": "Ajuste pedido",
    "aprovado": "Aprovado",
    "publicado": "Publicado",
}
FORMATS = {"feed": "Feed (foto)", "carrossel": "Carrossel", "story": "Story", "reels": "Reels"}
KINDS = {"logo": "Logo", "foto": "Foto do cliente", "arte": "Arte pronta", "outro": "Outro"}
WEEKDAYS = ["seg", "ter", "qua", "qui", "sex", "sáb", "dom"]
MONTHS = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto",
          "setembro", "outubro", "novembro", "dezembro"]


def agora() -> datetime:
    """Data e hora local (fuso do negócio), sem segundos."""
    tz = ZoneInfo(current_app.config["TIMEZONE"])
    return datetime.now(tz).replace(tzinfo=None, second=0, microsecond=0)


def start_of_day(d: date) -> datetime:
    return datetime.combine(d, time.min)


def month_bounds(year: int, month: int) -> tuple[datetime, datetime]:
    start = datetime(year, month, 1)
    end = datetime(year + 1, 1, 1) if month == 12 else datetime(year, month + 1, 1)
    return start, end


def parse_money(text: str) -> int | None:
    """'1.500,00' / '1500' / '350,5' -> centavos. Vazio -> None. Inválido -> ValueError."""
    s = text.strip().replace("R$", "").replace(" ", "")
    if not s:
        return None
    if "," in s:
        s = s.replace(".", "").replace(",", ".")
    elif re.fullmatch(r"\d{1,3}(\.\d{3})+", s):  # 1.500 = mil e quinhentos
        s = s.replace(".", "")
    try:
        value = Decimal(s)
    except InvalidOperation:
        raise ValueError(text) from None
    if value < 0 or not value.is_finite():
        raise ValueError(text)
    return int((value * 100).quantize(Decimal("1")))


def brl(cents: int | None) -> str:
    if cents is None:
        return "—"
    s = f"{cents / 100:,.2f}".replace(",", "_").replace(".", ",").replace("_", ".")
    return f"R$ {s}"


def safe_next(url: str | None, default: str) -> str:
    """Só aceita voltar para páginas do próprio site."""
    if url and url.startswith("/") and not url.startswith("//") and "\\" not in url:
        return url
    return default


def whatsapp_link(phone: str, text: str) -> str | None:
    digits = re.sub(r"\D", "", phone or "")
    if not digits:
        return None
    if len(digits) in (10, 11):  # DDD + número, sem o 55
        digits = "55" + digits
    return f"https://wa.me/{digits}?text={quote(text)}"


def short_datetime(dt: datetime | None) -> str:
    if dt is None:
        return ""
    return f"{WEEKDAYS[dt.weekday()]}, {dt:%d/%m} às {dt:%H:%M}"


def file_size(n: int) -> str:
    if n >= 1024 * 1024:
        return f"{n / 1024 / 1024:.1f} MB".replace(".", ",")
    return f"{max(1, n // 1024)} KB"
