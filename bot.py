from __future__ import annotations

import asyncio
import html
import logging
import math
import os
import secrets
import string
import time
from urllib.parse import quote_plus, urljoin, urlparse

import aiohttp
import aiosqlite
from aiohttp import web
from bs4 import BeautifulSoup

from aiogram import Bot, Dispatcher, F
from aiogram.enums import ContentType
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    BotCommand,
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    LabeledPrice,
    Message,
    PreCheckoutQuery,
)


# ============================================================
#  SCRIPT FINDER BETA — CONFIGURATION
# ============================================================

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
ADMIN_ID = 8996403397

DB_PATH = os.getenv("DB_PATH", "script_finder.db")
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "8080"))

SPONSOR_URL = os.getenv("SPONSOR_URL", "")
COMMUNITY_URL = os.getenv("COMMUNITY_URL", "")
CHANNEL_URL = os.getenv("CHANNEL_URL", "")

BETA_LABEL = "🧪 <b>SCRIPT FINDER BETA</b>"
ROULETTE_PRICE = 7
ROULETTE_SLOTS = 7
MAX_ACTIVE_CODES = 5
INVOICE_RESERVATION_SECONDS = 1200

MM2_SCRIPT_URL = (
    "https://raw.githubusercontent.com/"
    "ZenosScript/Mm2Autofarm/refs/heads/main/Valentines"
)

MM2_LOADSTRING = (
    'loadstring(game:HttpGet('
    '"https://raw.githubusercontent.com/'
    'ZenosScript/Mm2Autofarm/refs/heads/main/Valentines"))()'
)

DB: aiosqlite.Connection | None = None
DB_LOCK = asyncio.Lock()
HTTP_TIMEOUT = aiohttp.ClientTimeout(total=18)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 Chrome/126 Safari/537.36"
    )
}

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
log = logging.getLogger("script-finder")

bot = Bot(BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())


# ============================================================
#  PROMO CATALOG — PRICES ARE EXACTLY AS REQUESTED
# ============================================================

PROMO_TYPES = {
    "premium3": {
        "name": "Premium на 3 дня",
        "description": "Premium-доступ на 3 дня",
        "price": 10,
        "kind": "premium",
        "days": 3,
    },
    "premium5": {
        "name": "Premium на 5 дней",
        "description": "Premium-доступ на 5 дней",
        "price": 18,
        "kind": "premium",
        "days": 5,
    },
    "discount5": {
        "name": "Скидка 5%",
        "description": "Скидка 5% на одну покупку в магазине",
        "price": 5,
        "kind": "discount",
        "percent": 5,
    },
    "discount15": {
        "name": "Скидка 15%",
        "description": "Скидка 15% на одну покупку в магазине",
        "price": 7,
        "kind": "discount",
        "percent": 15,
    },
    "discount30": {
        "name": "Скидка 30%",
        "description": "Скидка 30% на одну покупку в магазине",
        "price": 13,
        "kind": "discount",
        "percent": 30,
    },
    "discount50": {
        "name": "Скидка 50%",
        "description": "Скидка 50% на одну покупку в магазине",
        "price": 17,
        "kind": "discount",
        "percent": 50,
    },
    "mm2freeze": {
        "name": "Заморозка скрипта MM2",
        "description": "Персональный промокод на скрипт MM2",
        "price": 5,
        "kind": "script",
    },
}


# ============================================================
#  STATES
# ============================================================

class SearchState(StatesGroup):
    waiting_for_game = State()


class RedeemState(StatesGroup):
    waiting_for_code = State()


class AdminAddScriptState(StatesGroup):
    waiting_for_data = State()


class AdminRouletteState(StatesGroup):
    waiting_for_data = State()


class AdminProductState(StatesGroup):
    waiting_for_data = State()


# ============================================================
#  DATABASE SCHEMA
# ============================================================

