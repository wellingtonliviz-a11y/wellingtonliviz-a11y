import io
import re
from datetime import datetime, timedelta

import pytest

from app import create_app
from app.models import Client, File, Post
from app.util import parse_money

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64


@pytest.fixture
def app(tmp_path):
    return create_app({"TESTING": True, "DATABASE_URL": f"sqlite:///{tmp_path}/t.db",
                       "ADMIN_EMAILS": ["dono@ex.com"], "ADMIN_INITIAL_PASSWORD": "senha-forte-1",
                       "APP_URL": "http://localhost"})


def _csrf(client, path="/entrar"):
    html = client.get(path).get_data(as_text=True)
    return re.search(r'name="_csrf" value="([^"]+)"', html).group(1)


@pytest.fixture
def web(app):
    c = app.test_client()
    token = _csrf(c)
    r = c.post("/entrar", data={"_csrf": token, "email": "dono@ex.com", "password": "senha-forte-1"})
    assert r.status_code == 302
    c.token = _csrf(c, "/conta")  # o login renova a sessão
    return c


def _new_client(web, **extra):
    data = {"_csrf": web.token, "name": "Padaria Pão Quente", "segment": "Padaria", "instagram": "@paoquente",
            "color_primary": "#aa3300", "color_secondary": "#ffcc00", "monthly_fee": "1.500,00",
            "payment_day": "10", "posts_per_month": "12", "phone": "(11) 98888-7777", **extra}
    r = web.post("/clientes/novo", data=data, content_type="multipart/form-data")
    assert r.status_code == 302, r.get_data(as_text=True)
    return int(r.headers["Location"].rstrip("/").split("/")[-1])


def test_login_required(app):
    r = app.test_client().get("/clientes")
    assert r.status_code == 302 and "/entrar" in r.headers["Location"]


def test_wrong_password(app):
    c = app.test_client()
    r = c.post("/entrar", data={"_csrf": _csrf(c), "email": "dono@ex.com", "password": "x"})
    assert "incorretos" in r.get_data(as_text=True)


def test_csrf_required(web):
    assert web.post("/clientes/novo", data={"name": "X"}).status_code == 400


def test_parse_money():
    assert parse_money("1.500,00") == 150000
    assert parse_money("1.500") == 150000
    assert parse_money("350,5") == 35050
    assert parse_money("99.90") == 9990
    assert parse_money("") is None
    with pytest.raises(ValueError):
        parse_money("abc")


def test_create_client_and_pages(web, app):
    cid = _new_client(web, logo=(io.BytesIO(PNG), "logo.png"))
    c = app.db.session.get(Client, cid)
    assert c.instagram == "paoquente" and c.monthly_fee_cents == 150000 and c.logo_id
    html = web.get(f"/clientes/{cid}").get_data(as_text=True)
    assert "Padaria Pão Quente" in html and "wa.me/5511988887777" in html
    assert web.get("/clientes").status_code == 200
    assert web.get("/").status_code == 200
    assert web.get(f"/clientes/{cid}/editar").status_code == 200


def test_invalid_client_not_saved(web, app):
    r = web.post("/clientes/novo", data={"_csrf": web.token, "name": "", "color_primary": "#000000",
                                         "color_secondary": "#ffffff"})
    assert r.status_code == 200 and "Informe o nome" in r.get_data(as_text=True)
    assert app.db.session.query(Client).count() == 0


def test_upload_rejects_unknown_type(web, app):
    cid = _new_client(web)
    r = web.post(f"/clientes/{cid}/arquivos", content_type="multipart/form-data", follow_redirects=True,
                 data={"_csrf": web.token, "kind": "foto",
                       "arquivos": [(io.BytesIO(PNG), "a.png"), (io.BytesIO(b"<html>"), "b.html")]})
    assert "b.html" in r.get_data(as_text=True)
    files = app.db.session.query(File).all()
    assert [f.mime for f in files] == ["image/png"]
    resp = web.get(f"/arquivos/{files[0].id}?baixar=1")
    assert resp.data == PNG and "attachment" in resp.headers["Content-Disposition"]


