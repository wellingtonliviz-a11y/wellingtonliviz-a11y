"""Agência: organiza clientes, logos, artes e a programação de postagens no Instagram."""
import logging

from flask import Flask, g, render_template
from sqlalchemy import select
from werkzeug.middleware.proxy_fix import ProxyFix
from werkzeug.security import generate_password_hash

from .config import load_config
from .models import Database, User
from .util import FORMATS, KINDS, STATUSES, brl, file_size, short_datetime


def create_app(overrides: dict | None = None) -> Flask:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    app = Flask(__name__)
    app.config.update(load_config())
    if overrides:
        app.config.update(overrides)
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

    app.db = Database(app.config["DATABASE_URL"])

    from . import aprovacao, arquivos, auth, cli, clientes, postagens
    from .security import check_csrf, csrf_token, load_current_user

    for module in (auth, clientes, arquivos, postagens, aprovacao):
        app.register_blueprint(module.bp)
    cli.register(app)

    app.before_request(load_current_user)
    app.before_request(check_csrf)

    @app.teardown_appcontext
    def remove_session(_exc=None):
        app.db.session.remove()

    app.jinja_env.filters.update(brl=brl, data_curta=short_datetime, tamanho=file_size)

    @app.context_processor
    def inject():
        return {"csrf_token": csrf_token, "product_name": app.config["PRODUCT_NAME"],
                "STATUSES": STATUSES, "FORMATS": FORMATS, "KINDS": KINDS}

    @app.after_request
    def security_headers(resp):
        resp.headers.setdefault("X-Content-Type-Options", "nosniff")
        resp.headers.setdefault("X-Frame-Options", "DENY")
        resp.headers.setdefault("Referrer-Policy", "same-origin")
        return resp

    @app.errorhandler(400)
    @app.errorhandler(403)
    @app.errorhandler(404)
    @app.errorhandler(413)
    def error_page(err):
        return render_template("erro.html", error=err, public=g.get("user") is None), err.code

    _bootstrap_admins(app)
    # com gunicorn --preload cada processo abre as próprias conexões
    app.db.engine.dispose()
    return app


def _bootstrap_admins(app: Flask) -> None:
    """Cria as contas de ADMIN_EMAILS no primeiro start, com ADMIN_INITIAL_PASSWORD."""
    password = app.config["ADMIN_INITIAL_PASSWORD"]
    if not password:
        return
    db = app.db.session
    try:
        for email in app.config["ADMIN_EMAILS"]:
            if db.scalar(select(User).where(User.email == email)) is None:
                db.add(User(email=email, name="", password_hash=generate_password_hash(password)))
                logging.getLogger(__name__).info("Conta criada: %s", email)
        db.commit()
    finally:
        app.db.session.remove()
