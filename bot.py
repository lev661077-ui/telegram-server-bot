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

# --- НАСТРОЙКИ ---
PREMIUM_PRICE_STARS = 30
FREEZE_PRICE_STARS = 10
FREE_LIMIT = 5
PREMIUM_LIMIT = 15
STREAK_DAYS = 3

# ⚠️ ВСТАВЬ СВОЙ ID из @userinfobot
ADMIN_ID = 123456789

bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
dp = Dispatcher(storage=MemoryStorage())

# --- ФАЙЛЫ ---
USERS_FILE = "users.txt"
PREMIUM_FILE = "premium.txt"
FREEZE_FILE = "freeze_buyers.txt"
TRIAL_FILE = "trial_premium.txt"
DISCOUNT_FILE = "discount_users.txt"
SHOP_FILE = "shop.txt"
PROMO_FILE = "promocodes.txt"

def load_set(filename):
    if os.path.exists(filename):
        with open(filename) as f:
            return set(line.strip() for line in f if line.strip())
    return set()

def save_set(filename, data):
    with open(filename, "w") as f:
        for item in data:
            f.write(f"{item}\n")

def load_dict(filename, keys_count):
    data = {}
    if os.path.exists(filename):
        with open(filename) as f:
            for line in f:
                p = line.strip().split("|")
                if len(p) == keys_count:
                    data[p[0]] = p[1:]
    return data

def save_dict(filename, data):
    with open(filename, "w") as f:
        for k, v in data.items():
            f.write(f"{k}|" + "|".join(str(x) for x in v) + "\n")

users = load_set(USERS_FILE)
premium_users = load_set(PREMIUM_FILE)
freeze_buyers = load_set(FREEZE_FILE)
discount_users = load_set(DISCOUNT_FILE)

def is_premium(user_id: int) -> bool:
    uid = str(user_id)
    return uid == str(ADMIN_ID) or uid in premium_users

def has_search_premium(user_id: int) -> bool:
    if is_premium(user_id): return True
    trials = load_dict(TRIAL_FILE, 1)
    uid = str(user_id)
    if uid in trials:
        try:
            if datetime.fromisoformat(trials[uid][0]) > datetime.now():
                return True
        except: pass
    return False

def has_freeze(user_id: int) -> bool:
    uid = str(user_id)
    return uid == str(ADMIN_ID) or uid in premium_users or uid in freeze_buyers

def generate_code():
    return "PROMO-" + "".join(random.choices(string.ascii_uppercase + string.digits, k=8))

class SearchStates(StatesGroup):
    waiting_for_query = State()

class PromoStates(StatesGroup):
    waiting_for_code = State()

class DonateStates(StatesGroup):
    waiting_for_amount = State()


GAMES_INDEX = {
    "brookhaven":  {"name": "📜 Brookhaven", "menu": "menu_brookhaven"},
    "mm2":         {"name": "🎮 MM2", "menu": "menu_mm2"},
    "blox":        {"name": "🍇 Blox Fruits", "menu": "menu_bloxfruits"},
    "99":          {"name": "🌙 99 Ночей", "menu": "menu_99nights"},
    "steal":       {"name": "🥚 Steal an Egg", "menu": "menu_stealanegg"},
    "egg":         {"name": "🥚 Steal an Egg", "menu": "menu_stealanegg"},
}