SCHEMA = """
PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    username TEXT NOT NULL DEFAULT '',
    first_name TEXT NOT NULL DEFAULT '',
    premium_until INTEGER NOT NULL DEFAULT 0,
    created_at INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS scripts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    game TEXT NOT NULL,
    title TEXT NOT NULL,
    url TEXT NOT NULL,
    source TEXT NOT NULL DEFAULT 'admin',
    created_at INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_scripts_game
ON scripts(game);

CREATE TABLE IF NOT EXISTS products (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    price INTEGER NOT NULL CHECK(price > 0),
    delivery TEXT NOT NULL DEFAULT '',
    active INTEGER NOT NULL DEFAULT 1,
    created_at INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS roulette_scripts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    url TEXT NOT NULL,
    active INTEGER NOT NULL DEFAULT 1,
    created_at INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS promo_codes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code TEXT UNIQUE NOT NULL,
    user_id INTEGER NOT NULL,
    promo_type TEXT NOT NULL,
    description TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'unused',
    payment_charge_id TEXT UNIQUE NOT NULL,
    created_at INTEGER NOT NULL,
    activated_at INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_promo_owner_status
ON promo_codes(user_id, status);

CREATE TABLE IF NOT EXISTS invoice_reservations (
    payload TEXT PRIMARY KEY,
    user_id INTEGER NOT NULL,
    kind TEXT NOT NULL,
    created_at INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_reservations_user
ON invoice_reservations(user_id, kind, created_at);

CREATE TABLE IF NOT EXISTS payments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    telegram_charge_id TEXT UNIQUE NOT NULL,
    provider_charge_id TEXT NOT NULL DEFAULT '',
    user_id INTEGER NOT NULL,
    payload TEXT NOT NULL,
    amount INTEGER NOT NULL,
    currency TEXT NOT NULL,
    kind TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'processing',
    created_at INTEGER NOT NULL,
    processed_at INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS purchases (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    product_id INTEGER,
    product_name TEXT NOT NULL,
    original_price INTEGER NOT NULL,
    paid_price INTEGER NOT NULL,
    discount_percent INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL,
    payment_charge_id TEXT UNIQUE NOT NULL,
    created_at INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS user_discounts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    percent INTEGER NOT NULL,
    promo_code TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'unused',
    created_at INTEGER NOT NULL,
    used_at INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_discount_owner_status
ON user_discounts(user_id, status);

CREATE TABLE IF NOT EXISTS roulette_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    script_title TEXT NOT NULL,
    script_url TEXT NOT NULL,
    payment_charge_id TEXT UNIQUE NOT NULL,
    created_at INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""


async def init_db():
    global DB

    DB = await aiosqlite.connect(DB_PATH)
    DB.row_factory = aiosqlite.Row

    await DB.execute("PRAGMA journal_mode=WAL")
    await DB.execute("PRAGMA busy_timeout=5000")
    await DB.executescript(SCHEMA)
    await DB.commit()

    log.info("SQLite initialized: %s", DB_PATH)


async def db_execute(sql, params=()):
    async with DB_LOCK:
        cur = await DB.execute(sql, params)
        await DB.commit()
        return cur


async def db_one(sql, params=()):
    async with DB_LOCK:
        cur = await DB.execute(sql, params)
        row = await cur.fetchone()
        await cur.close()
        return row


async def db_all(sql, params=()):
    async with DB_LOCK:
        cur = await DB.execute(sql, params)
        rows = await cur.fetchall()
        await cur.close()
        return rows


async def ensure_user(user):
    now = int(time.time())

    await db_execute(
        """
        INSERT INTO users(user_id, username, first_name, created_at)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(user_id) DO UPDATE SET
            username=excluded.username,
            first_name=excluded.first_name
        """,
        (
            user.id,
            user.username or "",
            user.first_name or "",
            now,
        ),
    )


async def user_is_premium(user_id: int) -> bool:
    row = await db_one(
        "SELECT premium_until FROM users WHERE user_id=?",
        (user_id,),
    )
    return bool(row and int(row["premium_until"]) > int(time.time()))


async def count_unused_codes(user_id: int) -> int:
    row = await db_one(
        """
        SELECT COUNT(*) AS n
        FROM promo_codes
        WHERE user_id=? AND status='unused'
        """,
        (user_id,),
    )
    return int(row["n"] or 0)


async def count_reserved_promo_invoices(user_id: int) -> int:
    cutoff = int(time.time()) - INVOICE_RESERVATION_SECONDS

    row = await db_one(
        """
        SELECT COUNT(*) AS n
        FROM invoice_reservations
        WHERE user_id=? AND kind='promo' AND created_at>=?
        """,
        (user_id, cutoff),
    )
    return int(row["n"] or 0)


async def get_active_discounts(user_id: int):
    return await db_all(
        """
        SELECT *
        FROM user_discounts
        WHERE user_id=? AND status='unused'
        ORDER BY percent DESC, id ASC
        """,
        (user_id,),
    )


async def create_unique_code() -> str:
    alphabet = string.ascii_uppercase + string.digits

    for _ in range(50):
        code = "SF-" + "".join(
            secrets.choice(alphabet) for _ in range(10)
        )
        exists = await db_one(
            "SELECT id FROM promo_codes WHERE code=?",
            (code,),
        )
        if not exists:
            return code

    raise RuntimeError("Unable to generate a unique promo code")


async def cleanup_reservations():
    cutoff = int(time.time()) - INVOICE_RESERVATION_SECONDS
    await db_execute(
        "DELETE FROM invoice_reservations WHERE created_at<?",
        (cutoff,),
    )


# ============================================================
#  KEYBOARDS
# ============================================================

def kb(rows):
    return InlineKeyboardMarkup(inline_keyboard=rows)


def btn(text, callback=None, url=None):
    if url:
        return InlineKeyboardButton(text=text, url=url)
    return InlineKeyboardButton(text=text, callback_data=callback)


def main_keyboard(user_id: int):
    rows = [
        [
            btn("🔎 Поиск скриптов", "search"),
            btn("👑 Premium", "premium"),
        ],
        [
            btn("🎰 Рулетка — 7 ⭐", "roulette"),
            btn("🛒 Магазин", "shop"),
        ],
        [
            btn("🎟 Промокоды", "promos"),
            btn("🎟 Ввести промокод", "redeem"),
        ],
        [
            btn("🤝 Спонсор", "sponsor"),
            btn("👥 Сообщество", "community"),
        ],
        [btn("❤️ Донат", "donate")],
    ]

    if user_id == ADMIN_ID:
        rows.append([btn("🛡 Админ-панель", "admin")])

    return kb(rows)


def back_menu(user_id: int):
    return kb([[btn("⬅️ Главное меню", "home")]])


def promo_keyboard():
    rows = []

    for key, item in PROMO_TYPES.items():
        rows.append([
            btn(
                f"{item['name']} — {item['price']} ⭐",
                f"promo_buy:{key}",
            )
        ])

    rows.append([btn("📋 Мои промокоды", "my_codes")])
    rows.append([btn("⬅️ Главное меню", "home")])
    return kb(rows)


# ============================================================
#  GENERAL HELPERS
# ============================================================

def esc(value) -> str:
    return html.escape(str(value or ""))


def valid_http_url(value: str) -> bool:
    try:
        parsed = urlparse(value)
        return parsed.scheme in ("https", "http") and bool(parsed.netloc)
    except Exception:
        return False


async def notify_admin(text: str):
    try:
        await bot.send_message(
            ADMIN_ID,
            text,
            disable_web_page_preview=True,
        )
    except Exception:
        log.exception("Admin notification failed")


async def show_home(target, user):
    await ensure_user(user)

    text = (
        f"{BETA_LABEL}\n\n"
        f"Привет, {esc(user.first_name or 'пользователь')}!\n"
        "Выбери нужный раздел."
    )

    if isinstance(target, CallbackQuery):
        try:
            await target.message.edit_text(
                text,
                reply_markup=main_keyboard(user.id),
            )
        except Exception:
            await target.message.answer(
                text,
                reply_markup=main_keyboard(user.id),
            )
    else:
        await target.answer(
            text,
            reply_markup=main_keyboard(user.id),
        )


async def make_payload(kind: str, user_id: int, extra: str = "") -> str:
    nonce = secrets.token_urlsafe(8)
    return f"{kind}|{user_id}|{extra}|{nonce}"


def parse_payload(payload: str):
    parts = payload.split("|")
    if len(parts) != 4:
        raise ValueError("Malformed invoice payload")

    kind, owner, extra, nonce = parts
    return kind, int(owner), extra, nonce


async def send_invoice(
    user_id: int,
    title: str,
    description: str,
    amount: int,
    payload: str,
):
    if amount < 1:
        raise ValueError("Invoice amount must be positive")

    await bot.send_invoice(
        chat_id=user_id,
        title=title[:32],
        description=description[:255],
        payload=payload,
        provider_token="",
        currency="XTR",
        prices=[LabeledPrice(label=title[:32], amount=int(amount))],
    )


async def reserve_invoice(payload, user_id, kind):
    now = int(time.time())

    async with DB_LOCK:
        await DB.execute(
            "DELETE FROM invoice_reservations WHERE created_at<?",
            (now - INVOICE_RESERVATION_SECONDS,),
        )
        await DB.execute(
            """
            INSERT INTO invoice_reservations(payload, user_id, kind, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (payload, user_id, kind, now),
        )
        await DB.commit()


async def remove_reservation(payload):
    await db_execute(
        "DELETE FROM invoice_reservations WHERE payload=?",
        (payload,),
    )


# ============================================================
#  /START AND NAVIGATION
# ============================================================

@dp.message(CommandStart())
async def cmd_start(message: Message):
    await show_home(message, message.from_user)


@dp.message(Command("menu"))
async def cmd_menu(message: Message):
    await show_home(message, message.from_user)


@dp.message(Command("id"))
async def cmd_id(message: Message):
    await ensure_user(message.from_user)
    await message.answer(
        f"Твой Telegram ID: <code>{message.from_user.id}</code>"
    )


@dp.callback_query(F.data == "home")
async def cb_home(call: CallbackQuery, state: FSMContext):
    await state.clear()
    await show_home(call, call.from_user)
    await call.answer()


# ============================================================
#  TELEGRAM STARS PRE-CHECKOUT
# ============================================================

async def expected_invoice_amount(kind, user_id, extra):
    if kind == "promo":
        item = PROMO_TYPES.get(extra)
        return item["price"] if item else None

    if kind == "roulette":
        return ROULETTE_PRICE

    if kind == "donate":
        try:
            amount = int(extra)
        except ValueError:
            return None
        return amount if amount in (5, 10, 25, 50) else None

    if kind == "product":
        parts = extra.split(",")
        if len(parts) != 2:
            return None

        try:
            product_id = int(parts[0])
            discount_id = int(parts[1])
        except ValueError:
            return None

        product = await db_one(
            "SELECT * FROM products WHERE id=? AND active=1",
            (product_id,),
        )
        if not product:
            return None

        price = int(product["price"])

        if discount_id:
            discount = await db_one(
                """
                SELECT * FROM user_discounts
                WHERE id=? AND user_id=? AND status='unused'
                """,
                (discount_id, user_id),
            )
            if not discount:
                return None

            percent = int(discount["percent"])
            price = max(1, math.ceil(price * (100 - percent) / 100))

        return price

    return None


