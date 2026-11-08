"""Login, proteção de formulários (CSRF), limite de tentativas e links de nova senha."""
import secrets
import threading
import time
from collections import defaultdict, deque
from functools import wraps

from flask import abort, current_app, g, redirect, request, session, url_for
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from .models import User


# ---------- sessão ----------
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
        session.clear()
        return
    g.user = user


def login_required(view):
    @wraps(view)
    def wrapper(*args, **kwargs):
        if g.get("user") is None:
            if request.path.startswith("/api/"):
                abort(401)
            return redirect(url_for("auth.login"))
        return view(*args, **kwargs)
    return wrapper


def is_admin(user: User | None) -> bool:
    return bool(user) and user.email in current_app.config["ADMIN_EMAILS"]


def admin_required(view):
    @wraps(view)
    @login_required
    def wrapper(*args, **kwargs):
        if not is_admin(g.user):
            abort(404)
        return view(*args, **kwargs)
    return wrapper


# ---------- CSRF ----------
def csrf_token() -> str:
    if "csrf" not in session:
        session["csrf"] = secrets.token_urlsafe(24)
    return session["csrf"]


def check_csrf() -> None:
    """Formulários precisam do token; a API exige um cabeçalho que outro site não consegue enviar."""
    if request.method in ("GET", "HEAD", "OPTIONS"):
        return
    if request.blueprint == "webhooks":
        return
    if request.path.startswith("/api/"):
        if request.headers.get("X-Requested-With") != "fetch":
            abort(403)
        return
    sent = request.form.get("csrf", "")
    if not sent or not secrets.compare_digest(sent, session.get("csrf", "")):
        abort(400, "Formulário expirado. Volte, atualize a página e tente de novo.")


# ---------- limite de tentativas ----------
class RateLimiter:
    def __init__(self, max_hits: int, window_seconds: int):
        self.max_hits, self.window = max_hits, window_seconds
        self.hits: dict[str, deque] = defaultdict(deque)
        self.lock = threading.Lock()

    def allow(self, key: str) -> bool:
        now = time.monotonic()
        with self.lock:
            q = self.hits[key]
            while q and now - q[0] > self.window:
                q.popleft()
            if len(q) >= self.max_hits:
                return False
            q.append(now)
            return True

    def reset(self) -> None:
        with self.lock:
            self.hits.clear()


login_limiter = RateLimiter(10, 15 * 60)
email_limiter = RateLimiter(5, 60 * 60)


# ---------- link de nova senha ----------
def _serializer() -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(current_app.config["SECRET_KEY"], salt="nova-senha")


def make_reset_token(user: User) -> str:
    return _serializer().dumps({"uid": user.id, "pv": _pw_fingerprint(user)})


def read_reset_token(token: str, max_age: int = 3600) -> User | None:
    try:
        data = _serializer().loads(token, max_age=max_age)
    except (BadSignature, SignatureExpired):
        return None
    user = current_app.db.session.get(User, data.get("uid"))
    # o link deixa de valer depois que a senha é trocada
    if user is None or not user.active or data.get("pv") != _pw_fingerprint(user):
        return None
    return user
