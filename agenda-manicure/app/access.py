"""Regras de liberação e bloqueio de acesso a partir das compras."""
import secrets
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session
from werkzeug.security import generate_password_hash

from .models import Purchase, User, utcnow

# sem caracteres confusos (0/O, 1/l/I)
_ALPHABET = "abcdefghjkmnpqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ23456789"


def generate_password(length: int = 10) -> str:
    return "".join(secrets.choice(_ALPHABET) for _ in range(length))


def hash_password(password: str) -> str:
    return generate_password_hash(password)


_PARTICLES = {"da", "de", "do", "das", "dos", "e", "di", "du"}


def format_name(name: str) -> str:
    """'wellington felipe liviz da fonseca' -> 'Wellington Felipe Liviz da Fonseca'."""
    words = " ".join((name or "").split()).split(" ")
    out = []
    for i, w in enumerate(words):
        low = w.lower()
        out.append(low if i > 0 and low in _PARTICLES else low[:1].upper() + low[1:])
    return " ".join(out).strip()[:255]


def normalize_email(email: str) -> str:
    return (email or "").strip().lower()


@dataclass
class GrantResult:
    user: User
    password: str | None = None      # preenchida só quando o usuário é novo
    reactivated: bool = False         # usuário existia e estava bloqueado
    duplicate: bool = False           # aviso repetido da plataforma: nada mudou


def grant_access(db: Session, platform: str, transaction_id: str, email: str, name: str = "",
                 product_id: str = "", event: str = "") -> GrantResult:
    email = normalize_email(email)
    transaction_id = transaction_id or f"{platform}:{email}"
    purchase = db.scalar(select(Purchase).where(Purchase.platform == platform,
                                                Purchase.transaction_id == transaction_id))
    user = db.scalar(select(User).where(User.email == email))
    duplicate = purchase is not None and purchase.status == "ativa" and user is not None and user.active

    if purchase is None:
        purchase = Purchase(platform=platform, transaction_id=transaction_id, email=email,
                            product_id=str(product_id or ""), status="ativa")
        db.add(purchase)
    purchase.status = "ativa"
    purchase.last_event = event[:60]
    purchase.updated_at = utcnow()

    result = GrantResult(user=user, duplicate=duplicate)  # type: ignore[arg-type]
    if user is None:
        password = generate_password()
        user = User(email=email, name=format_name(name), password_hash=hash_password(password),
                    active=True)
        db.add(user)
        result.user, result.password = user, password
    elif not user.active:
        user.active = True
        result.reactivated = True
    if name and not user.name:
        user.name = format_name(name)
    db.commit()
    return result


def revoke_access(db: Session, platform: str, transaction_id: str, email: str, event: str = "") -> bool:
    """Revoga a compra. Bloqueia o usuário se ele não tiver outra compra ativa.

    Retorna True se o usuário foi bloqueado.
    """
    email = normalize_email(email)
    purchase = None
    if transaction_id:
        purchase = db.scalar(select(Purchase).where(Purchase.platform == platform,
                                                    Purchase.transaction_id == transaction_id))
    if purchase is None and email:
        # ex: cancelamento de assinatura sem número da transação
        purchase = db.scalar(select(Purchase).where(Purchase.platform == platform, Purchase.email == email,
                                                    Purchase.status == "ativa"))
    if purchase is None:
        if not email:
            return False
        purchase = Purchase(platform=platform, transaction_id=transaction_id or f"{platform}:{email}",
                            email=email, status="revogada")
        db.add(purchase)
    purchase.status = "revogada"
    purchase.last_event = event[:60]
    purchase.updated_at = utcnow()
    db.flush()

    email = purchase.email
    still_active = db.scalar(select(Purchase).where(Purchase.email == email, Purchase.status == "ativa"))
    user = db.scalar(select(User).where(User.email == email))
    blocked = False
    if user and user.active and not still_active:
        user.active = False
        blocked = True
    db.commit()
    return blocked