@dp.pre_checkout_query()
async def pre_checkout(query: PreCheckoutQuery):
    try:
        kind, owner_id, extra, nonce = parse_payload(
            query.invoice_payload
        )

        if owner_id != query.from_user.id:
            await query.answer(
                ok=False,
                error_message="Этот счёт принадлежит другому пользователю.",
            )
            return

        if query.currency != "XTR":
            await query.answer(
                ok=False,
                error_message="Неверная валюта платежа.",
            )
            return

        expected = await expected_invoice_amount(
            kind, owner_id, extra
        )

        if expected is None or int(query.total_amount) != int(expected):
            await query.answer(
                ok=False,
                error_message="Цена счёта не совпадает с каталогом.",
            )
            return

        if kind == "promo":
            reserved = await db_one(
                """
                SELECT payload FROM invoice_reservations
                WHERE payload=? AND user_id=? AND kind='promo'
                """,
                (query.invoice_payload, owner_id),
            )

            if not reserved:
                await query.answer(
                    ok=False,
                    error_message="Счёт устарел. Открой магазин и попробуй снова.",
                )
                return

            unused = await count_unused_codes(owner_id)
            pending = await count_reserved_promo_invoices(owner_id)

            if unused + pending > MAX_ACTIVE_CODES:
                await query.answer(
                    ok=False,
                    error_message="Достигнут лимит промокодов.",
                )
                return

        if kind == "roulette":
            count = await db_one(
                """
                SELECT COUNT(*) AS n
                FROM roulette_scripts
                WHERE active=1
                """
            )

            if int(count["n"]) != ROULETTE_SLOTS:
                await query.answer(
                    ok=False,
                    error_message="Рулетка сейчас недоступна: нужно ровно 7 скриптов.",
                )
                return

        if kind == "product":
            parts = extra.split(",")
            discount_id = int(parts[1])

            if discount_id:
                discount = await db_one(
                    """
                    SELECT id FROM user_discounts
                    WHERE id=? AND user_id=? AND status='unused'
                    """,
                    (discount_id, owner_id),
                )

                if not discount:
                    await query.answer(
                        ok=False,
                        error_message="Промокод скидки уже использован.",
                    )
                    return

        await query.answer(ok=True)

    except Exception:
        log.exception("Pre-checkout error")
        await query.answer(
            ok=False,
            error_message="Не удалось проверить оплату. Попробуй ещё раз.",
        )


# ============================================================
#  PAYMENT PROCESSING
# ============================================================

async def register_payment(payment, user_id, payload, kind):
    """
    Сохраняет charge_id как UNIQUE.
    False означает, что такой платёж уже обрабатывался.
    """
    now = int(time.time())

    async with DB_LOCK:
        try:
            cur = await DB.execute(
                """
                INSERT INTO payments(
                    telegram_charge_id, provider_charge_id,
                    user_id, payload, amount, currency,
                    kind, status, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, 'processing', ?)
                """,
                (
                    payment.telegram_payment_charge_id,
                    payment.provider_payment_charge_id or "",
                    user_id,
                    payload,
                    int(payment.total_amount),
                    payment.currency,
                    kind,
                    now,
                ),
            )
            await DB.commit()
            return cur.rowcount == 1
        except aiosqlite.IntegrityError:
            await DB.rollback()
            return False


async def mark_payment_done(charge_id):
    await db_execute(
        """
        UPDATE payments
        SET status='completed', processed_at=?
        WHERE telegram_charge_id=?
        """,
        (int(time.time()), charge_id),
    )


async def mark_payment_failed(charge_id):
    await db_execute(
        """
        UPDATE payments SET status='needs_admin'
        WHERE telegram_charge_id=?
        """,
        (charge_id,),
    )


async def make_paid_promo(user_id, promo_type, charge_id):
    item = PROMO_TYPES[promo_type]
    code = await create_unique_code()
    now = int(time.time())

    await db_execute(
        """
        INSERT INTO promo_codes(
            code, user_id, promo_type, description,
            status, payment_charge_id, created_at
        ) VALUES (?, ?, ?, ?, 'unused', ?, ?)
        """,
        (
            code,
            user_id,
            promo_type,
            item["description"],
            charge_id,
            now,
        ),
    )

    return code


async def process_promo_payment(message, extra, charge_id):
    item = PROMO_TYPES.get(extra)
    if not item:
        raise ValueError("Unknown promo type")

    user_id = message.from_user.id
    unused = await count_unused_codes(user_id)

    if unused >= MAX_ACTIVE_CODES:
        # Не теряем оплату. Код сохраняется, администратор уведомляется.
        await notify_admin(
            "⚠️ Пользователь оплатил промокод при достижении лимита.\n"
            f"ID: <code>{user_id}</code>\n"
            f"Платёж: <code>{esc(charge_id)}</code>\n"
            "Проверь покупку и свяжись с пользователем."
        )

    code = await make_paid_promo(user_id, extra, charge_id)
    await remove_reservation(message.successful_payment.invoice_payload)

    text = (
        "✅ <b>Оплата успешна!</b>\n\n"
        f"🎟 Код: <code>{esc(code)}</code>\n"
        f"🎁 Функция: <b>{esc(item['name'])}</b>\n"
        f"📝 {esc(item['description'])}\n\n"
        "Код персональный и одноразовый.\n"
        "Нажми «Ввести промокод» в главном меню, чтобы активировать его."
    )

    await message.answer(
        text,
        reply_markup=main_keyboard(user_id),
    )


async def process_roulette_payment(message, charge_id):
    user_id = message.from_user.id

    scripts = await db_all(
        """
        SELECT title, url FROM roulette_scripts
        WHERE active=1 ORDER BY id
        """
    )

    if len(scripts) != ROULETTE_SLOTS:
        raise RuntimeError(
            "Roulette script count changed after payment"
        )

    # Случайный выбор среди семи скриптов, добавленных администратором.
    import secrets as secure_random
    winner = secure_random.choice(scripts)

    await db_execute(
        """
        INSERT INTO roulette_log(
            user_id, script_title, script_url,
            payment_charge_id, created_at
        ) VALUES (?, ?, ?, ?, ?)
        """,
        (
            user_id,
            winner["title"],
            winner["url"],
            charge_id,
            int(time.time()),
        ),
    )

    await message.answer(
        "🎰 <b>Рулетка завершена!</b>\n\n"
        f"🎁 Результат: <b>{esc(winner['title'])}</b>\n"
        f"🔗 {esc(winner['url'])}\n\n"
        "Стоимость прокрута: 7 ⭐",
        reply_markup=main_keyboard(user_id),
        disable_web_page_preview=True,
    )


async def process_product_payment(message, extra, charge_id, paid_amount):
    user_id = message.from_user.id
    parts = extra.split(",")

    if len(parts) != 2:
        raise ValueError("Invalid product invoice payload")

    product_id = int(parts[0])
    discount_id = int(parts[1])

    product = await db_one(
        "SELECT * FROM products WHERE id=? AND active=1",
        (product_id,),
    )

    if not product:
        raise RuntimeError("Product unavailable after payment")

    percent = 0

    if discount_id:
        discount = await db_one(
            """
            SELECT * FROM user_discounts
            WHERE id=? AND user_id=? AND status='unused'
            """,
            (discount_id, user_id),
        )

        if not discount:
            raise RuntimeError("Discount unavailable after payment")

        percent = int(discount["percent"])

        await db_execute(
            """
            UPDATE user_discounts
            SET status='used', used_at=?
            WHERE id=? AND status='unused'
            """,
            (int(time.time()), discount_id),
        )

    await db_execute(
        """
        INSERT INTO purchases(
            user_id, product_id, product_name,
            original_price, paid_price, discount_percent,
            status, payment_charge_id, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, 'paid', ?, ?)
        """,
        (
            user_id,
            product_id,
            product["name"],
            int(product["price"]),
            int(paid_amount),
            percent,
            charge_id,
            int(time.time()),
        ),
    )

    delivery = product["delivery"] or product["description"]

    await message.answer(
        "✅ <b>Покупка успешна!</b>\n\n"
        f"🛒 Товар: <b>{esc(product['name'])}</b>\n"
        f"💰 Цена без скидки: {product['price']} ⭐\n"
        f"💳 Оплачено: {paid_amount} ⭐\n"
        f"🏷 Скидка: {percent}%\n\n"
        f"📦 {esc(delivery)}",
        reply_markup=main_keyboard(user_id),
    )


