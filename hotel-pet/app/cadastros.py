"""Tutores, pets e vacinas."""
from flask import Blueprint, abort, current_app, flash, redirect, render_template, request, url_for
from sqlalchemy import func, or_, select

from .models import SIZES, SPECIES, Pet, Tutor, Vaccine
from .security import login_required
from .util import parse_date

bp = Blueprint("cadastros", __name__)

TUTOR_FIELDS = ("name", "phone", "email", "cpf", "address", "emergency_contact", "notes")
PET_TEXT_FIELDS = ("name", "breed", "weight_kg", "food", "medications", "allergies", "behavior",
                   "vet_name", "vet_phone", "notes")


def _get(model, obj_id):
    obj = current_app.db.session.get(model, obj_id) if obj_id else None
    if obj is None:
        abort(404)
    return obj


# ---------- Tutores ----------

@bp.get("/tutores")
@login_required
def tutors():
    db = current_app.db.session
    q = request.args.get("q", "").strip()
    stmt = select(Tutor).order_by(Tutor.name)
    if q:
        like = f"%{q.lower()}%"
        pet_owner = select(Pet.tutor_id).where(func.lower(Pet.name).like(like))
        stmt = stmt.where(or_(func.lower(Tutor.name).like(like), Tutor.phone.like(f"%{q}%"),
                              Tutor.id.in_(pet_owner)))
    return render_template("tutores.html", tutors=db.scalars(stmt.limit(200)).all(), q=q)


@bp.route("/tutores/novo", methods=["GET", "POST"])
@bp.route("/tutores/<int:tutor_id>/editar", methods=["GET", "POST"])
@login_required
def tutor_form(tutor_id=None):
    db = current_app.db.session
    tutor = _get(Tutor, tutor_id) if tutor_id else Tutor()
    if request.method == "POST":
        for f in TUTOR_FIELDS:
            setattr(tutor, f, request.form.get(f, "").strip())
        if not tutor.name:
            flash("Informe o nome do tutor.", "erro")
        elif not tutor.phone:
            flash("Informe um telefone (WhatsApp) para contato.", "erro")
        else:
            if tutor.id is None:
                db.add(tutor)
            db.commit()
            flash("Tutor salvo.", "ok")
            if tutor_id is None:
                return redirect(url_for("cadastros.pet_form", tutor=tutor.id))
            return redirect(url_for("cadastros.tutor", tutor_id=tutor.id))
        db.rollback()
    return render_template("tutor_form.html", tutor=tutor)


@bp.get("/tutores/<int:tutor_id>")
@login_required
def tutor(tutor_id):
    return render_template("tutor.html", tutor=_get(Tutor, tutor_id))


# ---------- Pets ----------

@bp.route("/pets/novo", methods=["GET", "POST"])
@bp.route("/pets/<int:pet_id>/editar", methods=["GET", "POST"])
@login_required
def pet_form(pet_id=None):
    db = current_app.db.session
    if pet_id:
        pet = _get(Pet, pet_id)
        tutor = pet.tutor
    else:
        tutor = _get(Tutor, request.args.get("tutor", type=int))
        pet = Pet(tutor_id=tutor.id, species="cao")
    if request.method == "POST":
        for f in PET_TEXT_FIELDS:
            setattr(pet, f, request.form.get(f, "").strip())
        pet.species = request.form.get("species", "")
        pet.size = request.form.get("size", "") if pet.species == "cao" else ""
        pet.sex = request.form.get("sex", "") if request.form.get("sex") in ("M", "F") else ""
        pet.birth_date = parse_date(request.form.get("birth_date"))
        pet.neutered = request.form.get("neutered") == "1"
        if not pet.name:
            flash("Informe o nome do pet.", "erro")
        elif pet.species not in SPECIES:
            flash("Escolha se é cão ou gato.", "erro")
        elif pet.species == "cao" and pet.size not in SIZES:
            flash("Escolha o porte do cão.", "erro")
        else:
            if pet.id is None:
                db.add(pet)
            db.commit()
            flash(f"{pet.name} salvo(a). Cadastre as vacinas abaixo.", "ok")
            return redirect(url_for("cadastros.pet", pet_id=pet.id))
        db.rollback()
    return render_template("pet_form.html", pet=pet, tutor=tutor)


@bp.get("/pets/<int:pet_id>")
@login_required
def pet(pet_id):
    from .models import Booking, booking_pets
    pet = _get(Pet, pet_id)
    stays = current_app.db.session.scalars(
        select(Booking).join(booking_pets).where(booking_pets.c.pet_id == pet.id)
        .order_by(Booking.check_in.desc())).all()
    return render_template("pet.html", pet=pet, stays=stays)


@bp.post("/pets/<int:pet_id>/vacinas")
@login_required
def vaccine_add(pet_id):
    db = current_app.db.session
    pet = _get(Pet, pet_id)
    name = request.form.get("name", "").strip()
    valid_until = parse_date(request.form.get("valid_until"))
    applied_on = parse_date(request.form.get("applied_on"))
    if not name or valid_until is None:
        flash("Informe o nome da vacina e a validade.", "erro")
    elif applied_on and applied_on > valid_until:
        flash("A data de aplicação está depois da validade.", "erro")
    else:
        db.add(Vaccine(pet_id=pet.id, name=name, applied_on=applied_on, valid_until=valid_until))
        db.commit()
        flash(f"Vacina {name} cadastrada.", "ok")
    return redirect(url_for("cadastros.pet", pet_id=pet.id) + "#vacinas")


@bp.post("/vacinas/<int:vaccine_id>/excluir")
@login_required
def vaccine_delete(vaccine_id):
    db = current_app.db.session
    v = _get(Vaccine, vaccine_id)
    pet_id = v.pet_id
    db.delete(v)
    db.commit()
    flash("Vacina removida.", "ok")
    return redirect(url_for("cadastros.pet", pet_id=pet_id) + "#vacinas")
