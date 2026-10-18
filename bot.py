import asyncio
import csv
import html
import io
import json
import logging
import os
import random
import re
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import quote, urljoin

import aiohttp
from aiohttp import web
from aiogram import Bot, Dispatcher, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramAPIError
from aiogram.filters import Command, CommandStart
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    LabeledPrice,
    PreCheckoutQuery,
)

# =========================================================
# CONFIG
# =========================================================

TOKEN = os.getenv("BOT_TOKEN")
if not TOKEN:
    raise RuntimeError(
        "BOT_TOKEN не задан. Добавь переменную BOT_TOKEN "
        "в Render -> Environment."
    )

ADMIN_ID = 123456789       # ЗАМЕНИ на свой Telegram ID
SPONSOR_ID = 111111111     # ЗАМЕНИ на нужный Telegram ID

SUB_PRICE = 60
SUB_RENEW_PRICE = 20
FREE_L = 5
PREM_L = 15
ROLL_PRICE = 5
F_PRICE = 10

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = Path(os.getenv("DATA_DIR", str(BASE_DIR / "data")))
DATA_DIR.mkdir(parents=True, exist_ok=True)

USERS_FILE = DATA_DIR / "users.json"
SUBS_FILE = DATA_DIR / "subscriptions.json"
PROMOS_FILE = DATA_DIR / "promos.json"
SHOP_FILE = DATA_DIR / "shop.json"
STATS_FILE = DATA_DIR / "stats.json"
FILTERS_FILE = DATA_DIR / "filters.json"
SPONSORS_FILE = DATA_DIR / "sponsors.json"
TRIALS_FILE = DATA_DIR / "trials.json"
DONATIONS_FILE = DATA_DIR / "donations.json"

SOCIAL_URL = "https://t.me/+LBs19_JzpW0yNmZi"
RENDER_URL = os.getenv("RENDER_EXTERNAL_URL", "").rstrip("/")
PORT = int(os.getenv("PORT", "8080"))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
log = logging.getLogger("telegram-bot")

bot = Bot(
    TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML),
)
dp = Dispatcher()

# Temporary conversations are kept in memory.
# They reset if Render restarts the service.
waiting = {}
last_results = {}
user_category = {}

CATEGORIES = {
    "brookhaven": "Brookhaven",
    "mm2": "Murder Mystery 2",
    "blox": "Blox Fruits",
    "99nights": "99 Nights",
    "egg": "Steal an Egg",
}

# These are user-provided script examples. Use at your own discretion.
SCRIPTS = {
    "brookhaven": [
        ("Redz", "loadstring(game:HttpGet('https://pastebin.com/raw/1r7cEW7G'))()"),
        ("Lord", 'loadstring(game:HttpGet("https://raw.githubusercontent.com/SUPREMEAURA350/KAISER-VERSION-2-/refs/heads/main/Kaiserspam"))()'),
        ("LolaHub", 'loadstring(game:HttpGet("https://raw.githubusercontent.com/niriel015/Painel-LolaHub/refs/heads/main/Lola-hub-ne-pai"))()'),
        ("Saiki", 'loadstring(game:HttpGet("https://raw.githubusercontent.com/SaikiWithTheBanHammer/ScriptBlox/main/LifeIsDisasterIndeedLol"))()'),
    ],
    "mm2": [
        ("Madara", 'loadstring(game:HttpGet("https://raw.githubusercontent.com/IsThisMe01/Project-Madara/refs/heads/main/mm22.lua"))()'),
        ("Moondiety", 'loadstring(game:HttpGet("https://scriptblox.com/raw/Murder-Mystery-2-KEYLESS-InstaWin-AutoFarm-Kill-all-XRay-nd-more-by-Moondiety-48644"))()'),
        ("Godmode", 'loadstring(game:HttpGet("https://pastefy.app/a2dAk154/raw"))()'),
        ("Freeze", 'loadstring(game:HttpGet("https://cdn.sourceb.in/bins/9MHwJQNJkm/0"))()'),
        ("Freeze Trade", 'loadstring(game:HttpGet("https://raw.githubusercontent.com/txnic255/MM2-FREEZE-TRADE-V5.5-NEWEST-GUI-SCRIPT-/refs/heads/main/SCRIPT%20V5.5%20GUI%20AND%20SCRIPT"))()'),
    ],
    "blox": [
        ("Min", 'loadstring(game:HttpGet("https://raw.githubusercontent.com/LuaCrack/Min/refs/heads/main/MinXt2Eng"))()'),
        ("Redz", 'local Settings = { JoinTeam = "Pirates", Translator = true }\ngetgenv().BETA_VERSION = true\nloadstring(game:HttpGet("https://raw.githubusercontent.com/tlredz/Scripts/refs/heads/main/main.luau"))(Settings)'),
        ("Basement", 'loadstring(game:HttpGet("https://raw.githubusercontent.com/Cazzanos/The-basement/main/Basement%20hub", true))()'),
        ("AutoFarm", 'loadstring(game:HttpGetAsync("https://raw.githubusercontent.com/indexeduu/BF-NewVer/refs/heads/main/V3New.lua"))()'),
    ],
    "99nights": [
        ("Script 1", 'loadstring(game:HttpGet("https://api.luarmor.net/files/v3/loaders/705e9a93cc18214fb77ab95686a8dba9.lua"))()'),
        ("FoxnameHub", 'KEY - 111222HHH\n\nloadstring(game:HttpGet("https://raw.githubusercontent.com/caomod2077/Script/refs/heads/main/FoxnameHub.lua"))()'),
        ("NTT Hub", 'loadstring(game:HttpGet("https://ntt-hub.xyz/api/repo?id1=main&id2=lua"))()'),
    ],
    "egg": [
        ("Steal an Egg 1", 'loadstring(game:HttpGet("https://raw.githubusercontent.com/sabscrip-arch/srver/refs/heads/main/Stealanegg"))()'),
        ("Lennon Hub 2", 'loadstring(game:HttpGet("https://raw.githubusercontent.com/lennonxscripts/lennonhubv2/refs/heads/main/stealaneggv2"))()'),
        ("Lennon Hub 3", 'loadstring(game:HttpGet("https://raw.githubusercontent.com/lennonxscripts/lennonhubv2/refs/heads/main/stealaneggv2"))()'),
    ],
}