@dp.message(F.content_type == ContentType.SUCCESSFUL_PAYMENT)
async def successful_payment(message: Message):
    payment = message.successful_payment
    user_id = message.from_user.id

    try:
        kind, owner_id, extra, nonce = parse_payload(
            payment.invoice_payload
        )
    except Exception:
        log.exception("Malformed payment payload")
        await notify_admin(
            f"🚨 Некорректный платёжный payload от {user_id}"
        )
        await message.answer(
            "Платёж получен, но счёт не удалось распознать. "
            "Администратор уведомлён."
        )
        return

    if owner_id != user_id:
        await notify_admin(
            "🚨 Несовпадение пользователя и владельца счёта.\n"
            f"User: {user_id}, payload owner: {owner_id}"
        )
        return

    expected = await expected_invoice_amount(kind, user_id, extra)
    if (
        payment.currency != "XTR"
        or expected is None
        or int(payment.total_amount) != int(expected)
    ):
        await notify_admin(
            "🚨 Платёж не прошёл сверку суммы.\n"
            f"User: {user_id}\n"
            f"Kind: {esc(kind)}\n"
            f"Received: {payment.total_amount} {esc(payment.currency)}\n"
            f"Expected: {expected}"
        )
        await message.answer(
            "Оплата получена, но её сумма требует проверки. "
            "Администратор уведомлён."
        )
        return

    first_time = await register_payment(
        payment,
        user_id,
        payment.invoice_payload,
        kind,
    )

    if not first_time:
        await message.answer(
            "Этот платёж уже зарегистрирован. Повторная выдача товара запрещена."
        )
        return

    await notify_admin(
        "⭐ <b>Новый платёж Script Finder BETA</b>\n"
        f"Пользователь: <code>{user_id}</code>\n"
        f"Сумма: <b>{payment.total_amount} ⭐</b>\n"
        f"Тип: <code>{esc(kind)}</code>\n"
        f"Charge ID: <code>{esc(payment.telegram_payment_charge_id)}</code>"
    )

    try:
        if kind == "promo":
            await process_promo_payment(
                message,
                extra,
                payment.telegram_payment_charge_id,
            )

        elif kind == "roulette":
            await process_roulette_payment(
                message,
                payment.telegram_payment_charge_id,
            )

        elif kind == "product":
            await process_product_payment(
                message,
                extra,
                payment.telegram_payment_charge_id,
                int(payment.total_amount),
            )

        elif kind == "donate":
            await message.answer(
                "❤️ Спасибо за поддержку Script Finder BETA!",
                reply_markup=main_keyboard(user_id),
            )

        else:
            raise ValueError("Unknown payment type")

        await mark_payment_done(payment.telegram_payment_charge_id)

    except Exception:
        log.exception("Payment fulfilment failed")
        await mark_payment_failed(payment.telegram_payment_charge_id)

        await notify_admin(
            "🚨 Ошибка выдачи после оплаты.\n"
            f"Пользователь: <code>{user_id}</code>\n"
            f"Charge: <code>{esc(payment.telegram_payment_charge_id)}</code>\n"
            "Проверь статус платежа и выдай товар вручную при необходимости."
        )

        await message.answer(
            "Платёж зарегистрирован, но возникла ошибка выдачи. "
            "Администратор уведомлён. Не оплачивай повторно."
        )


# ============================================================
#  PROMO SHOP
# ============================================================

@dp.callback_query(F.data == "promos")
async def cb_promos(call: CallbackQuery):
    await call.message.edit_text(
        "🎟 <b>Магазин промокодов</b>\n\n"
        "После подтверждённой оплаты выдаётся персональный код.\n"
        "У каждого кода указана своя функция.\n"
        "Код можно активировать один раз.\n"
        "Максимум 5 неактивированных кодов на пользователя.\n\n"
        "Выбери нужный промокод:",
        reply_markup=promo_keyboard(),
    )
    await call.answer()


@dp.callback_query(F.data.startswith("promo_buy:"))
async def cb_buy_promo(call: CallbackQuery):
    user_id = call.from_user.id
    promo_type = call.data.split(":", 1)[1]
    item = PROMO_TYPES.get(promo_type)

    if not item:
        await call.answer("Такого промокода нет.", show_alert=True)
        return

    await cleanup_reservations()

    unused = await count_unused_codes(user_id)
    pending = await count_reserved_promo_invoices(user_id)

    if unused + pending >= MAX_ACTIVE_CODES:
        await call.answer(
            "Максимум 5 неактивированных промокодов и ожидающих счетов. "
            "Сначала активируй один из кодов.",
            show_alert=True,
        )
        return

    payload = await make_payload("promo", user_id, promo_type)
    await reserve_invoice(payload, user_id, "promo")

    try:
        await send_invoice(
            user_id,
            item["name"],
            item["description"],
            item["price"],
            payload,
        )
        await call.answer("Счёт отправлен в личные сообщения.")
    except Exception:
        await remove_reservation(payload)
        log.exception("Could not send promo invoice")
        await call.answer(
            "Не удалось отправить счёт. Попробуй позже.",
            show_alert=True,
        )


@dp.callback_query(F.data == "my_codes")
async def cb_my_codes(call: CallbackQuery):
    rows = await db_all(
        """
        SELECT code, description, status, created_at
        FROM promo_codes
        WHERE user_id=?
        ORDER BY id DESC
        LIMIT 50
        """,
        (call.from_user.id,),
    )

    if not rows:
        text = "У тебя пока нет промокодов."
    else:
        text = "🎟 <b>Твои промокоды</b>\n\n"
        for row in rows:
            status = (
                "🟢 Не активирован"
                if row["status"] == "unused"
                else "⚪ Активирован"
            )
            text += (
                f"🔑 <code>{esc(row['code'])}</code>\n"
                f"🎁 Функция: {esc(row['description'])}\n"
                f"Статус: {status}\n\n"
            )

    await call.message.edit_text(
        text,
        reply_markup=back_menu(call.from_user.id),
    )
    await call.answer()


# ============================================================
#  REDEEM PROMO CODES
# ============================================================

@dp.callback_query(F.data == "redeem")
async def cb_redeem(call: CallbackQuery, state: FSMContext):
    await state.set_state(RedeemState.waiting_for_code)
    await call.message.answer(
        "🎟 <b>Ввести промокод</b>\n\n"
        "Отправь свой код отдельным сообщением.\n"
        "Можно активировать только свой, ещё не использованный код."
    )
    await call.answer()


