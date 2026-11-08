"""Calculadora (logada e demonstração) e API que guarda os dados do cliente."""
import json

from flask import Blueprint, abort, current_app, g, jsonify, redirect, render_template, request, url_for

from .models import UserData, utcnow
from .security import is_admin, login_required

bp = Blueprint("main", __name__)
MAX_DATA_BYTES = 512 * 1024


@bp.get("/")
@login_required
def app_page():
    return render_template("calculadora.html", mode="conta", admin=is_admin(g.user))


@bp.get("/demo")
def demo():
    if not current_app.config["DEMO_ENABLED"]:
        return redirect(url_for("auth.login"))
    return render_template("calculadora.html", mode="demo", admin=False)


@bp.get("/termos")
def terms():
    return render_template("termos.html")


@bp.get("/privacidade")
def privacy():
    return render_template("privacidade.html")


@bp.get("/saude")
def health():
    return jsonify(status="ok")


@bp.get("/api/dados")
@login_required
def get_data():
    row = current_app.db.session.get(UserData, g.user.id)
    return jsonify(data=json.loads(row.data) if row else None)


@bp.put("/api/dados")
@login_required
def put_data():
    raw = request.get_data()
    if len(raw) > MAX_DATA_BYTES:
        abort(413)
    data = request.get_json(silent=True)
    if not isinstance(data, dict) or data.get("v") != 1 or not isinstance(data.get("products"), list) \
            or not isinstance(data.get("ingredients"), list) or not isinstance(data.get("settings"), dict):
        abort(400, "dados inválidos")
    db = current_app.db.session
    row = db.get(UserData, g.user.id)
    text = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    if row is None:
        db.add(UserData(user_id=g.user.id, data=text, updated_at=utcnow()))
    else:
        row.data, row.updated_at = text, utcnow()
    db.commit()
    return jsonify(ok=True)
