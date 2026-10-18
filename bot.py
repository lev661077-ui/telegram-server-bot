import os
import asyncio
import re
import random
import string
import aiohttp
import csv
import io
import html
from datetime import datetime, timedelta
from urllib.parse import urljoin, urlparse
from aiohttp import web
from aiogram import Bot, Dispatcher, F, types
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import LabeledPrice, PreCheckoutQuery, BufferedInputFile


# ============================================================
# CONFIG
# ============================================================

TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = 123456789
SPONSOR_ID = 111111111

# Premium: 60 Stars for the first week, 20 Stars for renewal.
P_PRICE = 60
SUB_PRICE = 60
SUB_RENEW_PRICE = 20

F_PRICE = 10
FREE_L = 5
PREM_L = 15
ROLL_PRICE = 5

BETA_NOTICE = (
    "\n\n🧪 <b>Внимание!</b> Это BETA-версия бота. "
    "Некоторые функции могут работать нестабильно или не работать."
)

if not TOKEN:
    raise RuntimeError(
        "BOT_TOKEN не задан. Добавь BOT_TOKEN в Environment "
        "на Render. Не вставляй токен в исходный код."
    )

bot = Bot(
    token=TOKEN,
    default=DefaultBotProperties(parse_mode="HTML"),
)
dp = Dispatcher(storage=MemoryStorage())

UF = "u.txt"
PF = "p.txt"
FF = "f.txt"
TF = "t.txt"
DF = "d.txt"
SF = "s.txt"
PRF = "pr.txt"
SPF = "sp.txt"
SUBF = "sub.txt"
SFF = "sf.txt"

SCRIPTBLOX_API = "https://scriptblox.com/api/script/search"

SEARCH_SITES = [
    ("DeltaScripts.org", "https://deltascripts.org/"),
    ("DeltaScripts.ru", "https://deltascripts.ru/"),
    ("Scriptrb", "https://scriptrb.com/post.php?id=1891"),
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 Chrome/131.0 Safari/537.36",
    "Accept": "application/json, text/html, */*",
}

HTTP_TIMEOUT = aiohttp.ClientTimeout(total=15)
last_search = {}


# ============================================================
# FILE STORAGE
# ============================================================

def ls(filename):
    if not os.path.exists(filename):
        return set()

    with open(filename, "r", encoding="utf-8") as file:
        return {line.strip() for line in file if line.strip()}


def ss(filename, data):
    with open(filename, "w", encoding="utf-8") as file:
        for item in data:
            file.write(f"{item}\n")


def ld(filename, columns):
    data = {}

    if not os.path.exists(filename):
        return data

    with open(filename, "r", encoding="utf-8") as file:
        for line in file:
            parts = line.rstrip("\n").split("|")
            if len(parts) == columns and parts[0]:
                data[parts[0]] = parts[1:]

    return data


def sd(filename, data):
    with open(filename, "w", encoding="utf-8") as file:
        for key, values in data.items():
            file.write(
                f"{key}|" + "|".join(str(value) for value in values) + "\n"
            )


def lsp():
    data = {}

    if os.path.exists(SPF):
        with open(SPF, "r", encoding="utf-8") as file:
            for line in file:
                parts = line.rstrip("\n").split("|")
                if len(parts) == 3:
                    data[parts[0]] = {
                        "level": parts[1],
                        "last_claimed": parts[2],
                    }

    return data


def ssp(data):
    with open(SPF, "w", encoding="utf-8") as file:
        for user, values in data.items():
            file.write(
                f"{user}|{values['level']}|"
                f"{values['last_claimed']}\n"
            )


users = ls(UF)
prem = ls(PF)
frz = ls(FF)
dis = ls(DF)


# ============================================================
# SUBSCRIPTIONS AND ACCESS
# ============================================================

def get_subscription_expiry(user_id):
    subscriptions = ld(SUBF, 2)
    row = subscriptions.get(str(user_id))

    if not row:
        return None

    try:
        expiry = datetime.fromisoformat(row[0])
        if expiry > datetime.now():
            return expiry
    except (ValueError, TypeError, IndexError):
        return None

    return None


def has_subscription(user_id):
    return get_subscription_expiry(user_id) is not None


def is_p(user_id):
    user_id = str(user_id)
    return (
        user_id == str(ADMIN_ID)
        or user_id in prem
        or has_subscription(user_id)
    )


def has_sp(user_id):
    user_id = str(user_id)

    if is_p(user_id):
        return True

    trials = ld(TF, 2)
    row = trials.get(user_id)

    if row:
        try:
            return datetime.fromisoformat(row[0]) > datetime.now()
        except (ValueError, TypeError, IndexError):
            return False

    return False


def has_f(user_id):
    user_id = str(user_id)
    return (
        user_id == str(ADMIN_ID)
        or user_id in frz
        or is_p(user_id)
    )


def has_roulette_access(user_id):
    user_id = str(user_id)

    if user_id == str(ADMIN_ID) or is_p(user_id):
        return True

    trials = ld(TF, 2)
    row = trials.get(user_id)

    if not row:
        return False

    try:
        return datetime.fromisoformat(row[0]) > datetime.now()
    except (ValueError, TypeError, IndexError):
        return False


def subscription_price(user_id):
    user_id = str(user_id)

    if has_subscription(user_id):
        return SUB_RENEW_PRICE

    maximum_discount = 0

    for entry in dis:
        parts = entry.split("|")
        if len(parts) == 2 and parts[0] == user_id:
            try:
                maximum_discount = max(
                    maximum_discount, int(parts[1])
                )
            except ValueError:
                pass

    return max(1, round(SUB_PRICE * (1 - maximum_discount / 100)))


def activate_subscription(user_id, renewing=False):
    user_id = str(user_id)
    subscriptions = ld(SUBF, 2)
    now = datetime.now()

    current_expiry = get_subscription_expiry(user_id)

    if renewing and current_expiry:
        start = current_expiry
    else:
        start = now

    subscriptions[user_id] = [
        (start + timedelta(days=7)).isoformat()
    ]
    sd(SUBF, subscriptions)

    return subscriptions[user_id][0]


# ============================================================
# PROMO CODES
# ============================================================

def gen():
    return "PROMO-" + "".join(
        random.choices(string.ascii_uppercase + string.digits, k=8)
    )


def add_promo(user_id, promo_type, value, days=3):
    promos = ld(PRF, 6)

    active = []
    for key, row in promos.items():
        if row[2] != str(user_id) or row[3] != "no":
            continue

        try:
            if row[4] == "inf" or datetime.fromisoformat(row[4]) > datetime.now():
                active.append(key)
        except (ValueError, TypeError):
            continue

    if len(active) >= 10 and str(user_id) != str(ADMIN_ID):
        return None

    code = gen()
    expiry = (
        (datetime.now() + timedelta(days=days)).isoformat()
        if days > 0 else "inf"
    )

    promos[code] = [
        promo_type,
        str(value),
        str(user_id),
        "no",
        expiry,
    ]

    sd(PRF, promos)
    return code


def get_active_promos(user_id):
    promos = ld(PRF, 6)
    active = {}

    for code, row in promos.items():
        if row[2] != str(user_id) or row[3] != "no":
            continue

        try:
            if row[4] == "inf" or datetime.fromisoformat(row[4]) > datetime.now():
                active[code] = row
        except (ValueError, TypeError):
            continue

    return active