@dp.message(RedeemState.waiting_for_code)
async def process_redeem(message: Message, state: FSMContext):
    raw = (message.text or "").strip().upper()

    if len(raw) > 64:
        await message.answer("Код слишком длинный.")
        return

    async with DB_LOCK:
        try:
            await DB.execute("BEGIN IMMEDIATE")

            cur = await DB.execute(
                "SELECT * FROM promo_codes WHERE code=?",
                (raw,),
            )
            promo = await cur.fetchone()
            await cur.close()

            if not promo or int(promo["user_id"]) != message.from_user.id:
                await DB.rollback()
                await message.answer(
                    "❌ Код не найден или принадлежит другому пользователю."
                )
                return

            if promo["status"] != "unused":
                await DB.rollback()
                await message.answer("❌ Этот промокод уже использован.")
                await state.clear()
                return

            item = PROMO_TYPES.get(promo["promo_type"])
            if not item:
                await DB.rollback()
                await message.answer("❌ Функция промокода не найдена.")
                return

            now = int(time.time())
            user_id = message.from_user.id

            if item["kind"] == "premium":
                cur = await DB.execute(
                    "SELECT premium_until FROM users WHERE user_id=?",
                    (user_id,),
                )
                user_row = await cur.fetchone()
                await cur.close()

                old_until = (
                    int(user_row["premium_until"])
                    if user_row else 0
                )
                new_until = max(old_until, now) + int(item["days"]) * 86400

                await DB.execute(
                    "UPDATE users SET premium_until=? WHERE user_id=?",
                    (new_until, user_id),
                )

            elif item["kind"] == "discount":
                await DB.execute(
                    """
                    INSERT INTO user_discounts(
                        user_id, percent, promo_code, status, created_at
                    ) VALUES (?, ?, ?, 'unused', ?)
                    """,
                    (
                        user_id,
                        int(item["percent"]),
                        raw,
                        now,
                    ),
                )

            elif item["kind"] == "script":
                await DB.execute(
                    """
                    INSERT INTO purchases(
                        user_id, product_id, product_name,
                        original_price, paid_price, discount_percent,
                        status, payment_charge_id, created_at
                    ) VALUES (?, NULL, ?, ?, ?, 0, 'redeemed', ?, ?)
                    """,
                    (
                        user_id,
                        item["name"],
                        item["price"],
                        item["price"],
                        f"redeem-{promo['id']}",
                        now,
                    ),
                )

            await DB.execute(
                """
                UPDATE promo_codes
                SET status='used', activated_at=?
                WHERE id=? AND status='unused'
                """,
                (now, promo["id"]),
            )

            await DB.commit()

        except Exception:
            await DB.rollback()
            log.exception("Promo activation failed")
            await message.answer(
                "Ошибка активации. Попробуй ещё раз или обратись к администратору."
            )
            return

    await state.clear()

    if item["kind"] == "premium":
        result = (
            f"👑 Premium активирован на {item['days']} дня.\n"
            "Срок сохранён в базе данных."
        )

    elif item["kind"] == "discount":
        result = (
            f"🏷 Скидка {item['percent']}% добавлена в твой аккаунт.\n"
            "Она будет доступна при следующей покупке товара в магазине."
        )

    elif item["kind"] == "script":
        result = (
            "❄️ <b>Заморозка скрипта MM2</b>\n\n"
            f"<code>{esc(MM2_LOADSTRING)}</code>\n\n"
            "Проверяй содержимое стороннего скрипта перед запуском."
        )

    else:
        result = "Функция активирована."

    await message.answer(
        "🎉 <b>Промокод успешно активирован!</b>\n\n"
        f"🎁 Функция: <b>{esc(item['name'])}</b>\n\n"
        f"{result}",
        reply_markup=main_keyboard(message.from_user.id),
    )

    await notify_admin(
        "🎟 <b>Промокод активирован</b>\n"
        f"Пользователь: <code>{message.from_user.id}</code>\n"
        f"Функция: {esc(item['name'])}\n"
        f"Код: <code>{esc(raw)}</code>"
    )


# ============================================================
#  NORMAL STORE + DISCOUNT APPLICATION
# ============================================================

@dp.callback_query(F.data == "shop")
async def cb_shop(call: CallbackQuery):
    products = await db_all(
        "SELECT * FROM products WHERE active=1 ORDER BY id DESC"
    )

    rows = []
    text = "🛒 <b>Магазин Script Finder</b>\n\n"

    if not products:
        text += "Пока нет дополнительных товаров.\n"
    else:
        for product in products:
            text += (
                f"• <b>{esc(product['name'])}</b> — "
                f"{product['price']} ⭐\n"
                f"{esc(product['description'])}\n\n"
            )
            rows.append([
                btn(
                    f"{product['name']} — {product['price']} ⭐",
                    f"product:{product['id']}",
                )
            ])

    rows.append([btn("🎟 Магазин промокодов", "promos")])
    rows.append([btn("⬅️ Главное меню", "home")])

    await call.message.edit_text(
        text,
        reply_markup=kb(rows),
    )
    await call.answer()


@dp.callback_query(F.data.startswith("product:"))
async def cb_product(call: CallbackQuery):
    try:
        product_id = int(call.data.split(":", 1)[1])
    except ValueError:
        await call.answer("Некорректный товар.", show_alert=True)
        return

    product = await db_one(
        "SELECT * FROM products WHERE id=? AND active=1",
        (product_id,),
    )

    if not product:
        await call.answer("Товар недоступен.", show_alert=True)
        return

    discounts = await get_active_discounts(call.from_user.id)

    rows = []
    if discounts:
        rows.append([
            btn(
                f"Применить скидку {d['percent']}%",
                f"product_buy:{product_id}:{d['id']}",
            )
        ])

    rows.append([
        btn(
            f"Купить за {product['price']} ⭐ без скидки",
            f"product_buy:{product_id}:0",
        )
    ])
    rows.append([btn("⬅️ Магазин", "shop")])

    text = (
        f"🛒 <b>{esc(product['name'])}</b>\n\n"
        f"{esc(product['description'])}\n\n"
        f"Цена: <b>{product['price']} ⭐</b>\n"
    )

    if discounts:
        text += "\nУ тебя есть доступные скидки. Выбери одну ниже."
    else:
        text += "\nНет доступных скидок. Купить можно по полной цене."

    await call.message.edit_text(text, reply_markup=kb(rows))
    await call.answer()


@dp.callback_query(F.data.startswith("product_buy:"))
async def cb_product_buy(call: CallbackQuery):
    parts = call.data.split(":")

    if len(parts) != 3:
        await call.answer("Некорректный запрос.", show_alert=True)
        return

    try:
        product_id = int(parts[1])
        discount_id = int(parts[2])
    except ValueError:
        await call.answer("Некорректный товар.", show_alert=True)
        return

    product = await db_one(
        "SELECT * FROM products WHERE id=? AND active=1",
        (product_id,),
    )

    if not product:
        await call.answer("Товар недоступен.", show_alert=True)
        return

    original_price = int(product["price"])
    percent = 0

    if discount_id:
        discount = await db_one(
            """
            SELECT * FROM user_discounts
            WHERE id=? AND user_id=? AND status='unused'
            """,
            (discount_id, call.from_user.id),
        )

        if not discount:
            await call.answer(
                "Скидка уже использована или не принадлежит тебе.",
                show_alert=True,
            )
            return

        percent = int(discount["percent"])

    final_price = (
        max(1, math.ceil(original_price * (100 - percent) / 100))
        if percent else original_price
    )

    extra = f"{product_id},{discount_id}"
    payload = await make_payload("product", call.from_user.id, extra)

    try:
        await send_invoice(
            call.from_user.id,
            product["name"],
            (
                f"{product['description']} "
                f"Цена: {final_price} Stars. Скидка: {percent}%."
            ),
            final_price,
            payload,
        )
        await call.answer("Счёт отправлен в личные сообщения.")
    except Exception:
        log.exception("Product invoice error")
        await call.answer("Не удалось отправить счёт.", show_alert=True)


# ============================================================
#  PREMIUM PAGE
# ============================================================

@dp.callback_query(F.data == "premium")
async def cb_premium(call: CallbackQuery):
    row = await db_one(
        "SELECT premium_until FROM users WHERE user_id=?",
        (call.from_user.id,),
    )

    until = int(row["premium_until"]) if row else 0

    if until > int(time.time()):
        status = (
            "✅ Premium активен до "
            f"<code>{time.strftime('%Y-%m-%d %H:%M UTC', time.gmtime(until))}</code>"
        )
    else:
        status = "Сейчас Premium не активен."

    await call.message.edit_text(
        "👑 <b>Premium Script Finder</b>\n\n"
        f"{status}\n\n"
        "Premium открывает дополнительные источники поиска:\n"
        "• ScriptBlox\n"
        "• Scriptrb\n"
        "• DeltaScripts.org\n"
        "• DeltaScripts.ru\n\n"
        "Промокоды Premium:\n"
        "• 3 дня — 10 ⭐\n"
        "• 5 дней — 18 ⭐",
        reply_markup=kb([
            [btn("Premium на 3 дня — 10 ⭐", "promo_buy:premium3")],
            [btn("Premium на 5 дней — 18 ⭐", "promo_buy:premium5")],
            [btn("⬅️ Главное меню", "home")],
        ]),
    )
    await call.answer()


# ============================================================
#  ROULETTE
# ============================================================

