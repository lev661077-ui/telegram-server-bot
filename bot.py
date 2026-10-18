
import os
import html
import json
import sqlite3
import logging
import asyncio
from datetime import datetime, timedelta, timezone
from pathlib import Path

from aiohttp import web, ClientSession, ClientTimeout
from aiogram import Bot, Dispatcher, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import Command, CommandStart
from aiogram.types import (
    Message, CallbackQuery, PreCheckoutQuery,
    LabeledPrice, InlineKeyboardMarkup, InlineKeyboardButton,
    ReplyKeyboardMarkup, KeyboardButton,
)
from aiogram.exceptions import TelegramAPIError


# ============================================================
# CONFIG
# ============================================================

TOKEN = os.getenv("BOT_TOKEN", "").strip()
ADMIN_ID = int(os.getenv("ADMIN_ID", "8996403397"))
PORT = int(os.getenv("PORT", "10000"))
DB_PATH = os.getenv("DB_PATH", "data/bot.sqlite3")

PREMIUM_PRICE = int(os.getenv("PREMIUM_PRICE", "60"))
RENEW_PRICE = int(os.getenv("RENEW_PRICE", "20"))
DONATION_PRICE = int(os.getenv("DONATION_PRICE", "10"))
PREMIUM_DAYS = int(os.getenv("PREMIUM_DAYS", "7"))

AI_API_KEY = os.getenv("AI_API_KEY", "").strip()
AI_BASE_URL = os.getenv(
    "AI_BASE_URL", "https://api.openai.com/v1"
).rstrip("/")
AI_MODEL = os.getenv("AI_MODEL", "gpt-4o-mini")

if not TOKEN:
    raise RuntimeError("Add BOT_TOKEN to Render environment variables.")

Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
log = logging.getLogger("roulette_beta")

bot = Bot(
    TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML),
)
dp = Dispatcher()

waiting = {}
search_state = set()
promo_state = set()


# ============================================================
# DATABASE
# ============================================================

def connect():
    con = sqlite3.connect(DB_PATH, timeout=20)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA busy_timeout=20000")
    return con


def now():
    return datetime.now(timezone.utc)


def stamp():
    return now().isoformat()


def safe(value):
    return html.escape(str(value or ""))


def init_db():
    with connect() as db:
        db.executescript("""
        CREATE TABLE IF NOT EXISTS users(
            id INTEGER PRIMARY KEY,
            username TEXT DEFAULT '',
            name TEXT DEFAULT '',
            joined TEXT NOT NULL,
            blocked INTEGER DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS subscriptions(
            user_id INTEGER PRIMARY KEY,
            expires TEXT NOT NULL,
            source TEXT DEFAULT 'payment'
        );

        CREATE TABLE IF NOT EXISTS payments(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            charge TEXT UNIQUE NOT NULL,
            payload TEXT NOT NULL,
            amount INTEGER NOT NULL,
            currency TEXT NOT NULL,
            created TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS scripts(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            category TEXT NOT NULL,
            platform TEXT DEFAULT 'Все',
            description TEXT DEFAULT '',
            url TEXT DEFAULT '',
            premium INTEGER DEFAULT 0,
            sponsor INTEGER DEFAULT 0,
            active INTEGER DEFAULT 1,
            created TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS communities(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            category TEXT DEFAULT 'Общее',
            description TEXT DEFAULT '',
            url TEXT NOT NULL,
            premium INTEGER DEFAULT 0,
            active INTEGER DEFAULT 1
        );

        CREATE TABLE IF NOT EXISTS products(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT DEFAULT '',
            price INTEGER NOT NULL,
            active INTEGER DEFAULT 1
        );

        CREATE TABLE IF NOT EXISTS promos(
            code TEXT PRIMARY KEY,
            description TEXT NOT NULL,
            days INTEGER DEFAULT 0,
            uses_limit INTEGER DEFAULT 1,
            uses INTEGER DEFAULT 0,
            enabled INTEGER DEFAULT 1
        );

        CREATE TABLE IF NOT EXISTS promo_users(
            code TEXT NOT NULL,
            user_id INTEGER NOT NULL,
            created TEXT NOT NULL,
            PRIMARY KEY(code, user_id)
        );

        CREATE TABLE IF NOT EXISTS favorites(
            user_id INTEGER NOT NULL,
            script_id INTEGER NOT NULL,
            PRIMARY KEY(user_id, script_id)
        );

        CREATE TABLE IF NOT EXISTS audit(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            actor INTEGER NOT NULL,
            action TEXT NOT NULL,
            details TEXT DEFAULT '',
            created TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_scripts_active
            ON scripts(active, category);

        CREATE INDEX IF NOT EXISTS idx_payments_user
            ON payments(user_id);
        """)

        count = db.execute(
            "SELECT COUNT(*) FROM scripts"
        ).fetchone()[0]

        if count == 0:
            examples = [
                (
                    "Рулетка: обзор правил",
                    "Рулетка",
                    "Web",
                    "Информационный обзор правил и типов ставок.",
                    "https://example.com/",
                    0, 0, 1, stamp(),
                ),
                (
                    "Анализ истории результатов",
                    "Аналитика",
                    "Web",
                    "Демонстрационный инструмент для просмотра истории.",
                    "https://example.com/",
                    0, 0, 1, stamp(),
                ),
                (
                    "Расширенный фильтр статистики",
                    "Аналитика",
                    "Web",
                    "Демо-карточка расширенного поиска для Premium.",
                    "https://example.com/",
                    1, 0, 1, stamp(),
                ),
            ]
            db.executemany("""
                INSERT INTO scripts(
                    title, category, platform, description, url,
                    premium, sponsor, active, created
                ) VALUES(?,?,?,?,?,?,?,?,?)
            """, examples)

        if db.execute(
            "SELECT COUNT(*) FROM products"
        ).fetchone()[0] == 0:
            db.execute("""
                INSERT INTO products(title, description, price)
                VALUES(?,?,?)
            """, (
                "Premium на 7 дней",
                "Расширенные фильтры и дополнительные функции поиска.",
                PREMIUM_PRICE,
            ))