def test_post_flow_and_approval(web, app):
    cid = _new_client(web)
    day = (datetime.now() + timedelta(days=2)).strftime("%Y-%m-%d")
    r = web.post("/postagens/nova", content_type="multipart/form-data", data={
        "_csrf": web.token, "client_id": str(cid), "date": day, "time": "18:30", "format": "feed",
        "status": "aprovacao", "theme": "Pão de queijo", "caption": "Saiu fornada!", "hashtags": "#padaria",
        "artes": [(io.BytesIO(PNG), "arte.png")]})
    assert r.status_code == 302
    post = app.db.session.query(Post).one()
    assert post.scheduled_at.strftime("%H:%M") == "18:30" and len(post.arts) == 1
    assert web.get(f"/postagens/{post.id}").status_code == 200
    assert "Pão de queijo" in web.get(f"/agenda?mes={day[:7]}").get_data(as_text=True)

    # o comerciante abre o link sem login
    token = app.db.session.get(Client, cid).approval_token
    public = app.test_client()
    page = public.get(f"/aprovar/{token}").get_data(as_text=True)
    assert "Saiu fornada!" in page
    art_id = post.arts[0].id
    assert public.get(f"/aprovar/{token}/arquivo/{art_id}").status_code == 200
    assert public.get(f"/arquivos/{art_id}").status_code == 302  # área interna continua fechada
    assert public.get("/aprovar/token-errado").status_code == 404

    csrf = _csrf(public, f"/aprovar/{token}")
    r = public.post(f"/aprovar/{token}/{post.id}", data={"_csrf": csrf, "acao": "ajuste", "comentario": ""})
    app.db.session.expire_all()
    assert app.db.session.get(Post, post.id).status == "aprovacao"  # ajuste exige comentário
    public.post(f"/aprovar/{token}/{post.id}", data={"_csrf": csrf, "acao": "ajuste", "comentario": "Preço 9,90"})
    app.db.session.expire_all()
    p = app.db.session.get(Post, post.id)
    assert p.status == "ajuste" and "Preço 9,90" in p.feedback

    web.post(f"/postagens/{post.id}/status", data={"_csrf": web.token, "status": "aprovacao"})
    public.post(f"/aprovar/{token}/{post.id}", data={"_csrf": csrf, "acao": "aprovar"})
    app.db.session.expire_all()
    p = app.db.session.get(Post, post.id)
    assert p.status == "aprovado" and p.approved_at

    web.post(f"/postagens/{post.id}/status", data={"_csrf": web.token, "status": "publicado"})
    app.db.session.expire_all()
    assert app.db.session.get(Post, post.id).published_at

    # excluir a postagem mantém a arte na pasta do cliente
    web.post(f"/postagens/{post.id}/excluir", data={"_csrf": web.token})
    app.db.session.expire_all()
    assert app.db.session.query(Post).count() == 0
    assert app.db.session.get(File, art_id).post_id is None


def test_archived_client_link_stops(web, app):
    cid = _new_client(web)
    token = app.db.session.get(Client, cid).approval_token
    web.post(f"/clientes/{cid}/ativo", data={"_csrf": web.token})
    assert app.test_client().get(f"/aprovar/{token}").status_code == 404


def test_internal_files_hidden_from_public(web, app):
    cid = _new_client(web)
    web.post(f"/clientes/{cid}/arquivos", content_type="multipart/form-data",
             data={"_csrf": web.token, "kind": "foto", "arquivos": [(io.BytesIO(PNG), "interna.png")]})
    f = app.db.session.query(File).one()
    token = app.db.session.get(Client, cid).approval_token
    assert app.test_client().get(f"/aprovar/{token}/arquivo/{f.id}").status_code == 404


def test_open_redirect_blocked(app):
    c = app.test_client()
    r = c.post("/entrar", data={"_csrf": _csrf(c), "email": "dono@ex.com", "password": "senha-forte-1",
                                "next": "//evil.com"})
    assert r.headers["Location"] == "/"


def test_art_editor_saves_png(web, app):
    cid = _new_client(web, address="Rua A, 1")
    day = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
    web.post("/postagens/nova", data={"_csrf": web.token, "client_id": str(cid), "date": day, "theme": "Promo"})
    post = app.db.session.query(Post).one()
    html = web.get(f"/clientes/{cid}/criar-arte?post={post.id}").get_data(as_text=True)
    assert "Rua A, 1" in html and "Salvar na postagem" in html
    r = web.post(f"/clientes/{cid}/criar-arte", content_type="multipart/form-data",
                 data={"_csrf": web.token, "post_id": str(post.id), "arte": (io.BytesIO(PNG), "a.png")})
    assert r.status_code == 200 and r.json["ok"] and r.json["voltar"] == f"/postagens/{post.id}"
    app.db.session.expire_all()
    assert len(app.db.session.get(Post, post.id).arts) == 1
    # outro tipo de arquivo é recusado
    r = web.post(f"/clientes/{cid}/criar-arte", content_type="multipart/form-data",
                 data={"_csrf": web.token, "arte": (io.BytesIO(b"%PDF-1.4"), "a.pdf")})
    assert r.status_code == 400
    assert app.db.session.query(File).count() == 1
    # postagem de outro cliente não é aceita
    other = _new_client(web, name="Outro")
    r = web.post(f"/clientes/{other}/criar-arte", content_type="multipart/form-data",
                 data={"_csrf": web.token, "post_id": str(post.id), "arte": (io.BytesIO(PNG), "b.png")})
    assert r.json["voltar"].startswith(f"/clientes/{other}")
