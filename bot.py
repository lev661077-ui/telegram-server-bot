import os
import asyncio
import re
import random
import string
import aiohttp
import csv
import io
import html
import logging

from datetime import datetime, timedelta
from aiohttp import web

from aiogram import Bot, Dispatcher, F, types
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    LabeledPrice,
    PreCheckoutQuery,
    BufferedInputFile,
)


# =========================================================
# CONFIGURATION
# =========================================================

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TOKEN = os.getenv("BOT_TOKEN")

if not TOKEN:
    raise RuntimeError(
        "BOT_TOKEN не задан. Добавь его в Render → Environment."
    )

ADMIN_ID = 123456789  # ВСТАВЬ СВОЙ TELEGRAM ID
SPONSOR_ID = 111111111  # ВСТАВЬ ID СПОНСОРА

P_PRICE = 30
F_PRICE = 10
FREE_L = 5
PREM_L = 15
ROLL_PRICE = 5
SUB_PRICE = 100

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

bot = Bot(
    token=TOKEN,
    default=DefaultBotProperties(parse_mode="HTML"),
)

dp = Dispatcher(storage=MemoryStorage())

last_search = {}


# =========================================================
# FILE STORAGE
# =========================================================

def ls(filename):
    if not os.path.exists(filename):
        return set()

    with open(filename, "r", encoding="utf-8") as file:
        return {
            line.strip()
            for line in file
            if line.strip()
        }


def ss(filename, data):
    with open(filename, "w", encoding="utf-8") as file:
        for item in data:
            file.write(f"{item}\n")


def ld(filename, columns):
    data = {}

    if os.path.exists(filename):
        with open(filename, "r", encoding="utf-8") as file:
            for line in file:
                parts = line.rstrip("\n").split("|")

                if len(parts) == columns:
                    data[parts[0]] = parts[1:]

    return data