# =========================================================
# JSON STORAGE
# =========================================================

def read_json(path, default):
    try:
        if path.exists():
            with path.open("r", encoding="utf-8") as f:
                return json.load(f)
    except (OSError, json.JSONDecodeError) as exc:
        log.warning("Cannot read %s: %s", path.name, exc)
    return default


def write_json(path, data):
    temp = path.with_suffix(path.suffix + ".tmp")
    with temp.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    temp.replace(path)


def get_users():
    return read_json(USERS_FILE, {})


def save_users(data):
    write_json(USERS_FILE, data)


def get_subs():
    return read_json(SUBS_FILE, {})


def save_subs(data):
    write_json(SUBS_FILE, data)


def get_promos():
    return read_json(PROMOS_FILE, {})


def save_promos(data):
    write_json(PROMOS_FILE, data)


def get_shop():
    return read_json(SHOP_FILE, {})


def save_shop(data):
    write_json(SHOP_FILE, data)


def get_stats():
    return read_json(STATS_FILE, {"searches": 0, "payments": 0})


def save_stats(data):
    write_json(STATS_FILE, data)


def get_filters():
    return read_json(FILTERS_FILE, {})


def save_filters(data):
    write_json(FILTERS_FILE, data)


def get_sponsors():
    return read_json(SPONSORS_FILE, {})


def save_sponsors(data):
    write_json(SPONSORS_FILE, data)


def get_trials():
    return read_json(TRIALS_FILE, {})


def save_trials(data):
    write_json(TRIALS_FILE, data)


def get_donations():
    return read_json(DONATIONS_FILE, {})


def save_donations(data):
    write_json(DONATIONS_FILE, data)


def register_user(user):
    users = get_users()
    uid = str(user.id)
    if uid not in users:
        users[uid] = {
            "name": user.full_name,
            "joined": datetime.now(timezone.utc).isoformat(),
            "searches": 0,
        }
        save_users(users)


def active_sub(user_id):
    if int(user_id) == ADMIN_ID:
        return True

    subs = get_subs()
    value = subs.get(str(user_id))
    if not value:
        return False

    try:
        return datetime.fromisoformat(value) > datetime.now(timezone.utc)
    except (ValueError, TypeError):
        return False


def has_sponsor(user_id):
    sponsors = get_sponsors()
    return str(user_id) in sponsors


def is_premium(user_id):
    return (
        int(user_id) == ADMIN_ID
        or active_sub(user_id)
        or has_sponsor(user_id)
    )


def expiry_text(user_id):
    value = get_subs().get(str(user_id))
    if not value:
        return "не оформлена"
    try:
        dt = datetime.fromisoformat(value)
        return dt.strftime("%d.%m.%Y %H:%M UTC")
    except (ValueError, TypeError):
        return "неизвестно"


def extend_subscription(user_id, days=7):
    subs = get_subs()
    uid = str(user_id)
    now = datetime.now(timezone.utc)

    try:
        current = datetime.fromisoformat(subs.get(uid, ""))
    except (ValueError, TypeError):
        current = now

    if current < now:
        current = now

    current += timedelta(days=days)
    subs[uid] = current.isoformat()
    save_subs(subs)
    return current


def record_search(user_id):
    users = get_users()
    uid = str(user_id)
    users.setdefault(uid, {"name": uid, "joined": datetime.now(timezone.utc).isoformat(), "searches": 0})
    users[uid]["searches"] = int(users[uid].get("searches", 0)) + 1
    save_users(users)

    stats = get_stats()
    stats["searches"] = int(stats.get("searches", 0)) + 1
    save_stats(stats)


# =========================================================
# KEYBOARDS
# =========================================================

def ik(rows):
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=label, callback_data=data) for label, data in row]
            for row in rows
        ]
    )


def main_kb():
    return ik([
        [("🔎 Поиск скриптов", "search"), ("🎮 Категории", "categories")],
        [("⭐ Подписка", "subscription"), ("🎁 Промокод", "promo")],
        [("📌 Мои фильтры", "filters"), ("📤 Экспорт CSV", "csv")],
        [("🛒 Магазин", "shop"), ("🎰 Рулетка", "roulette")],
        [("🧊 Freeze", "freeze"), ("💝 Поддержать", "donate")],
        [("📊 Моя статистика", "mystats"), ("ℹ️ Помощь", "help")],
        [("🌐 Наш канал", "social")],
    ])