def register(user):
    with connect() as db:
        db.execute("""
            INSERT INTO users(id, username, name, joined)
            VALUES(?,?,?,?)
            ON CONFLICT(id) DO UPDATE SET
                username=excluded.username,
                name=excluded.name
        """, (
            user.id, user.username or "",
            user.full_name or "", stamp(),
        ))


def log_action(actor, action, details=""):
    with connect() as db:
        db.execute("""
            INSERT INTO audit(actor, action, details, created)
            VALUES(?,?,?,?)
        """, (actor, action, str(details)[:500], stamp()))


def admin(uid):
    return int(uid) == ADMIN_ID


def premium(uid):
    if admin(uid):
        return True

    with connect() as db:
        row = db.execute(
            "SELECT expires FROM subscriptions WHERE user_id=?",
            (uid,),
        ).fetchone()

    if not row:
        return False

    try:
        return datetime.fromisoformat(row["expires"]) > now()
    except ValueError:
        return False


def expiry(uid):
    if admin(uid):
        return "Бессрочно — администратор"

    with connect() as db:
        row = db.execute(
            "SELECT expires FROM subscriptions WHERE user_id=?",
            (uid,),
        ).fetchone()

    if not row:
        return "Нет Premium"

    try:
        end = datetime.fromisoformat(row["expires"])
        if end <= now():
            return "Подписка истекла"
        return end.strftime("%d.%m.%Y %H:%M UTC")
    except ValueError:
        return "Неизвестно"


def grant_premium(uid, days, source="admin"):
    if admin(uid):
        return "Бессрочно"

    days = max(1, min(int(days), 36500))
    current = expiry_datetime(uid)
    start = current if current and current > now() else now()
    end = start + timedelta(days=days)

    with connect() as db:
        db.execute("""
            INSERT INTO subscriptions(user_id, expires, source)
            VALUES(?,?,?)
            ON CONFLICT(user_id) DO UPDATE SET
                expires=excluded.expires,
                source=excluded.source
        """, (uid, end.isoformat(), source))

    return end.strftime("%d.%m.%Y %H:%M UTC")


def expiry_datetime(uid):
    with connect() as db:
        row = db.execute(
            "SELECT expires FROM subscriptions WHERE user_id=?",
            (uid,),
        ).fetchone()

    if not row:
        return None
    try:
        return datetime.fromisoformat(row["expires"])
    except ValueError:
        return None


def revoke_premium(uid):
    if admin(uid):
        return False
    with connect() as db:
        db.execute(
            "DELETE FROM subscriptions WHERE user_id=?", (uid,)
        )
    return True


def save_payment(user_id, charge, payload, amount, currency):
    with connect() as db:
        cur = db.execute("""
            INSERT OR IGNORE INTO payments(
                user_id, charge, payload, amount, currency, created
            ) VALUES(?,?,?,?,?,?)
        """, (
            user_id, charge, payload, amount, currency, stamp()
        ))
        return cur.rowcount == 1


# ============================================================
# KEYBOARDS
# ============================================================

def menu(uid):
    rows = [
        [KeyboardButton(text="🔎 Поиск скриптов"),
         KeyboardButton(text="👑 Premium")],
        [KeyboardButton(text="🛍 Магазин"),
         KeyboardButton(text="🎟 Промокод")],
        [KeyboardButton(text="🌐 Сообщества"),
         KeyboardButton(text="⭐ Избранное")],
        [KeyboardButton(text="👤 Профиль"),
         KeyboardButton(text="❤️ Поддержать")],
        [KeyboardButton(text="ℹ️ Помощь")],
    ]
    if admin(uid):
        rows.append([KeyboardButton(text="🛠 Админ-панель")])
    return ReplyKeyboardMarkup(
        keyboard=rows,
        resize_keyboard=True,
    )


def inline(rows):
    return InlineKeyboardMarkup(inline_keyboard=rows)


def main_button():
    return inline([[
        InlineKeyboardButton(
            text="⬅️ Главное меню", callback_data="main"
        )
    ]])


def premium_buttons(uid):
    if admin(uid):
        return main_button()
    return inline([
        [InlineKeyboardButton(
            text=f"⭐ Купить Premium — {PREMIUM_PRICE} Stars",
            callback_data="buy_premium"
        )],
        [InlineKeyboardButton(
            text=f"🔄 Продлить — {RENEW_PRICE} Stars",
            callback_data="renew_premium"
        )],
        [InlineKeyboardButton(
            text="⬅️ Назад", callback_data="main"
        )],
    ])


