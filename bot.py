import os
import asyncio
import re
import random
import string
from datetime import datetime, timedelta, date
import aiohttp
from aiohttp import web
from aiogram import Bot, Dispatcher, F, types
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import LabeledPrice, PreCheckoutQuery

TOKEN = os.getenv("BOT_TOKEN")

PREMIUM_PRICE_STARS = 30
FREEZE_PRICE_STARS = 10
FREE_LIMIT = 5
PREMIUM_LIMIT = 15
STREAK_DAYS = 3

# ⚠️ ВСТАВЬ СВОЙ ID из @userinfobot
ADMIN_ID = 8996403397

bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
dp = Dispatcher(storage=MemoryStorage())

# --- Файлы ---
USERS_FILE = "users.txt"
PREMIUM_FILE = "premium.txt"
FREEZE_FILE = "freeze_buyers.txt"
STREAK_FILE = "streaks.txt"
PROMO_FILE = "promocodes.txt"
TRIAL_FILE = "trial_premium.txt"
DISCOUNT_FILE = "discount_users.txt"


def load_set(filename):
    if os.path.exists(filename):
        with open(filename) as f:
            return set(line.strip() for line in f if line.strip())
    return set()

def save_set(filename, data):
    with open(filename, "w") as f:
        for item in data:
            f.write(f"{item}\n")

def load_streaks():
    data = {}
    if os.path.exists(STREAK_FILE):
        with open(STREAK_FILE) as f:
            for line in f:
                p = line.strip().split("|")
                if len(p) == 3:
                    data[p[0]] = {"streak": int(p[1]), "last": p[2]}
    return data

def save_streaks(data):
    with open(STREAK_FILE, "w") as f:
        for uid, d in data.items():
            f.write(f"{uid}|{d['streak']}|{d['last']}\n")

def load_promos():
    data = {}
    if os.path.exists(PROMO_FILE):
        with open(PROMO_FILE) as f:
            for line in f:
                p = line.strip().split("|")
                if len(p) == 4:
                    data[p[0]] = {"type": p[1], "value": p[2], "used_by": p[3]}
    return data

def save_promos(data):
    with open(PROMO_FILE, "w") as f:
        for code, info in data.items():
            f.write(f"{code}|{info['type']}|{info['value']}|{info['used_by']}\n")

def load_trials():
    data = {}
    if os.path.exists(TRIAL_FILE):
        with open(TRIAL_FILE) as f:
            for line in f:
                p = line.strip().split("|")
                if len(p) == 2:
                    data[p[0]] = p[1]
    return data

def save_trials(data):
    with open(TRIAL_FILE, "w") as f:
        for uid, exp in data.items():
            f.write(f"{uid}|{exp}\n")


users = load_set(USERS_FILE)
premium_users = load_set(PREMIUM_FILE)
freeze_buyers = load_set(FREEZE_FILE)
discount_users = load_set(DISCOUNT_FILE)


def is_premium(user_id: int) -> bool:
    uid = str(user_id)
    if uid == str(ADMIN_ID):
        return True
    if uid in premium_users:
        return True
    trials = load_trials()
    if uid in trials:
        try:
            if datetime.fromisoformat(trials[uid]) > datetime.now():
                return True
        except Exception:
            pass
    return False


def has_freeze(user_id: int) -> bool:
    uid = str(user_id)
    if uid == str(ADMIN_ID) or uid in premium_users or uid in freeze_buyers:
        return True
    return False


def generate_promo_code():
    return "STREAK-" + "".join(random.choices(string.ascii_uppercase + string.digits, k=6))


