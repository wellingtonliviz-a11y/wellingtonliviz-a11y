"""Login, proteção de formulários (CSRF) e limite de tentativas."""
import secrets
import threading
import time
from collections import defaultdict, deque
from functools import wraps

from flask import abort, current_app, g, redirect, request, session, url_for

from .models import User


def _pw_fingerprint(user: User) -> str:
    # muda quando a senha muda: derruba sessões antigas
    return user.password_hash[-16:]


def login_user(user: User) -> None:
    session.clear()
    session.permanent = True
    session["uid"] = user.id
    session["pv"] = _pw_fingerprint(user)


def logout_user() -> None:
    session.clear()


def load_current_user() -> None:
    g.user = None
    uid = session.get("uid")
    if not uid:
        return
    user = current_app.db.session.get(User, uid)
    if user is None or not user.active or session.get("pv") != _pw_fingerprint(user):
        session.pop("uid", None)
        session.pop("pv", None)
        return
    g.user = user


def login_required(view):
    @wraps(view)
    def wrapper(*args, **kwargs):
        if g.get("user") is None:
            return redirect(url_for("auth.login", next=request.full_path.rstrip("?")))
        return view(*args, **kwargs)
    return wrapper


def csrf_token() -> str:
    if "_csrf" not in session:
        session["_csrf"] = secrets.token_urlsafe(32)
    return session["_csrf"]


def check_csrf() -> None:
    if request.method != "POST":
        return
    sent = request.form.get("_csrf", "")
    expected = session.get("_csrf", "")
    if not sent or not expected or not secrets.compare_digest(sent, expected):
        abort(400, "Formulário expirado. Volte, recarregue a página e tente de novo.")


class RateLimiter:
    """Conta tentativas por chave numa janela de tempo (memória do processo)."""

    def __init__(self, limit: int, window: int):
        self.limit, self.window = limit, window
        self.hits: dict[str, deque] = defaultdict(deque)
        self.lock = threading.Lock()

    def allow(self, key: str) -> bool:
        now = time.monotonic()
        with self.lock:
            q = self.hits[key]
            while q and now - q[0] > self.window:
                q.popleft()
            if len(q) >= self.limit:
                return False
            q.append(now)
            return True


login_limiter = RateLimiter(limit=10, window=600)