def admin_buttons():
    return inline([
        [InlineKeyboardButton(
            text="📊 Статистика", callback_data="a:stats"
        )],
        [InlineKeyboardButton(
            text="👑 Premium-пользователи",
            callback_data="a:premium"
        )],
        [InlineKeyboardButton(
            text="💳 Платежи", callback_data="a:payments"
        )],
        [InlineKeyboardButton(
            text="📚 Каталог скриптов", callback_data="a:scripts"
        )],
        [InlineKeyboardButton(
            text="🌐 Сообщества", callback_data="a:communities"
        )],
        [InlineKeyboardButton(
            text="🤖 AI-анализ", callback_data="a:ai"
        )],
        [InlineKeyboardButton(
            text="⬅️ Главное меню", callback_data="main"
        )],
    ])


# ============================================================
# NOTIFICATIONS AND PAYMENTS
# ============================================================

async def admin_notify(text):
    try:
        await bot.send_message(ADMIN_ID, text)
    except TelegramAPIError:
        log.exception("Admin notification failed")


async def invoice(message, title, description, payload, amount):
    await bot.send_invoice(
        chat_id=message.chat.id,
        title=title[:32],
        description=description[:255],
        payload=payload,
        currency="XTR",
        prices=[LabeledPrice(label=title[:32], amount=amount)],
    )


def expected_amount(payload):
    if payload.startswith("premium:"):
        return PREMIUM_PRICE
    if payload.startswith("renew:"):
        return RENEW_PRICE
    if payload.startswith("donation:"):
        return DONATION_PRICE
    if payload.startswith("product:"):
        with connect() as db:
            try:
                product_id = int(payload.split(":")[1])
            except (ValueError, IndexError):
                return None
            row = db.execute(
                "SELECT price FROM products WHERE id=? AND active=1",
                (product_id,),
            ).fetchone()
            return int(row["price"]) if row else None
    return None


@dp.pre_checkout_query()
async def pre_checkout(query: PreCheckoutQuery):
    payload = query.invoice_payload
    expected = expected_amount(payload)

    try:
        intended_uid = int(payload.rsplit(":", 1)[1])
    except (ValueError, IndexError):
        intended_uid = -1

    if (
        query.currency != "XTR"
        or expected is None
        or query.total_amount != expected
        or intended_uid != query.from_user.id
    ):
        await query.answer(
            ok=False,
            error_message="Заказ не прошёл проверку. Создай новый счёт.",
        )
        return

    await query.answer(ok=True)


@dp.message(F.successful_payment)
async def successful_payment(message: Message):
    payment = message.successful_payment
    if not payment or not message.from_user:
        return

    user_id = message.from_user.id
    payload = payment.invoice_payload

    # Record once. Duplicate updates cannot grant Premium twice.
    inserted = save_payment(
        user_id,
        payment.telegram_payment_charge_id,
        payload,
        payment.total_amount,
        payment.currency,
    )

    if not inserted:
        await message.answer("Этот платёж уже был обработан.")
        return

    await admin_notify(
        "⭐ <b>Новая оплата Telegram Stars</b>\n\n"
        f"Пользователь: {safe(message.from_user.full_name)}\n"
        f"Username: @{safe(message.from_user.username or 'нет')}\n"
        f"ID: <code>{user_id}</code>\n"
        f"Сумма: <b>{payment.total_amount} ⭐</b>\n"
        f"Заказ: <code>{safe(payload)}</code>\n"
        f"Charge ID: <code>{safe(payment.telegram_payment_charge_id)}</code>"
    )

    if payload.startswith(("premium:", "renew:")):
        end = grant_premium(user_id, PREMIUM_DAYS, "payment")
        await message.answer(
            "✅ Оплата подтверждена!\n"
            f"Premium активен до: <b>{safe(end)}</b>"
        )
        await admin_notify(
            f"👑 Premium выдан пользователю <code>{user_id}</code>."
        )
    elif payload.startswith("donation:"):
        await message.answer("❤️ Спасибо за поддержку проекта!")
    elif payload.startswith("product:"):
        await message.answer(
            "✅ Оплата товара подтверждена. "
            "Администратор может проверить заказ в разделе платежей."
        )


# ============================================================
# START, PROFILE, PREMIUM
# ============================================================

@dp.message(CommandStart())
async def start(message: Message):
    register(message.from_user)
    if is_blocked(message.from_user.id):
        return
    await message.answer(
        f"👋 Добро пожаловать в <b>{safe('Script Finder Beta')}</b>!\n\n"
        "Ищи скрипты, изучай каталог, сообщества и Premium-функции.",
        reply_markup=menu(message.from_user.id),
    )


def is_blocked(uid):
    with connect() as db:
        row = db.execute(
            "SELECT blocked FROM users WHERE id=?", (uid,)
        ).fetchone()
    return bool(row and row["blocked"])


@dp.message(Command("id"))
async def cmd_id(message: Message):
    register(message.from_user)
    await message.answer(
        f"Твой Telegram ID: <code>{message.from_user.id}</code>"
    )


@dp.message(Command("profile"))
async def cmd_profile(message: Message):
    await show_profile(message)


async def show_profile(message: Message):
    uid = message.from_user.id
    register(message.from_user)
    status = "👑 Premium" if premium(uid) else "Бесплатный доступ"
    await message.answer(
        f"👤 <b>Профиль</b>\n\n"
        f"ID: <code>{uid}</code>\n"
        f"Имя: {safe(message.from_user.full_name)}\n"
        f"Статус: {status}\n"
        f"Подписка до: {safe(expiry(uid))}",
        reply_markup=main_button(),
    )


@dp.message(Command("premium"))
async def cmd_premium(message: Message):
    await show_premium(message)