# ============================================================
# FSM STATES
# ============================================================

class SS(StatesGroup):
    wait = State()


class PS(StatesGroup):
    wait = State()


class DS(StatesGroup):
    wait = State()


class FS(StatesGroup):
    wait_name = State()
    wait_query = State()


# ============================================================
# EXISTING GAME SCRIPTS
# ============================================================

SC = {
    "redz": (
        "loadstring(game:HttpGet("
        "'https://pastebin.com/raw/1r7cEW7G'))()"
    ),
    "lord": (
        'loadstring(game:HttpGet("'
        "https://raw.githubusercontent.com/SUPREMEAURA350/"
        "KAISER-VERSION-2-/refs/heads/main/Kaiserspam"
        '"))()'
    ),
    "lola": (
        'loadstring(game:HttpGet("'
        "https://raw.githubusercontent.com/niriel015/"
        "Painel-LolaHub/refs/heads/main/Lola-hub-ne-pai"
        '"))()'
    ),
    "saiki": (
        'loadstring(game:HttpGet("'
        "https://raw.githubusercontent.com/SaikiWithTheBanHammer/"
        "ScriptBlox/main/LifeIsDisasterIndeedLol"
        '"))()'
    ),
    "madara": (
        'loadstring(game:HttpGet("'
        "https://raw.githubusercontent.com/IsThisMe01/"
        "Project-Madara/refs/heads/main/mm22.lua"
        '"))()'
    ),
    "moondiety": (
        'loadstring(game:HttpGet("'
        "https://scriptblox.com/raw/Murder-Mystery-2-KEYLESS-"
        "InstaWin-AutoFarm-Kill-all-XRay-nd-more-by-Moondiety-48644"
        '"))()'
    ),
    "godmode": (
        'loadstring(game:HttpGet("'
        "https://pastefy.app/a2dAk154/raw"
        '"))()'
    ),
    "bf_min": (
        'loadstring(game:HttpGet("'
        "https://raw.githubusercontent.com/LuaCrack/Min/"
        "refs/heads/main/MinXt2Eng"
        '"))()'
    ),
    "bf_redz": (
        'local Settings = { JoinTeam = "Pirates", Translator = true }\n'
        "getgenv().BETA_VERSION = true\n"
        'loadstring(game:HttpGet("'
        "https://raw.githubusercontent.com/tlredz/Scripts/"
        "refs/heads/main/main.luau"
        '"))(Settings)'
    ),
    "bf_basement": (
        'loadstring(game:HttpGet("'
        "https://raw.githubusercontent.com/Cazzanos/"
        "The-basement/main/Basement%20hub"
        '", true))()'
    ),
    "bf_autofarm": (
        'loadstring(game:HttpGetAsync("'
        "https://raw.githubusercontent.com/indexeduu/BF-NewVer/"
        "refs/heads/main/V3New.lua"
        '"))()'
    ),
    "99_1": (
        'loadstring(game:HttpGet("'
        "https://api.luarmor.net/files/v3/loaders/"
        "705e9a93cc18214fb77ab95686a8dba9.lua"
        '"))()'
    ),
    "99_2": (
        "KEY - 111222HHH\n\n"
        'loadstring(game:HttpGet("'
        "https://raw.githubusercontent.com/caomod2077/Script/"
        "refs/heads/main/FoxnameHub.lua"
        '"))()'
    ),
    "99_3": (
        'loadstring(game:HttpGet("'
        "https://ntt-hub.xyz/api/repo?id1=main&id2=lua"
        '"))()'
    ),
    "egg_1": (
        'loadstring(game:HttpGet("'
        "https://raw.githubusercontent.com/sabscrip-arch/"
        "srver/refs/heads/main/Stealanegg"
        '"))()'
    ),
    "egg_2": (
        'loadstring(game:HttpGet("'
        "https://raw.githubusercontent.com/lennonxscripts/"
        "lennonhubv2/refs/heads/main/stealaneggv2"
        '"))()'
    ),
    "egg_3": (
        'loadstring(game:HttpGet("'
        "https://raw.githubusercontent.com/lennonxscripts/"
        "lennonhubv2/refs/heads/main/stealaneggv2"
        '"))()'
    ),
}


# ============================================================
# MAIN MENU
# ============================================================

def kb(user_id):
    user_id = str(user_id)

    status = "⭐ Премиум" if is_p(user_id) else "🆓 Бесплатно"
    sponsors = lsp()

    sponsor_mark = ""
    if user_id in sponsors:
        if sponsors[user_id]["level"] == "gold":
            sponsor_mark = " 🌟"
        elif sponsors[user_id]["level"] == "bronze":
            sponsor_mark = " 🥉"

    subscription_mark = " ✅" if has_subscription(user_id) else ""

    return types.InlineKeyboardMarkup(
        inline_keyboard=[
            [types.InlineKeyboardButton(text="📜 Brookhaven", callback_data="mbh")],
            [types.InlineKeyboardButton(text="🎮 MM2", callback_data="mmm")],
            [types.InlineKeyboardButton(text="🍇 Blox Fruits", callback_data="mbf")],
            [types.InlineKeyboardButton(text="🌙 99 Ночей", callback_data="m99")],
            [types.InlineKeyboardButton(text="🥚 Steal an Egg", callback_data="meg")],
            [types.InlineKeyboardButton(text="🔍 Поиск", callback_data="ms")],
            [types.InlineKeyboardButton(text="📁 Мои фильтры", callback_data="sf_menu")],
            [types.InlineKeyboardButton(text="🎲 Рулетка", callback_data="roul")],
            [types.InlineKeyboardButton(text="🛒 Магазин", callback_data="shop")],
            [types.InlineKeyboardButton(
                text=f"💎 Подписка{subscription_mark}",
                callback_data="sub_menu"
            )],
            [types.InlineKeyboardButton(text="🎁 Промокод", callback_data="ep")],
            [types.InlineKeyboardButton(text=f"💎 Спонсор{sponsor_mark}", callback_data="dm")],
            [types.InlineKeyboardButton(text=f"⭐ Статус: {status}", callback_data="bp")],
            [types.InlineKeyboardButton(text="👥 Юзеры", callback_data="su")],
            [types.InlineKeyboardButton(
                text="💬 Соцсети",
                url="https://t.me/+LBs19_JzpW0yNmZi"
            )],
        ]
    )


# ============================================================
# START
# ============================================================

@dp.message(F.text == "/start")
async def start(message, state: FSMContext):
    await state.clear()

    user_id = str(message.from_user.id)
    is_new = user_id not in users

    if is_new:
        users.add(user_id)
        ss(UF, users)

    text = "🔥 <b>Привет!</b>\n\n"

    if is_new:
        promo = add_promo(user_id, "trial", 3, 3)
        if promo:
            text += (
                "🎁 <b>Подарок новичку!</b>\n"
                f"Твой промокод: <code>{promo}</code>\n"
                "Он даёт 3 дня доступа к рулетке.\n\n"
            )

    text += "Выбери категорию:" + BETA_NOTICE
    await message.answer(text, reply_markup=kb(user_id))