SCRIPTS_CODES = {
    "redz": "<pre>loadstring(game:HttpGet('https://pastebin.com/raw/1r7cEW7G'))()</pre>",
    "lord": "<pre>loadstring(game:HttpGet(\"https://raw.githubusercontent.com/SUPREMEAURA350/KAISER-VERSION-2-/refs/heads/main/Kaiserspam\"))()</pre>",
    "lola": "<pre>loadstring(game:HttpGet(\"https://raw.githubusercontent.com/niriel015/Painel-LolaHub/refs/heads/main/Lola-hub-ne-pai\"))()</pre>",
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

def main_menu_kb(uid):
    status = "⭐ Премиум" if is_premium(uid) else "🆓 Бесплатно"
    return types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="📜 Brookhaven", callback_data="menu_brookhaven")],
        [types.InlineKeyboardButton(text="🎮 MM2", callback_data="menu_mm2")],
        [types.InlineKeyboardButton(text="🍇 Blox Fruits", callback_data="menu_bloxfruits")],
        [types.InlineKeyboardButton(text="🌙 99 Ночей", callback_data="menu_99nights")],
        [types.InlineKeyboardButton(text="🥚 Steal an Egg", callback_data="menu_stealanegg")],
        [types.InlineKeyboardButton(text="🔍 Поиск", callback_data="menu_search")],
        [types.InlineKeyboardButton(text="🛒 Магазин", callback_data="shop")],
        [types.InlineKeyboardButton(text="🎁 Промокод", callback_data="enter_promo")],
        [types.InlineKeyboardButton(text="💎 Стать спонсором", callback_data="donate_menu")],
        [types.InlineKeyboardButton(text=f"⭐ Премиум ({status})", callback_data="buy_premium")],
        [types.InlineKeyboardButton(text="👥 Пользователи", callback_data="show_users")],
        [types.InlineKeyboardButton(text="💬 Сообщество", url="https://t.me/+LBs19_JzpW0yNmZi")],
    ])

@dp.message(F.text == "/start")
async def start(message: types.Message, state: FSMContext):
    await state.clear()
    uid = message.from_user.id
    is_new = str(uid) not in users
    
    if is_new:
        users.add(str(uid))
        save_set(USERS_FILE, users)

    text = f"🔥 <b>Привет!</b>\n\n"
    
    if is_new:
        code = generate_code()
        promos = load_dict(PROMO_FILE, 4)
        promos[code] = ["trial", "3", str(uid), "no"]
        save_dict(PROMO_FILE, promos)
        text += f"🎁 <b>Ты новичок! Держи подарок:</b>\n"
        text += f"Промокод на 3 дня поиска: <code>{code}</code>\n\n"

    text += f"Активируй его кнопкой 🎁 Промокод."
    await message.answer(text, reply_markup=main_menu_kb(uid))


# ============ ДОНАТ ============
@dp.callback_query(F.data == "donate_menu")
async def donate_menu(callback: types.CallbackQuery):
    amounts = [10, 25, 50, 100, 250, 500, 1000]
    buttons = []
    row = []
    for amount in amounts:
        row.append(types.InlineKeyboardButton(text=f"{amount}⭐", callback_data=f"donate_{amount}"))
        if len(row) == 3:
            buttons.append(row)
            row = []
    if row: buttons.append(row)

    buttons.append([types.InlineKeyboardButton(text="✏️ Своя сумма", callback_data="donate_custom")])
    buttons.append([types.InlineKeyboardButton(text="🔙 Назад", callback_data="menu_main")])

    await callback.message.edit_text(
        "💎 <b>Стать спонсором</b>\n\nВыбери сумму в звёздах:",
        reply_markup=types.InlineKeyboardMarkup(inline_keyboard=buttons),
    )
    await callback.answer()

@dp.callback_query(F.data.startswith("donate_") & ~F.data.in_({"donate_menu", "donate_custom"}))
async def process_donate(callback: types.CallbackQuery):
    amount = int(callback.data.split("_")[1])
    await send_donate_invoice(callback.from_user.id, amount)
    await callback.answer()

@dp.callback_query(F.data == "donate_custom")
async def donate_custom(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.edit_text(
        "💎 <b>Введи сумму</b> (от 1 до 1000):",
        reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[
            [types.InlineKeyboardButton(text="❌ Отмена", callback_data="donate_menu")]
        ]),
    )
    await state.set_state(DonateStates.waiting_for_amount)

@dp.message(DonateStates.waiting_for_amount)
async def process_custom_donate(message: types.Message, state: FSMContext):
    await state.clear()
    try:
        amount = int(message.text.strip())
        if amount < 1 or amount > 1000: raise ValueError
        await send_donate_invoice(message.from_user.id, amount)
    except ValueError:
        await message.answer("❌ Неверная сумма. Введи от 1 до 1000.", reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[
            [types.InlineKeyboardButton(text="🔙 Попробовать снова", callback_data="donate_custom")]
        ]))

