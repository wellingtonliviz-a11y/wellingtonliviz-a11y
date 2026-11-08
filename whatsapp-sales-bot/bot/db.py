"""Camada de dados em SQLite: produtos, clientes, carrinho e pedidos."""
import sqlite3
from contextlib import contextmanager
from datetime import datetime

SCHEMA = """
CREATE TABLE IF NOT EXISTS products (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    code        TEXT UNIQUE NOT NULL,
    name        TEXT NOT NULL,
    price_cents INTEGER NOT NULL,
    stock       INTEGER,               -- NULL = estoque não controlado
    active      INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS customers (
    phone      TEXT PRIMARY KEY,
    name       TEXT,
    state      TEXT NOT NULL DEFAULT 'idle',
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS cart_items (
    phone      TEXT NOT NULL,
    product_id INTEGER NOT NULL REFERENCES products(id),
    qty        INTEGER NOT NULL,
    PRIMARY KEY (phone, product_id)
);

CREATE TABLE IF NOT EXISTS orders (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    phone       TEXT NOT NULL,
    total_cents INTEGER NOT NULL,
    status      TEXT NOT NULL DEFAULT 'novo',
    address     TEXT,
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS order_items (
    order_id    INTEGER NOT NULL REFERENCES orders(id),
    product_id  INTEGER NOT NULL,
    name        TEXT NOT NULL,
    price_cents INTEGER NOT NULL,
    qty         INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS processed_messages (
    id TEXT PRIMARY KEY
);
"""


def now() -> str:
    return datetime.now().isoformat(timespec="seconds")