def categories_kb():
    return ik([
        [(name, "cat:" + key)]
        for key, name in CATEGORIES.items()
    ] + [[("⬅️ Меню", "menu")]])


def back_kb():
    return ik([[("⬅️ Меню", "menu")]])


def sub_kb(user_id):
    if active_sub(user_id):
        rows = [
            [(f"🔄 Продлить на неделю — {SUB_RENEW_PRICE} ⭐", "pay:sub_renew")],
            [("📅 Срок подписки", "sub_expiry")],
        ]
    else:
        rows = [[(f"⭐ Активировать на неделю — {SUB_PRICE} ⭐", "pay:sub_new")]]
    rows.append([("⬅️ Меню", "menu")])
    return ik(rows)


def search_results_kb(results):
    rows = []
    for i, item in enumerate(results[:10]):
        url = item.get("url")
        if url and url.startswith(("https://", "http://")):
            rows.append([(f"🌐 {item['title'][:45]}", "noop")])
    rows.append([("📤 CSV", "csv"), ("⬅️ Меню", "menu")])
    return ik(rows)


# =========================================================
# SEARCH
# =========================================================

def english_only(query):
    return not re.search(r"[А-Яа-яЁё]", query)


def query_terms(query):
    return {
        word.lower()
        for word in re.findall(r"[a-zA-Z0-9]+", query)
        if len(word) > 1
    }


def normalize_api_result(item):
    if not isinstance(item, dict):
        return None

    title = item.get("title") or item.get("name") or "Untitled"
    game = item.get("game") or item.get("gameName") or ""
    if isinstance(game, dict):
        game = game.get("name", "")

    raw_url = item.get("script") or item.get("url") or item.get("link") or ""
    if isinstance(raw_url, dict):
        raw_url = raw_url.get("url", "")

    if raw_url.startswith("/"):
        raw_url = urljoin("https://scriptblox.com", raw_url)
    elif raw_url and not raw_url.startswith(("https://", "http://")):
        raw_url = ""

    snippet = item.get("description") or item.get("scriptText") or ""
    if not isinstance(snippet, str):
        snippet = ""

    return {
        "title": str(title)[:200],
        "game": str(game)[:120],
        "url": str(raw_url)[:1000],
        "snippet": snippet[:500],
        "source": "ScriptBlox",
    }


async def scriptblox_search(session, query, game=""):
    full_query = " ".join(x for x in (game, query) if x).strip()
    url = "https://scriptblox.com/api/script/search"
    params = {
        "q": full_query,
        "mode": "free",
        "key": "0",
        "max": "20",
        "strict": "true",
    }

    try:
        async with session.get(
            url,
            params=params,
            timeout=aiohttp.ClientTimeout(total=15),
        ) as response:
            if response.status != 200:
                log.warning("ScriptBlox returned HTTP %s", response.status)
                return []
            data = await response.json(content_type=None)
    except (aiohttp.ClientError, asyncio.TimeoutError, ValueError) as exc:
        log.warning("ScriptBlox search failed: %s", exc)
        return []

    items = data.get("result", {}).get("scripts", [])
    if not isinstance(items, list):
        return []

    output = []
    for item in items:
        normalized = normalize_api_result(item)
        if normalized:
            output.append(normalized)
    return output


async def scrape_public_page(session, url, source, query, game=""):
    """Extract only real public page links; never invent script URLs."""
    terms = query_terms(" ".join((query, game)))
    found = []

    try:
        async with session.get(
            url,
            timeout=aiohttp.ClientTimeout(total=12),
            headers={"User-Agent": "Mozilla/5.0"},
        ) as response:
            if response.status != 200:
                return []
            body = await response.text(errors="ignore")
    except (aiohttp.ClientError, asyncio.TimeoutError) as exc:
        log.info("Source %s unavailable: %s", source, exc)
        return []

    # Lightweight public HTML parsing without external dependencies.
    for match in re.finditer(
        r'<a\b[^>]*href=["\']([^"\']+)["\'][^>]*>(.*?)</a>',
        body,
        re.IGNORECASE | re.DOTALL,
    ):
        href, raw_title = match.groups()
        title = re.sub(r"<[^>]+>", " ", raw_title)
        title = html.unescape(re.sub(r"\s+", " ", title)).strip()

        if not title or len(title) < 3:
            continue

        link = urljoin(url, html.unescape(href))
        if not link.startswith("https://"):
            continue

        if any(x in link.lower() for x in ("login", "register", "privacy", "terms")):
            continue

        combined = (title + " " + link).lower()
        if terms and not any(term in combined for term in terms):
            continue

        found.append({
            "title": title[:200],
            "game": game,
            "url": link,
            "snippet": "",
            "source": source,
        })

        if len(found) >= 10:
            break

    return found