@dp.message(F.text == "/mycodes")
async def my_codes(message):
    user_id = str(message.from_user.id)
    active = get_active_promos(user_id)

    if not active:
        await message.answer("Нет активных промокодов.")
        return

    text = "🎁 <b>Твои промокоды:</b>\n\n"

    for code, row in active.items():
        expiry = "бессрочно" if row[4] == "inf" else row[4][:10]

        if row[0] == "discount":
            text += (
                f"<code>{html.escape(code)}</code> — "
                f"💰 Скидка {html.escape(row[1])}% (до {expiry})\n"
            )
        else:
            text += (
                f"<code>{html.escape(code)}</code> — "
                f"🎲 Рулетка {html.escape(row[1])} дн. (до {expiry})\n"
            )

    await message.answer(text, reply_markup=kb(user_id))


# ============================================================
# PREMIUM SUBSCRIPTION
# ============================================================

@dp.callback_query(F.data == "sub_menu")
async def sub_menu(callback):
    user_id = str(callback.from_user.id)
    expiry = get_subscription_expiry(user_id)

    if expiry:
        button_text = f"🔄 Продлить за {SUB_RENEW_PRICE} ⭐"
        description = (
            "💎 <b>Premium активен</b>\n"
            f"Действует до: <code>{expiry.strftime('%Y-%m-%d %H:%M')}</code>\n\n"
            f"Продление на 7 дней: ⭐ {SUB_RENEW_PRICE}"
        )
    else:
        button_text = f"💎 Купить на неделю за {SUB_PRICE} ⭐"
        description = (
            "💎 <b>Premium-подписка</b>\n\n"
            f"Первая неделя: ⭐ {SUB_PRICE}\n"
            f"Продление на неделю: ⭐ {SUB_RENEW_PRICE}\n\n"
            "Подписка не продлевается автоматически. "
            "Для следующей недели нужно снова оплатить продление."
        )

    keyboard = types.InlineKeyboardMarkup(
        inline_keyboard=[
            [types.InlineKeyboardButton(
                text=button_text,
                callback_data="premium_pay"
            )],
            [types.InlineKeyboardButton(
                text="❌ Отмена",
                callback_data="premium_cancel"
            )],
            [types.InlineKeyboardButton(
                text="🔙 Меню",
                callback_data="mm"
            )],
        ]
    )

    await callback.message.answer(
        description + BETA_NOTICE,
        reply_markup=keyboard
    )
    await callback.answer()


@dp.callback_query(F.data == "premium_cancel")
async def premium_cancel(callback):
    await callback.message.edit_text(
        "Покупка отменена. Оплата не произведена.",
        reply_markup=kb(callback.from_user.id)
    )
    await callback.answer()


@dp.callback_query(F.data == "premium_pay")
async def premium_pay(callback):
    user_id = str(callback.from_user.id)
    renewing = has_subscription(user_id)
    amount = SUB_RENEW_PRICE if renewing else subscription_price(user_id)
    payload = "sub_renew" if renewing else "sub_new"

    await bot.send_invoice(
        chat_id=callback.from_user.id,
        title="💎 Premium — продление" if renewing else "💎 Premium",
        description=(
            "Продление Premium на 7 дней"
            if renewing else
            "Первая неделя Premium"
        ),
        payload=payload,
        provider_token="",
        currency="XTR",
        prices=[
            LabeledPrice(
                label="Premium",
                amount=amount
            )
        ]
    )

    await callback.answer("Счёт отправлен ⭐")


# ============================================================
# SAVED SEARCH FILTERS
# ============================================================

@dp.callback_query(F.data == "sf_menu")
async def sf_menu(callback):
    user_id = str(callback.from_user.id)
    filters = ld(SFF, 5)
    mine = {
        key: value for key, value in filters.items()
        if value[0] == user_id
    }

    buttons = []

    for key, value in mine.items():
        buttons.append([
            types.InlineKeyboardButton(
                text=f"🔍 {value[1]}",
                callback_data=f"sf_use_{key}"
            )
        ])

    buttons.append([
        types.InlineKeyboardButton(
            text="➕ Сохранить новый фильтр",
            callback_data="sf_add"
        )
    ])
    buttons.append([
        types.InlineKeyboardButton(text="🔙 Меню", callback_data="mm")
    ])

    await callback.message.edit_text(
        "📁 <b>Мои фильтры поиска</b>",
        reply_markup=types.InlineKeyboardMarkup(inline_keyboard=buttons)
    )
    await callback.answer()


@dp.callback_query(F.data == "sf_add")
async def sf_add(callback, state: FSMContext):
    await callback.message.answer(
        "Введи название фильтра, например: MM2 Autofarm"
    )
    await state.set_state(FS.wait_name)
    await callback.answer()


@dp.message(FS.wait_name)
async def sf_name(message, state: FSMContext):
    name = (message.text or "").strip()

    if not name:
        await message.answer("Название не может быть пустым.")
        return

    await state.update_data(name=name[:80])
    await message.answer("Теперь введи поисковый запрос на английском.")
    await state.set_state(FS.wait_query)


@dp.message(FS.wait_query)
async def sf_query(message, state: FSMContext):
    data = await state.get_data()
    name = data.get("name", "Filter")
    query = (message.text or "").strip()

    if not query:
        await message.answer("Запрос не может быть пустым.")
        return

    user_id = str(message.from_user.id)
    filters = ld(SFF, 5)

    key = gen()[:8]
    filters[key] = [user_id, name, query, "no"]
    sd(SFF, filters)

    await state.clear()
    await message.answer(
        f"✅ Фильтр «{html.escape(name)}» сохранён!",
        reply_markup=kb(user_id)
    )


@dp.callback_query(F.data.startswith("sf_use_"))
async def sf_use(callback, state: FSMContext):
    key = callback.data.split("_", 2)[2]
    filters = ld(SFF, 5)
    user_id = str(callback.from_user.id)

    if key not in filters or filters[key][0] != user_id:
        await callback.answer("Фильтр не найден.", show_alert=True)
        return

    query = filters[key][2]
    await state.update_data(query=query)

    await callback.message.answer(
        f"🔎 Поиск по фильтру: {html.escape(query)}"
    )
    await run_search(callback.message, state, user_id)
    await callback.answer()


# ============================================================
# SCRIPT SEARCH: SCRIPTBLOX API
# ============================================================

def normalize_script_item(item, source="ScriptBlox"):
    title = str(item.get("title") or "").strip()
    if not title:
        return None

    game = item.get("game") or {}
    if isinstance(game, dict):
        game_name = str(game.get("name") or "Не указана")
    else:
        game_name = str(game or "Не указана")

    slug = str(item.get("slug") or "").strip()
    url = str(item.get("url") or "").strip()

    if not url and slug:
        if slug.startswith(("https://", "http://")):
            url = slug
        else:
            url = urljoin("https://scriptblox.com/", "script/" + slug.lstrip("/"))

    if not url:
        return None

    script = item.get("script") or item.get("scriptContent") or ""

    return {
        "title": title,
        "game": game_name,
        "script": str(script),
        "url": url,
        "source": source,
        "verified": bool(item.get("verified", False)),
        "has_key": bool(item.get("key", False)),
        "patched": bool(item.get("isPatched", False)),
    }