def update_streak(user_id: int):
    """Обновляет streak. Возвращает (streak, promo_or_none)."""
    uid = str(user_id)
    today = date.today().isoformat()
    yesterday = (date.today() - timedelta(days=1)).isoformat()

    streaks = load_streaks()
    if uid not in streaks:
        streaks[uid] = {"streak": 1, "last": today}
        save_streaks(streaks)
        return 1, None

    last = streaks[uid]["last"]
    if last == today:
        return streaks[uid]["streak"], None
    elif last == yesterday:
        streaks[uid]["streak"] += 1
    else:
        streaks[uid]["streak"] = 1

    streaks[uid]["last"] = today
    current = streaks[uid]["streak"]

    if current >= STREAK_DAYS:
        # Генерируем промокод
        promos = load_promos()
        code = generate_promo_code()
        while code in promos:
            code = generate_promo_code()

        promo_type = random.choice(["discount", "trial"])
        if promo_type == "discount":
            promos[code] = {"type": "discount", "value": "50", "used_by": ""}
        else:
            promos[code] = {"type": "trial", "value": "3", "used_by": ""}
        save_promos(promos)

        streaks[uid]["streak"] = 0
        save_streaks(streaks)
        return 0, code

    save_streaks(streaks)
    return current, None


class SearchStates(StatesGroup):
    waiting_for_query = State()

class PromoStates(StatesGroup):
    waiting_for_code = State()


GAMES_INDEX = {
    "brookhaven":  {"name": "📜 Brookhaven", "menu": "menu_brookhaven"},
    "брукхейвен":  {"name": "📜 Brookhaven", "menu": "menu_brookhaven"},
    "mm2":         {"name": "🎮 MM2", "menu": "menu_mm2"},
    "мурдер":      {"name": "🎮 MM2", "menu": "menu_mm2"},
    "blox":        {"name": "🍇 Blox Fruits", "menu": "menu_bloxfruits"},
    "блокс":       {"name": "🍇 Blox Fruits", "menu": "menu_bloxfruits"},
    "99":          {"name": "🌙 99 Ночей", "menu": "menu_99nights"},
    "ночей":       {"name": "🌙 99 Ночей", "menu": "menu_99nights"},
    "steal":       {"name": "🥚 Steal an Egg", "menu": "menu_stealanegg"},
    "egg":         {"name": "🥚 Steal an Egg", "menu": "menu_stealanegg"},
    "стил":        {"name": "🥚 Steal an Egg", "menu": "menu_stealanegg"},
    "яйц":         {"name": "🥚 Steal an Egg", "menu": "menu_stealanegg"},
}

SEARCH_INDEX = {
    "redz": "🔥 Redz9999 2026", "lord": "🚀 Lord-Kaiser",
    "lola": "🌐 LOLA HUB", "saiki": "🎧 Saiki Music",
    "madara": "🥷 Madara", "moondiety": "🔪 Moondiety",
    "godmode": "🛡️ God mode", "lennon": "🎧 Lennon Hub V2",
}