async def show_premium(message: Message):
    uid = message.from_user.id
    if premium(uid):
        status = "У тебя активен Premium."
    else:
        status = "Открой расширенные функции с Premium."
    await message.answer(
        f"👑 <b>Premium</b>\n\n{status}\n"
        f"Цена: {PREMIUM_PRICE} Telegram Stars за {PREMIUM_DAYS} дней.",
        reply_markup=premium_buttons(uid),
    )


@dp.callback_query(F.data == "buy_premium")
async def buy_premium(call: CallbackQuery):
    if admin(call.from_user.id):
        await call.answer("У тебя Premium бесплатно.", show_alert=True)
        return
    await invoice(
        call.message,
        "Premium",
        f"Premium-доступ на {PREMIUM_DAYS} дней",
        f"premium:{call.from_user.id}",
        PREMIUM_PRICE,
    )
    await call.answer()


@dp.callback_query(F.data == "renew_premium")
async def renew_premium(call: CallbackQuery):
    if admin(call.from_user.id):
        await call.answer("У тебя постоянный Premium.", show_alert=True)
        return
    await invoice(
        call.message,
        "Продление Premium",
        f"Продление Premium на {PREMIUM_DAYS} дней",
        f"renew:{call.from_user.id}",
        RENEW_PRICE,
    )
    await call.answer()


@dp.message(F.text == "👑 Premium")
async def menu_premium(message: Message):
    await show_premium(message)


@dp.message(F.text == "👤 Профиль")
async def menu_profile(message: Message):
    await show_profile(message)


# ============================================================
# SCRIPT CATALOG AND SEARCH
# ============================================================

def search_scripts(query="", category="", platform="", premium_only=False):
    sql = "SELECT * FROM scripts WHERE active=1"
    params = []

    if query:
        sql += " AND (title LIKE ? OR description LIKE ? OR category LIKE ?)"
        wildcard = f"%{query}%"
        params += [wildcard, wildcard, wildcard]

    if category:
        sql += " AND category=?"
        params.append(category)

    if platform:
        sql += " AND platform=?"
        params.append(platform)

    if premium_only:
        sql += " AND premium=1"

    sql += " ORDER BY sponsor DESC, id DESC LIMIT 30"

    with connect() as db:
        return db.execute(sql, params).fetchall()


def script_card(row, uid):
    is_locked = bool(row["premium"]) and not premium(uid)
    sponsor = "📢 <b>Спонсор</b>\n" if row["sponsor"] else ""
    access = "🔒 Premium" if is_locked else "✅ Доступно"

    text = (
        f"{sponsor}📚 <b>{safe(row['title'])}</b>\n"
        f"Категория: {safe(row['category'])}\n"
        f"Платформа: {safe(row['platform'])}\n"
        f"Доступ: {access}\n\n"
        f"{safe(row['description'])}"
    )

    buttons = []
    if is_locked:
        buttons.append([
            InlineKeyboardButton(
                text="👑 Открыть Premium",
                callback_data="show_premium",
            )
        ])
    else:
        buttons.append([
            InlineKeyboardButton(
                text="🔗 Открыть",
                url=row["url"] if row["url"].startswith(
                    ("https://", "http://")
                ) else "https://example.com/",
            )
        ])

    buttons.append([
        InlineKeyboardButton(
            text="⭐ В избранное",
            callback_data=f"fav:{row['id']}",
        )
    ])
    return text, inline(buttons)


@dp.message(F.text == "🔎 Поиск скриптов")
async def begin_search(message: Message):
    uid = message.from_user.id
    if not premium(uid):
        await message.answer(
            "🔎 Напиши запрос для поиска по названию, категории "
            "или описанию.\n\n"
            "Расширенные фильтры доступны в Premium."
        )
    else:
        await message.answer(
            "👑 Premium-поиск: напиши запрос, название категории "
            "или платформы."
        )
    search_state.add(uid)


@dp.message(Command("search"))
async def command_search(message: Message):
    args = message.text.partition(" ")[2].strip()
    if not args:
        await message.answer("Пример: /search аналитика")
        return
    await deliver_search(message, args)


async def deliver_search(message: Message, query: str):
    uid = message.from_user.id
    rows = search_scripts(query=query)
    if not rows:
        await message.answer(
            "Ничего не найдено. Попробуй другое слово."
        )
        return

    await message.answer(f"🔎 Найдено результатов: {len(rows)}")
    for row in rows:
        text, keyboard = script_card(row, uid)
        await message.answer(text, reply_markup=keyboard)


@dp.message(F.text == "⭐ Избранное")
async def favorites(message: Message):
    uid = message.from_user.id
    with connect() as db:
        rows = db.execute("""
            SELECT s.* FROM scripts s
            JOIN favorites f ON f.script_id=s.id
            WHERE f.user_id=? AND s.active=1
            ORDER BY s.id DESC LIMIT 30
        """, (uid,)).fetchall()

    if not rows:
        await message.answer("Избранное пока пусто.")
        return

    for row in rows:
        text, keyboard = script_card(row, uid)
        await message.answer(text, reply_markup=keyboard)


