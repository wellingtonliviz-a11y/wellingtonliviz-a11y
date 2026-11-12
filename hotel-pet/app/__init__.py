"""Hotel Pet: gestão de hospedagem para cães e gatos."""
import logging

from flask import Flask, g, render_template
from sqlalchemy import select
from werkzeug.middleware.proxy_fix import ProxyFix

from .config import load_config
from .models import LOG_KINDS, PAY_METHODS, SIZES, SPECIES, STATUS, Database, Room, User
from . import util


def create_app(overrides: dict | None = None) -> Flask:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    app = Flask(__name__)
    app.config.update(load_config())
    if overrides:
        app.config.update(overrides)
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)
    app.db = Database(app.config["DATABASE_URL"])

    from . import auth, cadastros, gestao, painel, reservas
    from .security import check_csrf, csrf_token, load_current_user

    for mod in (auth, painel, cadastros, reservas, gestao):
        app.register_blueprint(mod.bp)
    app.before_request(load_current_user)
    app.before_request(check_csrf)

    @app.teardown_appcontext
    def remove_session(_exc=None):
        app.db.session.remove()

    app.jinja_env.filters.update(money=util.money, money_input=util.money_input, br_date=util.br_date,
                                 local_dt=util.local_dt)
    app.jinja_env.globals.update(SPECIES=SPECIES, SIZES=SIZES, STATUS=STATUS, PAY_METHODS=PAY_METHODS,
                                 LOG_KINDS=LOG_KINDS, csrf_token=csrf_token)

    @app.context_processor
    def inject():
        return {"hotel_name": app.config["HOTEL_NAME"], "company_name": app.config["COMPANY_NAME"],
                "today": util.today(), "current_user": g.get("user")}

    @app.after_request
    def security_headers(resp):
        resp.headers.setdefault("X-Content-Type-Options", "nosniff")
        resp.headers.setdefault("X-Frame-Options", "DENY")
        resp.headers.setdefault("Referrer-Policy", "same-origin")
        return resp

    @app.errorhandler(400)
    @app.errorhandler(403)
    @app.errorhandler(404)
    def error_page(err):
        return render_template("erro.html", error=err), err.code

    @app.get("/saude")
    def health():
        return {"ok": True}

    @app.cli.command("demo")
    def demo_cmd():
        """Cria dados de exemplo (acomodações, tutores, pets e reservas)."""
        from .demo import seed
        with app.app_context():
            print(seed(app.db.session))

    _bootstrap(app)
    app.db.engine.dispose()  # com gunicorn --preload cada processo abre as próprias conexões
    return app


def _bootstrap(app: Flask) -> None:
    """Cria a conta do dono (ADMIN_EMAIL) e, se DEMO_DATA=1, os dados de exemplo no banco vazio."""
    from .access import hash_password

    db = app.db.session
    try:
        email, password = app.config["ADMIN_EMAIL"], app.config["ADMIN_INITIAL_PASSWORD"]
        if email and password and db.scalar(select(User).where(User.email == email)) is None:
            db.add(User(email=email, name="Administrador", password_hash=hash_password(password), is_admin=True))
            db.commit()
            logging.getLogger(__name__).info("Conta do administrador criada: %s", email)
        if app.config["DEMO_DATA"] and db.scalar(select(Room).limit(1)) is None:
            from .demo import seed
            with app.app_context():
                logging.getLogger(__name__).info(seed(db))
    finally:
        app.db.session.remove()