@dp.callback_query(F.data == "roulette")
async def cb_roulette(call: CallbackQuery):
    scripts = await db_all(
        """
        SELECT title FROM roulette_scripts
        WHERE active=1 ORDER BY id
        """
    )

    count = len(scripts)

    if count != ROULETTE_SLOTS:
        text = (
            "🎰 <b>Рулетка</b>\n\n"
            f"Стоимость прокрута: <b>{ROULETTE_PRICE} ⭐</b>\n"
            f"Добавлено админских скриптов: {count}/7.\n\n"
            "Рулетка откроется после добавления всех семи скриптов."
        )
        markup = back_menu(call.from_user.id)
    else:
        text = (
            "🎰 <b>Рулетка Script Finder</b>\n\n"
            "В пуле 7 скриптов, добавленных администратором.\n"
            "Каждый прокрут стоит ровно <b>7 ⭐</b>.\n"
            "Результат определяется после подтверждения платежа."
        )
        markup = kb([
            [btn("🎰 Прокрутить — 7 ⭐", "roulette_spin")],
            [btn("⬅️ Главное меню", "home")],
        ])

    await call.message.edit_text(text, reply_markup=markup)
    await call.answer()


@dp.callback_query(F.data == "roulette_spin")
async def cb_roulette_spin(call: CallbackQuery):
    scripts = await db_all(
        "SELECT id FROM roulette_scripts WHERE active=1"
    )

    if len(scripts) != ROULETTE_SLOTS:
        await call.answer(
            "Нужно ровно 7 скриптов от администратора.",
            show_alert=True,
        )
        return

    payload = await make_payload("roulette", call.from_user.id)

    try:
        await send_invoice(
            call.from_user.id,
            "Рулетка Script Finder",
            "Один прокрут рулетки из 7 админских скриптов",
            ROULETTE_PRICE,
            payload,
        )
        await call.answer("Счёт на 7 ⭐ отправлен.")
    except Exception:
        log.exception("Roulette invoice error")
        await call.answer("Не удалось отправить счёт.", show_alert=True)


# ============================================================
#  SCRIPT SEARCH
# ============================================================

async def http_get_text(url: str) -> str:
    async with aiohttp.ClientSession(
        timeout=HTTP_TIMEOUT,
        headers=HEADERS,
    ) as session:
        async with session.get(
            url,
            allow_redirects=True,
        ) as response:
            if response.status != 200:
                raise RuntimeError(
                    f"HTTP {response.status}: {url}"
                )
            return await response.text(errors="ignore")


async def scriptblox_search(game: str, limit: int = 5):
    url = (
        "https://scriptblox.com/api/script/search?q="
        + quote_plus(game)
    )

    async with aiohttp.ClientSession(
        timeout=HTTP_TIMEOUT,
        headers=HEADERS,
    ) as session:
        async with session.get(url) as response:
            if response.status != 200:
                raise RuntimeError(
                    f"ScriptBlox HTTP {response.status}"
                )
            data = await response.json(content_type=None)

    container = data.get("result", {})
    items = container.get("scripts", [])
    results = []

    for item in items:
        title = str(item.get("title") or "Без названия")
        game_data = item.get("game") or {}

        if isinstance(game_data, dict):
            game_name = str(game_data.get("name") or "")
        else:
            game_name = str(game_data)

        # Если API явно указал другую игру, результат не показываем.
        if game_name and game.lower() not in game_name.lower():
            continue

        script_id = item.get("_id") or item.get("id")
        if not script_id:
            continue

        results.append({
            "title": title,
            "url": f"https://scriptblox.com/script/{script_id}",
            "source": "ScriptBlox",
            "game": game_name or game,
        })

        if len(results) >= limit:
            break

    return results


async def scrape_search_page(
    search_url: str,
    game: str,
    source_name: str,
    limit: int = 5,
):
    """
    Общий HTML-поиск для сайтов, у которых нет подтверждённого
    публичного API. Реальная выдача зависит от структуры сайта.
    """
    if not valid_http_url(search_url):
        return []

    content = await http_get_text(search_url)
    soup = BeautifulSoup(content, "html.parser")
    needle = game.casefold()

    results = []
    seen = set()

    for anchor in soup.find_all("a", href=True):
        title = " ".join(anchor.get_text(" ", strip=True).split())
        href = urljoin(search_url, anchor["href"].strip())

        if len(title) < 4 or not valid_http_url(href):
            continue

        combined = (title + " " + href).casefold()

        # Не показываем случайные ссылки, в которых не упоминается игра.
        if needle not in combined:
            continue

        if href in seen or href.rstrip("/") == search_url.rstrip("/"):
            continue

        seen.add(href)

        results.append({
            "title": title[:180],
            "url": href,
            "source": source_name,
            "game": game,
        })

        if len(results) >= limit:
            break

    return results


async def admin_script_search(game: str, limit: int = 5):
    rows = await db_all(
        """
        SELECT title, url, source, game
        FROM scripts
        WHERE lower(game)=lower(?) OR lower(title) LIKE lower(?)
        ORDER BY id DESC LIMIT ?
        """,
        (game, f"%{game}%", limit),
    )

    return [
        {
            "title": row["title"],
            "url": row["url"],
            "source": row["source"],
            "game": row["game"],
        }
        for row in rows
    ]


async def search_sources(game: str, premium: bool):
    results = []
    failures = []

    try:
        results.extend(await scriptblox_search(game, 5))
    except Exception as exc:
        log.warning("ScriptBlox search failed: %s", exc)
        failures.append("ScriptBlox")

    try:
        scriptrb_url = (
            "https://scriptrb.com/?s=" + quote_plus(game)
        )
        results.extend(
            await scrape_search_page(
                scriptrb_url, game, "Scriptrb", 5
            )
        )
    except Exception as exc:
        log.warning("Scriptrb search failed: %s", exc)
        failures.append("Scriptrb")

    if premium:
        sources = [
            (
                "DeltaScripts.org",
                "https://deltascripts.org/?s=" + quote_plus(game),
            ),
            (
                "DeltaScripts.ru",
                "https://deltascripts.ru/?s=" + quote_plus(game),
            ),
        ]

        for source, url in sources:
            try:
                results.extend(
                    await scrape_search_page(
                        url, game, source, 5
                    )
                )
            except Exception as exc:
                log.warning("%s search failed: %s", source, exc)
                failures.append(source)

    try:
        results.extend(await admin_script_search(game, 5))
    except Exception:
        log.exception("Admin script search failed")

    # Deduplicate URLs.
    unique = []
    seen = set()

    for result in results:
        url = result["url"]
        if url in seen:
            continue
        seen.add(url)
        unique.append(result)

    return unique[:20], failures


@dp.callback_query(F.data == "search")
async def cb_search(call: CallbackQuery, state: FSMContext):
    await state.set_state(SearchState.waiting_for_game)
    await call.message.answer(
        "🔎 Напиши название игры.\n"
        "Например: <b>MM2</b> или <b>Steal an Egg</b>."
    )
    await call.answer()