async def search_scripts(query, game, premium):
    async with aiohttp.ClientSession() as session:
        results = await scriptblox_search(session, query, game)

        if premium:
            extra_sources = [
                ("DeltaScripts", "https://deltascripts.org/"),
                ("DeltaScripts RU", "https://deltascripts.ru/"),
                ("Scriptrb", "https://scriptrb.com/post.php?id=1891"),
            ]

            tasks = [
                scrape_public_page(session, url, name, query, game)
                for name, url in extra_sources
            ]
            for batch in await asyncio.gather(*tasks, return_exceptions=True):
                if isinstance(batch, list):
                    results.extend(batch)

    terms = query_terms(" ".join((query, game)))
    unique = []
    seen = set()

    for item in results:
        title = item.get("title", "").strip()
        url = item.get("url", "")
        if not title or not url:
            continue

        key = url.lower().rstrip("/")
        if key in seen:
            continue

        combined = (title + " " + item.get("game", "") + " " + item.get("snippet", "")).lower()
        if terms and not any(term in combined for term in terms):
            # Keep API results returned for the exact query, but filter scraped pages.
            if item.get("source") != "ScriptBlox":
                continue

        seen.add(key)
        unique.append(item)

    return unique


async def send_search(message, query, category_key=None):
    query = query.strip()
    if not query:
        await message.answer("Напиши название скрипта или игры на английском.")
        return

    if not english_only(query):
        await message.answer(
            "Пожалуйста, введи запрос на английском. "
            "Я не перевожу русские запросы автоматически."
        )
        return

    game = CATEGORIES.get(category_key, "") if category_key else ""
    premium = is_premium(message.from_user.id)
    limit = 20 if premium else FREE_L

    await message.answer("🔎 Ищу скрипты. Подожди немного...")

    results = await search_scripts(query, game, premium)
    results = results[:limit]
    last_results[str(message.from_user.id)] = results
    record_search(message.from_user.id)

    if not results:
        await message.answer(
            f"❌ Ничего не найдено по запросу <b>{html.escape(query)}</b>"
            + (f" для игры <b>{html.escape(game)}</b>." if game else ".")
            + "\nПопробуй другое английское название."
        )
        return

    for item in results:
        title = html.escape(item.get("title", "Untitled"))
        game_name = html.escape(item.get("game") or game or "Не указана")
        source = html.escape(item.get("source", "Unknown"))
        snippet = html.escape(item.get("snippet", "")[:300])
        url = item.get("url", "")

        text = (
            f"🎮 <b>{title}</b>\n"
            f"Игра: {game_name}\n"
            f"Источник: {source}\n"
        )
        if snippet:
            text += f"\n{snippet}\n"
        if url.startswith(("https://", "http://")):
            text += f'\n<a href="{html.escape(url, quote=True)}">Открыть источник</a>'

        await message.answer(text, disable_web_page_preview=True)

    await message.answer(
        f"Найдено: {len(results)}. "
        "Можно сохранить запрос или экспортировать результаты.",
        reply_markup=ik([
            [("📌 Сохранить фильтр", "savefilter:" + query[:100])],
            [("📤 Экспорт CSV", "csv"), ("⬅️ Меню", "menu")],
        ]),
    )


# =========================================================
# START / MENU / GENERAL COMMANDS
# =========================================================

@dp.message(CommandStart())
async def start(message: Message):
    register_user(message.from_user)
    await message.answer(
        "👋 <b>Добро пожаловать в Script Finder!</b>\n\n"
        "Ищи скрипты, выбирай игры и управляй подпиской.\n"
        "Бесплатный поиск использует ScriptBlox.\n\n"
        "Выбери действие:",
        reply_markup=main_kb(),
    )


@dp.message(Command("help"))
async def help_command(message: Message):
    await message.answer(
        "<b>Помощь</b>\n"
        "• Нажми «Поиск скриптов» и введи английский запрос.\n"
        "• В категориях можно выбрать конкретную игру.\n"
        "• Подписка открывает дополнительные источники поиска.\n"
        "• Промокоды вводятся через меню.\n"
        "• Оплата проходит через Telegram Stars.",
        reply_markup=main_kb(),
    )


@dp.message(Command("id"))
async def id_command(message: Message):
    await message.answer(f"Твой Telegram ID: <code>{message.from_user.id}</code>")


@dp.message(Command("stats"))
async def stats_command(message: Message):
    if message.from_user.id != ADMIN_ID:
        await message.answer("Эта команда доступна администратору.")
        return

    users = get_users()
    stats = get_stats()
    await message.answer(
        f"<b>Статистика</b>\n"
        f"Пользователей: {len(users)}\n"
        f"Поисков: {stats.get('searches', 0)}\n"
        f"Платежей: {stats.get('payments', 0)}"
    )


# =========================================================
# CALLBACKS
# =========================================================

@dp.callback_query(F.data == "menu")
async def menu_callback(callback: CallbackQuery):
    await callback.answer()
    await callback.message.answer("Главное меню:", reply_markup=main_kb())


@dp.callback_query(F.data == "help")
async def help_callback(callback: CallbackQuery):
    await callback.answer()
    await callback.message.answer(
        "Отправь английский запрос для поиска. "
        "Если бот ничего не найдёт, попробуй более короткое название.",
        reply_markup=back_kb(),
    )


@dp.callback_query(F.data == "social")
async def social_callback(callback: CallbackQuery):
    await callback.answer()
    await callback.message.answer(
        f'Наш канал: <a href="{SOCIAL_URL}">открыть Telegram</a>',
        disable_web_page_preview=True,
    )


@dp.callback_query(F.data == "categories")
async def categories_callback(callback: CallbackQuery):
    await callback.answer()
    await callback.message.answer("Выбери игру:", reply_markup=categories_kb())