SCRIPTS_CODES = {
    "redz":  "<pre>loadstring(game:HttpGet('https://pastebin.com/raw/1r7cEW7G'))()</pre>",
    "lord":  "<pre>loadstring(game:HttpGet(\"https://raw.githubusercontent.com/SUPREMEAURA350/KAISER-VERSION-2-/refs/heads/main/Kaiserspam\"))()</pre>",
    "lola":  "<pre>loadstring(game:HttpGet(\"https://raw.githubusercontent.com/niriel015/Painel-LolaHub/refs/heads/main/Lola-hub-ne-pai\"))()</pre>",
    "saiki": "<pre>loadstring(game:HttpGet(\"https://raw.githubusercontent.com/SaikiWithTheBanHammer/ScriptBlox/main/LifeIsDisasterIndeedLol\"))()</pre>",
    "madara": "<pre>loadstring(game:HttpGet(\"https://raw.githubusercontent.com/IsThisMe01/Project-Madara/refs/heads/main/mm22.lua\"))()</pre>",
    "moondiety": "<pre>loadstring(game:HttpGet(\"https://scriptblox.com/raw/Murder-Mystery-2-KEYLESS-InstaWin-AutoFarm-Kill-all-XRay-nd-more-by-Moondiety-48644\"))()</pre>",
    "godmode": "<pre>loadstring(game:HttpGet(\"https://pastefy.app/a2dAk154/raw\"))()</pre>",
    "bf_min": "<pre>loadstring(game:HttpGet(\"https://raw.githubusercontent.com/LuaCrack/Min/refs/heads/main/MinXt2Eng\"))()</pre>",
    "bf_redz": "<pre>local Settings = {\n    JoinTeam = \"Pirates\";\n    Translator = true;\n}\ngetgenv().BETA_VERSION = true\nloadstring(game:HttpGet(\"https://raw.githubusercontent.com/tlredz/Scripts/refs/heads/main/main.luau\"))(Settings)</pre>",
    "bf_basement": "<pre>loadstring(game:HttpGet(\"https://raw.githubusercontent.com/Cazzanos/The-basement/main/Basement%20hub\", true))()</pre>",
    "bf_autofarm": "<pre>loadstring(game:HttpGetAsync(\"https://raw.githubusercontent.com/indexeduu/BF-NewVer/refs/heads/main/V3New.lua\"))()</pre>",
    "99_1": "<pre>loadstring(game:HttpGet(\"https://api.luarmor.net/files/v3/loaders/705e9a93cc18214fb77ab95686a8dba9.lua\"))()</pre>",
    "99_2": "<pre>KEY - 111222HHH\n\nloadstring(game:HttpGet(\"https://raw.githubusercontent.com/caomod2077/Script/refs/heads/main/FoxnameHub.lua\"))()</pre>",
    "99_3": "<pre>loadstring(game:HttpGet(\"https://ntt-hub.xyz/api/repo?id1=main&id2=lua\"))()</pre>",
    "egg_1": "<pre>loadstring(game:HttpGet(\"https://raw.githubusercontent.com/sabscrip-arch/srver/refs/heads/main/Stealanegg\"))()</pre>",
    "egg_2": "<pre>loadstring(game:HttpGet(\"https://raw.githubusercontent.com/lennonxscripts/lennonhubv2/refs/heads/main/stealaneggv2\"))()</pre>",
    "egg_3": "<pre>loadstring(game:HttpGet(\"https://raw.githubusercontent.com/lennonxscripts/lennonhubv2/refs/heads/main/stealaneggv2\"))()</pre>",
}


def main_menu_kb():
    return types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="📜 Script Brookhaven Delta", callback_data="menu_brookhaven")],
        [types.InlineKeyboardButton(text="🎮 MM2", callback_data="menu_mm2")],
        [types.InlineKeyboardButton(text="🍇 Blox Fruits", callback_data="menu_bloxfruits")],
        [types.InlineKeyboardButton(text="🌙 99 Ночей", callback_data="menu_99nights")],
        [types.InlineKeyboardButton(text="🥚 Steal an Egg", callback_data="menu_stealanegg")],
        [types.InlineKeyboardButton(text="🔍 Поиск", callback_data="menu_search")],
        [types.InlineKeyboardButton(text="🎁 Промокод", callback_data="enter_promo")],
        [types.InlineKeyboardButton(text="⭐ Премиум", callback_data="buy_premium")],
        [types.InlineKeyboardButton(text="👥 Пользователи", callback_data="show_users")],
        [types.InlineKeyboardButton(text="💬 Сообщество", url="https://t.me/+LBs19_JzpW0yNmZi")],
    ])


@dp.message(F.text == "/start")
async def start(message: types.Message, state: FSMContext):
    await state.clear()
    uid = message.from_user.id
    if str(uid) not in users:
        users.add(str(uid))
        save_set(USERS_FILE, users)

    streak, promo = update_streak(uid)

    status = "⭐ Премиум" if is_premium(uid) else "🆓 Бесплатно"

    text = f"🔥 <b>Привет!</b>\n\n"
    text += f"📊 Статус: <b>{status}</b>\n"
    text += f"🔥 Streak: <b>{streak}/{STREAK_DAYS}</b> дней\n"

    if promo:
        text += f"\n🎉 <b>Ты заработал промокод!</b>\n"
        text += f"Код: <code>{promo}</code>\n"
        text += f"Активируй его кнопкой 🎁 Промокод!"
    else:
        left = STREAK_DAYS - streak
        text += f"До следующего промокода: <b>{left}</b> дн.\n"

    text += f"\n🎁 Заходи каждый день — получай промокоды!"

    await message.answer(text, reply_markup=main_menu_kb())