async def s1(query, place_id=None):
    """Search ScriptBlox API using the actual user query."""
    params = {
        "q": query.strip(),
        "max": 20,
        "page": 1,
        "strict": "false",
        "sortBy": "updatedAt",
        "order": "desc",
    }

    if place_id and str(place_id).isdigit():
        params["placeId"] = int(place_id)

    try:
        async with aiohttp.ClientSession(timeout=HTTP_TIMEOUT) as session:
            async with session.get(
                SCRIPTBLOX_API,
                params=params,
                headers=HEADERS
            ) as response:
                if response.status != 200:
                    return []

                data = await response.json(content_type=None)

        items = data.get("result", {}).get("scripts", [])
        results = []

        for item in items:
            normalized = normalize_script_item(item)
            if normalized:
                results.append(normalized)

        return results

    except (aiohttp.ClientError, asyncio.TimeoutError, ValueError, TypeError):
        return []


# ============================================================
# EXTRA PUBLIC SOURCE SEARCH FOR PREMIUM
# ============================================================

def extract_public_links(page, base_url, source_name, query):
    """Extract matching public links from accessible HTML."""
    anchors = re.findall(
        r"""<a\b[^>]*href\s*=\s*(['"])(.*?)\1[^>]*>(.*?)</a>""",
        page,
        flags=re.IGNORECASE | re.DOTALL
    )

    terms = [
        term.lower()
        for term in re.findall(r"[a-zA-Z0-9_-]+", query)
        if len(term) > 1
    ]

    results = []
    seen = set()

    for _, href, raw_title in anchors:
        title = re.sub(r"<[^>]+>", " ", raw_title)
        title = html.unescape(re.sub(r"\s+", " ", title)).strip()
        href = html.unescape(href.strip())

        if not title or not href:
            continue

        full_url = urljoin(base_url, href)
        parsed = urlparse(full_url)

        if parsed.scheme not in ("https", "http"):
            continue

        if full_url in seen:
            continue

        # Avoid unrelated navigation and social links.
        if any(
            blocked in parsed.netloc.lower()
            for blocked in ("facebook.com", "instagram.com", "t.me", "discord.com")
        ):
            continue

        if terms and not any(term in title.lower() for term in terms):
            continue

        seen.add(full_url)
        results.append({
            "title": title[:180],
            "game": "Не указана",
            "script": "",
            "url": full_url,
            "source": source_name,
            "verified": False,
            "has_key": False,
            "patched": False,
        })

    return results[:15]


async def search_public_site(session, source_name, url, query):
    try:
        async with session.get(
            url,
            headers=HEADERS,
            timeout=HTTP_TIMEOUT,
            allow_redirects=True
        ) as response:
            if response.status != 200:
                return []

            content_type = response.headers.get("Content-Type", "").lower()
            if "html" not in content_type:
                return []

            page = await response.text(errors="ignore")

        return extract_public_links(page, url, source_name, query)

    except (aiohttp.ClientError, asyncio.TimeoutError):
        return []


async def s2(query):
    """Search DeltaScripts.org public pages."""
    async with aiohttp.ClientSession(timeout=HTTP_TIMEOUT) as session:
        return await search_public_site(
            session,
            "DeltaScripts.org",
            "https://deltascripts.org/",
            query
        )


async def s3(query):
    """Search DeltaScripts.ru public pages."""
    async with aiohttp.ClientSession(timeout=HTTP_TIMEOUT) as session:
        return await search_public_site(
            session,
            "DeltaScripts.ru",
            "https://deltascripts.ru/",
            query
        )


async def s4(query):
    """Search the specified public Scriptrb page."""
    async with aiohttp.ClientSession(timeout=HTTP_TIMEOUT) as session:
        return await search_public_site(
            session,
            "Scriptrb",
            "https://scriptrb.com/post.php?id=1891",
            query
        )


async def search_scripts(query, premium=False, place_id=None):
    """
    Free users: ScriptBlox.
    Premium users: ScriptBlox and the configured public sources.
    No translation, invented results, or fake script links.
    """
    query = (query or "").strip()
    if not query:
        return []

    tasks = [s1(query, place_id)]

    if premium:
        tasks.extend([
            s2(query),
            s3(query),
            s4(query),
        ])

    batches = await asyncio.gather(*tasks, return_exceptions=True)

    combined = []
    seen = set()

    for batch in batches:
        if isinstance(batch, Exception):
            continue

        for item in batch:
            url = str(item.get("url") or "").rstrip("/")
            title = str(item.get("title") or "").strip()

            if not url or not title:
                continue

            key = url.lower()
            if key in seen:
                continue

            seen.add(key)
            combined.append(item)

    return combined


# ============================================================
# SEARCH UI
# ============================================================

@dp.callback_query(F.data == "ms")
async def ms(callback, state: FSMContext):
    user_id = str(callback.from_user.id)

    if has_subscription(user_id):
        limit = 20
    elif has_sp(user_id):
        limit = PREM_L
    else:
        limit = FREE_L

    await callback.message.answer(
        f"🔍 <b>Поиск скриптов</b>\n"
        f"Лимит результатов: {limit}\n"
        "Введи запрос на английском.\n"
        "Например: Blox Fruits Auto Farm",
        reply_markup=types.InlineKeyboardMarkup(
            inline_keyboard=[
                [types.InlineKeyboardButton(
                    text="❌ Отмена",
                    callback_data="mm"
                )]
            ]
        )
    )

    await state.set_state(SS.wait)
    await callback.answer()


@dp.message(SS.wait)
async def ps(message, state: FSMContext):
    query = (message.text or "").strip()

    if not query:
        await message.answer("Введи поисковый запрос.")
        return

    await state.update_data(query=query)
    await run_search(message, state, str(message.from_user.id))
    await state.clear()