@dp.callback_query(F.data.startswith("cat:"))
async def category_callback(callback: CallbackQuery):
    await callback.answer()
    key = callback.data.split(":", 1)[1]

    if key not in CATEGORIES:
        await callback.message.answer("Неизвестная категория.")
        return

    user_category[str(callback.from_user.id)] = key
    await callback.message.answer(
        f"Выбрана игра: <b>{html.escape(CATEGORIES[key])}</b>\n"
        "Теперь напиши название скрипта или ключевые слова на английском."
    )


@dp.callback_query(F.data == "search")
async def search_callback(callback: CallbackQuery):
    await callback.answer()
    user_category.pop(str(callback.from_user.id), None)
    waiting[str(callback.from_user.id)] = "search"
    await callback.message.answer("Введи поисковый запрос на английском.")


@dp.message(F.text)
async def text_handler(message: Message):
    uid = str(message.from_user.id)
    state = waiting.get(uid)

    if state == "search":
        waiting.pop(uid, None)
        await send_search(message, message.text)
        return

    if state == "promo":
        waiting.pop(uid, None)
        await apply_promo(message, message.text.strip())
        return

    if state == "donation":
        waiting.pop(uid, None)
        await create_donation_invoice(message, message.text.strip())
        return

    if state == "filter_search":
        waiting.pop(uid, None)
        saved = get_filters()
        saved.setdefault(uid, [])
        query = message.text.strip()[:100]
        if query not in saved[uid]:
            saved[uid].append(query)
        save_filters(saved)
        await message.answer(f"Фильтр сохранён: <code>{html.escape(query)}</code>")
        return

    if uid in user_category:
        key = user_category.pop(uid)
        await send_search(message, message.text, key)
        return

    if message.text.startswith("/"):
        return

    await message.answer(
        "Выбери действие в меню или нажми «Поиск скриптов».",
        reply_markup=main_kb(),
    )


@dp.callback_query(F.data == "subscription")
async def subscription_callback(callback: CallbackQuery):
    await callback.answer()
    user_id = callback.from_user.id
    await callback.message.answer(
        "<b>⭐ Подписка</b>\n\n"
        f"Активация на 7 дней: {SUB_PRICE} Telegram Stars.\n"
        f"Продление на 7 дней: {SUB_RENEW_PRICE} Telegram Stars.\n\n"
        "Подписка открывает дополнительные источники поиска.\n"
        "После оплаты бот покажет дату окончания.",
        reply_markup=sub_kb(user_id),
    )


@dp.callback_query(F.data == "sub_expiry")
async def sub_expiry_callback(callback: CallbackQuery):
    await callback.answer()
    await callback.message.answer(
        f"Текущий срок подписки: <b>{expiry_text(callback.from_user.id)}</b>"
    )


@dp.callback_query(F.data.startswith("pay:"))
async def payment_callback(callback: CallbackQuery):
    await callback.answer()
    payload = callback.data.split(":", 1)[1]
    user_id = callback.from_user.id

    if payload == "sub_renew":
        if not active_sub(user_id):
            await callback.message.answer(
                "Активной подписки нет. Сначала выбери активацию."
            )
            return
        amount = SUB_RENEW_PRICE
        title = "Продление подписки на 7 дней"
        description = "Продление Script Finder на одну неделю."
    elif payload == "sub_new":
        if active_sub(user_id):
            await callback.message.answer(
                "Подписка уже активна. Выбери продление."
            )
            return
        amount = SUB_PRICE
        title = "Подписка на 7 дней"
        description = "Доступ к дополнительным источникам поиска на 7 дней."
    else:
        await callback.message.answer("Неизвестный тип оплаты.")
        return

    try:
        await bot.send_invoice(
            chat_id=user_id,
            title=title,
            description=description,
            payload=payload,
            currency="XTR",
            prices=[LabeledPrice(label=title, amount=amount)],
            provider_token="",
        )
    except TelegramAPIError as exc:
        log.exception("Could not send subscription invoice: %s", exc)
        await callback.message.answer(
            "Не удалось создать счёт. Попробуй ещё раз чуть позже."
        )


@dp.callback_query(F.data == "promo")
async def promo_callback(callback: CallbackQuery):
    await callback.answer()
    waiting[str(callback.from_user.id)] = "promo"
    await callback.message.answer("Введи промокод:")


async def apply_promo(message: Message, code: str):
    promos = get_promos()
    promo = promos.get(code.upper())

    if not promo:
        await message.answer("❌ Промокод не найден.")
        return

    if promo.get("used_by") and str(message.from_user.id) in promo["used_by"]:
        await message.answer("Ты уже использовал этот промокод.")
        return

    promo_type = promo.get("type", "discount")

    if promo_type == "trial":
        trials = get_trials()
        trials[str(message.from_user.id)] = (
            datetime.now(timezone.utc) + timedelta(days=1)
        ).isoformat()
        save_trials(trials)
        promo.setdefault("used_by", []).append(str(message.from_user.id))
        save_promos(promos)
        await message.answer("🎉 Пробный доступ выдан на 24 часа.")
        return

    if promo_type == "discount":
        percent = int(promo.get("percent", 0))
        if not 1 <= percent <= 90:
            await message.answer("Промокод настроен некорректно.")
            return
        promo.setdefault("used_by", []).append(str(message.from_user.id))
        save_promos(promos)
        await message.answer(
            f"Промокод принят: скидка {percent}% на следующую активацию. "
            "Для применения обратись к администратору или используй меню оплаты."
        )
        return

    await message.answer("Этот тип промокода не поддерживается.")


