from werkzeug.security import generate_password_hash


def hash_password(password: str) -> str:
    return generate_password_hash(password, method="pbkdf2:sha256:600000")


def normalize_email(email: str) -> str:
    return (email or "").strip().lower()