def sd(filename, data):
    with open(filename, "w", encoding="utf-8") as file:
        for key, values in data.items():
            file.write(
                f"{key}|"
                + "|".join(str(value) for value in values)
                + "\n"
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
        for user_id, values in data.items():
            file.write(
                f"{user_id}|"
                f"{values['level']}|"
                f"{values['last_claimed']}\n"
            )


users = ls(UF)
prem = ls(PF)
frz = ls(FF)
dis = ls(DF)


# =========================================================
# USER ACCESS
# =========================================================

def is_p(user_id):
    return (
        str(user_id) == str(ADMIN_ID)
        or str(user_id) in prem
    )


def has_sp(user_id):
    if is_p(user_id):
        return True

    roulette_data = ld(TF, 2)
    record = roulette_data.get(str(user_id))

    if record:
        try:
            return (
                datetime.fromisoformat(record[0])
                > datetime.now()
            )
        except (ValueError, TypeError):
            return False

    return False


def has_f(user_id):
    user_id = str(user_id)

    return (
        user_id == str(ADMIN_ID)
        or user_id in prem
        or user_id in frz
    )


def has_sub(user_id):
    """
    Совместимо с текущим форматом sub.txt:
    user_id|дата_покупки

    В исходной логике подписка не истекает автоматически.
    """
    return str(user_id) in ld(SUBF, 2)


# =========================================================
# PROMO CODES
# =========================================================

def gen():
    return "PROMO-" + "".join(
        random.choices(
            string.ascii_uppercase + string.digits,
            k=8,
        )
    )


def add_promo(user_id, promo_type, value, days=3):
    promos = ld(PRF, 6)
    user_id = str(user_id)

    active = []

    for key, values in promos.items():
        try:
            if (
                values[2] == user_id
                and values[3] == "no"
                and (
                    values[4] == "inf"
                    or datetime.fromisoformat(values[4])
                    > datetime.now()
                )
            ):
                active.append(key)
        except (ValueError, IndexError):
            continue

    if len(active) >= 10 and user_id != str(ADMIN_ID):
        return None

    code = gen()

    expiration = (
        (datetime.now() + timedelta(days=days)).isoformat()
        if days > 0
        else "inf"
    )

    promos[code] = [
        promo_type,
        str(value),
        user_id,
        "no",
        expiration,
    ]

    sd(PRF, promos)

    return code


def get_active_promos(user_id):
    promos = ld(PRF, 6)
    user_id = str(user_id)
    result = {}

    for code, values in promos.items():
        try:
            if (
                values[2] == user_id
                and values[3] == "no"
                and (
                    values[4] == "inf"
                    or datetime.fromisoformat(values[4])
                    > datetime.now()
                )
            ):
                result[code] = values
        except (ValueError, IndexError):
            continue

    return result


# =========================================================
# FSM STATES
# =========================================================

class SS(StatesGroup):
    wait = State()


class PS(StatesGroup):
    wait = State()


class DS(StatesGroup):
    wait = State()


class FS(StatesGroup):
    wait_name = State()
    wait_query = State()


# =========================================================
# LUA SCRIPT COLLECTION
# =========================================================

SC = {
    "redz": (
        "loadstring(game:HttpGet("
        "'https://pastebin.com/raw/1r7cEW7G'))()"
    ),

    "lord": (
        'loadstring(game:HttpGet('
        '"https://raw.githubusercontent.com/'
        'SUPREMEAURA350/KAISER-VERSION-2-/refs/heads/main/'
        'Kaiserspam"))()'
    ),

    "lola": (
        'loadstring(game:HttpGet('
        '"https://raw.githubusercontent.com/'
        'niriel015/Painel-LolaHub/refs/heads/main/'
        'Lola-hub-ne-pai"))()'
    ),

    "saiki": (
        'loadstring(game:HttpGet('
        '"https://raw.githubusercontent.com/'
        'SaikiWithTheBanHammer/ScriptBlox/main/'
        'LifeIsDisasterIndeedLol"))()'
    ),

    "madara": (
        'loadstring(game:HttpGet('
        '"https://raw.githubusercontent.com/'
        'IsThisMe01/Project-Madara/refs/heads/main/'
        'mm22.lua"))()'
    ),

    "moondiety": (
        'loadstring(game:HttpGet('
        '"https://scriptblox.com/raw/'
        'Murder-Mystery-2-KEYLESS-InstaWin-AutoFarm-Kill-all-'
        'XRay-nd-more-by-Moondiety-48644"))()'
    ),

    "godmode": (
        'loadstring(game:HttpGet('
        '"https://pastefy.app/a2dAk154/raw"))()'
    ),

    "bf_min": (
        'loadstring(game:HttpGet('
        '"https://raw.githubusercontent.com/'
        'LuaCrack/Min/refs/heads/main/MinXt2Eng"))()'
    ),

    "bf_redz": (
        'local Settings = { JoinTeam = "Pirates", '
        'Translator = true }\n'
        'getgenv().BETA_VERSION = true\n'
        'loadstring(game:HttpGet('
        '"https://raw.githubusercontent.com/'
        'tlredz/Scripts/refs/heads/main/main.luau"))(Settings)'
    ),

    "bf_basement": (
        'loadstring(game:HttpGet('
        '"https://raw.githubusercontent.com/'
        'Cazzanos/The-basement/main/Basement%20hub", '
        'true))()'
    ),

    "bf_autofarm": (
        'loadstring(game:HttpGetAsync('
        '"https://raw.githubusercontent.com/'
        'indexeduu/BF-NewVer/refs/heads/main/V3New.lua"))()'
    ),

    "99_1": (
        'loadstring(game:HttpGet('
        '"https://api.luarmor.net/files/v3/loaders/'
        '705e9a93cc18214fb77ab95686a8dba9.lua"))()'
    ),

    "99_2": (
        'KEY - 111222HHH\n\n'
        'loadstring(game:HttpGet('
        '"https://raw.githubusercontent.com/'
        'caomod2077/Script/refs/heads/main/FoxnameHub.lua"))()'
    ),

    "99_3": (
        'loadstring(game:HttpGet('
        '"https://ntt-hub.xyz/api/repo?id1=main&id2=lua"))()'
    ),

    "egg_1": (
        'loadstring(game:HttpGet('
        '"https://raw.githubusercontent.com/'
        'sabscrip-arch/srver/refs/heads/main/Stealanegg"))()'
    ),

    "egg_2": (
        'loadstring(game:HttpGet('
        '"https://raw.githubusercontent.com/'
        'lennonxscripts/lennonhubv2/refs/heads/main/'
        'stealaneggv2"))()'
    ),

    "egg_3": (
        'loadstring(game:HttpGet('
        '"https://raw.githubusercontent.com/'
        'lennonxscripts/lennonhubv2/refs/heads/main/'
        'stealaneggv2"))()'
    ),
}


# =========================================================
# MAIN MENU
# =========================================================

def kb(user_id):
    user_id = str(user_id)

    status = "⭐ Премиум" if is_p(user_id) else "🆓 Бесплатно"

    sponsor_data = lsp()

    sponsor_badge = ""

    if user_id in sponsor_data:
        level = sponsor_data[user_id]["level"]

        if level == "gold":
            sponsor_badge = " 🌟"
        elif level == "bronze":
            sponsor_badge = " 🥉"

    subscription_badge = " ✅" if has_sub(user_id) else ""

    return types.InlineKeyboardMarkup(
        inline_keyboard=[
            [
                types.InlineKeyboardButton(
                    text="📜 Brookhaven",
                    callback_data="mbh",
                )
            ],
            [
                types.InlineKeyboardButton(
                    text="🎮 MM2",
                    callback_data="mmm",
                )
            ],
            [
                types.InlineKeyboardButton(
                    text="🍇 Blox Fruits",
                    callback_data="mbf",
                )
            ],
            [
                types.InlineKeyboardButton(
                    text="🌙 99 Ночей",
                    callback_data="m99",
                )
            ],
            [
                types.InlineKeyboardButton(
                    text="🥚 Steal an Egg",
                    callback_data="meg",
                )
            ],
            [
                types.InlineKeyboardButton(
                    text="🔍 Поиск",
                    callback_data="ms",
                )
            ],
            [
                types.InlineKeyboardButton(
                    text="📁 Мои фильтры",
                    callback_data="sf_menu",
                )
            ],
            [
                types.InlineKeyboardButton(
                    text="🎲 Рулетка (5⭐)",
                    callback_data="roul",
                )
            ],
            [
                types.InlineKeyboardButton(
                    text="🛒 Магазин",
                    callback_data="shop",
                )
            ],
            [
                types.InlineKeyboardButton(
                    text=f"💎 Подписка{subscription_badge}",
                    callback_data="sub_menu",
                )
            ],
            [
                types.InlineKeyboardButton(
                    text="🎁 Промокод",
                    callback_data="ep",
                )
            ],
            [
                types.InlineKeyboardButton(
                    text=f"💎 Спонсор{sponsor_badge}",
                    callback_data="dm",
                )
            ],
            [
                types.InlineKeyboardButton(
                    text=f"⭐ Премиум ({status})",
                    callback_data="bp",
                )
            ],
            [
                types.InlineKeyboardButton(
                    text="👥 Юзеры",
                    callback_data="su",
                )
            ],
            [
                types.InlineKeyboardButton(
                    text="💬 Соцсети",
                    url="https://t.me/+LBs19_JzpW0yNmZi",
                )
            ],
        ]
    )


# =========================================================
# START
# =========================================================

@dp.message(F.text == "/start")
async def start(m: types.Message, state: FSMContext):
    await state.clear()

    user_id = str(m.from_user.id)
    is_new = user_id not in users

    if is_new:
        users.add(user_id)
        ss(UF, users)

    text = "🔥 <b>Привет!</b>\n\n"

    if is_new:
        add_promo(user_id, "trial", 3, 3)

        text += (
            "🎁 <b>Ты новичок! Держи подарок:</b>\n"
            "Промокод на 3 дня рулетки в /mycodes\n\n"
        )

    await m.answer(
        text + "Выбери категорию:",
        reply_markup=kb(user_id),
    )


# =========================================================
# PREMIUM SUBSCRIPTION
# =========================================================

@dp.callback_query(F.data == "sub_menu")
async def sub_menu(cb: types.CallbackQuery):
    keyboard = types.InlineKeyboardMarkup(
        inline_keyboard=[
            [
                types.InlineKeyboardButton(
                    text=f"⭐ Купить за {SUB_PRICE} звёзд",
                    callback_data="premium_pay",
                )
            ],
            [
                types.InlineKeyboardButton(
                    text="❌ Отмена",
                    callback_data="premium_cancel",
                )
            ],
        ]
    )

    await cb.message.answer(
        f"💎 <b>Премиум-подписка</b>\n\n"
        f"Стоимость: ⭐ {SUB_PRICE}\n"
        "Хотите оплатить?",
        reply_markup=keyboard,
    )

    await cb.answer()


@dp.callback_query(F.data == "premium_cancel")
async def premium_cancel(cb: types.CallbackQuery):
    await cb.message.edit_text(
        "✅ Покупка отменена. Оплата не произведена."
    )

    await cb.answer()


@dp.callback_query(F.data == "premium_pay")
async def premium_pay(cb: types.CallbackQuery):
    user_id = str(cb.from_user.id)

    if has_sub(user_id):
        await cb.answer(
            "💎 Подписка уже активна!",
            show_alert=True,
        )
        return

    await bot.send_invoice(
        chat_id=cb.from_user.id,
        title="💎 Премиум-подписка",
        description="Расширенный поиск и функции премиума",
        payload="sub_access",
        provider_token="",
        currency="XTR",
        prices=[
            LabeledPrice(
                label="Премиум",
                amount=SUB_PRICE,
            )
        ],
    )

    await cb.answer("Счёт отправлен ⭐")


# =========================================================
# SAVED SEARCH FILTERS
# =========================================================

@dp.callback_query(F.data == "sf_menu")
async def sf_menu(cb: types.CallbackQuery):
    user_id = str(cb.from_user.id)
    filters = ld(SFF, 5)

    my_filters = {
        key: value
        for key, value in filters.items()
        if value[0] == user_id
    }

    buttons = []

    for key, value in my_filters.items():
        buttons.append(
            [
                types.InlineKeyboardButton(
                    text=f"🔍 {value[1]}",
                    callback_data=f"sf_use_{key}",
                )
            ]
        )

    buttons.append(
        [
            types.InlineKeyboardButton(
                text="➕ Сохранить новый фильтр",
                callback_data="sf_add",
            )
        ]
    )

    buttons.append(
        [
            types.InlineKeyboardButton(
                text="🔙 Меню",
                callback_data="mm",
            )
        ]
    )

    await cb.message.edit_text(
        "📁 <b>Мои фильтры поиска</b>",
        reply_markup=types.InlineKeyboardMarkup(
            inline_keyboard=buttons
        ),
    )

    await cb.answer()


@dp.callback_query(F.data == "sf_add")
async def sf_add(cb: types.CallbackQuery, state: FSMContext):
    await cb.message.edit_text(
        "Введи название для фильтра "
        "(например: 'ММ2 Автофарм'):"
    )

    await state.set_state(FS.wait_name)
    await cb.answer()


@dp.message(FS.wait_name)
async def sf_name(m: types.Message, state: FSMContext):
    name = (m.text or "").strip()

    if not name:
        await m.answer("Введи непустое название.")
        return

    await state.update_data(name=name)
    await m.answer("Теперь введи поисковый запрос:")
    await state.set_state(FS.wait_query)


@dp.message(FS.wait_query)
async def sf_query(m: types.Message, state: FSMContext):
    data = await state.get_data()

    name = data.get("name", "Мой фильтр")
    query = (m.text or "").strip()
    user_id = str(m.from_user.id)

    if not query:
        await m.answer("Поисковый запрос не может быть пустым.")
        return

    filters = ld(SFF, 5)
    key = gen()[:8]

    filters[key] = [
        user_id,
        name,
        query,
        "no",
    ]

    sd(SFF, filters)

    await state.clear()

    await m.answer(
        f"✅ Фильтр «{html.escape(name)}» сохранён!",
        reply_markup=kb(user_id),
    )


@dp.callback_query(F.data.startswith("sf_use_"))
async def sf_use(cb: types.CallbackQuery, state: FSMContext):
    key = cb.data[len("sf_use_"):]

    filters = ld(SFF, 5)
    user_id = str(cb.from_user.id)

    if key not in filters:
        await cb.answer("❌ Фильтр не найден.", show_alert=True)
        return

    if filters[key][0] != user_id:
        await cb.answer("❌ Это чужой фильтр.", show_alert=True)
        return

    query = filters[key][2]

    await cb.answer()
    await cb.message.answer(
        f"🔎 Запускаю поиск по фильтру: "
        f"{html.escape(query)}"
    )

    await state.update_data(query=query)
    await run_search(cb.message, state, user_id)


# =========================================================
# SEARCH
# =========================================================

@dp.callback_query(F.data == "ms")
async def ms(cb: types.CallbackQuery, state: FSMContext):
    user_id = str(cb.from_user.id)

    is_subscription = has_sub(user_id)

    limit = (
        20
        if is_subscription
        else PREM_L if has_sp(user_id)
        else FREE_L
    )

    await cb.message.edit_text(
        f"🔍 Поиск (до {limit} результатов):",
        reply_markup=types.InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    types.InlineKeyboardButton(
                        text="❌ Отмена",
                        callback_data="mm",
                    )
                ]
            ]
        ),
    )

    await state.set_state(SS.wait)
    await cb.answer()