async def send_donate_invoice(user_id: int, amount: int):
    await bot.send_invoice(
        chat_id=user_id, title="💎 Поддержка проекта",
        description=f"Ты отправляешь {amount} звёзд.",
        payload=f"donate_{amount}", provider_token="", currency="XTR",
        prices=[LabeledPrice(label="Донат", amount=amount)],
    )


# ============ МАГАЗИН ============
def generate_shop():
    shop_items = []
    types = ["discount", "trial3", "trial5"]
    prices = {"discount": 3, "trial3": 7, "trial5": 10}
    for _ in range(10):
        ptype = random.choice(types)
        code = generate_code()
        item = f"{code}|{ptype}|{prices[ptype]}|no|{datetime.now().isoformat()}"
        shop_items.append(item)
    with open(SHOP_FILE, "w") as f:
        f.write("\n".join(shop_items))

def get_shop():
    items = []
    if os.path.exists(SHOP_FILE):
        with open(SHOP_FILE) as f:
            for line in f:
                p = line.strip().split("|")
                if len(p) == 5:
                    items.append({"code": p[0], "type": p[1], "price": int(p[2]), "bought": p[3], "created": p[4]})
    return items

@dp.callback_query(F.data == "shop")
async def shop(callback: types.CallbackQuery):
    if not os.path.exists(SHOP_FILE) or (datetime.now() - datetime.fromtimestamp(os.path.getmtime(SHOP_FILE))).seconds > 30:
        generate_shop()

    items = get_shop()
    kb = []
    text = "🛒 <b>Магазин промокодов</b>\n<i>Обновляется каждые 30 секунд.</i>\n\n"
    
    for item in items:
        if item["bought"] == "yes": continue
        if item["type"] == "discount": title = "💰 Скидка 50%"
        elif item["type"] == "trial3": title = "⭐ Поиск 3 дня"
        else: title = "⭐ Поиск 5 дней"
        kb.append([types.InlineKeyboardButton(text=f"{title} — {item['price']}⭐", callback_data=f"buy_promo_{item['code']}")])

    kb.append([types.InlineKeyboardButton(text="🔄 Обновить", callback_data="shop")])
    kb.append([types.InlineKeyboardButton(text="🔙 Меню", callback_data="menu_main")])
    await callback.message.edit_text(text, reply_markup=types.InlineKeyboardMarkup(inline_keyboard=kb))

@dp.callback_query(F.data.startswith("buy_promo_"))
async def buy_promo(callback: types.CallbackQuery):
    code = callback.data.split("_")[2]
    items = get_shop()
    item = next((x for x in items if x["code"] == code), None)
    if not item or item["bought"] == "yes":
        await callback.answer("❌ Товар уже продан!", show_alert=True)
        return
    await bot.send_invoice(
        chat_id=callback.from_user.id, title="Покупка промокода",
        description=f"Код на {item['type']}", payload=f"promo_{code}",
        provider_token="", currency="XTR",
        prices=[LabeledPrice(label="Промокод", amount=item["price"])]
    )
    await callback.answer()


# ============ АКТИВАЦИЯ ПРОМО ============
@dp.callback_query(F.data == "enter_promo")
async def enter_promo(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.edit_text("🎁 <b>Введи промокод</b> текстом:", reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[[types.InlineKeyboardButton(text="❌ Отмена", callback_data="menu_main")]]))
    await state.set_state(PromoStates.waiting_for_code)

@dp.message(PromoStates.waiting_for_code)
async def process_promo(message: types.Message, state: FSMContext):
    await state.clear()
    uid = str(message.from_user.id)
    code = message.text.strip().upper()
    promos = load_dict(PROMO_FILE, 4)
    
    if code not in promos:
        await message.answer("❌ Промокод не найден.", reply_markup=main_menu_kb(uid))
        return
    ptype, val, used_by, _ = promos[code]
    if used_by != "no":
        await message.answer("❌ Уже активирован.", reply_markup=main_menu_kb(uid))
        return

    if ptype == "discount":
        discount_users.add(uid)
        save_set(DISCOUNT_FILE, discount_users)
        await message.answer(f"✅ <b>Скидка 50% активирована!</b>\nЦена на Премиум теперь 15⭐.", reply_markup=main_menu_kb(uid))
    elif ptype == "trial":
        days = int(val)
        expires = (datetime.now() + timedelta(days=days)).isoformat()
        trials = load_dict(TRIAL_FILE, 1)
        trials[uid] = [expires]
        save_dict(TRIAL_FILE, trials)
        await message.answer(f"✅ <b>Поиск на {days} дней активирован!</b>", reply_markup=main_menu_kb(uid))

    promos[code] = [ptype, val, uid, "yes"]
    save_dict(PROMO_FILE, promos)