@dp.callback_query(F.data.startswith("fav:"))
async def favorite_callback(call: CallbackQuery):
    try:
        script_id = int(call.data.split(":")[1])
    except ValueError:
        await call.answer("Неверный ID.")
        return

    uid = call.from_user.id
    with connect() as db:
        existing = db.execute("""
            SELECT 1 FROM favorites WHERE user_id=? AND script_id=?
        """, (uid, script_id)).fetchone()

        if existing:
            db.execute(
                "DELETE FROM favorites WHERE user_id=? AND script_id=?",
                (uid, script_id),
            )
            text = "Удалено из избранного."
        else:
            db.execute("""
                INSERT OR IGNORE INTO favorites(user_id, script_id)
                VALUES(?,?)
            """, (uid, script_id))
            text = "Добавлено в избранное."

    await call.answer(text)


# ============================================================
# COMMUNITIES
# ============================================================

@dp.message(F.text == "🌐 Сообщества")
async def communities(message: Message):
    uid = message.from_user.id
    with connect() as db:
        rows = db.execute("""
            SELECT * FROM communities
            WHERE active=1 ORDER BY id DESC LIMIT 30
        """).fetchall()

    if not rows:
        await message.answer(
            "🌐 Каталог сообществ пока пуст.\n"
            "Администратор может добавить сообщества командами /addcommunity."
        )
        return

    for row in rows:
        if row["premium"] and not premium(uid):
            await message.answer(
                f"🔒 <b>{safe(row['title'])}</b>\n"
                "Доступ к этой карточке требует Premium."
            )
            continue

        await message.answer(
            f"🌐 <b>{safe(row['title'])}</b>\n"
            f"Категория: {safe(row['category'])}\n"
            f"{safe(row['description'])}\n"
            f"Ссылка: {safe(row['url'])}"
        )


# ============================================================
# SHOP
# ============================================================

@dp.message(F.text == "🛍 Магазин")
async def shop(message: Message):
    uid = message.from_user.id
    with connect() as db:
        products = db.execute("""
            SELECT * FROM products WHERE active=1 ORDER BY id
        """).fetchall()

    if not products:
        await message.answer("Магазин пока пуст.")
        return

    for product in products:
        await message.answer(
            f"🛍 <b>{safe(product['title'])}</b>\n"
            f"{safe(product['description'])}\n"
            f"Цена: {product['price']} ⭐",
            reply_markup=inline([[
                InlineKeyboardButton(
                    text="Купить",
                    callback_data=f"product:{product['id']}",
                )
            ]]),
        )


@dp.callback_query(F.data.startswith("product:"))
async def buy_product(call: CallbackQuery):
    uid = call.from_user.id
    if admin(uid):
        await call.answer(
            "Для администратора все платные функции бесплатны.",
            show_alert=True,
        )
        return

    try:
        product_id = int(call.data.split(":")[1])
    except ValueError:
        await call.answer("Неверный товар.")
        return

    with connect() as db:
        product = db.execute("""
            SELECT * FROM products WHERE id=? AND active=1
        """, (product_id,)).fetchone()

    if not product:
        await call.answer("Товар недоступен.")
        return

    await bot.send_invoice(
        chat_id=call.message.chat.id,
        title=product["title"][:32],
        description=product["description"][:255],
        payload=f"product:{product_id}:{uid}",
        currency="XTR",
        prices=[LabeledPrice(
            label=product["title"][:32],
            amount=product["price"],
        )],
    )
    await call.answer()


# ============================================================
# DONATIONS
# ============================================================

@dp.message(F.text == "❤️ Поддержать")
async def donate(message: Message):
    await invoice(
        message,
        "Поддержка проекта",
        "Добровольная поддержка разработки бота",
        f"donation:{message.from_user.id}",
        DONATION_PRICE,
    )


# ============================================================
# PROMO CODES
# ============================================================

@dp.message(F.text == "🎟 Промокод")
async def promo_begin(message: Message):
    promo_state.add(message.from_user.id)
    await message.answer(
        "🎟 Отправь промокод следующим сообщением."
    )


async def redeem_promo(message: Message, code: str):
    uid = message.from_user.id
    code = code.strip().upper()

    with connect() as db:
        promo = db.execute("""
            SELECT * FROM promos
            WHERE code=? AND enabled=1
        """, (code,)).fetchone()

        if not promo:
            await message.answer("❌ Промокод не найден или отключён.")
            return

        used = db.execute("""
            SELECT 1 FROM promo_users WHERE code=? AND user_id=?
        """, (code, uid)).fetchone()

        if used:
            await message.answer("Ты уже использовал этот промокод.")
            return

        if promo["uses"] >= promo["uses_limit"]:
            await message.answer("Лимит активаций этого кода исчерпан.")
            return

        db.execute("""
            INSERT INTO promo_users(code, user_id, created)
            VALUES(?,?,?)
        """, (code, uid, stamp()))

        db.execute(
            "UPDATE promos SET uses=uses+1 WHERE code=?", (code,)
        )

        days = int(promo["days"])
        description = promo["description"]

    if days > 0:
        end = grant_premium(uid, days, "promo")
        await message.answer(
            f"✅ Промокод активирован!\n"
            f"Награда: {safe(description)}\n"
            f"Premium до: <b>{safe(end)}</b>"
        )
    else:
        await message.answer(
            f"✅ Промокод активирован!\n"
            f"Награда: {safe(description)}"
        )


# ============================================================
# AI ANALYSIS
# ============================================================

