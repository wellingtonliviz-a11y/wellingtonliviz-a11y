"""Tabelas: equipe, tutores, pets, vacinas, acomodações, reservas, extras, pagamentos e diário."""
from datetime import date, datetime, timezone

from sqlalchemy import (Boolean, Column, Date, DateTime, ForeignKey, Index, Integer, String, Table, Text,
                        create_engine)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship, scoped_session, sessionmaker


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


SPECIES = {"cao": "Cão", "gato": "Gato"}
SIZES = {"P": "Pequeno", "M": "Médio", "G": "Grande"}
SIZE_ORDER = {"P": 1, "M": 2, "G": 3}
STATUS = {"reservada": "Reservada", "hospedado": "Hospedado", "finalizada": "Finalizada", "cancelada": "Cancelada"}
ACTIVE_STATUS = ("reservada", "hospedado")
PAY_METHODS = {"pix": "Pix", "dinheiro": "Dinheiro", "credito": "Cartão de crédito", "debito": "Cartão de débito"}
LOG_KINDS = {"alimentacao": "🍽️ Alimentação", "medicacao": "💊 Medicação", "passeio": "🦮 Passeio / recreação",
             "banho": "🛁 Banho / higiene", "saude": "🩺 Saúde", "observacao": "📝 Observação"}


class User(Base):
    """Pessoa da equipe do hotel."""
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(120), default="")
    password_hash: Mapped[str] = mapped_column(String(255))
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Tutor(Base):
    """Dono(a) do pet."""
    __tablename__ = "tutors"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120), index=True)
    phone: Mapped[str] = mapped_column(String(30), default="")
    email: Mapped[str] = mapped_column(String(255), default="")
    cpf: Mapped[str] = mapped_column(String(20), default="")
    address: Mapped[str] = mapped_column(String(300), default="")
    emergency_contact: Mapped[str] = mapped_column(String(200), default="")
    notes: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    pets: Mapped[list["Pet"]] = relationship(back_populates="tutor", order_by="Pet.name")
    bookings: Mapped[list["Booking"]] = relationship(back_populates="tutor", order_by="Booking.check_in.desc()")


class Pet(Base):
    __tablename__ = "pets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tutor_id: Mapped[int] = mapped_column(ForeignKey("tutors.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(80))
    species: Mapped[str] = mapped_column(String(10))            # cao | gato
    breed: Mapped[str] = mapped_column(String(80), default="")
    size: Mapped[str] = mapped_column(String(1), default="")    # P | M | G (cães)
    sex: Mapped[str] = mapped_column(String(1), default="")     # M | F
    birth_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    weight_kg: Mapped[str] = mapped_column(String(10), default="")
    neutered: Mapped[bool] = mapped_column(Boolean, default=False)
    food: Mapped[str] = mapped_column(String(300), default="")          # ração, quantidade e horários
    medications: Mapped[str] = mapped_column(String(300), default="")
    allergies: Mapped[str] = mapped_column(String(300), default="")
    behavior: Mapped[str] = mapped_column(String(300), default="")      # sociável, medroso, não divide espaço...
    vet_name: Mapped[str] = mapped_column(String(120), default="")
    vet_phone: Mapped[str] = mapped_column(String(30), default="")
    notes: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    tutor: Mapped[Tutor] = relationship(back_populates="pets")
    vaccines: Mapped[list["Vaccine"]] = relationship(back_populates="pet", cascade="all, delete-orphan",
                                                     order_by="Vaccine.valid_until.desc()")

    @property
    def icon(self) -> str:
        return "🐶" if self.species == "cao" else "🐱"

    def age_text(self, today: date) -> str:
        if not self.birth_date:
            return ""
        months = (today.year - self.birth_date.year) * 12 + today.month - self.birth_date.month
        if today.day < self.birth_date.day:
            months -= 1
        if months < 12:
            return f"{max(months, 0)} {'mês' if months == 1 else 'meses'}"
        years = months // 12
        return f"{years} {'ano' if years == 1 else 'anos'}"

    def vaccine_issues(self, ref: date) -> list[str]:
        """Problemas de vacina na data `ref` (normalmente o dia da saída). Vale a dose mais recente de cada nome."""
        if not self.vaccines:
            return ["nenhuma vacina cadastrada"]
        latest: dict[str, Vaccine] = {}
        for v in self.vaccines:
            key = v.name.strip().lower()
            if key not in latest or v.valid_until > latest[key].valid_until:
                latest[key] = v
        return [f"{v.name} vence em {v.valid_until:%d/%m/%Y}" for v in latest.values() if v.valid_until < ref]