async def run_search(message, state: FSMContext, user_id):
    data = await state.get_data()
    query = str(data.get("query", "")).strip()

    if not query:
        await message.answer("Введи поисковый запрос.")
        return

    if has_subscription(user_id):
        limit = 20
    elif has_sp(user_id):
        limit = PREM_L
    else:
        limit = FREE_L

    status_message = await message.answer(
        f"🔎 Ищу: <code>{html.escape(query)}</code>..."
    )

    results = await search_scripts(
        query,
        premium=has_subscription(user_id) or is_p(user_id)
    )

    if not results:
        await status_message.edit_text(
            "❌ Ничего не найдено.\n"
            "Попробуй другой запрос или проверь написание.",
            reply_markup=types.InlineKeyboardMarkup(
                inline_keyboard=[
                    [types.InlineKeyboardButton(
                        text="🔍 Новый поиск",
                        callback_data="ms"
                    )],
                    [types.InlineKeyboardButton(
                        text="🔙 Меню",
                        callback_data="mm"
                    )],
                ]
            )
        )
        return

    results = results[:limit]
    output = [f"🌐 <b>Найдено: {len(results)}</b>\n"]
    csv_buffer = io.StringIO()
    writer = csv.writer(csv_buffer)
    writer.writerow(["Title", "Game", "Source", "URL", "Script"])

    for index, item in enumerate(results, 1):
        title = html.escape(item.get("title", "Без названия"))
        game = html.escape(item.get("game") or "Не указана")
        source = html.escape(item.get("source") or "Unknown")
        url = html.escape(item.get("url", ""), quote=True)

        flags = []
        if item.get("verified"):
            flags.append("✅ Verified")
        if item.get("has_key"):
            flags.append("🔑 Key")
        if item.get("patched"):
            flags.append("⚠️ Возможно, устарел")

        extra = ("\n" + " · ".join(flags)) if flags else ""

        output.append(
            f"<b>{index}. {title}</b>\n"
            f"🎮 Игра: {game}\n"
            f"🌐 Источник: {source}\n"
            f'🔗 <a href="{url}">Открыть оригинал</a>'
            f"{extra}"
        )

        writer.writerow([
            item.get("title", ""),
            item.get("game", ""),
            item.get("source", ""),
            item.get("url", ""),
            item.get("script", ""),
        ])

    last_search[str(user_id)] = csv_buffer.getvalue()

    buttons = [
        [types.InlineKeyboardButton(
            text="📥 Экспорт в CSV",
            callback_data="export_csv"
        )],
        [types.InlineKeyboardButton(
            text="🔍 Новый поиск",
            callback_data="ms"
        )],
        [types.InlineKeyboardButton(
            text="🔙 Меню",
            callback_data="mm"
        )],
    ]

    text = "\n\n".join(output)

    # Telegram message length limit: send results in smaller groups.
    chunks = []
    current = ""

    for block in output:
        if len(current) + len(block) + 2 > 3500:
            if current:
                chunks.append(current)
            current = block
        else:
            current = f"{current}\n\n{block}" if current else block

    if current:
        chunks.append(current)

    await status_message.edit_text(
        chunks[0],
        reply_markup=types.InlineKeyboardMarkup(inline_keyboard=buttons),
        disable_web_page_preview=True
    )

    for chunk in chunks[1:]:
        await message.answer(
            chunk,
            disable_web_page_preview=True
        )


@dp.callback_query(F.data == "export_csv")
async def export_csv(callback):
    user_id = str(callback.from_user.id)

    if user_id not in last_search:
        await callback.answer("Нет данных для экспорта.", show_alert=True)
        return

    file = BufferedInputFile(
        last_search[user_id].encode("utf-8-sig"),
        filename="scripts.csv"
    )

    await bot.send_document(
        chat_id=callback.from_user.id,
        document=file,
        caption="📥 Результаты поиска в CSV"
    )
    await callback.answer()


# ============================================================
# GAME SCRIPT CALLBACKS
# ============================================================

@dp.callback_query(F.data.startswith("c_"))
async def script_callback(callback):
    name = callback.data.split("_", 1)[1]
    user_id = str(callback.from_user.id)

    if name == "frz":
        if not has_f(user_id):
            await callback.answer(
                "❄️ Функция доступна с Premium или после покупки заморозки.",
                show_alert=True
            )
            await bot.send_message(
                callback.from_user.id,
                f"❄️ <b>Заморозка</b>\nСтоимость: {F_PRICE} ⭐",
                reply_markup=types.InlineKeyboardMarkup(
                    inline_keyboard=[
                        [types.InlineKeyboardButton(
                            text="⭐ Купить",
                            callback_data="bf"
                        )]
                    ]
                )
            )
            return

        freeze_scripts = (
            "loadstring(game:HttpGet("
            "'https://cdn.sourceb.in/bins/9MHwJQNJkm/0'))()\n\n"
            "loadstring(game:HttpGet("
            "'https://raw.githubusercontent.com/txnic255/"
            "MM2-FREEZE-TRADE-V5.5-NEWEST-GUI-SCRIPT-/refs/heads/main/"
            "SCRIPT%20V5.5%20GUI%20AND%20SCRIPT'))()"
        )

        await callback.answer("Отправляю скрипты.")
        await bot.send_message(
            callback.from_user.id,
            "❄️ <b>Скрипты заморозки</b>\n\n"
            f"<pre>{html.escape(freeze_scripts)}</pre>"
            + BETA_NOTICE
        )
        return

    code = SC.get(name)
    if not code:
        await callback.answer("Скрипт не найден.", show_alert=True)
        return

    markup = types.InlineKeyboardMarkup(
        inline_keyboard=[
            [types.InlineKeyboardButton(
                text="📋 Скопировать",
                copy_text=types.CopyTextButton(text=code)
            )],
            [types.InlineKeyboardButton(
                text="🔙 Меню",
                callback_data="mm"
            )],
        ]
    )

    await callback.answer("Отправляю.")
    await bot.send_message(
        callback.from_user.id,
        "✅ <b>Скрипт:</b>\n\n"
        f"<pre>{html.escape(code)}</pre>"
        + BETA_NOTICE,
        reply_markup=markup
    )


# ============================================================
# SPONSOR DONATIONS
# ============================================================

@dp.callback_query(F.data == "dm")
async def dm(callback):
    buttons = [
        [
            types.InlineKeyboardButton(
                text=f"{amount} ⭐",
                callback_data=f"d_{amount}"
            )
            for amount in [10, 25, 50]
        ],
        [
            types.InlineKeyboardButton(
                text=f"{amount} ⭐",
                callback_data=f"d_{amount}"
            )
            for amount in [100, 250, 500]
        ],
        [types.InlineKeyboardButton(
            text="1000 ⭐",
            callback_data="d_1000"
        )],
        [types.InlineKeyboardButton(
            text="✏️ Своя сумма",
            callback_data="dc"
        )],
        [types.InlineKeyboardButton(
            text="🔙 Назад",
            callback_data="mm"
        )],
    ]

    await callback.message.edit_text(
        "💎 <b>Стать спонсором</b>",
        reply_markup=types.InlineKeyboardMarkup(inline_keyboard=buttons)
    )
    await callback.answer()


@dp.callback_query(F.data.regexp(r"^d_\d+$"))
async def donation_payment(callback):
    amount = int(callback.data.split("_", 1)[1])

    await bot.send_invoice(
        chat_id=callback.from_user.id,
        title="💎 Донат",
        description=f"Поддержка бота: {amount} Stars",
        payload=f"d_{amount}",
        provider_token="",
        currency="XTR",
        prices=[LabeledPrice(label="Донат", amount=amount)]
    )
    await callback.answer()


@dp.callback_query(F.data == "dc")
async def donation_custom(callback, state: FSMContext):
    await callback.message.answer("Введи сумму от 1 до 1000 ⭐.")
    await state.set_state(DS.wait)
    await callback.answer()


@dp.message(DS.wait)
async def donation_custom_amount(message, state: FSMContext):
    await state.clear()

    try:
        amount = int((message.text or "").strip())
        if not 1 <= amount <= 1000:
            raise ValueError
    except ValueError:
        await message.answer("❌ Неверная сумма. Введи число от 1 до 1000.")
        return

    await bot.send_invoice(
        chat_id=message.from_user.id,
        title="💎 Донат",
        description=f"Поддержка бота: {amount} Stars",
        payload=f"d_{amount}",
        provider_token="",
        currency="XTR",
        prices=[LabeledPrice(label="Донат", amount=amount)]
    )


# ============================================================
# SHOP
# ============================================================

def gs():
    items = []
    discounts = [5, 10, 15, 20, 30, 50]

    for _ in range(10):
        item_type = random.choice(["discount", "trial3", "trial5"])

        if item_type == "discount":
            product_type = f"discount_{random.choice(discounts)}"
            price = 3
        elif item_type == "trial3":
            product_type = "trial3"
            price = 7
        else:
            product_type = "trial5"
            price = 10

        items.append(
            f"{gen()}|{product_type}|{price}|no|"
            f"{datetime.now().isoformat()}|inf"
        )

    with open(SF, "w", encoding="utf-8") as file:
        file.write("\n".join(items) + "\n")


