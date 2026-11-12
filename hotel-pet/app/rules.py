"""Regras de reserva: datas, espécie, porte, capacidade e acomodação livre."""
from datetime import date

from sqlalchemy import select

from .models import ACTIVE_STATUS, SIZE_ORDER, Booking, Pet, Room, Tutor


def overlapping(db, room_id: int, check_in: date, check_out: date, exclude_id: int | None = None) -> list[Booking]:
    """Reservas ativas na mesma acomodação que cruzam o período. A saída libera a vaga no mesmo dia."""
    q = select(Booking).where(Booking.room_id == room_id, Booking.status.in_(ACTIVE_STATUS),
                              Booking.check_in < check_out, Booking.check_out > check_in)
    if exclude_id:
        q = q.where(Booking.id != exclude_id)
    return list(db.scalars(q.order_by(Booking.check_in)))


def booking_errors(db, tutor: Tutor | None, room: Room | None, pets: list[Pet], check_in: date | None,
                   check_out: date | None, exclude_id: int | None = None) -> list[str]:
    errors = []
    if tutor is None:
        errors.append("Escolha o tutor.")
    if room is None or not room.active:
        errors.append("Escolha uma acomodação.")
    if not pets:
        errors.append("Escolha pelo menos um pet.")
    if check_in is None or check_out is None:
        errors.append("Informe as datas de entrada e saída.")
    elif check_out <= check_in:
        errors.append("A saída precisa ser depois da entrada (mínimo de uma diária).")
    if errors:
        return errors

    if any(p.tutor_id != tutor.id for p in pets):
        errors.append("Todos os pets precisam ser do mesmo tutor.")
    if len(pets) > room.capacity:
        errors.append(f"{room.name} comporta {room.capacity} pet(s); você escolheu {len(pets)}.")
    for p in pets:
        if p.species != room.species:
            errors.append(f"{p.name} é {'cão' if p.species == 'cao' else 'gato'} e {room.name} é para "
                          f"{'cães' if room.species == 'cao' else 'gatos'}.")
        elif p.species == "cao" and p.size and SIZE_ORDER.get(p.size, 0) > SIZE_ORDER.get(room.max_size, 3):
            errors.append(f"{p.name} é de porte {p.size} e {room.name} aceita até porte {room.max_size}.")
    for b in overlapping(db, room.id, check_in, check_out, exclude_id):
        errors.append(f"{room.name} já está ocupada de {b.check_in:%d/%m} a {b.check_out:%d/%m} "
                      f"({b.pet_names}).")
    return errors


def free_rooms(db, check_in: date, check_out: date, species: str | None = None) -> list[Room]:
    rooms = db.scalars(select(Room).where(Room.active.is_(True)).order_by(Room.species, Room.name))
    return [r for r in rooms if (species is None or r.species == species)
            and not overlapping(db, r.id, check_in, check_out)]