# ============ ПРОМОКОДЫ ============
@dp.callback_query(F.data == "enter_promo")
async def enter_promo(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.edit_text(
        "🎁 <b>Введи промокод</b>\n\n"
        "Отправь код сообщением, например: <code>STREAK-ABC123</code>",
        reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[
            [types.InlineKeyboardButton(text="❌ Отмена", callback_data="menu_main")]
        ]),
    )
    await state.set_state(PromoStates.waiting_for_code)


@dp.message(PromoStates.waiting_for_code)
async def process_promo(message: types.Message, state: FSMContext):
    await state.clear()
    uid = str(message.from_user.id)
    code = message.text.strip().upper()

    promos = load_promos()

    if code not in promos:
        await message.answer("❌ Промокод не найден.", reply_markup=main_menu_kb())
        return

    promo = promos[code]
    if promo["used_by"]:
        await message.answer("❌ Этот промокод уже использован.", reply_markup=main_menu_kb())
        return

    if promo["type"] == "discount":
        discount_users.add(uid)
        save_set(DISCOUNT_FILE, discount_users)
        await message.answer(
            "✅ <b>Промокод активирован!</b>\n\n"
            "💰 Скидка <b>50%</b> на Премиум.\n"
            f"Цена: <s>{PREMIUM_PRICE_STARS}⭐</s> → <b>{PREMIUM_PRICE_STARS // 2}⭐</b>\n\n"
            "Действует на следующую покупку.",
            reply_markup=main_menu_kb(),
        )
    elif promo["type"] == "trial":
        days = int(promo["value"])
        expires = (datetime.now() + timedelta(days=days)).isoformat()
        trials = load_trials()
        trials[uid] = expires
        save_trials(trials)
        await message.answer(
            f"✅ <b>Промокод активирован!</b>\n\n"
            f"⭐ Премиум бесплатно на <b>{days} дня</b>!\n"
            f"Действует до: <code>{expires[:10]}</code>",
            reply_markup=main_menu_kb(),
        )

    promo["used_by"] = uid
    promos[code] = promo
    save_promos(promos)


# ============ ПОКУПКА ПРЕМИУМА ============
@dp.callback_query(F.data == "buy_premium")
async def buy_premium(callback: types.CallbackQuery):
    uid = callback.from_user.id
    if is_premium(uid):
        await callback.answer("✅ У тебя уже есть Премиум!", show_alert=True)
        return

    price = PREMIUM_PRICE_STARS
    if str(uid) in discount_users:
        price = PREMIUM_PRICE_STARS // 2

    await bot.send_invoice(
        chat_id=uid,
        title="⭐ Премиум доступ",
        description=f"Поиск выдаёт {PREMIUM_LIMIT} скриптов вместо {FREE_LIMIT}.",
        payload="premium_access",
        provider_token="",
        currency="XTR",
        prices=[LabeledPrice(label="Премиум", amount=price)],
    )
    await callback.answer()


@dp.callback_query(F.data == "buy_freeze")
async def buy_freeze(callback: types.CallbackQuery):
    uid = callback.from_user.id
    if has_freeze(uid):
        await callback.answer("✅ У тебя уже есть Заморозка!", show_alert=True)
        return
    await bot.send_invoice(
        chat_id=uid,
        title="❄️ Заморозка трейда (MM2)",
        description=f"Доступ за {FREEZE_PRICE_STARS} звёзд.",
        payload="freeze_access",
        provider_token="",
        currency="XTR",
        prices=[LabeledPrice(label="Заморозка", amount=FREEZE_PRICE_STARS)],
    )
    await callback.answer()