@dp.message(SS.wait)
async def ps(m: types.Message, state: FSMContext):
    query = (m.text or "").strip().lower()

    if not query:
        await m.answer("Введи поисковый запрос.")
        return

    await state.update_data(query=query)

    try:
        await run_search(m, state, str(m.from_user.id))
    finally:
        await state.clear()


async def run_search(m, state: FSMContext, user_id):
    data = await state.get_data()
    query = data.get("query", "").strip()

    if not query:
        await m.answer("❌ Пустой поисковый запрос.")
        return

    is_subscription = has_sub(user_id)

    limit = (
        20
        if is_subscription
        else PREM_L if has_sp(user_id)
        else FREE_L
    )

    msg = await m.answer(
        f"🔎 Ищу: {html.escape(query)}..."
    )

    results = await s1(query)

    if "mm2" in query or "murder" in query:
        results.extend(await s2())
        results.extend(await s3())

    if is_subscription:
        results.extend(await s4())

    if not results:
        await msg.edit_text("❌ Ничего не найдено.")
        return

    unique = []
    seen = set()

    for item in results:
        title = item.get("title", "?")
        normalized = title.lower()

        if normalized in seen:
            continue

        seen.add(normalized)
        unique.append(item)

    text = f"🌐 Найдено: {len(unique)}\n\n"

    output = io.StringIO()
    writer = csv.writer(output)

    writer.writerow(["Title", "Game", "Script"])

    for index, item in enumerate(unique[:limit], 1):
        title = str(item.get("title", "?"))
        game_data = item.get("game") or {}
        game = str(game_data.get("name", "?"))
        script = str(item.get("script", ""))

        text += (
            f"<b>{index}. {html.escape(title)}</b>\n"
            f"🎮 {html.escape(game)}\n"
            f"<pre>{html.escape(script[:150])}"
            f"{'...' if len(script) > 150 else ''}</pre>\n\n"
        )

        writer.writerow([title, game, script])

    last_search[str(user_id)] = output.getvalue()

    buttons = []

    if unique:
        buttons.append(
            [
                types.InlineKeyboardButton(
                    text="📥 Экспорт в CSV",
                    callback_data="export_csv",
                )
            ]
        )

    buttons.append(
        [
            types.InlineKeyboardButton(
                text="🔙 Меню",
                callback_data="mm",
            )
        ]
    )

    # Telegram ограничивает длину одного сообщения.
    # Не отправляем текст, превышающий допустимый размер.
    if len(text) > 4000:
        text = text[:3900] + "\n\n…Список сокращён."

    await msg.edit_text(
        text,
        reply_markup=types.InlineKeyboardMarkup(
            inline_keyboard=buttons
        ),
    )