@dp.callback_query(F.data == "filters")
async def filters_callback(callback: CallbackQuery):
    await callback.answer()
    uid = str(callback.from_user.id)
    filters = get_filters().get(uid, [])

    if not filters:
        await callback.message.answer(
            "У тебя пока нет сохранённых фильтров.",
            reply_markup=ik([[("➕ Сохранить фильтр", "filter_add"), ("⬅️ Меню", "menu")]]),
        )
        return

    lines = ["<b>Твои фильтры</b>"]
    for index, query in enumerate(filters, start=1):
        lines.append(f"{index}. {html.escape(query)}")

    await callback.message.answer(
        "\n".join(lines),
        reply_markup=ik([
            [("🔎 Новый поиск", "filter_add")],
            [("⬅️ Меню", "menu")],
        ]),
    )


@dp.callback_query(F.data == "filter_add")
async def filter_add_callback(callback: CallbackQuery):
    await callback.answer()
    waiting[str(callback.from_user.id)] = "filter_search"
    await callback.message.answer("Введи запрос, который нужно сохранить:")


@dp.callback_query(F.data.startswith("savefilter:"))
async def save_filter_callback(callback: CallbackQuery):
    await callback.answer()
    query = callback.data.split(":", 1)[1][:100]
    uid = str(callback.from_user.id)
    saved = get_filters()
    saved.setdefault(uid, [])
    if query not in saved[uid]:
        saved[uid].append(query)
    save_filters(saved)
    await callback.message.answer(f"📌 Фильтр сохранён: {html.escape(query)}")


@dp.callback_query(F.data == "csv")
async def csv_callback(callback: CallbackQuery):
    await callback.answer()
    results = last_results.get(str(callback.from_user.id), [])

    if not results:
        await callback.message.answer("Сначала выполни поиск.")
        return

    output = io.StringIO()
    writer = csv.DictWriter(
        output,
        fieldnames=["title", "game", "source", "url", "snippet"],
        extrasaction="ignore",
    )
    writer.writeheader()
    writer.writerows(results)

    from aiogram.types import BufferedInputFile
    file = BufferedInputFile(
        output.getvalue().encode("utf-8-sig"),
        filename="script_search.csv",
    )
    await callback.message.answer_document(file, caption="Результаты поиска в CSV.")


@dp.callback_query(F.data == "mystats")
async def my_stats_callback(callback: CallbackQuery):
    await callback.answer()
    users = get_users()
    info = users.get(str(callback.from_user.id), {})
    await callback.message.answer(
        f"<b>Твоя статистика</b>\n"
        f"Поисков: {info.get('searches', 0)}\n"
        f"Подписка: {'активна' if active_sub(callback.from_user.id) else 'не активна'}\n"
        f"Окончание: {expiry_text(callback.from_user.id)}"
    )


# =========================================================
# SHOP / ROULETTE / FREEZE / DONATIONS
# =========================================================

@dp.callback_query(F.data == "shop")
async def shop_callback(callback: CallbackQuery):
    await callback.answer()
    shop = get_shop()
    rows = []

    for code, item in shop.items():
        if item.get("bought"):
            continue
        rows.append([
            (
                f"{item.get('name', code)} — {item.get('price', 0)} ⭐",
                "buy:" + code,
            )
        ])

    rows.append([("⬅️ Меню", "menu")])

    if not shop:
        await callback.message.answer(
            "Магазин пока пуст. Администратор может добавить товары."
        )
        return

    await callback.message.answer("🛒 Магазин:", reply_markup=ik(rows))


@dp.callback_query(F.data.startswith("buy:"))
async def buy_callback(callback: CallbackQuery):
    await callback.answer()
    code = callback.data.split(":", 1)[1]
    shop = get_shop()
    item = shop.get(code)

    if not item or item.get("bought"):
        await callback.message.answer("Товар недоступен.")
        return

    price = int(item.get("price", 0))
    if price < 1:
        await callback.message.answer("Некорректная цена товара.")
        return

    try:
        await bot.send_invoice(
            chat_id=callback.from_user.id,
            title=str(item.get("name", code))[:32],
            description="Покупка в магазине Script Finder.",
            payload="shop:" + code,
            currency="XTR",
            prices=[LabeledPrice(label=str(item.get("name", code))[:32], amount=price)],
            provider_token="",
        )
    except TelegramAPIError as exc:
        log.exception("Shop invoice failed: %s", exc)
        await callback.message.answer("Не удалось создать счёт.")


@dp.callback_query(F.data == "roulette")
async def roulette_callback(callback: CallbackQuery):
    await callback.answer()
    await callback.message.answer(
        f"🎰 Рулетка стоит {ROLL_PRICE} ⭐ за попытку.\n"
        "Нажми кнопку, чтобы оплатить попытку.",
        reply_markup=ik([[("🎰 Крутить", "payroulette"), ("⬅️ Меню", "menu")]]),
    )