async def ai_analyze(prompt: str):
    if not AI_API_KEY:
        return (
            "AI отключён: добавь AI_API_KEY в настройки Render. "
            "Без ключа бот продолжит работать без AI."
        )

    url = f"{AI_BASE_URL}/chat/completions"
    headers = {
        "Authorization": f"Bearer {AI_API_KEY}",
        "Content-Type": "application/json",
    }
    body = {
        "model": AI_MODEL,
        "messages": [
            {
                "role": "system",
                "content": (
                    "Ты помощник администратора Telegram-платформы. "
                    "Анализируй агрегированную статистику, "
                    "не придумывай отсутствующие факты. "
                    "Не утверждай, что рулетка предсказуема."
                ),
            },
            {"role": "user", "content": prompt[:6000]},
        ],
        "temperature": 0.2,
    }

    try:
        timeout = ClientTimeout(total=30)
        async with ClientSession(timeout=timeout) as session:
            async with session.post(
                url, headers=headers, json=body
            ) as response:
                data = await response.json()
                if response.status != 200:
                    log.error("AI error: %s", response.status)
                    return "AI-сервис вернул ошибку. Проверь настройки API."
                return data["choices"][0]["message"]["content"][:4000]
    except Exception:
        log.exception("AI request failed")
        return "Не удалось связаться с AI-сервисом."


# ============================================================
# ADMIN COMMANDS
# ============================================================

def require_admin(message):
    return message.from_user and admin(message.from_user.id)


@dp.message(Command("admin"))
async def admin_command(message: Message):
    if not require_admin(message):
        return
    await message.answer(
        "🛠 <b>Панель администратора</b>",
        reply_markup=admin_buttons(),
    )


@dp.message(F.text == "🛠 Админ-панель")
async def admin_menu(message: Message):
    if not require_admin(message):
        return
    await message.answer(
        "🛠 <b>Панель администратора</b>",
        reply_markup=admin_buttons(),
    )


@dp.callback_query(F.data.startswith("a:"))
async def admin_callback(call: CallbackQuery):
    if not admin(call.from_user.id):
        await call.answer("Доступ запрещён.", show_alert=True)
        return

    action = call.data.split(":")[1]

    if action == "stats":
        with connect() as db:
            users = db.execute(
                "SELECT COUNT(*) FROM users"
            ).fetchone()[0]
            scripts = db.execute(
                "SELECT COUNT(*) FROM scripts WHERE active=1"
            ).fetchone()[0]
            communities_count = db.execute(
                "SELECT COUNT(*) FROM communities WHERE active=1"
            ).fetchone()[0]
            payments = db.execute(
                "SELECT COUNT(*), COALESCE(SUM(amount),0) FROM payments"
            ).fetchone()

        await call.message.answer(
            "📊 <b>Статистика</b>\n\n"
            f"Пользователи: {users}\n"
            f"Активные скрипты: {scripts}\n"
            f"Сообщества: {communities_count}\n"
            f"Платежи: {payments[0]}\n"
            f"Получено Stars по записям: {payments[1]}"
        )

    elif action == "premium":
        with connect() as db:
            rows = db.execute("""
                SELECT s.user_id, s.expires, u.username
                FROM subscriptions s
                LEFT JOIN users u ON u.id=s.user_id
                WHERE s.expires > ?
                ORDER BY s.expires DESC LIMIT 50
            """, (stamp(),)).fetchall()

        lines = ["👑 <b>Premium-пользователи</b>"]
        for row in rows:
            lines.append(
                f"\nID: <code>{row['user_id']}</code> "
                f"@{safe(row['username'] or 'нет')}\n"
                f"До: {safe(row['expires'])}"
            )

        if len(lines) == 1:
            lines.append("\nАктивных подписок нет.")

        lines.append(
            f"\n\nАдминистратор: <code>{ADMIN_ID}</code> — "
            "Premium бессрочно."
        )
        await call.message.answer("\n".join(lines))

    elif action == "payments":
        with connect() as db:
            rows = db.execute("""
                SELECT user_id, amount, currency, payload, created
                FROM payments ORDER BY id DESC LIMIT 20
            """).fetchall()

        lines = ["💳 <b>Последние платежи</b>"]
        for row in rows:
            lines.append(
                f"\nID: <code>{row['user_id']}</code> | "
                f"{row['amount']} {safe(row['currency'])}\n"
                f"{safe(row['payload'])} | {safe(row['created'])}"
            )
        await call.message.answer("\n".join(lines))

    elif action == "scripts":
        with connect() as db:
            rows = db.execute("""
                SELECT id, title, category, premium, sponsor
                FROM scripts ORDER BY id DESC LIMIT 30
            """).fetchall()

        text = ["📚 <b>Каталог скриптов</b>"]
        for row in rows:
            text.append(
                f"\n#{row['id']} {safe(row['title'])} — "
                f"{safe(row['category'])}; "
                f"Premium={row['premium']}; "
                f"Sponsor={row['sponsor']}"
            )
        text.append(
            "\n\nДобавление: /addscript Название | Категория | "
            "Описание | URL | premium(0/1) | sponsor(0/1)"
        )
        await call.message.answer("\n".join(text))

    elif action == "communities":
        with connect() as db:
            rows = db.execute("""
                SELECT id, title, category, url
                FROM communities ORDER BY id DESC LIMIT 30
            """).fetchall()

        text = ["🌐 <b>Сообщества</b>"]
        for row in rows:
            text.append(
                f"\n#{row['id']} {safe(row['title'])} "
                f"({safe(row['category'])})\n{safe(row['url'])}"
            )
        text.append(
            "\n\nДобавить: /addcommunity Название | Категория | "
            "Описание | URL"
        )
        await call.message.answer("\n".join(text))

    elif action == "ai":
        await call.message.answer("🤖 Анализирую статистику...")
        with connect() as db:
            users = db.execute(
                "SELECT COUNT(*) FROM users"
            ).fetchone()[0]
            payments = db.execute(
                "SELECT COUNT(*), COALESCE(SUM(amount),0) FROM payments"
            ).fetchone()
            premium_count = db.execute("""
                SELECT COUNT(*) FROM subscriptions WHERE expires > ?
            """, (stamp(),)).fetchone()[0]

        prompt = (
            f"Пользователей: {users}. "
            f"Активных платных подписок: {premium_count}. "
            f"Платежей: {payments[0]}. "
            f"Сумма записанных платежей в Stars: {payments[1]}. "
            "Кратко проанализируй показатели и предложи улучшения."
        )
        result = await ai_analyze(prompt)
        await call.message.answer(
            f"🤖 <b>AI-анализ</b>\n\n{safe(result)}"
        )

    await call.answer()