@dp.callback_query(F.data == "export_csv")
async def export_csv(cb: types.CallbackQuery):
    user_id = str(cb.from_user.id)

    if user_id not in last_search:
        await cb.answer("❌ Нет данных для экспорта.")
        return

    file = BufferedInputFile(
        last_search[user_id].encode("utf-8-sig"),
        filename="scripts.csv",
    )

    await bot.send_document(
        chat_id=cb.from_user.id,
        document=file,
        caption="Ваши результаты поиска в CSV",
    )

    await cb.answer()


# =========================================================
# SCRIPT BUTTONS
# =========================================================

@dp.callback_query(F.data.startswith("c_"))
async def c(cb: types.CallbackQuery):
    name = cb.data[2:]
    user_id = str(cb.from_user.id)

    if name == "frz":
        if not has_f(user_id):
            await cb.answer(
                "❄️ Функция платная!",
                show_alert=True,
            )

            markup = types.InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        types.InlineKeyboardButton(
                            text="⭐ Купить",
                            callback_data="bf",
                        )
                    ]
                ]
            )

            await bot.send_message(
                cb.from_user.id,
                "❄️ <b>Заморозка</b>\nСтоимость: 10⭐",
                reply_markup=markup,
            )
            return

        await cb.answer("Отправляю ✅")

        text = (
            "❄️ <b>Заморозка</b>\n\n"
            "<pre>"
            "loadstring(game:HttpGet("
            '"https://cdn.sourceb.in/bins/9MHwJQNJkm/0"))()'
            "</pre>\n"
            "<pre>"
            "loadstring(game:HttpGet("
            "'https://raw.githubusercontent.com/"
            "txnic255/MM2-FREEZE-TRADE-V5.5-NEWEST-GUI-SCRIPT-/"
            "refs/heads/main/SCRIPT%20V5.5%20GUI%20AND%20SCRIPT'"
            "))()"
            "</pre>"
        )

        await bot.send_message(cb.from_user.id, text)
        return

    code = SC.get(name)

    if not code:
        await cb.answer("❌ Скрипт не найден.", show_alert=True)
        return

    await cb.answer("Отправляю ✅")

    markup = types.InlineKeyboardMarkup(
        inline_keyboard=[
            [
                types.InlineKeyboardButton(
                    text="📋 Скопировать",
                    copy_text=types.CopyTextButton(text=code),
                )
            ]
        ]
    )

    await bot.send_message(
        cb.from_user.id,
        "✅ <b>Твой скрипт:</b>\n\n"
        f"<pre>{html.escape(code)}</pre>",
        reply_markup=markup,
    )


# =========================================================
# SPONSOR / DONATIONS
# =========================================================

@dp.callback_query(F.data == "dm")
async def dm(cb: types.CallbackQuery):
    buttons = [
        [
            types.InlineKeyboardButton(
                text=f"{amount}⭐",
                callback_data=f"d_{amount}",
            )
            for amount in [10, 25, 50]
        ],
        [
            types.InlineKeyboardButton(
                text=f"{amount}⭐",
                callback_data=f"d_{amount}",
            )
            for amount in [100, 250, 500]
        ],
        [
            types.InlineKeyboardButton(
                text="1000⭐",
                callback_data="d_1000",
            )
        ],
        [
            types.InlineKeyboardButton(
                text="✏️ Своя сумма",
                callback_data="dc",
            )
        ],
        [
            types.InlineKeyboardButton(
                text="🔙 Назад",
                callback_data="mm",
            )
        ],
    ]

    await cb.message.edit_text(
        "💎 <b>Стать спонсором</b>",
        reply_markup=types.InlineKeyboardMarkup(
            inline_keyboard=buttons
        ),
    )

    await cb.answer()


@dp.callback_query(F.data.startswith("d_"))
async def pd(cb: types.CallbackQuery):
    try:
        amount = int(cb.data.split("_", 1)[1])
    except (ValueError, IndexError):
        await cb.answer("❌ Неверная сумма.", show_alert=True)
        return

    if not 1 <= amount <= 1000:
        await cb.answer("❌ Сумма должна быть от 1 до 1000.")
        return

    await bot.send_invoice(
        chat_id=cb.from_user.id,
        title="Донат",
        description=f"{amount}⭐",
        payload=f"d_{amount}",
        provider_token="",
        currency="XTR",
        prices=[
            LabeledPrice(
                label="Донат",
                amount=amount,
            )
        ],
    )

    await cb.answer()


@dp.callback_query(F.data == "dc")
async def dc(cb: types.CallbackQuery, state: FSMContext):
    await cb.message.edit_text("💎 Введи сумму (1–1000):")
    await state.set_state(DS.wait)
    await cb.answer()


@dp.message(DS.wait)
async def pcd(m: types.Message, state: FSMContext):
    try:
        amount = int((m.text or "").strip())

        if not 1 <= amount <= 1000:
            raise ValueError

    except ValueError:
        await m.answer("❌ Введи число от 1 до 1000.")
        return

    await state.clear()

    await bot.send_invoice(
        chat_id=m.from_user.id,
        title="Донат",
        description=f"{amount}⭐",
        payload=f"d_{amount}",
        provider_token="",
        currency="XTR",
        prices=[
            LabeledPrice(
                label="Донат",
                amount=amount,
            )
        ],
    )


# =========================================================
# SHOP PROMOCODES
# =========================================================

def gs():
    items = []
    discounts = [5, 10, 15, 20, 30, 50]

    for _ in range(10):
        item_type = random.choice(
            ["discount", "trial3", "trial5"]
        )

        created = datetime.now().isoformat()

        if item_type == "discount":
            item = (
                f"{gen()}|discount_"
                f"{random.choice(discounts)}|3|no|"
                f"{created}|inf"
            )
        elif item_type == "trial3":
            item = f"{gen()}|trial3|7|no|{created}|inf"
        else:
            item = f"{gen()}|trial5|10|no|{created}|inf"

        items.append(item)

    with open(SF, "w", encoding="utf-8") as file:
        file.write("\n".join(items) + "\n")


