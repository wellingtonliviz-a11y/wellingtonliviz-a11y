"""Envio de e-mails por SMTP (Brevo, Resend, Gmail com senha de app, etc.)."""
import logging
import smtplib
from email.message import EmailMessage

from flask import current_app

log = logging.getLogger(__name__)


def send_mail(to: str, subject: str, text: str) -> bool:
    cfg = current_app.config
    outbox = cfg.get("MAIL_OUTBOX")
    if outbox is not None:  # usado nos testes
        outbox.append({"to": to, "subject": subject, "text": text})
        return True
    if not cfg["SMTP_HOST"]:
        log.warning("SMTP não configurado. E-mail para %s não enviado:\n%s\n%s", to, subject, text)
        return False

    msg = EmailMessage()
    msg["From"] = cfg["MAIL_FROM"] or cfg["SMTP_USER"]
    msg["To"] = to
    msg["Subject"] = subject
    if cfg["SUPPORT_EMAIL"]:
        msg["Reply-To"] = cfg["SUPPORT_EMAIL"]
    msg.set_content(text)
    try:
        if cfg["SMTP_PORT"] == 465:
            server = smtplib.SMTP_SSL(cfg["SMTP_HOST"], 465, timeout=15)
        else:
            server = smtplib.SMTP(cfg["SMTP_HOST"], cfg["SMTP_PORT"], timeout=15)
            server.starttls()
        with server:
            if cfg["SMTP_USER"]:
                server.login(cfg["SMTP_USER"], cfg["SMTP_PASSWORD"])
            server.send_message(msg)
        return True
    except (smtplib.SMTPException, OSError) as exc:
        log.error("Falha ao enviar e-mail para %s: %s", to, exc)
        return False


def _signature() -> str:
    cfg = current_app.config
    lines = ["", "—", f"Equipe {cfg['PRODUCT_NAME']}"]
    if cfg["SUPPORT_EMAIL"]:
        lines.append(f"Dúvidas: {cfg['SUPPORT_EMAIL']}")
    return "\n".join(lines)


def send_access_email(name: str, email: str, password: str) -> bool:
    cfg = current_app.config
    first = (name or "").strip().split(" ")[0]
    first = first[:1].upper() + first[1:].lower() if first else ""
    text = (
        f"Olá{', ' + first if first else ''}!\n\n"
        f"Sua compra foi aprovada e seu acesso ao {cfg['PRODUCT_NAME']} está pronto.\n\n"
        f"Acesse: {cfg['APP_URL']}/entrar\n"
        f"E-mail: {email}\n"
        f"Senha: {password}\n\n"
        "Dica: depois de entrar, troque a senha em \"Minha conta\".\n"
        "No celular, adicione o site à tela inicial para usar como um aplicativo."
        + _signature()
    )
    return send_mail(email, f"Seu acesso ao {cfg['PRODUCT_NAME']}", text)


def send_reactivated_email(name: str, email: str) -> bool:
    cfg = current_app.config
    text = (
        f"Olá!\n\nSeu acesso ao {cfg['PRODUCT_NAME']} foi liberado.\n\n"
        f"Entre em {cfg['APP_URL']}/entrar com o e-mail {email} e a sua senha de sempre.\n"
        f"Esqueceu a senha? Use \"Esqueci minha senha\": {cfg['APP_URL']}/esqueci"
        + _signature()
    )
    return send_mail(email, f"Seu acesso ao {cfg['PRODUCT_NAME']} foi liberado", text)


def send_reset_email(email: str, link: str) -> bool:
    cfg = current_app.config
    text = (
        f"Olá!\n\nRecebemos um pedido para criar uma nova senha no {cfg['PRODUCT_NAME']}.\n\n"
        f"Clique no link (vale por 1 hora): {link}\n\n"
        "Se não foi você, ignore este e-mail. Sua senha atual continua valendo."
        + _signature()
    )
    return send_mail(email, f"Nova senha do {cfg['PRODUCT_NAME']}", text)