# ============ ОПЛАТА (ОБЩАЯ) ============
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
        await message.answer("⭐ <b>Спасибо за Премиум!</b>", reply_markup=main_menu_kb(uid))
    elif payload == "freeze_access":
        freeze_buyers.add(uid)
        save_set(FREEZE_FILE, freeze_buyers)
        await message.answer("❄️ <b>Спасибо за Заморозку!</b>", reply_markup=main_menu_kb(uid))
    elif payload.startswith("donate_"):
        amount = payload.split("_")[1]
        await message.answer(f"💎 <b>Спасибо за {amount} звёзд!</b>", reply_markup=main_menu_kb(uid))
    elif payload.startswith("promo_"):
        code = payload.split("_", 1)[1]
        items = get_shop()
        for i in items:
            if i["code"] == code: i["bought"] = "yes"
        with open(SHOP_FILE, "w") as f:
            for i in items: f.write(f"{i['code']}|{i['type']}|{i['price']}|{i['bought']}|{i['created']}\n")
        
        promos = load_dict(PROMO_FILE, 4)
        item = next((x for x in items if x["code"] == code), None)
        if item:
            ptype, val = ("discount", "50") if item["type"]=="discount" else ("trial", "3" if item["type"]=="trial3" else "5")
            promos[code] = [ptype, val, uid, "no"]
            save_dict(PROMO_FILE, promos)
            await message.answer(f"✅ <b>Куплено!</b>\nКод: <code>{code}</code>", reply_markup=main_menu_kb(uid))


# ============ ПОКУПКА ПРЕМИУМА ============
@dp.callback_query(F.data == "buy_premium")
async def buy_premium(callback: types.CallbackQuery):
    uid = callback.from_user.id
    if is_premium(uid):
        await callback.answer("✅ Уже есть!", show_alert=True); return
    price = 15 if str(uid) in discount_users else PREMIUM_PRICE_STARS
    await bot.send_invoice(chat_id=uid, title="⭐ Премиум доступ", description="Поиск 15 скриптов.", payload="premium_access", provider_token="", currency="XTR", prices=[LabeledPrice(label="Премиум", amount=price)])
    await callback.answer()

@dp.callback_query(F.data == "buy_freeze")
async def buy_freeze(callback: types.CallbackQuery):
    if has_freeze(callback.from_user.id):
        await callback.answer("✅ Уже есть!", show_alert=True); return
    await bot.send_invoice(chat_id=callback.from_user.id, title="❄️ Заморозка", description="MM2 скрипт", payload="freeze_access", provider_token="", currency="XTR", prices=[LabeledPrice(label="Заморозка", amount=FREEZE_PRICE_STARS)])
    await callback.answer()


# ============ ПОИСК ============
@dp.callback_query(F.data == "menu_search")
async def menu_search(callback: types.CallbackQuery, state: FSMContext):
    limit = PREMIUM_LIMIT if has_search_premium(callback.from_user.id) else FREE_LIMIT
    await callback.message.edit_text(f"🔍 <b>Поиск</b>\nДо <b>{limit}</b> скриптов. Напиши название:", reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[[types.InlineKeyboardButton(text="❌ Отмена", callback_data="menu_main")]]))
    await state.set_state(SearchStates.waiting_for_query)