@dp.callback_query(F.data == "payroulette")
async def roulette_invoice_callback(callback: CallbackQuery):
    await callback.answer()
    try:
        await bot.send_invoice(
            chat_id=callback.from_user.id,
            title="Рулетка",
            description="Одна попытка рулетки Script Finder.",
            payload="roulette",
            currency="XTR",
            prices=[LabeledPrice(label="Попытка рулетки", amount=ROLL_PRICE)],
            provider_token="",
        )
    except TelegramAPIError as exc:
        log.exception("Roulette invoice failed: %s", exc)
        await callback.message.answer("Не удалось создать счёт.")


@dp.callback_query(F.data == "freeze")
async def freeze_callback(callback: CallbackQuery):
    await callback.answer()
    await callback.message.answer(
        "<b>🧊 Freeze</b>\n"
        "Используй эти скрипты только если доверяешь их источникам.",
        reply_markup=ik([
            [("Freeze", "freezescript:0")],
            [("Freeze Trade", "freezescript:1")],
            [("⬅️ Меню", "menu")],
        ]),
    )


@dp.callback_query(F.data.startswith("freezescript:"))
async def freeze_script_callback(callback: CallbackQuery):
    await callback.answer()
    index = int(callback.data.split(":", 1)[1])
    scripts = SCRIPTS["mm2"]
    freeze_items = [x for x in scripts if "Freeze" in x[0]]

    if index >= len(freeze_items):
        await callback.message.answer("Скрипт не найден.")
        return

    name, script = freeze_items[index]
    await callback.message.answer(
        f"<b>{html.escape(name)}</b>\n<pre>{html.escape(script)}</pre>"
    )


@dp.callback_query(F.data == "donate")
async def donate_callback(callback: CallbackQuery):
    await callback.answer()
    waiting[str(callback.from_user.id)] = "donation"
    await callback.message.answer(
        "Введи число Telegram Stars для доната (от 1 до 1000):"
    )


async def create_donation_invoice(message: Message, raw_amount: str):
    try:
        amount = int(raw_amount)
    except ValueError:
        await message.answer("Введи целое число.")
        return

    if not 1 <= amount <= 1000:
        await message.answer("Можно отправить от 1 до 1000 Stars.")
        return

    try:
        await bot.send_invoice(
            chat_id=message.from_user.id,
            title="Поддержка проекта",
            description=f"Добровольный донат: {amount} Telegram Stars.",
            payload=f"donation:{amount}",
            currency="XTR",
            prices=[LabeledPrice(label="Донат проекту", amount=amount)],
            provider_token="",
        )
    except TelegramAPIError as exc:
        log.exception("Donation invoice failed: %s", exc)
        await message.answer("Не удалось создать счёт.")


# =========================================================
# TELEGRAM STARS PAYMENTS
# =========================================================

@dp.pre_checkout_query()
async def pre_checkout(pre_checkout: PreCheckoutQuery):
    payload = pre_checkout.invoice_payload
    amount = pre_checkout.total_amount
    valid = False

    if payload == "sub_new":
        valid = amount == SUB_PRICE and not active_sub(pre_checkout.from_user.id)
    elif payload == "sub_renew":
        valid = amount == SUB_RENEW_PRICE and active_sub(pre_checkout.from_user.id)
    elif payload == "roulette":
        valid = amount == ROLL_PRICE
    elif payload.startswith("donation:"):
        try:
            requested = int(payload.split(":", 1)[1])
            valid = amount == requested and 1 <= requested <= 1000
        except ValueError:
            valid = False
    elif payload.startswith("shop:"):
        code = payload.split(":", 1)[1]
        item = get_shop().get(code)
        valid = bool(item and not item.get("bought") and amount == int(item.get("price", 0)))

    await pre_checkout.answer(ok=valid, error_message=None if valid else "Счёт устарел или не подходит.")


@dp.message(F.successful_payment)
async def successful_payment(message: Message):
    payment = message.successful_payment
    payload = payment.invoice_payload
    user_id = message.from_user.id
    stats = get_stats()
    stats["payments"] = int(stats.get("payments", 0)) + 1
    save_stats(stats)

    if payload in ("sub_new", "sub_renew"):
        expires = extend_subscription(user_id, 7)
        await message.answer(
            "🎉 <b>Подписка активирована!</b>\n"
            f"Действует до: <b>{expires.strftime('%d.%m.%Y %H:%M UTC')}</b>\n\n"
            "⚠️ Бот находится в BETA-версии, поэтому некоторые функции "
            "могут не работать или работать нестабильно.",
            reply_markup=main_kb(),
        )
        return

    if payload == "roulette":
        prize = random.choice(["premium", "filter", "nothing"])
        if prize == "premium":
            expires = extend_subscription(user_id, 1)
            await message.answer(
                f"🎉 Выигрыш: 1 день подписки! До {expires.strftime('%d.%m.%Y %H:%M UTC')}."
            )
        elif prize == "filter":
            saved = get_filters()
            saved.setdefault(str(user_id), [])
            saved[str(user_id)].append("random")
            save_filters(saved)
            await message.answer("🎉 Выигрыш: бонусный фильтр добавлен.")
        else:
            await message.answer("В этот раз без выигрыша. Попробуй ещё раз позже.")
        return

    if payload.startswith("donation:"):
        amount = int(payload.split(":", 1)[1])
        donations = get_donations()
        donations[str(user_id)] = int(donations.get(str(user_id), 0)) + amount
        save_donations(donations)

        if amount >= 25:
            sponsors = get_sponsors()
            sponsors[str(user_id)] = True
            save_sponsors(sponsors)
            await message.answer(
                "💛 Спасибо за поддержку! Тебе открыт дополнительный поиск.\n"
                "⚠️ Бот находится в BETA-версии."
            )
        else:
            await message.answer("💝 Спасибо за донат и поддержку проекта!")
        return

    if payload.startswith("shop:"):
        code = payload.split(":", 1)[1]
        shop = get_shop()
        item = shop.get(code)
        if item and not item.get("bought"):
            item["bought"] = True
            save_shop(shop)
            reward = item.get("reward", "")
            await message.answer(
                "🛒 Покупка прошла успешно!\n"
                + (f"<pre>{html.escape(str(reward))}</pre>" if reward else "")
            )
        else:
            await message.answer("Платёж получен, но товар не найден. Напиши администратору.")
        return

    await message.answer("Платёж получен, но тип покупки не распознан. Обратись к администратору.")


