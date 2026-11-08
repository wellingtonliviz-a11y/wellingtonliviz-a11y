"""Lógica de conversa do robô.

Esta camada não sabe nada de WhatsApp: recebe (telefone, texto) e devolve uma
lista de mensagens a enviar. Assim dá para testar e simular no terminal.
"""
import re
import unicodedata
from dataclasses import dataclass
from datetime import datetime, timedelta

from .config import Config, only_digits
from .db import Database

STATUSES = {
    "novo": "🆕 Recebido",
    "confirmado": "✅ Confirmado",
    "preparando": "👩‍🍳 Em preparação",
    "enviado": "🚚 Saiu para entrega",
    "entregue": "📦 Entregue",
    "cancelado": "❌ Cancelado",
}

CUSTOMER_STATUS_MSG = {
    "confirmado": "Seu pedido *#{id}* foi confirmado! ✅ Já estamos cuidando dele.",
    "preparando": "Seu pedido *#{id}* está sendo preparado. 👩‍🍳",
    "enviado": "Seu pedido *#{id}* saiu para entrega! 🚚",
    "entregue": "Seu pedido *#{id}* foi entregue. 📦 Obrigado pela compra! 💚",
    "cancelado": "Seu pedido *#{id}* foi cancelado. Qualquer dúvida, é só chamar.",
}


@dataclass
class Outgoing:
    to: str
    text: str


def money(cents: int) -> str:
    s = f"{cents / 100:,.2f}"  # 1,234.56
    return "R$ " + s.replace(",", "X").replace(".", ",").replace("X", ".")


def parse_money(text: str) -> int | None:
    """Aceita '25', '25,90', '25.90', 'R$ 1.234,56'. Retorna centavos."""
    t = text.strip().lower().replace("r$", "").replace(" ", "")
    if not t:
        return None
    if "," in t:
        t = t.replace(".", "").replace(",", ".")
    elif t.count(".") > 1 or re.fullmatch(r"\d{1,3}(\.\d{3})+", t):
        t = t.replace(".", "")
    try:
        value = round(float(t) * 100)
    except ValueError:
        return None
    return value if value >= 0 else None


def normalize(text: str) -> str:
    text = unicodedata.normalize("NFKD", text.strip().lower())
    return "".join(ch for ch in text if not unicodedata.combining(ch))