@dp.message(SearchState.waiting_for_game)
async def process_search(message: Message, state: FSMContext):
    game = (message.text or "").strip()
    await state.clear()

    if len(game) < 2 or len(game) > 80:
        await message.answer(
            "Название игры должно быть от 2 до 80 символов."
        )
        return

    await message.answer(
        f"🔎 Ищу скрипты для <b>{esc(game)}</b>…"
    )

    premium = await user_is_premium(message.from_user.id)

    try:
        results, failures = await search_sources(game, premium)
    except Exception:
        log.exception("Search error")
        await message.answer("Поиск временно недоступен. Попробуй позже.")
        return

    if not results:
        text = (
            f"По игре <b>{esc(game)}</b> подходящих результатов не найдено."
        )
        if failures:
            text += (
                "\n\nНедоступные источники: "
                + ", ".join(esc(x) for x in failures)
            )
        await message.answer(
            text,
            reply_markup=main_keyboard(message.from_user.id),
        )
        return

    text = (
        f"🔎 <b>Результаты поиска: {esc(game)}</b>\n\n"
    )

    for index, item in enumerate(results, 1):
        text += (
            f"{index}. <b>{esc(item['title'])}</b>\n"
            f"🎮 Игра: {esc(item.get('game') or game)}\n"
            f"🌐 Источник: {esc(item['source'])}\n"
            f"🔗 {esc(item['url'])}\n\n"
        )

    if failures:
        text += (
            "⚠️ Часть источников не ответила: "
            + ", ".join(esc(x) for x in failures)
        )

    # Telegram ограничивает длину одного сообщения.
    chunks = [
        text[i:i + 3800]
        for i in range(0, len(text), 3800)
    ]

    for index, chunk in enumerate(chunks):
        await message.answer(
            chunk,
            disable_web_page_preview=True,
            reply_markup=(
                main_keyboard(message.from_user.id)
                if index == len(chunks) - 1
                else None
            ),
        )


# ============================================================
#  SPONSOR AND COMMUNITY
# ============================================================

@dp.callback_query(F.data == "sponsor")
async def cb_sponsor(call: CallbackQuery):
    rows = []

    if SPONSOR_URL and valid_http_url(SPONSOR_URL):
        rows.append([btn("🤝 Открыть спонсора", url=SPONSOR_URL)])

    rows.append([btn("⬅️ Главное меню", "home")])

    text = (
        "🤝 <b>Спонсор Script Finder</b>\n\n"
        "Спасибо за поддержку проекта."
    )

    if not SPONSOR_URL:
        text += (
            "\nСсылка пока не настроена. Укажи SPONSOR_URL "
            "в переменных окружения."
        )

    await call.message.edit_text(text, reply_markup=kb(rows))
    await call.answer()


@dp.callback_query(F.data == "community")
async def cb_community(call: CallbackQuery):
    rows = []

    if COMMUNITY_URL and valid_http_url(COMMUNITY_URL):
        rows.append([
            btn("👥 Открыть сообщество", url=COMMUNITY_URL)
        ])

    if CHANNEL_URL and valid_http_url(CHANNEL_URL):
        rows.append([
            btn("📣 Открыть канал", url=CHANNEL_URL)
        ])

    rows.append([btn("⬅️ Главное меню", "home")])

    text = (
        "👥 <b>Сообщество Script Finder</b>\n\n"
        "Здесь находятся ссылки на сообщество и канал проекта."
    )

    if not COMMUNITY_URL and not CHANNEL_URL:
        text += "\nАдминистратор ещё не настроил ссылки."

    await call.message.edit_text(text, reply_markup=kb(rows))
    await call.answer()


# ============================================================
#  DONATIONS
# ============================================================

@dp.callback_query(F.data == "donate")
async def cb_donate(call: CallbackQuery):
    await call.message.edit_text(
        "❤️ <b>Поддержать Script Finder</b>\n\n"
        "Выбери сумму доната в Telegram Stars.",
        reply_markup=kb([
            [
                btn("5 ⭐", "donate_amount:5"),
                btn("10 ⭐", "donate_amount:10"),
            ],
            [
                btn("25 ⭐", "donate_amount:25"),
                btn("50 ⭐", "donate_amount:50"),
            ],
            [btn("⬅️ Главное меню", "home")],
        ]),
    )
    await call.answer()


@dp.callback_query(F.data.startswith("donate_amount:"))
async def cb_donate_amount(call: CallbackQuery):
    try:
        amount = int(call.data.split(":", 1)[1])
    except ValueError:
        await call.answer("Неверная сумма.", show_alert=True)
        return

    if amount not in (5, 10, 25, 50):
        await call.answer("Неверная сумма.", show_alert=True)
        return

    payload = await make_payload(
        "donate",
        call.from_user.id,
        str(amount),
    )

    try:
        await send_invoice(
            call.from_user.id,
            "Донат Script Finder",
            "Добровольная поддержка проекта",
            amount,
            payload,
        )
        await call.answer("Счёт отправлен в личные сообщения.")
    except Exception:
        log.exception("Donation invoice error")
        await call.answer("Не удалось отправить счёт.", show_alert=True)


# ============================================================
#  ADMIN HELPERS
# ============================================================

def admin_user(user_id: int) -> bool:
    return int(user_id) == ADMIN_ID


async def require_admin_message(message: Message) -> bool:
    if not admin_user(message.from_user.id):
        await message.answer("⛔ Эта команда доступна только администратору.")
        return False
    return True


async def require_admin_callback(call: CallbackQuery) -> bool:
    if not admin_user(call.from_user.id):
        await call.answer("Нет доступа.", show_alert=True)
        return False
    return True


# ============================================================
#  ADMIN PANEL
# ============================================================

@dp.callback_query(F.data == "admin")
async def cb_admin(call: CallbackQuery):
    if not await require_admin_callback(call):
        return

    await call.message.edit_text(
        "🛡 <b>Админ-панель Script Finder BETA</b>\n\n"
        "Команды:\n"
        "/addscript GAME|TITLE|URL\n"
        "/rouletteadd TITLE|URL\n"
        "/roulette — список семи скриптов\n"
        "/rouletteclear — очистить рулетку\n"
        "/addproduct NAME|PRICE|DESCRIPTION|DELIVERY\n"
        "/products — товары магазина\n"
        "/productoff ID — выключить товар\n"
        "/users — пользователи\n"
        "/codes — промокоды\n"
        "/stats — статистика\n"
        "/helpadmin — справка",
        reply_markup=back_menu(call.from_user.id),
    )
    await call.answer()


@dp.message(Command("helpadmin"))
async def cmd_helpadmin(message: Message):
    if not await require_admin_message(message):
        return

    await message.answer(
        "<b>Админские команды</b>\n\n"
        "<code>/addscript GAME|TITLE|URL</code>\n"
        "Добавить скрипт в базу поиска.\n\n"
        "<code>/rouletteadd TITLE|URL</code>\n"
        "Добавить один скрипт рулетки. Максимум 7 активных.\n\n"
        "<code>/roulette</code> — посмотреть список.\n"
        "<code>/rouletteclear</code> — очистить список.\n\n"
        "<code>/addproduct NAME|PRICE|DESCRIPTION|DELIVERY</code>\n"
        "Добавить товар магазина.\n\n"
        "<code>/products</code> — список товаров.\n"
        "<code>/productoff ID</code> — отключить товар.\n"
        "<code>/users</code> — число пользователей.\n"
        "<code>/codes</code> — последние промокоды.\n"
        "<code>/stats</code> — статистика."
    )


@dp.message(Command("addscript"))
async def cmd_addscript(message: Message):
    if not await require_admin_message(message):
        return

    raw = message.text.partition(" ")[2]
    parts = [x.strip() for x in raw.split("|", 2)]

    if len(parts) != 3 or not all(parts):
        await message.answer(
            "Формат:\n<code>/addscript GAME|TITLE|URL</code>"
        )
        return

    game, title, url = parts

    if not valid_http_url(url):
        await message.answer("URL должен начинаться с http:// или https://.")
        return

    await db_execute(
        """
        INSERT INTO scripts(game, title, url, source, created_at)
        VALUES (?, ?, ?, 'admin', ?)
        """,
        (game, title, url, int(time.time())),
    )

    await message.answer(
        f"✅ Скрипт добавлен.\n"
        f"Игра: <b>{esc(game)}</b>\n"
        f"Название: <b>{esc(title)}</b>"
    )


