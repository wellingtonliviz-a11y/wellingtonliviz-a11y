"""Tabelas: equipe, clientes (comércios), arquivos e postagens.

Todas começam com "ag_" para poderem dividir o mesmo PostgreSQL com outros sistemas.
"""
import secrets
import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, LargeBinary, String, Text, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship, scoped_session, sessionmaker


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def new_token() -> str:
    return secrets.token_urlsafe(24)


class Base(DeclarativeBase):
    pass


class User(Base):
    """Quem usa o sistema (você e, se quiser, alguém da equipe)."""
    __tablename__ = "ag_users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(120), default="")
    password_hash: Mapped[str] = mapped_column(String(255))
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Client(Base):
    """Um comércio atendido: identidade visual, contato e contrato."""
    __tablename__ = "ag_clients"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    segment: Mapped[str] = mapped_column(String(80), default="")
    instagram: Mapped[str] = mapped_column(String(80), default="")
    contact_name: Mapped[str] = mapped_column(String(120), default="")
    phone: Mapped[str] = mapped_column(String(40), default="")
    email: Mapped[str] = mapped_column(String(255), default="")
    address: Mapped[str] = mapped_column(String(200), default="")           # sai no rodapé das artes
    color_primary: Mapped[str] = mapped_column(String(7), default="#7c3aed")
    color_secondary: Mapped[str] = mapped_column(String(7), default="#f59e0b")
    fonts: Mapped[str] = mapped_column(String(200), default="")
    voice: Mapped[str] = mapped_column(Text, default="")      # tom de voz, público, o que evitar
    notes: Mapped[str] = mapped_column(Text, default="")
    monthly_fee_cents: Mapped[int | None] = mapped_column(Integer, nullable=True)
    payment_day: Mapped[int | None] = mapped_column(Integer, nullable=True)
    posts_per_month: Mapped[int] = mapped_column(Integer, default=12)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    logo_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    # link secreto da página onde o cliente aprova as artes
    approval_token: Mapped[str] = mapped_column(String(64), unique=True, index=True, default=new_token)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class File(Base):
    """Logo, foto enviada pelo cliente ou arte pronta. Fica no banco (o disco do Render é apagado a cada deploy)."""
    __tablename__ = "ag_files"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=lambda: uuid.uuid4().hex)
    client_id: Mapped[int] = mapped_column(ForeignKey("ag_clients.id", ondelete="CASCADE"), index=True)
    post_id: Mapped[int | None] = mapped_column(ForeignKey("ag_posts.id", ondelete="SET NULL"),
                                                nullable=True, index=True)
    kind: Mapped[str] = mapped_column(String(20))            # logo | foto | arte | outro
    name: Mapped[str] = mapped_column(String(200), default="")
    mime: Mapped[str] = mapped_column(String(40))
    size: Mapped[int] = mapped_column(Integer, default=0)
    data: Mapped[bytes] = mapped_column(LargeBinary, deferred=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Post(Base):
    """Uma postagem programada para um cliente."""
    __tablename__ = "ag_posts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    client_id: Mapped[int] = mapped_column(ForeignKey("ag_clients.id", ondelete="CASCADE"), index=True)
    scheduled_at: Mapped[datetime] = mapped_column(DateTime, index=True)   # horário local, sem fuso
    format: Mapped[str] = mapped_column(String(20), default="feed")
    status: Mapped[str] = mapped_column(String(20), default="ideia", index=True)
    theme: Mapped[str] = mapped_column(String(200), default="")
    caption: Mapped[str] = mapped_column(Text, default="")
    hashtags: Mapped[str] = mapped_column(Text, default="")
    link: Mapped[str] = mapped_column(String(500), default="")             # Drive, Canva, vídeo...
    notes: Mapped[str] = mapped_column(Text, default="")
    feedback: Mapped[str] = mapped_column(Text, default="")                # o que o cliente respondeu
    approved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    client: Mapped[Client] = relationship(lazy="joined")
    arts: Mapped[list[File]] = relationship(lazy="selectin", order_by=File.created_at)


class Database:
    def __init__(self, url: str):
        self.engine = create_engine(url, pool_pre_ping=True)
        self.session = scoped_session(sessionmaker(bind=self.engine, expire_on_commit=False))
        Base.metadata.create_all(self.engine)
