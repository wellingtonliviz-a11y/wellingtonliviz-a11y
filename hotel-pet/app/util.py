"""Dinheiro em reais, datas, fuso horário e WhatsApp."""
import re
from datetime import date, datetime
from urllib.parse import quote
from zoneinfo import ZoneInfo

from flask import current_app


def tz() -> ZoneInfo:
    return ZoneInfo(current_app.config["TIMEZONE"])


def today() -> date:
    return datetime.now(tz()).date()


def local_dt(dt: datetime | None) -> datetime | None:
    return dt.astimezone(tz()) if dt else None


def parse_money(text: str | None) -> int | None:
    """'1.234,56' / '1234.56' / 'R$ 80' -> centavos. Vazio ou inválido -> None."""
    s = (text or "").strip().replace("R$", "").replace(" ", "")
    if not s:
        return None
    if "," in s:
        s = s.replace(".", "").replace(",", ".")
    elif s.count(".") > 1 or re.fullmatch(r"\d{1,3}(\.\d{3})+", s):
        s = s.replace(".", "")
    try:
        value = round(float(s) * 100)
    except ValueError:
        return None
    return value if value >= 0 else None


def money(cents: int | None) -> str:
    cents = cents or 0
    sign = "-" if cents < 0 else ""
    reais, cent = divmod(abs(cents), 100)
    return f"{sign}R$ {reais:,}".replace(",", ".") + f",{cent:02d}"


def money_input(cents: int | None) -> str:
    """Valor para preencher um campo de formulário ('80,00')."""
    return money(cents).replace("R$ ", "")


def parse_date(text: str | None) -> date | None:
    try:
        return date.fromisoformat((text or "").strip())
    except ValueError:
        return None


def br_date(d: date | datetime | None) -> str:
    return d.strftime("%d/%m/%Y") if d else ""


def wa_link(phone: str, message: str) -> str:
    """Link do WhatsApp. Números brasileiros sem DDI ganham o 55."""
    digits = re.sub(r"\D", "", phone or "")
    if len(digits) in (10, 11):
        digits = "55" + digits
    return f"https://wa.me/{digits}?text={quote(message)}" if digits else ""