def gsh():
    items = []

    if not os.path.exists(SF):
        return items

    with open(SF, "r", encoding="utf-8") as file:
        for line in file:
            parts = line.rstrip("\n").split("|")

            if len(parts) != 6:
                continue

            try:
                price = int(parts[2])
            except ValueError:
                continue

            items.append({
                "code": parts[0],
                "type": parts[1],
                "price": price,
                "bought": parts[3],
                "created": parts[4],
                "exp": parts[5],
            })

    return items


def save_shop(items):
    with open(SF, "w", encoding="utf-8") as file:
        for item in items:
            file.write(
                f"{item['code']}|{item['type']}|{item['price']}|"
                f"{item['bought']}|{item['created']}|"
                f"{item.get('exp', 'inf')}\n"
            )


def promo_from_shop_item(user_id, item):
    if item["type"].startswith("discount_"):
        promo_type = "discount"
        value = item["type"].split("_", 1)[1]
    else:
        promo_type = "trial"
        value = "3" if item["type"] == "trial3" else "5"

    return add_promo(user_id, promo_type, value, 3)


@dp.callback_query(F.data == "shop")
async def shop(callback):
    user_id = str(callback.from_user.id)

    if not os.path.exists(SF):
        gs()

    items = gsh()
    buttons = []

    for item in items:
        if item["bought"] == "yes":
            continue

        if item["type"].startswith("discount_"):
            title = f"💰 Скидка {item['type'].split('_', 1)[1]}%"
        elif item["type"] == "trial3":
            title = "🎲 Рулетка 3 дня"
        else:
            title = "🎲 Рулетка 5 дней"

        if user_id == str(ADMIN_ID):
            callback_data = f"freebp_{item['code']}"
            title = "👑 " + title
        else:
            callback_data = f"bp_{item['code']}"

        buttons.append([
            types.InlineKeyboardButton(
                text=f"{title} — {item['price']} ⭐",
                callback_data=callback_data
            )
        ])

    buttons.extend([
        [types.InlineKeyboardButton(
            text="🔄 Обновить",
            callback_data="refresh_shop"
        )],
        [types.InlineKeyboardButton(
            text="🔙 Меню",
            callback_data="mm"
        )],
    ])

    await callback.message.edit_text(
        "🛒 <b>Магазин</b>",
        reply_markup=types.InlineKeyboardMarkup(inline_keyboard=buttons)
    )
    await callback.answer()


@dp.callback_query(F.data == "refresh_shop")
async def refresh_shop(callback):
    gs()
    await shop(callback)


@dp.callback_query(F.data.startswith("freebp_"))
async def freebp(callback):
    user_id = str(callback.from_user.id)

    if user_id != str(ADMIN_ID):
        await callback.answer("Только для администратора.", show_alert=True)
        return

    code = callback.data.split("_", 1)[1]
    items = gsh()
    item = next((x for x in items if x["code"] == code), None)

    if not item or item["bought"] == "yes":
        await callback.answer("Товар не найден или уже продан.", show_alert=True)
        return

    promo = promo_from_shop_item(user_id, item)
    if not promo:
        await callback.answer("Не удалось создать промокод.", show_alert=True)
        return

    item["bought"] = "yes"
    save_shop(items)

    await callback.answer("Промокод создан.")
    await callback.message.edit_text(
        f"👑 <b>Промокод получен!</b>\n"
        f"Код: <code>{promo}</code>",
        reply_markup=kb(user_id)
    )


@dp.callback_query(F.data.startswith("bp_"))
async def shop_purchase(callback):
    code = callback.data.split("_", 1)[1]
    items = gsh()
    item = next((x for x in items if x["code"] == code), None)

    if not item or item["bought"] == "yes":
        await callback.answer("Товар уже продан или не найден.", show_alert=True)
        return

    await bot.send_invoice(
        chat_id=callback.from_user.id,
        title="🛒 Покупка в магазине",
        description=f"Товар: {item['type']}",
        payload=f"p_{code}",
        provider_token="",
        currency="XTR",
        prices=[LabeledPrice(label="Товар", amount=item["price"])]
    )
    await callback.answer("Счёт отправлен.")


# ============================================================
# PROMO ACTIVATION
# ============================================================

@dp.callback_query(F.data == "ep")
async def ep(callback, state: FSMContext):
    await callback.message.answer("🎁 Введи промокод:")
    await state.set_state(PS.wait)
    await callback.answer()


@dp.message(PS.wait)
async def pp(message, state: FSMContext):
    await state.clear()

    user_id = str(message.from_user.id)
    code = (message.text or "").strip().upper()
    promos = ld(PRF, 6)

    if code not in promos:
        await message.answer("❌ Промокод не найден.", reply_markup=kb(user_id))
        return

    promo_type, value, owner, used, expiry = promos[code]

    if used != "no":
        await message.answer("❌ Этот промокод уже активирован.", reply_markup=kb(user_id))
        return

    try:
        if expiry != "inf" and datetime.fromisoformat(expiry) < datetime.now():
            await message.answer("❌ Срок промокода истёк.", reply_markup=kb(user_id))
            return
    except ValueError:
        await message.answer("❌ Ошибка срока действия промокода.")
        return

    if promo_type == "discount":
        try:
            discount = int(value)
            if not 1 <= discount <= 90:
                raise ValueError
        except ValueError:
            await message.answer("❌ Некорректная скидка.")
            return

        dis.add(f"{user_id}|{discount}")
        ss(DF, dis)
        answer = f"✅ Скидка {discount}% активирована!"

    elif promo_type == "trial":
        try:
            days = int(value)
            if days < 1 or days > 365:
                raise ValueError
        except ValueError:
            await message.answer("❌ Некорректный срок промокода.")
            return

        trials = ld(TF, 2)
        old_expiry = None

        if user_id in trials:
            try:
                old_expiry = datetime.fromisoformat(trials[user_id][0])
            except ValueError:
                old_expiry = None

        start = old_expiry if old_expiry and old_expiry > datetime.now() else datetime.now()
        trials[user_id] = [(start + timedelta(days=days)).isoformat()]
        sd(TF, trials)
        answer = f"✅ Доступ к рулетке активирован на {days} дней!"

    else:
        await message.answer("❌ Неизвестный тип промокода.")
        return

    promos[code] = [promo_type, value, owner, "yes", expiry]
    sd(PRF, promos)

    await message.answer(answer, reply_markup=kb(user_id))


# ============================================================
# ROULETTE
# ============================================================

@dp.callback_query(F.data == "roul")
async def roul(callback):
    user_id = str(callback.from_user.id)

    if not has_roulette_access(user_id):
        await bot.send_invoice(
            chat_id=callback.from_user.id,
            title="🎲 Рулетка",
            description="Получение скриптов",
            payload="roulette",
            provider_token="",
            currency="XTR",
            prices=[LabeledPrice(label="Рулетка", amount=ROLL_PRICE)]
        )
        await callback.answer("Счёт отправлен.")
        return

    await callback.message.answer("🎲 Крутим рулетку...")
    await give_roulette_prize(callback.message, user_id)
    await callback.answer()


