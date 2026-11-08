"""Simulador no terminal: teste o robô sem precisar da conta da Meta.

Uso:
    python simulate.py

Comandos especiais:
    /vendedor  -> passa a falar como vendedor (comandos com #)
    /cliente   -> volta a falar como cliente
    /sair      -> encerra
"""
from bot.config import Config
from bot.db import Database
from bot.handlers import SalesBot

CUSTOMER = "5511900000001"
SELLER = "5511900000099"


def main():
    Config.ADMIN_PHONES = [SELLER]
    db = Database("simulador.db")
    bot = SalesBot(db)
    if not db.list_products():
        for code, name, price, stock in [
            ("P01", "Bolo de pote de chocolate", 1290, 10),
            ("P02", "Brigadeiro gourmet (cx 6un)", 1800, 5),
            ("P03", "Torta de limão (fatia)", 990, None),
        ]:
            db.upsert_product(code, name, price, stock)

    me = CUSTOMER
    print("Simulador do robô. Digite 'oi' para começar. /vendedor, /cliente, /sair\n")
    while True:
        who = "vendedor" if me == SELLER else "cliente"
        try:
            text = input(f"[{who}] > ")
        except (EOFError, KeyboardInterrupt):
            break
        if text == "/sair":
            break
        if text in ("/vendedor", "/cliente"):
            me = SELLER if text == "/vendedor" else CUSTOMER
            continue
        for out in bot.handle(me, text, name="Maria Cliente" if me == CUSTOMER else "Vendedor"):
            dest = "vendedor" if out.to == SELLER else ("cliente" if out.to == CUSTOMER else out.to)
            print(f"\n--- robô → {dest} ---\n{out.text}\n")


if __name__ == "__main__":
    main()
