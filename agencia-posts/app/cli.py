"""Comandos de terminal: flask --app wsgi criar-usuario email@exemplo.com"""
import click
from flask import Flask, current_app
from sqlalchemy import select
from werkzeug.security import generate_password_hash

from .models import User


def register(app: Flask) -> None:
    @app.cli.command("criar-usuario")
    @click.argument("email")
    @click.option("--nome", default="")
    @click.password_option("--senha", prompt="Senha")
    def create_user(email: str, nome: str, senha: str):
        """Cria (ou troca a senha de) quem pode entrar no sistema."""
        db = current_app.db.session
        email = email.strip().lower()
        user = db.scalar(select(User).where(User.email == email))
        if user is None:
            user = User(email=email, name=nome, password_hash="")
            db.add(user)
        user.password_hash = generate_password_hash(senha)
        user.active = True
        db.commit()
        click.echo(f"Pronto: {email} pode entrar.")