async def give_roulette_prize(message, user_id):
    status_message = await message.answer("🔎 Ищу результаты для рулетки...")

    queries = [
        "Infinite Yield",
        "Dark Dex",
        "Nameless Admin",
        "Simple Spy",
    ]

    random.shuffle(queries)
    found = []

    for query in queries[:3]:
        try:
            results = await s1(query)
            found.extend(results[:2])
        except Exception:
            continue

    unique = []
    seen = set()

    for item in found:
        key = item.get("url") or item.get("title")
        if key and key not in seen:
            seen.add(key)
            unique.append(item)

    if not unique:
        await status_message.edit_text(
            "❌ Не удалось найти результаты рулетки. Попробуй позже.",
            reply_markup=kb(user_id)
        )
        return

    lines = ["🎰 <b>Результаты рулетки:</b>\n"]

    for index, item in enumerate(unique[:5], 1):
        title = html.escape(item.get("title", "Без названия"))
        url = html.escape(item.get("url", ""), quote=True)
        source = html.escape(item.get("source", "ScriptBlox"))

        lines.append(
            f"{index}. <b>{title}</b>\n"
            f"🌐 {source}\n"
            f'🔗 <a href="{url}">Открыть</a>'
        )

    await status_message.edit_text(
        "\n\n".join(lines),
        reply_markup=kb(user_id),
        disable_web_page_preview=True
    )


# ============================================================
# FREEZE PURCHASE
# ============================================================

@dp.callback_query(F.data == "bf")
async def bf(callback):
    user_id = str(callback.from_user.id)

    if has_f(user_id):
        await callback.answer("Доступ уже есть.", show_alert=True)
        return

    await bot.send_invoice(
        chat_id=callback.from_user.id,
        title="❄️ Заморозка",
        description="Доступ к скриптам заморозки",
        payload="frz",
        provider_token="",
        currency="XTR",
        prices=[LabeledPrice(label="Заморозка", amount=F_PRICE)]
    )
    await callback.answer("Счёт отправлен.")


# ============================================================
# PAYMENT VALIDATION
# All Telegram Stars payments are checked in one handler.
# ============================================================

async def expected_payment_amount(payload, user_id):
    user_id = str(user_id)

    if payload == "sub_new":
        if has_subscription(user_id):
            return None
        return subscription_price(user_id)

    if payload in ("sub_renew", "sub_access"):
        if payload == "sub_renew" and not has_subscription(user_id):
            return None
        if payload == "sub_access":
            return SUB_PRICE
        return SUB_RENEW_PRICE

    if payload == "prem":
        return subscription_price(user_id)

    if payload == "frz":
        if has_f(user_id):
            return None
        return F_PRICE

    if payload == "roulette":
        if has_roulette_access(user_id):
            return None
        return ROLL_PRICE

    if payload.startswith("d_"):
        try:
            amount = int(payload.split("_", 1)[1])
            return amount if 1 <= amount <= 1000 else None
        except ValueError:
            return None

    if payload.startswith("p_"):
        code = payload.split("_", 1)[1]
        item = next((x for x in gsh() if x["code"] == code), None)

        if not item or item["bought"] == "yes":
            return None

        return item["price"]

    return None


@dp.pre_checkout_query()
async def payment_pre_checkout(query: PreCheckoutQuery):
    if query.currency != "XTR":
        await query.answer(
            ok=False,
            error_message="Неверная валюта платежа."
        )
        return

    expected = await expected_payment_amount(
        query.invoice_payload,
        query.from_user.id
    )

    if expected is None or query.total_amount != expected:
        await query.answer(
            ok=False,
            error_message=(
                "Сумма изменилась или платёж больше недоступен. "
                "Открой меню и создай новый счёт."
            )
        )
        return

    await query.answer(ok=True)


# ============================================================
# PAYMENT SUCCESS
# ============================================================

@dp.message(F.successful_payment)
async def payment_success(message):
    user_id = str(message.from_user.id)
    payment = message.successful_payment
    payload = payment.invoice_payload

    # First week or renewal.
    if payload in ("sub_new", "sub_renew", "sub_access", "prem"):
        renewing = payload == "sub_renew" or (
            payload == "sub_access" and has_subscription(user_id)
        )

        expiry = activate_subscription(user_id, renewing=renewing)

        # A discount is consumed after a successful first-week purchase.
        if not renewing:
            for entry in list(dis):
                if entry.startswith(f"{user_id}|"):
                    dis.discard(entry)
            ss(DF, dis)

        await message.answer(
            "🎉 <b>Оплата прошла успешно!</b>\n\n"
            "💎 Premium активирован.\n"
            f"📅 Действует до: <code>{expiry[:16].replace('T', ' ')}</code>\n"
            + BETA_NOTICE,
            reply_markup=kb(user_id)
        )
        return

    if payload == "frz":
        frz.add(user_id)
        ss(FF, frz)

        await message.answer(
            "❄️ <b>Заморозка активирована!</b>" + BETA_NOTICE,
            reply_markup=kb(user_id)
        )
        return

    if payload == "roulette":
        await message.answer("🎉 Оплата прошла! Запускаю рулетку.")
        await give_roulette_prize(message, user_id)
        return

    if payload.startswith("d_"):
        try:
            amount = int(payload.split("_", 1)[1])
        except ValueError:
            await message.answer("Платёж получен, но сумма не распознана.")
            return

        sponsors = lsp()
        level = "gold" if amount >= 25 else (
            "bronze" if 5 <= amount <= 10 else "none"
        )

        if level != "none":
            sponsors[user_id] = {
                "level": level,
                "last_claimed": "2000-01-01T00:00:00",
            }
            ssp(sponsors)

            await message.answer(
                f"💎 Спасибо за поддержку: {amount} ⭐!\n"
                f"Статус спонсора: {level.upper()}",
                reply_markup=kb(user_id)
            )
        else:
            await message.answer(
                f"💎 Спасибо за донат: {amount} ⭐!",
                reply_markup=kb(user_id)
            )

        return

    if payload.startswith("p_"):
        code = payload.split("_", 1)[1]
        items = gsh()
        item = next((x for x in items if x["code"] == code), None)

        if not item or item["bought"] == "yes":
            await message.answer(
                "Платёж получен, но товар уже недоступен. "
                "Свяжись с администратором."
            )
            return

        promo = promo_from_shop_item(user_id, item)

        if not promo:
            await message.answer(
                "Платёж получен, но промокод создать не удалось. "
                "Свяжись с администратором."
            )
            return

        item["bought"] = "yes"
        save_shop(items)

        await message.answer(
            "✅ <b>Покупка успешна!</b>\n"
            f"Твой промокод: <code>{promo}</code>",
            reply_markup=kb(user_id)
        )


# ============================================================
# PREMIUM STATUS
# ============================================================