@dp.pre_checkout_query()
async def process_pre_checkout(q: PreCheckoutQuery):
    await bot.answer_pre_checkout_query(q.id, ok=True)


@dp.message(F.successful_payment)
async def successful_payment(message: types.Message):
    uid = str(message.from_user.id)
    payload = message.successful_payment.invoice_payload

    if payload == "premium_access":
        premium_users.add(uid)
        save_set(PREMIUM_FILE, premium_users)
        if uid in discount_users:
            discount_users.discard(uid)
            save_set(DISCOUNT_FILE, discount_users)
        await message.answer("⭐ <b>Спасибо за Премиум!</b>\n\nТеперь поиск выдаёт до 15 скриптов.", reply_markup=main_menu_kb())

    elif payload == "freeze_access":
        freeze_buyers.add(uid)
        save_set(FREEZE_FILE, freeze_buyers)
        await message.answer("❄️ <b>Спасибо за Заморозку трейда!</b>", reply_markup=main_menu_kb())


# ============ ПОИСК ============
@dp.callback_query(F.data == "menu_search")
async def menu_search(callback: types.CallbackQuery, state: FSMContext):
    limit = PREMIUM_LIMIT if is_premium(callback.from_user.id) else FREE_LIMIT
    await callback.message.edit_text(
        f"🔍 <b>Поиск скриптов</b>\n\nНапиши название игры или скрипта.\nПоказываю до <b>{limit}</b>.",
        reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[
            [types.InlineKeyboardButton(text="❌ Отмена", callback_data="menu_main")]
        ]),
    )
    await state.set_state(SearchStates.waiting_for_query)


@dp.message(SearchStates.waiting_for_query)
async def process_search(message: types.Message, state: FSMContext):
    await state.clear()
    query = message.text.strip().lower()
    uid = message.from_user.id
    premium = is_premium(uid)
    limit = PREMIUM_LIMIT if premium else FREE_LIMIT

    known_game = None
    for kw, g in GAMES_INDEX.items():
        if kw in query:
            known_game = g
            break

    msg = await message.answer(f"🔎 Ищу: <code>{query}</code>...")
    all_scripts = await search_scriptblox(query)

    if "mm2" in query or "murder" in query or "мурдер" in query:
        all_scripts.extend(await search_cheater_fun())
        all_scripts.extend(await search_bo3())

    if not all_scripts:
        text = f"❌ <b>Не найдено:</b> <code>{query}</code>"
        kb = []
        if known_game:
            kb.append([types.InlineKeyboardButton(text=f"📂 Открыть {known_game['name']}", callback_data=known_game["menu"])])
        kb.append([types.InlineKeyboardButton(text="🔙 Меню", callback_data="menu_main")])
        await msg.edit_text(text, reply_markup=types.InlineKeyboardMarkup(inline_keyboard=kb))
        return

    seen = set()
    fresh = []
    for s in all_scripts:
        t = s.get("title", "").lower()
        if t and t not in seen:
            seen.add(t)
            fresh.append(s)

    total = len(fresh)
    shown = fresh[:limit]

    text = f"🌐 <b>Найдено ({total}):</b>\n\n"
    for i, s in enumerate(shown, 1):
        text += f"<b>{i}. {s.get('title','?')}</b>\n🎮 {s.get('game',{}).get('name','?')}\n<pre>{s.get('script','')[:200]}...</pre>\n\n"

    if not premium and total > FREE_LIMIT:
        text += f"🔒 Показано {FREE_LIMIT} из {total}.\n⭐ Премиум покажет 15."

    kb = []
    if known_game:
        kb.append([types.InlineKeyboardButton(text=f"📂 Открыть {known_game['name']}", callback_data=known_game["menu"])])
    if not premium and total > FREE_LIMIT:
        kb.append([types.InlineKeyboardButton(text=f"⭐ Премиум — {PREMIUM_PRICE_STARS}⭐", callback_data="buy_premium")])
    kb.append([types.InlineKeyboardButton(text="🔙 Меню", callback_data="menu_main")])

    await msg.edit_text(text, reply_markup=types.InlineKeyboardMarkup(inline_keyboard=kb))