class SalesBot:
    def __init__(self, db: Database, config: type[Config] = Config):
        self.db = db
        self.cfg = config

    # ------------------------------------------------------------------ entrada
    def handle(self, phone: str, text: str, name: str | None = None) -> list[Outgoing]:
        phone = only_digits(phone)
        text = (text or "").strip()
        if phone in self.cfg.ADMIN_PHONES and text.startswith("#"):
            return self.handle_admin(phone, text)
        return self.handle_customer(phone, text, name)

    # ------------------------------------------------------------------ cliente
    def handle_customer(self, phone: str, text: str, name: str | None) -> list[Outgoing]:
        customer = self.db.get_customer(phone, name)
        state = customer["state"]
        cmd = normalize(text)
        reply = lambda msg: [Outgoing(phone, msg)]  # noqa: E731

        # Em atendimento humano: o robô fica quieto, a não ser que peçam o menu
        if state == "human":
            if cmd in ("menu", "voltar", "robo"):
                self.db.set_state(phone, "idle")
                return reply(self.menu_text(customer["name"]))
            return []

        if state == "awaiting_address":
            if cmd in ("cancelar", "voltar", "menu", "0"):
                self.db.set_state(phone, "idle")
                return reply("Ok, finalização cancelada. Seu carrinho continua salvo. 🛒\n\n"
                             + self.menu_text(customer["name"]))
            return self.finish_order(phone, text, customer["name"])

        if cmd in ("", "oi", "ola", "menu", "0", "inicio", "bom dia", "boa tarde", "boa noite"):
            return reply(self.menu_text(customer["name"]))
        if cmd in ("1", "catalogo", "produtos", "cardapio"):
            return reply(self.catalog_text())
        if cmd in ("2", "carrinho"):
            return reply(self.cart_text(phone))
        if cmd in ("3", "finalizar", "fechar", "fechar pedido"):
            return self.start_checkout(phone)
        if cmd in ("4", "pedidos", "meus pedidos", "status"):
            return reply(self.my_orders_text(phone))
        if cmd in ("5", "atendente", "humano", "vendedor"):
            return self.call_human(phone, customer["name"])
        if cmd in ("6", "horario", "pix", "pagamento", "info"):
            return reply(self.info_text())
        if cmd in ("limpar", "esvaziar"):
            self.db.clear_cart(phone)
            return reply("Carrinho esvaziado. 🧹")

        m = re.fullmatch(r"(?:remover|tirar)\s+(\S+)", cmd)
        if m:
            product = self.db.get_product(m.group(1))
            if product and self.db.remove_from_cart(phone, product["id"]):
                return reply(f"Removi *{product['name']}* do carrinho.\n\n" + self.cart_text(phone))
            return reply("Esse produto não está no seu carrinho.")

        # "add P01 2", "quero P01", "comprar 2 P01" ou só "P01"
        m = re.fullmatch(r"(?:add|adicionar|quero|comprar)?\s*(?:(\d+)\s*x?\s+)?([a-z0-9-]+)(?:\s+(\d+))?",
                         cmd)
        if m:
            code = m.group(2)
            qty = int(m.group(1) or m.group(3) or 1)
            product = self.db.get_product(code)
            if product and product["active"]:
                return reply(self.add_item(phone, product, qty))

        return reply("Não entendi 🤔\n\n" + self.menu_text(customer["name"]))

    def menu_text(self, name: str | None = None) -> str:
        hello = f"Olá, {name.split()[0]}! 👋" if name else "Olá! 👋"
        return (
            f"{hello} Bem-vindo(a) à *{self.cfg.STORE_NAME}*.\n\n"
            "Digite o número da opção:\n"
            "1️⃣ Ver catálogo\n"
            "2️⃣ Meu carrinho\n"
            "3️⃣ Finalizar pedido\n"
            "4️⃣ Meus pedidos\n"
            "5️⃣ Falar com atendente\n"
            "6️⃣ Horário e pagamento"
        )

    def catalog_text(self) -> str:
        products = self.db.list_products()
        if not products:
            return "Nosso catálogo está sendo atualizado. Volte daqui a pouco! 🙏"
        lines = [f"🛍️ *Catálogo {self.cfg.STORE_NAME}*\n"]
        for p in products:
            if p["stock"] is not None and p["stock"] <= 0:
                extra = " _(esgotado)_"
            elif p["stock"] is not None and p["stock"] <= 3:
                extra = f" _(últimas {p['stock']})_"
            else:
                extra = ""
            lines.append(f"*{p['code']}* - {p['name']} — {money(p['price_cents'])}{extra}")
        lines.append("\nPara comprar, envie o *código* e a quantidade.\nEx: *add "
                     f"{products[0]['code']} 2*")
        return "\n".join(lines)

    def add_item(self, phone: str, product, qty: int) -> str:
        if qty <= 0:
            return "A quantidade precisa ser maior que zero."
        in_cart = self.db.cart_qty(phone, product["id"])
        if product["stock"] is not None and in_cart + qty > product["stock"]:
            if product["stock"] <= 0:
                return f"Poxa, *{product['name']}* está esgotado no momento. 😕"
            return (f"Temos apenas {product['stock']} unidade(s) de *{product['name']}* "
                    f"(você já tem {in_cart} no carrinho).")
        total_qty = self.db.add_to_cart(phone, product["id"], qty)
        return (f"✅ Adicionado: {qty}x *{product['name']}* "
                f"(agora {total_qty} no carrinho).\n\n"
                "Digite *2* para ver o carrinho ou *3* para finalizar.")

    def cart_text(self, phone: str) -> str:
        items = self.db.get_cart(phone)
        if not items:
            return "Seu carrinho está vazio. Digite *1* para ver o catálogo. 🛒"
        lines = ["🛒 *Seu carrinho*\n"]
        subtotal = 0
        for it in items:
            line_total = it["price_cents"] * it["qty"]
            subtotal += line_total
            lines.append(f"{it['qty']}x {it['name']} ({it['code']}) — {money(line_total)}")
        lines.append(f"\nSubtotal: *{money(subtotal)}*")
        if self.cfg.DELIVERY_FEE_CENTS:
            lines.append(f"Entrega: {money(self.cfg.DELIVERY_FEE_CENTS)}")
            lines.append(f"Total: *{money(subtotal + self.cfg.DELIVERY_FEE_CENTS)}*")
        lines.append("\n*3* finalizar · *remover CÓDIGO* · *limpar*")
        return "\n".join(lines)

    def start_checkout(self, phone: str) -> list[Outgoing]:
        if not self.db.get_cart(phone):
            return [Outgoing(phone, "Seu carrinho está vazio. Digite *1* para ver o catálogo. 🛒")]
        self.db.set_state(phone, "awaiting_address")
        return [Outgoing(phone, self.cart_text(phone).rsplit("\n\n", 1)[0] + "\n\n"
                         "📍 Para finalizar, envie o *endereço de entrega* "
                         "(rua, número, bairro) ou digite *retirada* para retirar no local.\n"
                         "Digite *cancelar* para voltar.")]

    def finish_order(self, phone: str, address_text: str, name: str | None) -> list[Outgoing]:
        pickup = normalize(address_text) in ("retirada", "retirar", "buscar")
        if not pickup and len(address_text) < 8:
            return [Outgoing(phone, "Hmm, esse endereço parece incompleto. Envie rua, número e "
                                    "bairro, ou *retirada*.")]
        address = "Retirada no local" if pickup else address_text
        fee = 0 if pickup else self.cfg.DELIVERY_FEE_CENTS
        result = self.db.create_order(phone, address, fee)
        self.db.set_state(phone, "idle")
        if isinstance(result, str):
            return [Outgoing(phone, result)]

        order = self.db.get_order(result)
        msg = (f"🎉 Pedido *#{order['id']}* recebido!\n\n"
               f"{self.order_items_text(order['id'])}\n"
               f"Total: *{money(order['total_cents'])}*\n"
               f"Entrega: {address}\n")
        if self.cfg.PIX_KEY:
            msg += (f"\n💸 Pague via *Pix*: `{self.cfg.PIX_KEY}`\n"
                    "Depois envie o comprovante aqui mesmo.\n")
        msg += "\nVocê vai receber atualizações por aqui. Digite *4* para acompanhar."

        out = [Outgoing(phone, msg)]
        alert = (f"🔔 *Novo pedido #{order['id']}*\n"
                 f"Cliente: {name or 'sem nome'} (wa.me/{phone})\n\n"
                 f"{self.order_items_text(order['id'])}\n"
                 f"Total: *{money(order['total_cents'])}*\n"
                 f"Entrega: {address}\n\n"
                 f"Confirmar: *#status {order['id']} confirmado*")
        out += [Outgoing(admin, alert) for admin in self.cfg.ADMIN_PHONES]
        return out

    def order_items_text(self, order_id: int) -> str:
        return "\n".join(
            f"{it['qty']}x {it['name']} — {money(it['price_cents'] * it['qty'])}"
            for it in self.db.get_order_items(order_id)
        )

    def my_orders_text(self, phone: str) -> str:
        orders = self.db.list_orders(phone=phone, limit=5)
        if not orders:
            return "Você ainda não fez pedidos. Digite *1* para ver o catálogo. 🛍️"
        lines = ["📋 *Seus últimos pedidos*\n"]
        for o in orders:
            lines.append(f"*#{o['id']}* — {money(o['total_cents'])} — "
                         f"{STATUSES.get(o['status'], o['status'])}")
        return "\n".join(lines)

    def call_human(self, phone: str, name: str | None) -> list[Outgoing]:
        self.db.set_state(phone, "human")
        out = [Outgoing(phone, "Certo! Um atendente vai falar com você em breve. 🙋\n"
                               "(Para voltar ao menu automático, digite *menu*.)")]
        alert = (f"🙋 *{name or phone}* pediu atendimento humano.\n"
                 f"Fale direto: wa.me/{phone}\n"
                 f"Ou responda por aqui: *#responder {phone} sua mensagem*\n"
                 f"Ao terminar: *#bot {phone}*")
        out += [Outgoing(admin, alert) for admin in self.cfg.ADMIN_PHONES]
        return out

    def info_text(self) -> str:
        msg = f"🕒 *Horário:* {self.cfg.BUSINESS_HOURS}\n"
        if self.cfg.PIX_KEY:
            msg += f"💸 *Pix:* `{self.cfg.PIX_KEY}`\n"
        if self.cfg.DELIVERY_FEE_CENTS:
            msg += f"🚚 *Taxa de entrega:* {money(self.cfg.DELIVERY_FEE_CENTS)}\n"
        return msg + "\nDigite *menu* para voltar."

    # ------------------------------------------------------------------ vendedor
    ADMIN_HELP = (
        "🧰 *Comandos do vendedor*\n\n"
        "*#pedidos* [status] — lista pedidos (ex: #pedidos novo)\n"
        "*#pedido 12* — detalhes do pedido\n"
        "*#status 12 confirmado* — muda status e avisa o cliente\n"
        "   (novo, confirmado, preparando, enviado, entregue, cancelado)\n"
        "*#produto P01 | Bolo de pote | 12,90 | 20* — cria/edita produto\n"
        "   (estoque é opcional)\n"
        "*#estoque P01 15* — ajusta estoque (*#estoque P01 livre* = sem controle)\n"
        "*#remover P01* — tira produto do catálogo\n"
        "*#catalogo* — ver catálogo como o cliente vê\n"
        "*#resumo* [hoje|semana|mes] — vendas do período\n"
        "*#responder 5511999998888 texto* — envia mensagem ao cliente\n"
        "*#bot 5511999998888* — devolve o cliente ao atendimento automático"
    )

    def handle_admin(self, phone: str, text: str) -> list[Outgoing]:
        parts = text[1:].split(maxsplit=1)
        cmd = normalize(parts[0]) if parts else ""
        arg = parts[1].strip() if len(parts) > 1 else ""
        reply = lambda msg: [Outgoing(phone, msg)]  # noqa: E731

        if cmd in ("ajuda", "help", "comandos", ""):
            return reply(self.ADMIN_HELP)

        if cmd == "pedidos":
            status = normalize(arg) or None
            if status and status not in STATUSES:
                return reply("Status inválido. Use: " + ", ".join(STATUSES))
            orders = self.db.list_orders(status=status, limit=15)
            if not orders:
                return reply("Nenhum pedido encontrado.")
            lines = ["📋 *Pedidos*" + (f" ({status})" if status else "") + "\n"]
            for o in orders:
                lines.append(f"*#{o['id']}* {o['customer_name'] or o['phone']} — "
                             f"{money(o['total_cents'])} — {STATUSES.get(o['status'], o['status'])}")
            return reply("\n".join(lines))

        if cmd == "pedido":
            order = self.db.get_order(int(arg)) if arg.isdigit() else None
            if not order:
                return reply("Pedido não encontrado. Use: #pedido 12")
            return reply(
                f"📦 *Pedido #{order['id']}* — {STATUSES.get(order['status'], order['status'])}\n"
                f"Cliente: {order['customer_name'] or '-'} (wa.me/{order['phone']})\n"
                f"Data: {order['created_at'].replace('T', ' ')}\n\n"
                f"{self.order_items_text(order['id'])}\n"
                f"Total: *{money(order['total_cents'])}*\n"
                f"Entrega: {order['address']}"
            )

        if cmd == "status":
            m = re.fullmatch(r"#?(\d+)\s+(\S+)", arg)
            status = normalize(m.group(2)) if m else ""
            if not m or status not in STATUSES:
                return reply("Use: #status 12 confirmado\nStatus: " + ", ".join(STATUSES))
            order = self.db.update_order_status(int(m.group(1)), status)
            if not order:
                return reply("Pedido não encontrado.")
            out = reply(f"Pedido *#{order['id']}* → {STATUSES[status]}. Cliente avisado. 👍")
            if status in CUSTOMER_STATUS_MSG:
                out.append(Outgoing(order["phone"], CUSTOMER_STATUS_MSG[status].format(id=order["id"])))
            return out

        if cmd == "produto":
            fields = [f.strip() for f in arg.split("|")]
            if len(fields) not in (3, 4) or not all(fields[:3]):
                return reply("Use: #produto P01 | Nome do produto | 12,90 | 20")
            price = parse_money(fields[2])
            if price is None:
                return reply("Preço inválido. Ex: 12,90")
            stock = None
            if len(fields) == 4 and fields[3]:
                if not fields[3].isdigit():
                    return reply("Estoque deve ser um número inteiro.")
                stock = int(fields[3])
            code = fields[0].upper()
            if not re.fullmatch(r"[A-Z0-9-]+", code) or code.isdigit():
                return reply("O código deve ter letras (ex: P01, BOLO1), sem espaços.")
            self.db.upsert_product(code, fields[1], price, stock)
            estoque = f", estoque {stock}" if stock is not None else ""
            return reply(f"✅ Produto *{code}* salvo: {fields[1]} — {money(price)}{estoque}")

        if cmd == "estoque":
            m = re.fullmatch(r"(\S+)\s+(\d+|livre)", arg, re.IGNORECASE)
            if not m:
                return reply("Use: #estoque P01 15")
            value = None if m.group(2).lower() == "livre" else int(m.group(2))
            if not self.db.set_stock(m.group(1), value):
                return reply("Produto não encontrado.")
            return reply(f"Estoque de *{m.group(1).upper()}* atualizado: "
                         f"{'sem controle' if value is None else value}.")

        if cmd == "remover":
            if not arg or not self.db.deactivate_product(arg):
                return reply("Produto não encontrado. Use: #remover P01")
            return reply(f"Produto *{arg.upper()}* removido do catálogo.")

        if cmd == "catalogo":
            return reply(self.catalog_text())

        if cmd == "resumo":
            period = normalize(arg) or "hoje"
            today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
            starts = {"hoje": today, "semana": today - timedelta(days=today.weekday()),
                      "mes": today.replace(day=1)}
            if period not in starts:
                return reply("Use: #resumo hoje | semana | mes")
            s = self.db.sales_summary(starts[period].isoformat(timespec="seconds"))
            ticket = s["total_cents"] // s["orders"] if s["orders"] else 0
            lines = [f"📊 *Resumo ({period})*\n",
                     f"Pedidos: {s['orders']}",
                     f"Faturamento: *{money(s['total_cents'])}*",
                     f"Ticket médio: {money(ticket)}",
                     f"Pedidos em aberto: {s['pending']}"]
            if s["top"]:
                lines.append("\n🏆 *Mais vendidos*")
                lines += [f"{t['qty']}x {t['name']}" for t in s["top"]]
            if s["low_stock"]:
                lines.append("\n⚠️ *Estoque baixo*")
                lines += [f"{p['code']} {p['name']}: {p['stock']}" for p in s["low_stock"]]
            return reply("\n".join(lines))

        if cmd == "responder":
            m = re.fullmatch(r"(\+?[\d\s-]{10,})\s+(.+)", arg, re.DOTALL)
            if not m:
                return reply("Use: #responder 5511999998888 sua mensagem")
            to = only_digits(m.group(1))
            return [Outgoing(to, f"💬 {m.group(2).strip()}"), Outgoing(phone, "Mensagem enviada. ✔️")]

        if cmd == "bot":
            to = only_digits(arg)
            if not to:
                return reply("Use: #bot 5511999998888")
            self.db.get_customer(to)
            self.db.set_state(to, "idle")
            return [Outgoing(phone, f"Cliente {to} voltou para o atendimento automático. 🤖"),
                    Outgoing(to, "Obrigado pelo contato! Se precisar de algo, digite *menu*. 😊")]

        return reply("Comando não reconhecido. Digite *#ajuda*.")