@dp.message(SearchStates.waiting_for_query)
async def process_search(message: types.Message, state: FSMContext):
    await state.clear()
    query = message.text.strip().lower()
    uid = message.from_user.id
    premium = has_search_premium(uid)
    limit = PREMIUM_LIMIT if premium else FREE_LIMIT
    msg = await message.answer(f"🔎 Ищу: <code>{query}</code>...")
    
    all_scripts = await search_scriptblox(query)
    if "mm2" in query or "murder" in query:
        all_scripts.extend(await search_cheater_fun())
        all_scripts.extend(await search_bo3())

    if not all_scripts:
        await msg.edit_text(f"❌ <b>Не найдено.</b>", reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[[types.InlineKeyboardButton(text="🔙 Меню", callback_data="menu_main")]]))
        return

    seen = set()
    fresh = [s for s in all_scripts if s.get("title", "").lower() not in seen and not seen.add(s.get("title", "").lower())]
    total = len(fresh)
    text = f"🌐 <b>Найдено ({total}):</b>\n\n"
    for i, s in enumerate(fresh[:limit], 1):
        text += f"<b>{i}. {s.get('title','?')}</b>\n🎮 {s.get('game',{}).get('name','?')}\n<pre>{s.get('script','')[:200]}...</pre>\n\n"
    
    kb = []
    if not premium and total > FREE_LIMIT:
        text += f"🔒 Показано {FREE_LIMIT} из {total}.\n"
        kb.append([types.InlineKeyboardButton(text=f"⭐ Купить Премиум", callback_data="buy_premium")])
        kb.append([types.InlineKeyboardButton(text=f"🛒 Купить Поиск в магазине", callback_data="shop")])
    
    kb.append([types.InlineKeyboardButton(text="🔙 Меню", callback_data="menu_main")])
    await msg.edit_text(text, reply_markup=types.InlineKeyboardMarkup(inline_keyboard=kb))

async def search_scriptblox(query: str):
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get("https://scriptblox.com/api/script/search", params={"q": query, "mode": "free", "key": 0, "max": 20, "strict": "true"}, timeout=15, headers={"User-Agent": "Mozilla/5.0"}) as r:
                if r.status == 200: return (await r.json()).get("result", {}).get("scripts", [])
    except Exception: pass
    return []

async def search_cheater_fun():
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get("https://cheater.fun/hacks_roblox/7931-murder-mystery-2-scripts.html", timeout=15, headers={"User-Agent": "Mozilla/5.0"}) as r:
                if r.status == 200:
                    html = await r.text()
                    m = re.findall(r'###\s*(.*?)\n.*?loadstring\(game:HttpGet\("([^"]+)"\)\)\(\)', html)
                    return [{"title": x[0].strip(), "script": f'loadstring(game:HttpGet("{x[1]}"))()', "game": {"name": "MM2"}} for x in m]
    except Exception: pass
    return []

async def search_bo3():
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get("https://bo3.gg/games/articles/murder-mystery-2-scripts", timeout=15, headers={"User-Agent": "Mozilla/5.0"}) as r:
                if r.status == 200:
                    html = await r.text()
                    m = re.findall(r'([^\n<]{5,60}?)\s*loadstring\(game:HttpGet\([\'"]([^\'"]+)[\'"]\)\)\(\)', html)
                    return [{"title": x[0].strip(), "script": f'loadstring(game:HttpGet("{x[1]}"))()', "game": {"name": "MM2"}} for x in m]
    except Exception: pass
    return []


# ============ КАТЕГОРИИ ============
@dp.callback_query(F.data == "menu_brookhaven")
async def menu_brookhaven(cb: types.CallbackQuery):
    s = {"🔥 Redz": "code_redz", "🚀 Lord": "code_lord", "🌐 LOLA": "code_lola", "🎧 Saiki": "code_saiki"}
    b = [[types.InlineKeyboardButton(text=t, callback_data=d)] for t, d in s.items()]
    b.append([types.InlineKeyboardButton(text="🔙 Назад", callback_data="menu_main")])
    await cb.message.edit_text("📜 Brookhaven:", reply_markup=types.InlineKeyboardMarkup(inline_keyboard=b))