async def search_scriptblox(query: str):
    url = "https://scriptblox.com/api/script/search"
    params = {"q": query, "mode": "free", "key": 0, "max": 20, "strict": "true"}
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params, timeout=15, headers={"User-Agent": "Mozilla/5.0"}) as r:
                if r.status == 200:
                    d = await r.json()
                    return d.get("result", {}).get("scripts", [])
    except Exception as e:
        print(f"SB error: {e}")
    return []


async def search_cheater_fun():
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get("https://cheater.fun/hacks_roblox/7931-murder-mystery-2-scripts.html",
                                   timeout=15, headers={"User-Agent": "Mozilla/5.0"}) as r:
                if r.status == 200:
                    html = await r.text()
                    m = re.findall(r'###\s*(.*?)\n.*?loadstring\(game:HttpGet\("([^"]+)"\)\)\(\)', html)
                    return [{"title": x[0].strip(), "script": f'loadstring(game:HttpGet("{x[1]}"))()', "game": {"name": "MM2"}} for x in m]
    except Exception as e:
        print(f"CF error: {e}")
    return []


async def search_bo3():
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get("https://bo3.gg/games/articles/murder-mystery-2-scripts",
                                   timeout=15, headers={"User-Agent": "Mozilla/5.0"}) as r:
                if r.status == 200:
                    html = await r.text()
                    m = re.findall(r'([^\n<]{5,60}?)\s*loadstring\(game:HttpGet\([\'"]([^\'"]+)[\'"]\)\)\(\)', html)
                    return [{"title": x[0].strip(), "script": f'loadstring(game:HttpGet("{x[1]}"))()', "game": {"name": "MM2"}} for x in m]
    except Exception as e:
        print(f"BO3 error: {e}")
    return []


# ============ ПРОЧЕЕ ============
@dp.callback_query(F.data == "show_users")
async def show_users(cb: types.CallbackQuery):
    await cb.answer(f"👥 Всего: {len(users)}\n⭐ Премиум: {len(premium_users)}", show_alert=True)


@dp.callback_query(F.data == "menu_brookhaven")
async def menu_brookhaven(cb: types.CallbackQuery):
    s = {"🔥 Redz9999 2026": "code_redz", "🚀 Lord-Kaiser": "code_lord", "🌐 LOLA HUB": "code_lola", "🎧 Saiki Music": "code_saiki"}
    b = [[types.InlineKeyboardButton(text=t, callback_data=d)] for t, d in s.items()]
    b.append([types.InlineKeyboardButton(text="🔙 Назад", callback_data="menu_main")])
    await cb.message.edit_text("📜 Brookhaven:", reply_markup=types.InlineKeyboardMarkup(inline_keyboard=b))


@dp.callback_query(F.data == "menu_mm2")
async def menu_mm2(cb: types.CallbackQuery):
    s = {"🥷 Madara": "code_madara", "🔪 Moondiety": "code_moondiety", "🛡️ God mode": "code_godmode", "❄️ Заморозка трейда": "code_mm2_freeze"}
    b = [[types.InlineKeyboardButton(text=t, callback_data=d)] for t, d in s.items()]
    b.append([types.InlineKeyboardButton(text="🔙 Назад", callback_data="menu_main")])
    await cb.message.edit_text("🎮 MM2:", reply_markup=types.InlineKeyboardMarkup(inline_keyboard=b))


@dp.callback_query(F.data == "menu_bloxfruits")
async def menu_bloxfruits(cb: types.CallbackQuery):
    s = {"🎮 Min Gaming": "code_bf_min", "🚀 Redz BETA": "code_bf_redz", "🏠 BF Script": "code_bf_basement", "⚡ Auto Farm": "code_bf_autofarm"}
    b = [[types.InlineKeyboardButton(text=t, callback_data=d)] for t, d in s.items()]
    b.append([types.InlineKeyboardButton(text="🔙 Назад", callback_data="menu_main")])
    await cb.message.edit_text("🍇 Blox Fruits:", reply_markup=types.InlineKeyboardMarkup(inline_keyboard=b))