@dp.callback_query(F.data == "bp")
async def premium_status(callback):
    user_id = str(callback.from_user.id)

    if has_subscription(user_id):
        expiry = get_subscription_expiry(user_id)
        text = (
            "💎 <b>Premium активен!</b>\n"
            f"Действует до: <code>{expiry.strftime('%Y-%m-%d %H:%M')}</code>\n"
            f"Продление: ⭐ {SUB_RENEW_PRICE} за 7 дней."
        )
    elif user_id in prem or user_id == str(ADMIN_ID):
        text = "💎 <b>Premium доступ активен.</b>"
    else:
        text = (
            "💎 <b>Premium</b>\n"
            f"Первая неделя: ⭐ {SUB_PRICE}\n"
            f"Продление: ⭐ {SUB_RENEW_PRICE} в неделю."
        )

    await callback.message.answer(
        text + BETA_NOTICE,
        reply_markup=types.InlineKeyboardMarkup(
            inline_keyboard=[
                [types.InlineKeyboardButton(
                    text="💎 Купить / продлить",
                    callback_data="sub_menu"
                )],
                [types.InlineKeyboardButton(
                    text="🔙 Меню",
                    callback_data="mm"
                )],
            ]
        )
    )
    await callback.answer()


# ============================================================
# GAME CATEGORY MENUS
# ============================================================

@dp.callback_query(F.data == "mbh")
async def mbh(callback):
    buttons = [
        [types.InlineKeyboardButton(text="🔥 Redz", callback_data="c_redz")],
        [types.InlineKeyboardButton(text="🚀 Lord", callback_data="c_lord")],
        [types.InlineKeyboardButton(text="🌐 LOLA", callback_data="c_lola")],
        [types.InlineKeyboardButton(text="🎧 Saiki", callback_data="c_saiki")],
        [types.InlineKeyboardButton(text="🔙 Назад", callback_data="mm")],
    ]

    await callback.message.edit_text(
        "📜 <b>Brookhaven</b>",
        reply_markup=types.InlineKeyboardMarkup(inline_keyboard=buttons)
    )
    await callback.answer()


@dp.callback_query(F.data == "mmm")
async def mmm(callback):
    buttons = [
        [types.InlineKeyboardButton(text="🥷 Madara", callback_data="c_madara")],
        [types.InlineKeyboardButton(text="🔪 Moondiety", callback_data="c_moondiety")],
        [types.InlineKeyboardButton(text="🛡️ God", callback_data="c_godmode")],
        [types.InlineKeyboardButton(text="❄️ Заморозка", callback_data="c_frz")],
        [types.InlineKeyboardButton(text="🔙 Назад", callback_data="mm")],
    ]

    await callback.message.edit_text(
        "🎮 <b>Murder Mystery 2</b>",
        reply_markup=types.InlineKeyboardMarkup(inline_keyboard=buttons)
    )
    await callback.answer()


@dp.callback_query(F.data == "mbf")
async def mbf(callback):
    buttons = [
        [types.InlineKeyboardButton(text="🎮 Min", callback_data="c_bf_min")],
        [types.InlineKeyboardButton(text="🚀 Redz B", callback_data="c_bf_redz")],
        [types.InlineKeyboardButton(text="🏠 Basement", callback_data="c_bf_basement")],
        [types.InlineKeyboardButton(text="⚡ Autofarm", callback_data="c_bf_autofarm")],
        [types.InlineKeyboardButton(text="🔙 Назад", callback_data="mm")],
    ]

    await callback.message.edit_text(
        "🍇 <b>Blox Fruits</b>",
        reply_markup=types.InlineKeyboardMarkup(inline_keyboard=buttons)
    )
    await callback.answer()


@dp.callback_query(F.data == "m99")
async def m99(callback):
    buttons = [
        [types.InlineKeyboardButton(text="📜 Скрипт 1", callback_data="c_99_1")],
        [types.InlineKeyboardButton(text="📜 Скрипт 2 (KEY)", callback_data="c_99_2")],
        [types.InlineKeyboardButton(text="📜 Скрипт 3", callback_data="c_99_3")],
        [types.InlineKeyboardButton(text="🔙 Назад", callback_data="mm")],
    ]

    await callback.message.edit_text(
        "🌙 <b>99 Nights</b>",
        reply_markup=types.InlineKeyboardMarkup(inline_keyboard=buttons)
    )
    await callback.answer()


@dp.callback_query(F.data == "meg")
async def meg(callback):
    buttons = [
        [types.InlineKeyboardButton(text="📜 Sabs", callback_data="c_egg_1")],
        [types.InlineKeyboardButton(text="🎧 Lennon V2", callback_data="c_egg_2")],
        [types.InlineKeyboardButton(text="🥚 Lennon Auto", callback_data="c_egg_3")],
        [types.InlineKeyboardButton(text="🔙 Назад", callback_data="mm")],
    ]

    await callback.message.edit_text(
        "🥚 <b>Steal an Egg</b>",
        reply_markup=types.InlineKeyboardMarkup(inline_keyboard=buttons)
    )
    await callback.answer()


@dp.callback_query(F.data == "mm")
async def mm(callback, state: FSMContext):
    await state.clear()

    await callback.message.edit_text(
        "🔥 <b>Выбери категорию:</b>",
        reply_markup=kb(callback.from_user.id)
    )
    await callback.answer()


# ============================================================
# USER STATISTICS
# ============================================================

@dp.callback_query(F.data == "su")
async def su(callback):
    active_subscriptions = sum(
        1 for user_id in users if has_subscription(user_id)
    )

    await callback.answer(
        f"👥 Всего пользователей: {len(users)}\n"
        f"⭐ Premium-подписок: {active_subscriptions}\n"
        f"💎 Сохранённых Premium-аккаунтов: {len(prem)}",
        show_alert=True
    )


# ============================================================
# ADMIN COMMANDS
# ============================================================

@dp.message(F.text == "/stats")
async def stats(message):
    if str(message.from_user.id) != str(ADMIN_ID):
        return

    active_subscriptions = sum(
        1 for user_id in users if has_subscription(user_id)
    )

    await message.answer(
        "<b>Статистика</b>\n"
        f"Пользователей: {len(users)}\n"
        f"Premium-подписок: {active_subscriptions}\n"
        f"Premium в старом списке: {len(prem)}\n"
        f"Заморозка: {len(frz)}\n"
        f"Промокодов: {len(ld(PRF, 6))}"
    )


# ============================================================
# RENDER WEBHOOK
# ============================================================

async def health(request):
    return web.Response(text="OK")


async def on_startup(app):
    base_url = os.getenv("RENDER_EXTERNAL_URL")

    if not base_url:
        raise RuntimeError(
            "RENDER_EXTERNAL_URL не задан. "
            "Проверь настройки Web Service на Render."
        )

    webhook_url = base_url.rstrip("/") + "/webhook"

    await bot.set_webhook(webhook_url)
    print(f"Webhook установлен: {webhook_url}")


async def on_shutdown(app):
    await bot.delete_webhook(drop_pending_updates=False)
    await bot.session.close()


def main():
    app = web.Application()

    from aiogram.webhook.aiohttp_server import SimpleRequestHandler

    webhook_handler = SimpleRequestHandler(
        dispatcher=dp,
        bot=bot
    )
    webhook_handler.register(app, path="/webhook")

    app.router.add_get("/", health)
    app.router.add_get("/health", health)

    app.on_startup.append(on_startup)
    app.on_cleanup.append(on_shutdown)

    port = int(os.getenv("PORT", "8080"))

    web.run_app(
        app,
        host="0.0.0.0",
        port=port
    )


if __name__ == "__main__":
    main()
