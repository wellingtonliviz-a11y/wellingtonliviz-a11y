"""Sessão, CSRF, login obrigatório e limite de tentativas de login."""
import hmac
import secrets
import threading
import time
from functools import wraps

from flask import abort, current_app, g, redirect, request, session, url_for

from .models import User


def csrf_token() -> str:
    if "csrf" not in session:
        session["csrf"] = secrets.token_urlsafe(32)
    return session["csrf"]


def check_csrf():
    if request.method != "POST" or not current_app.config.get("CSRF_ENABLED", True):
        return None
    sent = request.form.get("csrf_token", "")
    if not sent or not hmac.compare_digest(sent, session.get("csrf", "")):
        abort(400, "Formulário expirado. Volte, recarregue a página e tente de novo.")
    return None


def load_current_user():
    g.user = None
    uid = session.get("uid")
    if uid:
        user = current_app.db.session.get(User, uid)
        if user and user.active:
            g.user = user
        else:
            session.clear()


def login_user(user: User) -> None:
    session.clear()
    session.permanent = True
    session["uid"] = user.id


def logout_user() -> None:
    session.clear()


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not g.get("user"):
            return redirect(url_for("auth.login", next=request.path))
        return view(*args, **kwargs)
    return wrapped


def admin_required(view):
    @wraps(view)
    @login_required
    def wrapped(*args, **kwargs):
        if not g.user.is_admin:
            abort(403)
        return view(*args, **kwargs)
    return wrapped


class RateLimiter:
    """Conta tentativas por chave numa janela de tempo (em memória, por processo)."""

    def __init__(self, limit: int, window: int):
        self.limit, self.window = limit, window
        self.hits: dict[str, list[float]] = {}
        self.lock = threading.Lock()

    def allow(self, key: str) -> bool:
        now = time.monotonic()
        with self.lock:
            hits = [t for t in self.hits.get(key, []) if now - t < self.window]
            if len(hits) >= self.limit:
                self.hits[key] = hits
                return False
            hits.append(now)
            self.hits[key] = hits
            return True

    def reset(self) -> None:
        with self.lock:
            self.hits.clear()


login_limiter = RateLimiter(limit=10, window=15 * 60)