def gsh():
    items = []

    if os.path.exists(SF):
        with open(SF, "r", encoding="utf-8") as file:
            for line in file:
                parts = line.rstrip("\n").split("|")

                if len(parts) == 6:
                    try:
                        price = int(parts[2])
                    except ValueError:
                        continue

                    items.append(
                        {
                            "code": parts[0],
                            "type": parts[1],
                            "price": price,
                            "bought": parts[3],
                            "created": parts[4],
                            "exp": parts[5],
                        }
                    )

    return items


def save_shop(items):
    with open(SF, "w", encoding="utf-8") as file:
        for item in items:
            file.write(
                f"{item['code']}|"
                f"{item['type']}|"
                f"{item['price']}|"
                f"{item['bought']}|"
                f"{item['created']}|"
                f"{item.get('exp', 'inf')}\n"
            )


@dp.callback_query(F.data == "shop")
async def shop(cb: types.CallbackQuery):
    user_id = str(cb.from_user.id)

    if not os.path.exists(SF):
        gs()

    items = gsh()
    buttons = []

    for item in items:
        if item["bought"] == "yes":
            continue

        if item["type"].startswith("discount"):
            title = (
                "💰 Скидка "
                f"{item['type'].split('_', 1)[1]}%"
            )
        elif item["type"] == "trial3":
            title = "⭐ Рулетка 3д"
        else:
            title = "⭐ Рулетка 5д"

        prefix = "👑 " if user_id == str(ADMIN_ID) else ""

        callback_data = (
            f"freebp_{item['code']}"
            if user_id == str(ADMIN_ID)
            else f"bp_{item['code']}"
        )

        buttons.append(
            [
                types.InlineKeyboardButton(
                    text=f"{prefix}{title} — {item['price']}⭐",
                    callback_data=callback_data,
                )
            ]
        )

    buttons.extend(
        [
            [
                types.InlineKeyboardButton(
                    text="🔄 Обновить",
                    callback_data="refresh_shop",
                )
            ],
            [
                types.InlineKeyboardButton(
                    text="🔙 Меню",
                    callback_data="mm",
                )
            ],
        ]
    )

    await cb.message.edit_text(
        "🛒 <b>Магазин</b>",
        reply_markup=types.InlineKeyboardMarkup(
            inline_keyboard=buttons
        ),
    )

    await cb.answer()


@dp.callback_query(F.data == "refresh_shop")
async def refresh_shop(cb: types.CallbackQuery):
    gs()
    await shop(cb)


@dp.callback_query(F.data.startswith("freebp_"))
async def freebp(cb: types.CallbackQuery):
    user_id = str(cb.from_user.id)

    if user_id != str(ADMIN_ID):
        await cb.answer("❌ Вы не админ!", show_alert=True)
        return

    code = cb.data[len("freebp_"):]

    items = gsh()

    item = next(
        (value for value in items if value["code"] == code),
        None,
    )

    if not item or item["bought"] == "yes":
        await cb.answer(
            "❌ Товар не найден или уже забран.",
            show_alert=True,
        )
        return

    item["bought"] = "yes"
    save_shop(items)

    if item["type"].startswith("discount"):
        promo_type = "discount"
        value = item["type"].split("_", 1)[1]
    else:
        promo_type = "trial"
        value = "3" if item["type"] == "trial3" else "5"

    promo = add_promo(user_id, promo_type, value, 3)

    if not promo:
        await cb.answer(
            "❌ Не удалось создать промокод.",
            show_alert=True,
        )
        return

    await cb.answer("✅ Забрано!", show_alert=True)

    await cb.message.edit_text(
        "👑 <b>Промокод забран!</b>\n"
        f"Код: <code>{promo}</code>",
        reply_markup=kb(user_id),
    )


@dp.callback_query(F.data.startswith("bp_"))
async def bp(cb: types.CallbackQuery):
    code = cb.data[len("bp_"):]

    items = gsh()

    item = next(
        (value for value in items if value["code"] == code),
        None,
    )

    if not item or item["bought"] == "yes":
        await cb.answer("❌ Уже продан.", show_alert=True)
        return

    await bot.send_invoice(
        chat_id=cb.from_user.id,
        title="Промокод",
        description=f"Код на {item['type']}",
        payload=f"p_{code}",
        provider_token="",
        currency="XTR",
        prices=[
            LabeledPrice(
                label="Код",
                amount=item["price"],
            )
        ],
    )

    await cb.answer()


# =========================================================
# REDEEM PROMOCODE
# =========================================================

@dp.callback_query(F.data == "ep")
async def ep(cb: types.CallbackQuery, state: FSMContext):
    await cb.message.edit_text(
        "🎁 Введи промокод:",
        reply_markup=types.InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    types.InlineKeyboardButton(
                        text="❌ Отмена",
                        callback_data="mm",
                    )
                ]
            ]
        ),
    )

    await state.set_state(PS.wait)
    await cb.answer()


@dp.message(PS.wait)
async def pp(m: types.Message, state: FSMContext):
    await state.clear()

    user_id = str(m.from_user.id)
    code = (m.text or "").strip().upper()

    promos = ld(PRF, 6)

    if code not in promos:
        await m.answer(
            "❌ Промокод не найден.",
            reply_markup=kb(user_id),
        )
        return

    promo_type, value, owner, used, expiration = promos[code]

    if used != "no":
        await m.answer(
            "❌ Этот промокод уже активирован.",
            reply_markup=kb(user_id),
        )
        return

    if owner == user_id:
        await m.answer(
            "❌ Нельзя активировать собственный промокод.",
            reply_markup=kb(user_id),
        )
        return

    if expiration != "inf":
        try:
            if datetime.fromisoformat(expiration) < datetime.now():
                await m.answer(
                    "❌ Срок действия истёк.",
                    reply_markup=kb(user_id),
                )
                return
        except ValueError:
            await m.answer("❌ Некорректная дата промокода.")
            return

    if promo_type == "discount":
        dis.add(f"{user_id}|{value}")
        ss(DF, dis)

        await m.answer(
            f"✅ Скидка {value}% активирована!",
            reply_markup=kb(user_id),
        )

    elif promo_type == "trial":
        roulette_data = ld(TF, 2)

        current_expiration = datetime.now()

        if user_id in roulette_data:
            try:
                current_expiration = max(
                    current_expiration,
                    datetime.fromisoformat(
                        roulette_data[user_id][0]
                    ),
                )
            except ValueError:
                pass

        roulette_data[user_id] = [
            (
                current_expiration
                + timedelta(days=int(value))
            ).isoformat()
        ]

        sd(TF, roulette_data)

        await m.answer(
            f"✅ Рулетка на {value} дней активирована!",
            reply_markup=kb(user_id),
        )

    else:
        await m.answer(
            "❌ Неизвестный тип промокода.",
            reply_markup=kb(user_id),
        )
        return

    promos[code] = [
        promo_type,
        value,
        owner,
        "yes",
        expiration,
    ]

    sd(PRF, promos)