@dp.message(Command("rouletteadd"))
async def cmd_rouletteadd(message: Message):
    if not await require_admin_message(message):
        return

    raw = message.text.partition(" ")[2]
    parts = [x.strip() for x in raw.split("|", 1)]

    if len(parts) != 2 or not all(parts):
        await message.answer(
            "Формат:\n<code>/rouletteadd TITLE|URL</code>"
        )
        return

    title, url = parts

    if not valid_http_url(url):
        await message.answer("URL должен быть корректной HTTP(S)-ссылкой.")
        return

    row = await db_one(
        "SELECT COUNT(*) AS n FROM roulette_scripts WHERE active=1"
    )
    count = int(row["n"])

    if count >= ROULETTE_SLOTS:
        await message.answer(
            "Уже есть 7 активных скриптов. Используй /rouletteclear, "
            "если хочешь заменить список."
        )
        return

    await db_execute(
        """
        INSERT INTO roulette_scripts(title, url, active, created_at)
        VALUES (?, ?, 1, ?)
        """,
        (title, url, int(time.time())),
    )

    await message.answer(
        f"✅ Скрипт рулетки добавлен. Сейчас: {count + 1}/7."
    )


@dp.message(Command("roulette"))
async def cmd_roulette_list(message: Message):
    if not await require_admin_message(message):
        return

    rows = await db_all(
        """
        SELECT id, title, url
        FROM roulette_scripts
        WHERE active=1
        ORDER BY id
        """
    )

    if not rows:
        await message.answer("Рулетка пуста.")
        return

    text = "🎰 <b>Скрипты рулетки</b>\n\n"

    for row in rows:
        text += (
            f"#{row['id']} — <b>{esc(row['title'])}</b>\n"
            f"{esc(row['url'])}\n\n"
        )

    text += f"Всего: {len(rows)}/7"

    await message.answer(
        text,
        disable_web_page_preview=True,
    )


@dp.message(Command("rouletteclear"))
async def cmd_rouletteclear(message: Message):
    if not await require_admin_message(message):
        return

    await db_execute("DELETE FROM roulette_scripts")
    await message.answer(
        "Список рулетки очищен. Добавь семь новых скриптов через /rouletteadd."
    )


@dp.message(Command("addproduct"))
async def cmd_addproduct(message: Message):
    if not await require_admin_message(message):
        return

    raw = message.text.partition(" ")[2]
    parts = [x.strip() for x in raw.split("|", 3)]

    if len(parts) != 4 or not parts[0] or not parts[2]:
        await message.answer(
            "Формат:\n"
            "<code>/addproduct NAME|PRICE|DESCRIPTION|DELIVERY</code>"
        )
        return

    name, price_raw, description, delivery = parts

    try:
        price = int(price_raw)
        if price < 1:
            raise ValueError
    except ValueError:
        await message.answer("Цена должна быть положительным числом Stars.")
        return

    await db_execute(
        """
        INSERT INTO products(
            name, description, price, delivery, active, created_at
        ) VALUES (?, ?, ?, ?, 1, ?)
        """,
        (name, description, price, delivery, int(time.time())),
    )

    await message.answer(
        f"✅ Товар добавлен:\n"
        f"<b>{esc(name)}</b> — {price} ⭐"
    )


@dp.message(Command("products"))
async def cmd_products(message: Message):
    if not await require_admin_message(message):
        return

    rows = await db_all(
        "SELECT * FROM products ORDER BY id DESC"
    )

    if not rows:
        await message.answer("Товаров пока нет.")
        return

    text = "🛒 <b>Товары магазина</b>\n\n"

    for row in rows:
        text += (
            f"ID: <code>{row['id']}</code>\n"
            f"Название: <b>{esc(row['name'])}</b>\n"
            f"Цена: {row['price']} ⭐\n"
            f"Активен: {'да' if row['active'] else 'нет'}\n\n"
        )

    await message.answer(text)


@dp.message(Command("productoff"))
async def cmd_productoff(message: Message):
    if not await require_admin_message(message):
        return

    try:
        product_id = int(message.text.split(maxsplit=1)[1])
    except (IndexError, ValueError):
        await message.answer("Использование: /productoff ID")
        return

    await db_execute(
        "UPDATE products SET active=0 WHERE id=?",
        (product_id,),
    )
    await message.answer("Если товар существовал, он отключён.")


@dp.message(Command("users"))
async def cmd_users(message: Message):
    if not await require_admin_message(message):
        return

    row = await db_one("SELECT COUNT(*) AS n FROM users")
    await message.answer(f"👥 Пользователей в базе: {row['n']}")


@dp.message(Command("codes"))
async def cmd_codes(message: Message):
    if not await require_admin_message(message):
        return

    rows = await db_all(
        """
        SELECT code, user_id, promo_type, description,
               status, created_at
        FROM promo_codes
        ORDER BY id DESC LIMIT 50
        """
    )

    if not rows:
        await message.answer("Промокодов пока нет.")
        return

    text = "🎟 <b>Последние промокоды</b>\n\n"

    for row in rows:
        status = (
            "Не активирован"
            if row["status"] == "unused"
            else "Активирован"
        )
        text += (
            f"Код: <code>{esc(row['code'])}</code>\n"
            f"Функция: {esc(row['description'])}\n"
            f"Пользователь: <code>{row['user_id']}</code>\n"
            f"Статус: {status}\n\n"
        )

    await message.answer(text)


@dp.message(Command("stats"))
async def cmd_stats(message: Message):
    if not await require_admin_message(message):
        return

    users = await db_one("SELECT COUNT(*) AS n FROM users")
    payments = await db_one(
        "SELECT COUNT(*) AS n FROM payments WHERE status='completed'"
    )
    stars = await db_one(
        """
        SELECT COALESCE(SUM(amount), 0) AS n
        FROM payments WHERE status='completed'
        """
    )
    promos = await db_one("SELECT COUNT(*) AS n FROM promo_codes")
    used = await db_one(
        "SELECT COUNT(*) AS n FROM promo_codes WHERE status='used'"
    )
    spins = await db_one("SELECT COUNT(*) AS n FROM roulette_log")

    await message.answer(
        "📊 <b>Статистика Script Finder</b>\n\n"
        f"Пользователи: {users['n']}\n"
        f"Завершённые платежи: {payments['n']}\n"
        f"Сумма завершённых платежей: {stars['n']} ⭐\n"
        f"Созданные промокоды: {promos['n']}\n"
        f"Активированные промокоды: {used['n']}\n"
        f"Прокрутки рулетки: {spins['n']}"
    )


# ============================================================
#  FALLBACK HANDLER
# ============================================================

@dp.message()
async def fallback_message(message: Message):
    if message.from_user:
        await ensure_user(message.from_user)

    await message.answer(
        "Используй кнопки меню или команду /start.",
        reply_markup=main_keyboard(message.from_user.id),
    )


# ============================================================
#  HEALTH SERVER
# ============================================================

async def health_handler(request: web.Request):
    return web.json_response({
        "status": "ok",
        "service": "Script Finder BETA",
        "time": int(time.time()),
    })


async def start_health_server():
    app = web.Application()
    app.router.add_get("/", health_handler)
    app.router.add_get("/health", health_handler)

    runner = web.AppRunner(app)
    await runner.setup()

    site = web.TCPSite(runner, HOST, PORT)
    await site.start()

    log.info("Health server started at %s:%s", HOST, PORT)
    return runner


# ============================================================
#  STARTUP / SHUTDOWN
# ============================================================

async def main():
    if not BOT_TOKEN:
        raise RuntimeError(
            "Не задан BOT_TOKEN. Создай бота через BotFather "
            "и передай токен через переменную окружения BOT_TOKEN."
        )

    await init_db()

    await bot.set_my_commands([
        BotCommand(command="start", description="Главное меню"),
        BotCommand(command="menu", description="Открыть меню"),
        BotCommand(command="id", description="Узнать Telegram ID"),
    ])

    runner = await start_health_server()

    log.info("Starting Script Finder BETA")

    try:
        await dp.start_polling(
            bot,
            allowed_updates=dp.resolve_used_update_types(),
        )
    finally:
        await runner.cleanup()

        if DB is not None:
            await DB.close()

        await bot.session.close()
        log.info("Script Finder BETA stopped")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        log.info("Shutdown requested")