class Database:
    def __init__(self, path: str):
        self.path = path
        # ":memory:" precisa de uma única conexão para não perder os dados
        self._shared = sqlite3.connect(path, check_same_thread=False) if path == ":memory:" else None
        with self.conn() as c:
            c.executescript(SCHEMA)

    @contextmanager
    def conn(self):
        c = self._shared or sqlite3.connect(self.path)
        c.row_factory = sqlite3.Row
        try:
            yield c
            c.commit()
        except Exception:
            c.rollback()
            raise
        finally:
            if self._shared is None:
                c.close()

    # ---------- deduplicação de mensagens (a Meta pode reenviar o webhook) ----------
    def mark_processed(self, message_id: str) -> bool:
        """Retorna False se a mensagem já foi processada antes."""
        with self.conn() as c:
            try:
                c.execute("INSERT INTO processed_messages (id) VALUES (?)", (message_id,))
                return True
            except sqlite3.IntegrityError:
                return False

    # ---------- clientes ----------
    def get_customer(self, phone: str, name: str | None = None) -> sqlite3.Row:
        with self.conn() as c:
            c.execute(
                "INSERT OR IGNORE INTO customers (phone, name, created_at) VALUES (?, ?, ?)",
                (phone, name, now()),
            )
            if name:
                c.execute("UPDATE customers SET name = ? WHERE phone = ?", (name, phone))
            return c.execute("SELECT * FROM customers WHERE phone = ?", (phone,)).fetchone()

    def set_state(self, phone: str, state: str) -> None:
        with self.conn() as c:
            c.execute("UPDATE customers SET state = ? WHERE phone = ?", (state, phone))

    # ---------- produtos ----------
    def list_products(self, only_active: bool = True) -> list[sqlite3.Row]:
        sql = "SELECT * FROM products"
        if only_active:
            sql += " WHERE active = 1"
        with self.conn() as c:
            return c.execute(sql + " ORDER BY code").fetchall()

    def get_product(self, code: str) -> sqlite3.Row | None:
        with self.conn() as c:
            return c.execute(
                "SELECT * FROM products WHERE UPPER(code) = UPPER(?)", (code,)
            ).fetchone()

    def upsert_product(self, code: str, name: str, price_cents: int, stock: int | None) -> None:
        with self.conn() as c:
            c.execute(
                """INSERT INTO products (code, name, price_cents, stock, active)
                   VALUES (UPPER(?), ?, ?, ?, 1)
                   ON CONFLICT(code) DO UPDATE SET
                     name = excluded.name, price_cents = excluded.price_cents,
                     stock = excluded.stock, active = 1""",
                (code, name, price_cents, stock),
            )

    def set_stock(self, code: str, stock: int | None) -> bool:
        with self.conn() as c:
            cur = c.execute(
                "UPDATE products SET stock = ? WHERE UPPER(code) = UPPER(?)", (stock, code)
            )
            return cur.rowcount > 0

    def deactivate_product(self, code: str) -> bool:
        with self.conn() as c:
            cur = c.execute(
                "UPDATE products SET active = 0 WHERE UPPER(code) = UPPER(?)", (code,)
            )
            c.execute(
                "DELETE FROM cart_items WHERE product_id IN "
                "(SELECT id FROM products WHERE UPPER(code) = UPPER(?))",
                (code,),
            )
            return cur.rowcount > 0

    # ---------- carrinho ----------
    def add_to_cart(self, phone: str, product_id: int, qty: int) -> int:
        with self.conn() as c:
            c.execute(
                """INSERT INTO cart_items (phone, product_id, qty) VALUES (?, ?, ?)
                   ON CONFLICT(phone, product_id) DO UPDATE SET qty = qty + excluded.qty""",
                (phone, product_id, qty),
            )
            return c.execute(
                "SELECT qty FROM cart_items WHERE phone = ? AND product_id = ?",
                (phone, product_id),
            ).fetchone()["qty"]

    def cart_qty(self, phone: str, product_id: int) -> int:
        with self.conn() as c:
            row = c.execute(
                "SELECT qty FROM cart_items WHERE phone = ? AND product_id = ?",
                (phone, product_id),
            ).fetchone()
            return row["qty"] if row else 0

    def remove_from_cart(self, phone: str, product_id: int) -> bool:
        with self.conn() as c:
            cur = c.execute(
                "DELETE FROM cart_items WHERE phone = ? AND product_id = ?", (phone, product_id)
            )
            return cur.rowcount > 0

    def clear_cart(self, phone: str) -> None:
        with self.conn() as c:
            c.execute("DELETE FROM cart_items WHERE phone = ?", (phone,))

    def get_cart(self, phone: str) -> list[sqlite3.Row]:
        with self.conn() as c:
            return c.execute(
                """SELECT p.id AS product_id, p.code, p.name, p.price_cents, p.stock, ci.qty
                   FROM cart_items ci JOIN products p ON p.id = ci.product_id
                   WHERE ci.phone = ? AND p.active = 1 ORDER BY p.code""",
                (phone,),
            ).fetchall()

    # ---------- pedidos ----------
    def create_order(self, phone: str, address: str, delivery_fee_cents: int = 0) -> int | str:
        """Cria o pedido a partir do carrinho, baixando o estoque.

        Retorna o ID do pedido ou uma mensagem de erro (str).
        """
        with self.conn() as c:
            items = c.execute(
                """SELECT p.id AS product_id, p.code, p.name, p.price_cents, p.stock, ci.qty
                   FROM cart_items ci JOIN products p ON p.id = ci.product_id
                   WHERE ci.phone = ? AND p.active = 1""",
                (phone,),
            ).fetchall()
            if not items:
                return "Seu carrinho está vazio."
            for it in items:
                if it["stock"] is not None and it["qty"] > it["stock"]:
                    return (
                        f"Só temos {it['stock']} unidade(s) de *{it['name']}* em estoque. "
                        f"Ajuste a quantidade e tente novamente."
                    )
            total = sum(it["price_cents"] * it["qty"] for it in items) + delivery_fee_cents
            ts = now()
            cur = c.execute(
                "INSERT INTO orders (phone, total_cents, address, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (phone, total, address, ts, ts),
            )
            order_id = cur.lastrowid
            for it in items:
                c.execute(
                    "INSERT INTO order_items (order_id, product_id, name, price_cents, qty) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (order_id, it["product_id"], it["name"], it["price_cents"], it["qty"]),
                )
                c.execute(
                    "UPDATE products SET stock = stock - ? WHERE id = ? AND stock IS NOT NULL",
                    (it["qty"], it["product_id"]),
                )
            c.execute("DELETE FROM cart_items WHERE phone = ?", (phone,))
            return order_id

    def get_order(self, order_id: int) -> sqlite3.Row | None:
        with self.conn() as c:
            return c.execute(
                """SELECT o.*, cu.name AS customer_name FROM orders o
                   LEFT JOIN customers cu ON cu.phone = o.phone WHERE o.id = ?""",
                (order_id,),
            ).fetchone()

    def get_order_items(self, order_id: int) -> list[sqlite3.Row]:
        with self.conn() as c:
            return c.execute(
                "SELECT * FROM order_items WHERE order_id = ?", (order_id,)
            ).fetchall()

    def list_orders(self, status: str | None = None, phone: str | None = None,
                    limit: int = 20) -> list[sqlite3.Row]:
        sql = """SELECT o.*, cu.name AS customer_name FROM orders o
                 LEFT JOIN customers cu ON cu.phone = o.phone WHERE 1=1"""
        args: list = []
        if status:
            sql += " AND o.status = ?"
            args.append(status)
        if phone:
            sql += " AND o.phone = ?"
            args.append(phone)
        sql += " ORDER BY o.id DESC LIMIT ?"
        args.append(limit)
        with self.conn() as c:
            return c.execute(sql, args).fetchall()

    def update_order_status(self, order_id: int, status: str) -> sqlite3.Row | None:
        with self.conn() as c:
            order = c.execute("SELECT * FROM orders WHERE id = ?", (order_id,)).fetchone()
            if not order:
                return None
            # devolve o estoque ao cancelar (apenas uma vez)
            if status == "cancelado" and order["status"] != "cancelado":
                for it in c.execute(
                    "SELECT product_id, qty FROM order_items WHERE order_id = ?", (order_id,)
                ).fetchall():
                    c.execute(
                        "UPDATE products SET stock = stock + ? WHERE id = ? AND stock IS NOT NULL",
                        (it["qty"], it["product_id"]),
                    )
            c.execute(
                "UPDATE orders SET status = ?, updated_at = ? WHERE id = ?",
                (status, now(), order_id),
            )
            return c.execute("SELECT * FROM orders WHERE id = ?", (order_id,)).fetchone()

    def sales_summary(self, since_iso: str) -> dict:
        with self.conn() as c:
            row = c.execute(
                """SELECT COUNT(*) AS n, COALESCE(SUM(total_cents), 0) AS total
                   FROM orders WHERE created_at >= ? AND status != 'cancelado'""",
                (since_iso,),
            ).fetchone()
            top = c.execute(
                """SELECT oi.name, SUM(oi.qty) AS qty FROM order_items oi
                   JOIN orders o ON o.id = oi.order_id
                   WHERE o.created_at >= ? AND o.status != 'cancelado'
                   GROUP BY oi.name ORDER BY qty DESC LIMIT 5""",
                (since_iso,),
            ).fetchall()
            pending = c.execute(
                "SELECT COUNT(*) AS n FROM orders WHERE status IN ('novo', 'confirmado')"
            ).fetchone()["n"]
            low_stock = c.execute(
                "SELECT code, name, stock FROM products "
                "WHERE active = 1 AND stock IS NOT NULL AND stock <= 3 ORDER BY stock"
            ).fetchall()
            return {
                "orders": row["n"],
                "total_cents": row["total"],
                "top": top,
                "pending": pending,
                "low_stock": low_stock,
            }