# =========================================================
# ROULETTE
# =========================================================

@dp.callback_query(F.data == "roul")
async def roul(cb: types.CallbackQuery):
    user_id = str(cb.from_user.id)

    if not (
        user_id == str(ADMIN_ID)
        or user_id in ld(TF, 2)
    ):
        await bot.send_invoice(
            chat_id=cb.from_user.id,
            title="🎲 Рулетка",
            description="Скрипты за 5⭐",
            payload="roulette",
            provider_token="",
            currency="XTR",
            prices=[
                LabeledPrice(
                    label="Рулетка",
                    amount=ROLL_PRICE,
                )
            ],
        )

        await cb.answer("Счёт отправлен.")
        return

    await cb.answer()
    await give_roulette_prize(cb.message, user_id)


async def give_roulette_prize(m, user_id):
    msg = await m.answer("🔎 Ищу...")

    queries = [
        "Infinite Yield",
        "Dark Dex",
        "Nameless Admin",
        "Simple Spy",
    ]

    found = []
    random.shuffle(queries)

    for query in queries[:3]:
        try:
            results = await s1(query)

            if results:
                found.extend(results[:2])

        except Exception:
            logger.exception("Ошибка поиска для рулетки")

    if not found:
        found = [
            {
                "title": "Infinite Yield",
                "script": (
                    "loadstring(game:HttpGet("
                    "'https://raw.githubusercontent.com/"
                    "EdgeIY/infiniteyield/master/source'))()"
                ),
            }
        ]

    text = "🎰 <b>Твой выигрыш:</b>\n\n"

    for index, item in enumerate(found[:5], 1):
        title = html.escape(str(item.get("title", "?")))
        script = html.escape(str(item.get("script", "")))

        text += (
            f"<b>{index}. {title}</b>\n"
            f"<pre>{script}</pre>\n\n"
        )

    if len(text) > 4000:
        text = text[:3900] + "\n\n…"

    await msg.edit_text(
        text,
        reply_markup=kb(user_id),
    )


# =========================================================
# PREMIUM AND FREEZE PURCHASES
# =========================================================

@dp.callback_query(F.data == "bp")
async def bpr(cb: types.CallbackQuery):
    user_id = str(cb.from_user.id)

    if is_p(user_id):
        await cb.answer("✅ Премиум уже есть!", show_alert=True)
        return

    max_discount = 0

    for discount in dis:
        if discount.startswith(f"{user_id}|"):
            try:
                amount = int(discount.split("|", 1)[1])
                max_discount = max(max_discount, amount)
            except (ValueError, IndexError):
                continue

    price = max(
        1,
        int(P_PRICE * (1 - max_discount / 100)),
    )

    await bot.send_invoice(
        chat_id=cb.from_user.id,
        title="⭐ Премиум",
        description=(
            f"Скидка {max_discount}%"
            if max_discount > 0
            else "Премиум-доступ"
        ),
        payload="prem",
        provider_token="",
        currency="XTR",
        prices=[
            LabeledPrice(
                label="Премиум",
                amount=price,
            )
        ],
    )

    await cb.answer()


@dp.callback_query(F.data == "bf")
async def bf(cb: types.CallbackQuery):
    if has_f(cb.from_user.id):
        await cb.answer("✅ Уже есть!", show_alert=True)
        return

    await bot.send_invoice(
        chat_id=cb.from_user.id,
        title="❄️ Заморозка",
        description="MM2",
        payload="frz",
        provider_token="",
        currency="XTR",
        prices=[
            LabeledPrice(
                label="Заморозка",
                amount=F_PRICE,
            )
        ],
    )

    await cb.answer()


# =========================================================
# PAYMENT VALIDATION
# =========================================================

def expected_premium_price(user_id):
    max_discount = 0

    for discount in dis:
        if discount.startswith(f"{user_id}|"):
            try:
                amount = int(discount.split("|", 1)[1])
                max_discount = max(max_discount, amount)
            except (ValueError, IndexError):
                continue

    return max(
        1,
        int(P_PRICE * (1 - max_discount / 100)),
    )


def expected_payment(payload, user_id):
    if payload == "sub_access":
        return SUB_PRICE

    if payload == "prem":
        return expected_premium_price(str(user_id))

    if payload == "frz":
        return F_PRICE

    if payload == "roulette":
        return ROLL_PRICE

    if payload.startswith("d_"):
        try:
            amount = int(payload.split("_", 1)[1])

            if 1 <= amount <= 1000:
                return amount
        except ValueError:
            return None

    if payload.startswith("p_"):
        code = payload[len("p_"):]

        item = next(
            (
                value
                for value in gsh()
                if value["code"] == code
            ),
            None,
        )

        if item and item["bought"] != "yes":
            return item["price"]

    return None


@dp.pre_checkout_query()
async def pcq(q: PreCheckoutQuery):
    payload = q.invoice_payload
    user_id = str(q.from_user.id)

    amount = expected_payment(payload, user_id)

    if amount is None:
        await q.answer(
            ok=False,
            error_message="Неизвестный или недоступный платёж.",
        )
        return

    if q.currency != "XTR" or q.total_amount != amount:
        await q.answer(
            ok=False,
            error_message="Неверная сумма платежа.",
        )
        return

    if payload == "sub_access" and has_sub(user_id):
        await q.answer(
            ok=False,
            error_message="Подписка уже активирована.",
        )
        return

    if payload == "prem" and is_p(user_id):
        await q.answer(
            ok=False,
            error_message="Премиум уже активен.",
        )
        return

    if payload == "frz" and has_f(user_id):
        await q.answer(
            ok=False,
            error_message="Доступ уже есть.",
        )
        return

    await q.answer(ok=True)


# =========================================================
# SUCCESSFUL PAYMENTS
# =========================================================