@dp.callback_query(F.data == "menu_99nights")
async def menu_99nights(cb: types.CallbackQuery):
    s = {"📜 Script 1": "code_99_1", "📜 Script 2": "code_99_2", "📜 Script 3": "code_99_3"}
    b = [[types.InlineKeyboardButton(text=t, callback_data=d)] for t, d in s.items()]
    b.append([types.InlineKeyboardButton(text="🔙 Назад", callback_data="menu_main")])
    await cb.message.edit_text("🌙 99 Ночей:", reply_markup=types.InlineKeyboardMarkup(inline_keyboard=b))


@dp.callback_query(F.data == "menu_stealanegg")
async def menu_stealanegg(cb: types.CallbackQuery):
    s = {"📜 Script 1 (Sabs)": "code_egg_1", "🎧 Lennon Hub V2": "code_egg_2", "🥚 Lennon Auto-Steal": "code_egg_3"}
    b = [[types.InlineKeyboardButton(text=t, callback_data=d)] for t, d in s.items()]
    b.append([types.InlineKeyboardButton(text="🔙 Назад", callback_data="menu_main")])
    await cb.message.edit_text("🥚 Steal an Egg:", reply_markup=types.InlineKeyboardMarkup(inline_keyboard=b))


@dp.callback_query(F.data == "menu_main")
async def menu_main(cb: types.CallbackQuery, state: FSMContext):
    await state.clear()
    uid = cb.from_user.id
    status = "⭐ Премиум" if is_premium(uid) else "🆓 Бесплатно"
    streaks = load_streaks()
    streak = streaks.get(str(uid), {}).get("streak", 0)

    text = f"🔥 Привет!\n📊 Статус: <b>{status}</b>\n🔥 Streak: <b>{streak}/{STREAK_DAYS}</b>"
    await cb.message.edit_text(text, reply_markup=main_menu_kb())


@dp.callback_query(F.data.startswith("code_"))
async def send_script_code(cb: types.CallbackQuery):
    name = cb.data.split("_", 1)[1]
    uid = cb.from_user.id

    if name == "mm2_freeze":
        if not has_freeze(uid):
            await cb.answer("❄️ Платный скрипт!", show_alert=True)
            await bot.send_message(uid,
                "❄️ <b>Заморозка трейда (MM2)</b>\n\n"
                f"Стоимость: <b>{FREEZE_PRICE_STARS}⭐</b>",
                reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[
                    [types.InlineKeyboardButton(text=f"⭐ Купить за {FREEZE_PRICE_STARS}⭐", callback_data="buy_freeze")]
                ]))
            return
        await cb.answer("Отправляю ✅")
        await bot.send_message(uid,
            "❄️ <b>Заморозка трейда</b>\n\n"
            "<b>Основной:</b>\n<pre>loadstring(game:HttpGet(\"https://cdn.sourceb.in/bins/9MHwJQNJkm/0\"))()</pre>\n\n"
            "<b>Резервный:</b>\n<pre>loadstring(game:HttpGet('https://raw.githubusercontent.com/txnic255/MM2-FREEZE-TRADE-V5.5-NEWEST-GUI-SCRIPT-/refs/heads/main/SCRIPT%20V5.5%20GUI%20AND%20SCRIPT'))()</pre>")
        return

    await cb.answer("Отправляю ✅")
    code = SCRIPTS_CODES.get(name.lower(), "Не найден.")
    await bot.send_message(uid, f"✅ Вы выбрали:\n{code}")


# ============ ВЕБ-СЕРВЕР ============
async def health(request):
    return web.Response(text="Bot is alive")


async def start_web():
    app = web.Application()
    app.router.add_get("/", health)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.getenv("PORT", 8080))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()


async def main():
    await asyncio.gather(dp.start_polling(bot), start_web())


if __name__ == "__main__":
    asyncio.run(main())