@dp.message(Command("grant"))
async def grant_command(message: Message):
    if not require_admin(message):
        return

    parts = message.text.split()
    if len(parts) != 3:
        await message.answer("Формат: /grant USER_ID DAYS")
        return

    try:
        uid, days = int(parts[1]), int(parts[2])
        end = grant_premium(uid, days)
    except ValueError:
        await message.answer("Укажи корректные ID и число дней.")
        return

    log_action(ADMIN_ID, "grant_premium", f"{uid}:{days}")
    await message.answer(
        f"✅ Premium выдан пользователю {uid} до {safe(end)}"
    )
    try:
        await bot.send_message(
            uid, f"👑 Администратор выдал тебе Premium на {days} дней."
        )
    except TelegramAPIError:
        pass


@dp.message(Command("revoke"))
async def revoke_command(message: Message):
    if not require_admin(message):
        return

    parts = message.text.split()
    if len(parts) != 2 or not parts[1].isdigit():
        await message.answer("Формат: /revoke USER_ID")
        return

    uid = int(parts[1])
    if not revoke_premium(uid):
        await message.answer("Нельзя снять постоянный Premium владельца.")
        return

    log_action(ADMIN_ID, "revoke_premium", str(uid))
    await message.answer(f"Доступ Premium снят у {uid}.")


@dp.message(Command("addscript"))
async def add_script(message: Message):
    if not require_admin(message):
        return

    args = message.text.partition(" ")[2]
    parts = [p.strip() for p in args.split("|")]

    if len(parts) != 6:
        await message.answer(
            "Формат:\n/addscript Название | Категория | Описание | "
            "URL | premium(0/1) | sponsor(0/1)"
        )
        return

    title, category, description, url, prem, sponsor = parts

    if not url.startswith(("https://", "http://")):
        await message.answer("URL должен начинаться с https:// или http://")
        return

    if prem not in ("0", "1") or sponsor not in ("0", "1"):
        await message.answer("premium и sponsor должны быть 0 или 1.")
        return

    with connect() as db:
        db.execute("""
            INSERT INTO scripts(
                title, category, description, url,
                premium, sponsor, created
            ) VALUES(?,?,?,?,?,?,?)
        """, (
            title, category, description, url,
            int(prem), int(sponsor), stamp(),
        ))

    log_action(ADMIN_ID, "add_script", title)
    await message.answer("✅ Скрипт добавлен в каталог.")


@dp.message(Command("addcommunity"))
async def add_community(message: Message):
    if not require_admin(message):
        return

    parts = [
        p.strip()
        for p in message.text.partition(" ")[2].split("|")
    ]
    if len(parts) != 4:
        await message.answer(
            "Формат:\n/addcommunity Название | Категория | "
            "Описание | URL"
        )
        return

    title, category, description, url = parts
    if not url.startswith(("https://", "http://")):
        await message.answer("Укажи корректный URL.")
        return

    with connect() as db:
        db.execute("""
            INSERT INTO communities(title, category, description, url)
            VALUES(?,?,?,?)
        """, (title, category, description, url))

    log_action(ADMIN_ID, "add_community", title)
    await message.answer("✅ Сообщество добавлено.")


@dp.message(Command("makepromo"))
async def make_promo(message: Message):
    if not require_admin(message):
        return

    parts = [
        p.strip()
        for p in message.text.partition(" ")[2].split("|")
    ]
    if len(parts) != 4:
        await message.answer(
            "Формат:\n/makepromo КОД | описание награды | дни Premium | лимит"
        )
        return

    code, description, days_text, limit_text = parts

    try:
        days, limit = int(days_text), int(limit_text)
        if days < 0 or limit < 1:
            raise ValueError
    except ValueError:
        await message.answer("Дни должны быть >= 0, лимит >= 1.")
        return

    code = code.upper()
    try:
        with connect() as db:
            db.execute("""
                INSERT INTO promos(
                    code, description, days, uses_limit
                ) VALUES(?,?,?,?)
            """, (code, description, days, limit))
    except sqlite3.IntegrityError:
        await message.answer("Такой промокод уже существует.")
        return

    log_action(ADMIN_ID, "make_promo", code)
    await message.answer(
        f"🎟 Промокод создан: <code>{safe(code)}</code>\n"
        f"Награда: {safe(description)}\n"
        f"Premium-дней: {days}\n"
        f"Лимит: {limit}"
    )