@dp.message(F.successful_payment)
async def sp(m: types.Message):
    payment = m.successful_payment

    user_id = str(m.from_user.id)
    payload = payment.invoice_payload

    # Дополнительная проверка валюты и суммы
    amount = expected_payment(payload, user_id)

    if (
        payment.currency != "XTR"
        or amount is None
        or payment.total_amount != amount
    ):
        logger.warning(
            "Некорректный успешный платёж: user=%s payload=%s",
            user_id,
            payload,
        )

        await m.answer(
            "⚠️ Не удалось автоматически подтвердить покупку. "
            "Обратись к администратору."
        )
        return

    if payload == "prem":
        prem.add(user_id)
        ss(PF, prem)

        dis_copy = set(dis)

        for discount in list(dis_copy):
            if discount.startswith(f"{user_id}|"):
                dis_copy.remove(discount)

        dis.clear()
        dis.update(dis_copy)
        ss(DF, dis)

        await m.answer(
            "⭐ Спасибо за покупку Премиума!",
            reply_markup=kb(user_id),
        )

    elif payload == "frz":
        frz.add(user_id)
        ss(FF, frz)

        await m.answer(
            "❄️ Заморозка активирована!",
            reply_markup=kb(user_id),
        )

    elif payload == "sub_access":
        subscriptions = ld(SUBF, 2)

        if user_id not in subscriptions:
            subscriptions[user_id] = [
                datetime.now().isoformat()
            ]

            sd(SUBF, subscriptions)

        await m.answer(
            "🎉 <b>Оплата прошла успешно!</b>\n\n"
            "💎 Подписка активирована.",
            reply_markup=kb(user_id),
        )

    elif payload == "roulette":
        await give_roulette_prize(m, user_id)

    elif payload.startswith("d_"):
        donation_amount = int(payload.split("_", 1)[1])

        sponsor_data = lsp()

        if donation_amount >= 25:
            level = "gold"
        elif 5 <= donation_amount <= 10:
            level = "bronze"
        else:
            level = "none"

        if level != "none":
            sponsor_data[user_id] = {
                "level": level,
                "last_claimed": "2000-01-01T00:00:00",
            }

            ssp(sponsor_data)

            await m.answer(
                f"💎 Спасибо за {donation_amount}⭐!\n"
                f"🌟 Статус: {level.upper()}",
                reply_markup=kb(user_id),
            )
        else:
            await m.answer(
                f"💎 Спасибо за {donation_amount}⭐!",
                reply_markup=kb(user_id),
            )

    elif payload.startswith("p_"):
        code = payload[len("p_"):]

        items = gsh()

        item = next(
            (
                value
                for value in items
                if value["code"] == code
            ),
            None,
        )

        if not item or item["bought"] == "yes":
            await m.answer(
                "⚠️ Товар уже куплен или недоступен. "
                "Обратись к администратору."
            )
            return

        item["bought"] = "yes"
        save_shop(items)

        if item["type"].startswith("discount"):
            promo_type = "discount"
            value = item["type"].split("_", 1)[1]
        else:
            promo_type = "trial"
            value = (
                "3"
                if item["type"] == "trial3"
                else "5"
            )

        promo = add_promo(
            user_id,
            promo_type,
            value,
            3,
        )

        if promo:
            await m.answer(
                "✅ Покупка прошла успешно!\n"
                f"Код: <code>{promo}</code>",
                reply_markup=kb(user_id),
            )
        else:
            await m.answer(
                "⚠️ Платёж получен, но промокод не создан. "
                "Обратись к администратору."
            )


# =========================================================
# SCRIPT SEARCH SOURCES
# =========================================================

async def s1(query):
    url = "https://scriptblox.com/api/script/search"

    try:
        timeout = aiohttp.ClientTimeout(total=10)

        async with aiohttp.ClientSession(
            timeout=timeout
        ) as session:
            async with session.get(
                url,
                params={
                    "q": query,
                    "mode": "free",
                    "key": 0,
                    "max": 20,
                    "strict": "true",
                },
                headers={"User-Agent": "Mozilla/5.0"},
            ) as response:

                if response.status != 200:
                    logger.warning(
                        "ScriptBlox вернул HTTP %s",
                        response.status,
                    )
                    return []

                data = await response.json()

                return (
                    data.get("result", {}).get("scripts", [])
                )

    except (
        aiohttp.ClientError,
        asyncio.TimeoutError,
        ValueError,
    ):
        logger.exception("Ошибка запроса ScriptBlox")
        return []


async def s2():
    url = (
        "https://cheater.fun/"
        "hacks_roblox/7931-murder-mystery-2-scripts.html"
    )

    try:
        timeout = aiohttp.ClientTimeout(total=10)

        async with aiohttp.ClientSession(
            timeout=timeout
        ) as session:
            async with session.get(
                url,
                headers={"User-Agent": "Mozilla/5.0"},
            ) as response:

                if response.status != 200:
                    return []

                page = await response.text()

        matches = re.findall(
            r'###\s*\*(.*?)\n.*?'
            r'loadstring\(game:HttpGet\("([^"]+)"\)\)\(\)',
            page,
            re.DOTALL,
        )

        return [
            {
                "title": title.strip(),
                "script": (
                    f'loadstring(game:HttpGet("{script_url}"))()'
                ),
                "game": {"name": "MM2"},
            }
            for title, script_url in matches
        ]

    except (
        aiohttp.ClientError,
        asyncio.TimeoutError,
        ValueError,
    ):
        logger.exception("Ошибка источника s2")
        return []


async def s3():
    url = (
        "https://bo3.gg/games/articles/"
        "murder-mystery-2-scripts"
    )

    try:
        timeout = aiohttp.ClientTimeout(total=10)

        async with aiohttp.ClientSession(
            timeout=timeout
        ) as session:
            async with session.get(
                url,
                headers={"User-Agent": "Mozilla/5.0"},
            ) as response:

                if response.status != 200:
                    return []

                page = await response.text()

        matches = re.findall(
            r'([^\n<]{5,60}?)\s*'
            r'loadstring\(game:HttpGet\(["\']'
            r'([^"\']+)["\']\)\)\(\)',
            page,
            re.DOTALL,
        )

        return [
            {
                "title": title.strip(),
                "script": (
                    f'loadstring(game:HttpGet("{script_url}"))()'
                ),
                "game": {"name": "MM2"},
            }
            for title, script_url in matches
        ]

    except (
        aiohttp.ClientError,
        asyncio.TimeoutError,
        ValueError,
    ):
        logger.exception("Ошибка источника s3")
        return []