class Vaccine(Base):
    __tablename__ = "vaccines"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    pet_id: Mapped[int] = mapped_column(ForeignKey("pets.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(60))               # V10, Antirrábica, Gripe, V4...
    applied_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    valid_until: Mapped[date] = mapped_column(Date)

    pet: Mapped[Pet] = relationship(back_populates="vaccines")


class Room(Base):
    """Baia, suíte ou gatil. Cada reserva ocupa a acomodação inteira (uma família por vez)."""
    __tablename__ = "rooms"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(60))
    species: Mapped[str] = mapped_column(String(10))            # cao | gato
    max_size: Mapped[str] = mapped_column(String(1), default="G")  # maior porte de cão aceito
    capacity: Mapped[int] = mapped_column(Integer, default=1)   # pets da mesma família
    daily_rate_cents: Mapped[int] = mapped_column(Integer, default=0)  # diária por pet
    description: Mapped[str] = mapped_column(String(200), default="")
    active: Mapped[bool] = mapped_column(Boolean, default=True)


booking_pets = Table(
    "booking_pets", Base.metadata,
    Column("booking_id", ForeignKey("bookings.id", ondelete="CASCADE"), primary_key=True),
    Column("pet_id", ForeignKey("pets.id", ondelete="CASCADE"), primary_key=True),
)


class Booking(Base):
    """Reserva / hospedagem. A diária fica gravada na reserva: mudar o preço da acomodação não altera reservas antigas."""
    __tablename__ = "bookings"
    __table_args__ = (Index("ix_bookings_room_dates", "room_id", "check_in", "check_out"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tutor_id: Mapped[int] = mapped_column(ForeignKey("tutors.id", ondelete="CASCADE"), index=True)
    room_id: Mapped[int] = mapped_column(ForeignKey("rooms.id"))
    check_in: Mapped[date] = mapped_column(Date)
    check_out: Mapped[date] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(12), default="reservada")
    daily_rate_cents: Mapped[int] = mapped_column(Integer, default=0)
    discount_cents: Mapped[int] = mapped_column(Integer, default=0)
    notes: Mapped[str] = mapped_column(Text, default="")
    belongings: Mapped[str] = mapped_column(String(300), default="")   # o que o pet trouxe (caminha, brinquedo...)
    checked_in_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    checked_out_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    tutor: Mapped[Tutor] = relationship(back_populates="bookings")
    room: Mapped[Room] = relationship()
    pets: Mapped[list[Pet]] = relationship(secondary=booking_pets, order_by="Pet.name")
    extras: Mapped[list["Extra"]] = relationship(cascade="all, delete-orphan", order_by="Extra.id")
    payments: Mapped[list["Payment"]] = relationship(cascade="all, delete-orphan", order_by="Payment.paid_on")
    logs: Mapped[list["LogEntry"]] = relationship(cascade="all, delete-orphan", order_by="LogEntry.created_at.desc()")

    @property
    def nights(self) -> int:
        return max((self.check_out - self.check_in).days, 1)

    @property
    def lodging_cents(self) -> int:
        return self.nights * self.daily_rate_cents * max(len(self.pets), 1)

    @property
    def extras_cents(self) -> int:
        return sum(e.price_cents for e in self.extras)

    @property
    def total_cents(self) -> int:
        if self.status == "cancelada":
            return 0
        return max(self.lodging_cents + self.extras_cents - self.discount_cents, 0)

    @property
    def paid_cents(self) -> int:
        return sum(p.amount_cents for p in self.payments)

    @property
    def balance_cents(self) -> int:
        return self.total_cents - self.paid_cents

    @property
    def pet_names(self) -> str:
        return ", ".join(p.name for p in self.pets)


class Extra(Base):
    """Serviço adicional cobrado na reserva (banho, tosa, transporte, adestramento...)."""
    __tablename__ = "extras"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    booking_id: Mapped[int] = mapped_column(ForeignKey("bookings.id", ondelete="CASCADE"), index=True)
    description: Mapped[str] = mapped_column(String(120))
    price_cents: Mapped[int] = mapped_column(Integer)


class Payment(Base):
    __tablename__ = "payments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    booking_id: Mapped[int] = mapped_column(ForeignKey("bookings.id", ondelete="CASCADE"), index=True)
    amount_cents: Mapped[int] = mapped_column(Integer)
    method: Mapped[str] = mapped_column(String(10))
    paid_on: Mapped[date] = mapped_column(Date, index=True)
    note: Mapped[str] = mapped_column(String(120), default="")


class LogEntry(Base):
    """Diário da hospedagem: o que aconteceu com o pet (comeu, tomou remédio, passeou...)."""
    __tablename__ = "log_entries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    booking_id: Mapped[int] = mapped_column(ForeignKey("bookings.id", ondelete="CASCADE"), index=True)
    pet_id: Mapped[int | None] = mapped_column(ForeignKey("pets.id", ondelete="SET NULL"), nullable=True)
    kind: Mapped[str] = mapped_column(String(12))
    text: Mapped[str] = mapped_column(String(500))
    user_name: Mapped[str] = mapped_column(String(120), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    pet: Mapped[Pet | None] = relationship()


class Database:
    def __init__(self, url: str):
        self.engine = create_engine(url, pool_pre_ping=True)
        self.session = scoped_session(sessionmaker(bind=self.engine, expire_on_commit=False))
        Base.metadata.create_all(self.engine)