@dp.message(Command("block"))
async def block_user(message: Message):
    if not require_admin(message):
        return
    parts = message.text.split()
    if len(parts) != 2 or not parts[1].isdigit():
        await message.answer("Формат: /block USER_ID")
        return

    uid = int(parts[1])
    with connect() as db:
        db.execute("UPDATE users SET blocked=1 WHERE id=?", (uid,))
    log_action(ADMIN_ID, "block_user", str(uid))
    await message.answer(f"Пользователь {uid} заблокирован в боте.")


@dp.message(Command("unblock"))
async def unblock_user(message: Message):
    if not require_admin(message):
        return
    parts = message.text.split()
    if len(parts) != 2 or not parts[1].isdigit():
        await message.answer("Формат: /unblock USER_ID")
        return

    uid = int(parts[1])
    with connect() as db:
        db.execute("UPDATE users SET blocked=0 WHERE id=?", (uid,))
    log_action(ADMIN_ID, "unblock_user", str(uid))
    await message.answer(f"Пользователь {uid} разблокирован.")


@dp.message(Command("users"))
async def list_users(message: Message):
    if not require_admin(message):
        return

    with connect() as db:
        rows = db.execute("""
            SELECT id, username, name, joined, blocked
            FROM users ORDER BY joined DESC LIMIT 40
        """).fetchall()

    lines = ["👥 <b>Последние пользователи</b>"]
    for row in rows:
        lines.append(
            f"\n<code>{row['id']}</code> "
            f"@{safe(row['username'] or 'нет')} "
            f"{safe(row['name'])} "
            f"{'🚫' if row['blocked'] else ''}"
        )
    await message.answer("\n".join(lines))


@dp.message(Command("stats"))
async def stats(message: Message):
    if not require_admin(message):
        return

    with connect() as db:
        users = db.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        scripts = db.execute(
            "SELECT COUNT(*) FROM scripts WHERE active=1"
        ).fetchone()[0]
        payments = db.execute(
            "SELECT COUNT(*), COALESCE(SUM(amount),0) FROM payments"
        ).fetchone()
        subs = db.execute("""
            SELECT COUNT(*) FROM subscriptions WHERE expires>?
        """, (stamp(),)).fetchone()[0]

    await message.answer(
        "📊 <b>Статистика</b>\n\n"
        f"Пользователей: {users}\n"
        f"Скриптов: {scripts}\n"
        f"Активных подписок: {subs}\n"
        f"Платежей: {payments[0]}\n"
        f"Сумма записей: {payments[1]} Stars"
    )


@dp.message(Command("help"))
@dp.message(F.text == "ℹ️ Помощь")
async def help_message(message: Message):
    await message.answer(
        "<b>Команды бота</b>\n\n"
        "/start — меню\n"
        "/id — узнать Telegram ID\n"
        "/profile — профиль\n"
        "/premium — Premium\n"
        "/search запрос — поиск\n"
        "/help — помощь\n\n"
        "Команды администратора доступны только владельцу:\n"
        "/admin, /stats, /users\n"
        "/grant USER_ID DAYS\n"
        "/revoke USER_ID\n"
        "/addscript Название | Категория | Описание | URL | 0/1 | 0/1\n"
        "/addcommunity Название | Категория | Описание | URL\n"
        "/makepromo КОД | награда | дни | лимит\n"
        "/block USER_ID, /unblock USER_ID"
    )


# ============================================================
# GENERAL TEXT HANDLER
# ============================================================

@dp.callback_query(F.data == "main")
async def go_main(call: CallbackQuery):
    await call.message.answer(
        "Главное меню:",
        reply_markup=menu(call.from_user.id),
    )
    await call.answer()


@dp.callback_query(F.data == "show_premium")
async def show_premium_callback(call: CallbackQuery):
    await show_premium(call.message)
    await call.answer()


@dp.message(F.text)
async def text_router(message: Message):
    uid = message.from_user.id
    register(message.from_user)

    if is_blocked(uid) and not admin(uid):
        return

    text = message.text.strip()

    if uid in promo_state:
        promo_state.discard(uid)
        await redeem_promo(message, text)
        return

    if uid in search_state:
        search_state.discard(uid)
        await deliver_search(message, text)
        return

    # Do not swallow commands or known menu buttons.
    if text.startswith("/"):
        return

    known = {
        "🔎 Поиск скриптов", "👑 Premium", "🛍 Магазин",
        "🎟 Промокод", "🌐 Сообщества", "⭐ Избранное",
        "👤 Профиль", "❤️ Поддержать", "ℹ️ Помощь",
        "🛠 Админ-панель",
    }
    if text not in known:
        await message.answer(
            "Не понял команду. Используй меню или /help.",
            reply_markup=menu(uid),
        )


# ============================================================
# RENDER HEALTH SERVER
# ============================================================

async def health(request):
    return web.json_response({
        "status": "ok",
        "service": "script-finder-beta",
        "time": stamp(),
    })


async def start_health_server():
    app = web.Application()
    app.router.add_get("/", health)
    app.router.add_get("/health", health)

    runner = web.AppRunner(app)
    await runner.setup()

    site = web.TCPSite(runner, "0.0.0.0", PORT)
    await site.start()
    log.info("Health server listening on port %s", PORT)


# ============================================================
# STARTUP
# ============================================================

async def main():
    init_db()
    log.info("Database initialized.")

    await start_health_server()

    # Notify owner when the bot starts, if the owner has opened
    # a conversation with the bot before.
    await admin_notify("🟢 Script Finder Beta запущен.")

    await dp.start_polling(
        bot,
        allowed_updates=dp.resolve_used_update_types(),
    )


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        log.info("Bot stopped.")