@dp.callback_query(F.data == "menu_mm2")
async def menu_mm2(cb: types.CallbackQuery):
    s = {"🥷 Madara": "code_madara", "🔪 Moondiety": "code_moondiety", "🛡️ God": "code_godmode", "❄️ Заморозка": "code_mm2_freeze"}
    b = [[types.InlineKeyboardButton(text=t, callback_data=d)] for t, d in s.items()]
    b.append([types.InlineKeyboardButton(text="🔙 Назад", callback_data="menu_main")])
    await cb.message.edit_text("🎮 MM2:", reply_markup=types.InlineKeyboardMarkup(inline_keyboard=b))

@dp.callback_query(F.data == "menu_bloxfruits")
async def menu_bloxfruits(cb: types.CallbackQuery):
    s = {"🎮 Min": "code_bf_min", "🚀 Redz B": "code_bf_redz", "🏠 Base": "code_bf_basement", "⚡ Farm": "code_bf_autofarm"}
    b = [[types.InlineKeyboardButton(text=t, callback_data=d)] for t, d in s.items()]
    b.append([types.InlineKeyboardButton(text="🔙 Назад", callback_data="menu_main")])
    await cb.message.edit_text("🍇 Blox Fruits:", reply_markup=types.InlineKeyboardMarkup(inline_keyboard=b))

@dp.callback_query(F.data == "menu_99nights")
async def menu_99nights(cb: types.CallbackQuery):
    s = {"📜 1": "code_99_1", "📜 2": "code_99_2", "📜 3": "code_99_3"}
    b = [[types.InlineKeyboardButton(text=t, callback_data=d)] for t, d in s.items()]
    b.append([types.InlineKeyboardButton(text="🔙 Назад", callback_data="menu_main")])
    await cb.message.edit_text("🌙 99 Ночей:", reply_markup=types.InlineKeyboardMarkup(inline_keyboard=b))

@dp.callback_query(F.data == "menu_stealanegg")
async def menu_stealanegg(cb: types.CallbackQuery):
    s = {"📜 Sabs": "code_egg_1", "🎧 Lennon V2": "code_egg_2", "🥚 Auto": "code_egg_3"}
    b = [[types.InlineKeyboardButton(text=t, callback_data=d)] for t, d in s.items()]
    b.append([types.InlineKeyboardButton(text="🔙 Назад", callback_data="menu_main")])
    await cb.message.edit_text("🥚 Steal Egg:", reply_markup=types.InlineKeyboardMarkup(inline_keyboard=b))

@dp.callback_query(F.data == "menu_main")
async def menu_main(cb: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await cb.message.edit_text("🔥 Выбери категорию:", reply_markup=main_menu_kb(cb.from_user.id))

@dp.callback_query(F.data.startswith("code_"))
async def send_script_code(cb: types.CallbackQuery):
    name = cb.data.split("_", 1)[1]
    uid = cb.from_user.id
    if name == "mm2_freeze":
        if not has_freeze(uid):
            await cb.answer("❄️ Платный скрипт!", show_alert=True)
            await bot.send_message(uid, "❄️ <b>Заморозка</b>\nСтоимость: 10⭐", reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[[types.InlineKeyboardButton(text="⭐ Купить", callback_data="buy_freeze")]]))
            return
        await cb.answer("Отправляю ✅")
        await bot.send_message(uid, "❄️ <b>Заморозка</b>\n\n<b>Основной:</b>\n<pre>loadstring(game:HttpGet(\"https://cdn.sourceb.in/bins/9MHwJQNJkm/0\"))()</pre>\n\n<b>Резервный:</b>\n<pre>loadstring(game:HttpGet('https://raw.githubusercontent.com/txnic255/MM2-FREEZE-TRADE-V5.5-NEWEST-GUI-SCRIPT-/refs/heads/main/SCRIPT%20V5.5%20GUI%20AND%20SCRIPT'))()</pre>")
        return
    await cb.answer("Отправляю ✅")
    code = SCRIPTS_CODES.get(name.lower(), "Не найден.")
    await bot.send_message(uid, f"✅ Вы выбрали:\n{code}")

@dp.callback_query(F.data == "show_users")
async def show_users(cb: types.CallbackQuery):
    await cb.answer(f"👥 Всего: {len(users)}\n⭐ Премиум: {len(premium_users)}", show_alert=True)


async def health(request): return web.Response(text="Bot is alive")

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
