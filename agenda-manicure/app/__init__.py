"""Agendamento Inteligente: preço dos serviços e agenda online, vendido pela Hotmart/Kiwify/Asaas."""
import logging

from flask import Flask, g, render_template
from sqlalchemy import select
from werkzeug.middleware.proxy_fix import ProxyFix

from .config import load_config
from .models import Database, User


def create_app(overrides: dict | None = None) -> Flask:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    app = Flask(__name__)
    app.config.update(load_config())
    if overrides:
        app.config.update(overrides)
    # Render e Railway ficam atrás de um proxy HTTPS
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

    app.db = Database(app.config["DATABASE_URL"])

    from . import admin, agenda, auth, main, webhooks
    from .security import check_csrf, csrf_token, is_admin, load_current_user

    app.register_blueprint(main.bp)
    app.register_blueprint(auth.bp)
    app.register_blueprint(admin.bp)
    app.register_blueprint(webhooks.bp)
    app.register_blueprint(agenda.bp)

    app.before_request(load_current_user)
    app.before_request(check_csrf)

    @app.teardown_appcontext
    def remove_session(_exc=None):
        app.db.session.remove()

    @app.context_processor
    def inject():
        cfg = app.config
        return {"csrf_token": csrf_token, "product_name": cfg["PRODUCT_NAME"],
                "support_email": cfg["SUPPORT_EMAIL"], "checkout_url": cfg["CHECKOUT_URL"],
                "demo_enabled": cfg["DEMO_ENABLED"], "is_admin": is_admin(g.get("user")),
                "company_name": cfg["COMPANY_NAME"], "company_doc": cfg["COMPANY_DOC"],
                "company_email": cfg["COMPANY_EMAIL"], "app_url": cfg["APP_URL"],
                "plan_price": cfg["PLAN_PRICE"]}

    @app.after_request
    def security_headers(resp):
        resp.headers.setdefault("X-Content-Type-Options", "nosniff")
        resp.headers.setdefault("X-Frame-Options", "DENY")
        resp.headers.setdefault("Referrer-Policy", "same-origin")
        return resp

    @app.errorhandler(400)
    @app.errorhandler(404)
    def error_page(err):
        return render_template("erro.html", error=err), err.code

    _bootstrap_admins(app)
    # com gunicorn --preload cada processo abre as próprias conexões
    app.db.engine.dispose()
    return app


def _bootstrap_admins(app: Flask) -> None:
    """Cria a conta do dono (ADMIN_EMAILS) no primeiro start, com ADMIN_INITIAL_PASSWORD."""
    password = app.config["ADMIN_INITIAL_PASSWORD"]
    if not password:
        return
    from .access import hash_password

    db = app.db.session
    try:
        for email in app.config["ADMIN_EMAILS"]:
            if db.scalar(select(User).where(User.email == email)) is None:
                db.add(User(email=email, name="Administrador", password_hash=hash_password(password)))
                logging.getLogger(__name__).info("Conta de administrador criada: %s", email)
        db.commit()
    finally:
        app.db.session.remove()
