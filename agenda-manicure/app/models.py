"""Tabelas do banco: clientes (manicures), dados do sistema, compras e agendamentos."""
from datetime import datetime, timezone

from sqlalchemy import (Boolean, DateTime, ForeignKey, Index, Integer, LargeBinary, String, Text, UniqueConstraint,
                        create_engine)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, scoped_session, sessionmaker


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255), default="")
    password_hash: Mapped[str] = mapped_column(String(255))
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    access_email_sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class UserData(Base):
    __tablename__ = "user_data"

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    data: Mapped[str] = mapped_column(Text)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Purchase(Base):
    __tablename__ = "purchases"
    __table_args__ = (UniqueConstraint("platform", "transaction_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    platform: Mapped[str] = mapped_column(String(20))         # hotmart | kiwify | manual
    transaction_id: Mapped[str] = mapped_column(String(120))
    email: Mapped[str] = mapped_column(String(255), index=True)
    product_id: Mapped[str] = mapped_column(String(120), default="")
    status: Mapped[str] = mapped_column(String(20))           # ativa | revogada
    last_event: Mapped[str] = mapped_column(String(60), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class BookingLink(Base):
    """Endereço público da página de agendamento (/a/<slug>)."""
    __tablename__ = "booking_links"

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    slug: Mapped[str] = mapped_column(String(40), unique=True, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Appointment(Base):
    """Um horário na agenda. Data e hora ficam no horário local da manicure (TIMEZONE)."""
    __tablename__ = "appointments"
    __table_args__ = (Index("ix_appointments_user_day", "user_id", "day"),)

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    day: Mapped[str] = mapped_column(String(10))                  # AAAA-MM-DD
    start_min: Mapped[int] = mapped_column(Integer)                # minutos desde 00:00
    duration: Mapped[int] = mapped_column(Integer)                 # minutos
    status: Mapped[str] = mapped_column(String(12))                # pendente | confirmado | concluido | cancelado | bloqueio
    source: Mapped[str] = mapped_column(String(10), default="manual")  # online | manual
    client_name: Mapped[str] = mapped_column(String(120), default="")
    client_phone: Mapped[str] = mapped_column(String(20), default="")
    services: Mapped[str] = mapped_column(String(300), default="")  # nomes, ex: "Pé + Mão"
    price_cents: Mapped[int] = mapped_column(Integer, default=0)
    note: Mapped[str] = mapped_column(String(300), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Photo(Base):
    """Fotos dos serviços (já reduzidas no navegador)."""
    __tablename__ = "photos"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    mime: Mapped[str] = mapped_column(String(20))
    data: Mapped[bytes] = mapped_column(LargeBinary)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Database:
    def __init__(self, url: str):
        self.engine = create_engine(url, pool_pre_ping=True)
        self.session = scoped_session(sessionmaker(bind=self.engine, expire_on_commit=False))
        Base.metadata.create_all(self.engine)