async def s4():
    url = "https://deltascripts.org/"

    try:
        timeout = aiohttp.ClientTimeout(total=10)

        async with aiohttp.ClientSession(
            timeout=timeout
        ) as session:
            async with session.get(
                url,
                headers={"User-Agent": "Mozilla/5.0"},
            ) as response:

                if response.status != 200:
                    return []

                page = await response.text()

        titles = re.findall(
            r"<h2[^>]*>(.*?)</h2>",
            page,
            re.IGNORECASE | re.DOTALL,
        )

        return [
            {
                "title": re.sub(
                    r"<[^>]+>",
                    "",
                    title,
                ).strip(),
                "script": (
                    "loadstring(game:HttpGet("
                    "'https://deltascripts.org/'))()"
                ),
                "game": {"name": "Delta"},
            }
            for title in titles[:5]
        ]

    except (
        aiohttp.ClientError,
        asyncio.TimeoutError,
        ValueError,
    ):
        logger.exception("Ошибка источника s4")
        return []


# =========================================================
# GAME CATEGORY MENUS
# =========================================================

@dp.callback_query(F.data == "mbh")
async def mbh(cb: types.CallbackQuery):
    buttons = [
        [
            types.InlineKeyboardButton(
                text=title,
                callback_data=data,
            )
        ]
        for title, data in {
            "🔥 Redz": "c_redz",
            "🚀 Lord": "c_lord",
            "🌐 LOLA": "c_lola",
            "🎧 Saiki": "c_saiki",
        }.items()
    ]

    buttons.append(
        [
            types.InlineKeyboardButton(
                text="🔙 Назад",
                callback_data="mm",
            )
        ]
    )

    await cb.message.edit_text(
        "📜 Brookhaven:",
        reply_markup=types.InlineKeyboardMarkup(
            inline_keyboard=buttons
        ),
    )

    await cb.answer()


@dp.callback_query(F.data == "mmm")
async def mmm(cb: types.CallbackQuery):
    buttons = [
        [
            types.InlineKeyboardButton(
                text=title,
                callback_data=data,
            )
        ]
        for title, data in {
            "🥷 Madara": "c_madara",
            "🔪 Moondiety": "c_moondiety",
            "🛡️ God": "c_godmode",
            "❄️ Заморозка": "c_frz",
        }.items()
    ]

    buttons.append(
        [
            types.InlineKeyboardButton(
                text="🔙 Назад",
                callback_data="mm",
            )
        ]
    )

    await cb.message.edit_text(
        "🎮 MM2:",
        reply_markup=types.InlineKeyboardMarkup(
            inline_keyboard=buttons
        ),
    )

    await cb.answer()


@dp.callback_query(F.data == "mbf")
async def mbf(cb: types.CallbackQuery):
    buttons = [
        [
            types.InlineKeyboardButton(
                text=title,
                callback_data=data,
            )
        ]
        for title, data in {
            "🎮 Min": "c_bf_min",
            "🚀 Redz B": "c_bf_redz",
            "🏠 Base": "c_bf_basement",
            "⚡ Farm": "c_bf_autofarm",
        }.items()
    ]

    buttons.append(
        [
            types.InlineKeyboardButton(
                text="🔙 Назад",
                callback_data="mm",
            )
        ]
    )

    await cb.message.edit_text(
        "🍇 Blox Fruits:",
        reply_markup=types.InlineKeyboardMarkup(
            inline_keyboard=buttons
        ),
    )

    await cb.answer()


@dp.callback_query(F.data == "m99")
async def m99(cb: types.CallbackQuery):
    buttons = [
        [
            types.InlineKeyboardButton(
                text=title,
                callback_data=data,
            )
        ]
        for title, data in {
            "📜 1": "c_99_1",
            "📜 2 (KEY)": "c_99_2",
            "📜 3": "c_99_3",
        }.items()
    ]

    buttons.append(
        [
            types.InlineKeyboardButton(
                text="🔙 Назад",
                callback_data="mm",
            )
        ]
    )

    await cb.message.edit_text(
        "🌙 99 Ночей:",
        reply_markup=types.InlineKeyboardMarkup(
            inline_keyboard=buttons
        ),
    )

    await cb.answer()


@dp.callback_query(F.data == "meg")
async def meg(cb: types.CallbackQuery):
    buttons = [
        [
            types.InlineKeyboardButton(
                text=title,
                callback_data=data,
            )
        ]
        for title, data in {
            "📜 Sabs": "c_egg_1",
            "🎧 Lennon V2": "c_egg_2",
            "🥚 Lennon Auto": "c_egg_3",
        }.items()
    ]

    buttons.append(
        [
            types.InlineKeyboardButton(
                text="🔙 Назад",
                callback_data="mm",
            )
        ]
    )

    await cb.message.edit_text(
        "🥚 Steal Egg:",
        reply_markup=types.InlineKeyboardMarkup(
            inline_keyboard=buttons
        ),
    )

    await cb.answer()


# =========================================================
# BACK TO MENU
# =========================================================

@dp.callback_query(F.data == "mm")
async def mm(cb: types.CallbackQuery, state: FSMContext):
    await state.clear()

    await cb.message.edit_text(
        "🔥 Выбери категорию:",
        reply_markup=kb(cb.from_user.id),
    )

    await cb.answer()


# =========================================================
# USER STATISTICS
# =========================================================

@dp.callback_query(F.data == "su")
async def su(cb: types.CallbackQuery):
    await cb.answer(
        f"👥 Всего пользователей: {len(users)}\n"
        f"⭐ Премиум: {len(prem)}",
        show_alert=True,
    )


# =========================================================
# RENDER WEB SERVER
# =========================================================

async def health(request):
    return web.Response(text="OK")


async def on_startup(app):
    render_url = os.getenv("RENDER_EXTERNAL_URL")

    if not render_url:
        render_url = (
            "https://telegram-server-bot-b5v3.onrender.com"
        )

    webhook_url = render_url.rstrip("/") + "/webhook"

    await bot.set_webhook(webhook_url)

    logger.info("Webhook установлен: %s", webhook_url)


async def on_shutdown(app):
    await bot.delete_webhook()
    await bot.session.close()


def main():
    app = web.Application()

    from aiogram.webhook.aiohttp_server import (
        SimpleRequestHandler,
    )

    webhook_handler = SimpleRequestHandler(
        dispatcher=dp,
        bot=bot,
    )

    webhook_handler.register(
        app,
        path="/webhook",
    )

    app.router.add_get("/", health)
    app.router.add_get("/health", health)

    app.on_startup.append(on_startup)
    app.on_shutdown.append(on_shutdown)

    port = int(os.getenv("PORT", "8080"))

    web.run_app(
        app,
        host="0.0.0.0",
        port=port,
    )


if __name__ == "__main__":
    main()