# =========================================================
# ADMIN COMMANDS
# =========================================================

@dp.message(Command("addpromo"))
async def admin_addpromo(message: Message):
    if message.from_user.id != ADMIN_ID:
        return

    # Format: /addpromo CODE discount 25
    # Or: /addpromo CODE trial
    parts = (message.text or "").split()
    if len(parts) < 3:
        await message.answer(
            "Формат:\n"
            "<code>/addpromo CODE discount 25</code>\n"
            "<code>/addpromo CODE trial</code>"
        )
        return

    code = parts[1].upper()
    promo_type = parts[2].lower()

    if not re.fullmatch(r"[A-Z0-9_-]{3,32}", code):
        await message.answer("Код должен содержать 3–32 символа A-Z, 0-9, _ или -.")
        return

    promos = get_promos()

    if promo_type == "discount":
        if len(parts) != 4:
            await message.answer("Укажи процент скидки: /addpromo CODE discount 25")
            return
        try:
            percent = int(parts[3])
        except ValueError:
            await message.answer("Процент должен быть числом.")
            return
        if not 1 <= percent <= 90:
            await message.answer("Процент должен быть от 1 до 90.")
            return
        promos[code] = {"type": "discount", "percent": percent, "used_by": []}
    elif promo_type == "trial":
        promos[code] = {"type": "trial", "used_by": []}
    else:
        await message.answer("Тип промокода: discount или trial.")
        return

    save_promos(promos)
    await message.answer(f"Промокод <code>{html.escape(code)}</code> создан.")


@dp.message(Command("additem"))
async def admin_additem(message: Message):
    if message.from_user.id != ADMIN_ID:
        return

    # Format: /additem code price name | reward text
    raw = (message.text or "").partition(" ")[2]
    left, sep, reward = raw.partition("|")
    parts = left.strip().split(maxsplit=2)

    if len(parts) < 3:
        await message.answer(
            "Формат:\n"
            "<code>/additem CODE PRICE Название | Текст награды</code>"
        )
        return

    code, price_text, name = parts
    try:
        price = int(price_text)
    except ValueError:
        await message.answer("Цена должна быть числом.")
        return

    if not 1 <= price <= 10000:
        await message.answer("Цена должна быть от 1 до 10000 Stars.")
        return

    shop = get_shop()
    shop[code] = {
        "name": name[:60],
        "price": price,
        "reward": reward.strip()[:3000],
        "bought": False,
        "created": datetime.now(timezone.utc).isoformat(),
    }
    save_shop(shop)
    await message.answer(f"Товар {html.escape(name)} добавлен.")


@dp.message(Command("addpremium"))
async def admin_addpremium(message: Message):
    if message.from_user.id != ADMIN_ID:
        return

    parts = (message.text or "").split()
    if len(parts) != 2 or not parts[1].isdigit():
        await message.answer("Формат: /addpremium TELEGRAM_ID")
        return

    target_id = int(parts[1])
    sponsors = get_sponsors()
    sponsors[str(target_id)] = True
    save_sponsors(sponsors)
    await message.answer(f"Дополнительный поиск открыт для ID {target_id}.")


# =========================================================
# HEALTH SERVER + STARTUP
# =========================================================

async def health(request):
    return web.json_response({
        "status": "ok",
        "service": "script-finder-bot",
        "time": datetime.now(timezone.utc).isoformat(),
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
    return runner


async def main():
    runner = None

    try:
        # Polling and webhook cannot be used simultaneously.
        # Remove an old webhook without discarding pending messages.
        await bot.delete_webhook(drop_pending_updates=False)

        me = await bot.get_me()
        log.info("Telegram bot authorized: @%s (id=%s)", me.username, me.id)

        runner = await start_health_server()

        log.info("Starting Telegram long polling...")
        await dp.start_polling(
            bot,
            allowed_updates=dp.resolve_used_update_types(),
            close_bot_session=False,
        )
    finally:
        if runner:
            await runner.cleanup()
        await bot.session.close()
        log.info("Bot stopped.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        log.info("Stopped by keyboard interrupt.")
    except Exception:
        log.exception("Fatal startup error.")
        raise
