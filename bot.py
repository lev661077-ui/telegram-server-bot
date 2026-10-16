import os
import asyncio
import aiohttp
from aiohttp import web
from aiogram import Bot, Dispatcher, F, types
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import LabeledPrice, PreCheckoutQuery

TOKEN = os.getenv("BOT_TOKEN")

# Настройки премиума
PREMIUM_PRICE_STARS = 50
FREE_LIMIT = 5
PREMIUM_LIMIT = 10

bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
dp = Dispatcher(storage=MemoryStorage())

# --- Файлы для хранения ---
USERS_FILE = "users.txt"
PREMIUM_FILE = "premium.txt"

def load_set(filename):
    if os.path.exists(filename):
        with open(filename, "r") as f:
            return set(line.strip() for line in f if line.strip())
    return set()

def save_set(filename, data):
    with open(filename, "w") as f:
        for item in data:
            f.write(f"{item}\n")

users = load_set(USERS_FILE)
premium_users = load_set(PREMIUM_FILE)

def is_premium(user_id: int) -> bool:
    return str(user_id) in premium_users


# --- Состояние для поиска ---
class SearchStates(StatesGroup):
    waiting_for_query = State()


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
    "redz":        "🔥 Redz9999 2026",
    "lord":        "🚀 Lord-Kaiser",
    "lola":        "🌐 LOLA HUB",
    "saiki":       "🎧 Saiki Music",
    "madara":      "🥷 Madara",
    "moondiety":   "🔪 Moondiety",
    "godmode":     "🛡️ God mode",
    "min gaming":  "🎮 Min Gaming",
    "redz beta":   "🚀 Redz BETA",
    "basement":    "🏠 BF Script",
    "auto farm":   "⚡ Auto Farm",
    "lennon":      "🎧 Lennon Hub V2",
    "sabs":        "📜 Script 1 (Sabs)",
}

SCRIPTS_CODES = {
    "redz":      "<pre>loadstring(game:HttpGet('https://pastebin.com/raw/1r7cEW7G'))()</pre>",
    "lord":      "<pre>loadstring(game:HttpGet(\"https://raw.githubusercontent.com/SUPREMEAURA350/KAISER-VERSION-2-/refs/heads/main/Kaiserspam\"))()</pre>",
    "lola":      "<pre>loadstring(game:HttpGet(\"https://raw.githubusercontent.com/niriel015/Painel-LolaHub/refs/heads/main/Lola-hub-ne-pai\"))()</pre>",
    "saiki":     "<pre>loadstring(game:HttpGet(\"https://raw.githubusercontent.com/SaikiWithTheBanHammer/ScriptBlox/main/LifeIsDisasterIndeedLol\"))()</pre>",
    "madara":    "<pre>loadstring(game:HttpGet(\"https://raw.githubusercontent.com/IsThisMe01/Project-Madara/refs/heads/main/mm22.lua\"))()</pre>",
    "moondiety": "<pre>loadstring(game:HttpGet(\"https://scriptblox.com/raw/Murder-Mystery-2-KEYLESS-InstaWin-AutoFarm-Kill-all-XRay-nd-more-by-Moondiety-48644\"))()</pre>",
    "godmode":   "<pre>loadstring(game:HttpGet(\"https://pastefy.app/a2dAk154/raw\"))()</pre>",
    "bf_min":      "<pre>loadstring(game:HttpGet(\"https://raw.githubusercontent.com/LuaCrack/Min/refs/heads/main/MinXt2Eng\"))()</pre>",
    "bf_redz":     "<pre>local Settings = {\n    JoinTeam = \"Pirates\";\n    Translator = true;\n}\ngetgenv().BETA_VERSION = true\nloadstring(game:HttpGet(\"https://raw.githubusercontent.com/tlredz/Scripts/refs/heads/main/main.luau\"))(Settings)</pre>",
    "bf_basement": "<pre>loadstring(game:HttpGet(\"https://raw.githubusercontent.com/Cazzanos/The-basement/main/Basement%20hub\", true))()</pre>",
    "bf_autofarm": "<pre>loadstring(game:HttpGetAsync(\"https://raw.githubusercontent.com/indexeduu/BF-NewVer/refs/heads/main/V3New.lua\"))()</pre>",
    "99_1": "<pre>loadstring(game:HttpGet(\"https://api.luarmor.net/files/v3/loaders/705e9a93cc18214fb77ab95686a8dba9.lua\"))()</pre>",
    "99_2": "<pre>KEY - 111222HHH\n\nloadstring(game:HttpGet(\"https://raw.githubusercontent.com/caomod2077/Script/refs/heads/main/FoxnameHub.lua\"))()</pre>",
    "99_3": "<pre>loadstring(game:HttpGet(\"https://ntt-hub.xyz/api/repo?id1=main&id2=lua\"))()</pre>",
    "egg_1": "<pre>loadstring(game:HttpGet(\"https://raw.githubusercontent.com/sabscrip-arch/srver/refs/heads/main/Stealanegg\"))()</pre>",
    "egg_2": "<pre>loadstring(game:HttpGet(\"https://raw.githubusercontent.com/lennonxscripts/lennonhubv2/refs/heads/main/stealaneggv2\"))()</pre>",
    "egg_3": "<pre>loadstring(game:HttpGet(\"https://raw.githubusercontent.com/lennonxscripts/lennonhubv2/refs/heads/main/stealaneggv2\"))()</pre>",
}


# ============ ГЛАВНОЕ МЕНЮ ============
@dp.message(F.text == "/start")
async def start(message: types.Message, state: FSMContext):
    await state.clear()
    if str(message.from_user.id) not in users:
        users.add(str(message.from_user.id))
        save_set(USERS_FILE, users)

    status = "⭐ Премиум" if is_premium(message.from_user.id) else "🆓 Бесплатно"
    keyboard = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="📜 Script Brookhaven Delta", callback_data="menu_brookhaven")],
        [types.InlineKeyboardButton(text="🎮 MM2", callback_data="menu_mm2")],
        [types.InlineKeyboardButton(text="🍇 Blox Fruits", callback_data="menu_bloxfruits")],
        [types.InlineKeyboardButton(text="🌙 99 Ночей", callback_data="menu_99nights")],
        [types.InlineKeyboardButton(text="🥚 Steal an Egg", callback_data="menu_stealanegg")],
        [types.InlineKeyboardButton(text="🔍 Поиск", callback_data="menu_search")],
        [types.InlineKeyboardButton(text=f"⭐ Премиум ({status})", callback_data="buy_premium")],
        [types.InlineKeyboardButton(text="👥 Пользователи", callback_data="show_users")],
        [types.InlineKeyboardButton(text="💬 Сообщество", url="https://t.me/+LBs19_JzpW0yNmZi")],
    ])
    await message.answer(
        f"🔥 Приветствую тебя!\nСтатус: <b>{status}</b>\nВыбери категорию скриптов:",
        reply_markup=keyboard,
    )


# ============ ПОКУПКА ПРЕМИУМА ============
@dp.callback_query(F.data == "buy_premium")
async def buy_premium(callback: types.CallbackQuery):
    if is_premium(callback.from_user.id):
        await callback.answer("✅ У тебя уже есть премиум!", show_alert=True)
        return

    await bot.send_invoice(
        chat_id=callback.from_user.id,
        title="⭐ Премиум доступ",
        description=f"Поиск выдаёт {PREMIUM_LIMIT} скриптов вместо {FREE_LIMIT}.",
        payload="premium_access",
        provider_token="",
        currency="XTR",
        prices=[LabeledPrice(label="Премиум", amount=PREMIUM_PRICE_STARS)],
    )
    await callback.answer()


@dp.pre_checkout_query()
async def process_pre_checkout(pre_checkout_q: PreCheckoutQuery):
    await bot.answer_pre_checkout_query(pre_checkout_q.id, ok=True)


@dp.message(F.successful_payment)
async def successful_payment(message: types.Message):
    if message.successful_payment.invoice_payload == "premium_access":
        premium_users.add(str(message.from_user.id))
        save_set(PREMIUM_FILE, premium_users)
        await message.answer(
            "⭐ <b>Спасибо за покупку!</b>\n\n"
            f"Теперь поиск выдаёт до <b>{PREMIUM_LIMIT}</b> скриптов.\n"
            "Приятного использования! 🚀"
        )


# ============ ПОИСК ============
@dp.callback_query(F.data == "menu_search")
async def menu_search(callback: types.CallbackQuery, state: FSMContext):
    limit = PREMIUM_LIMIT if is_premium(callback.from_user.id) else FREE_LIMIT
    await callback.message.edit_text(
        f"🔍 <b>Поиск скриптов</b>\n\n"
        f"Напиши название игры или скрипта.\n"
        f"Показываю до <b>{limit}</b> скриптов.\n\n"
        f"Например: <code>brookhaven</code>, <code>arsenal</code>, <code>mm2</code>",
        reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[
            [types.InlineKeyboardButton(text="❌ Отмена", callback_data="menu_main")]
        ]),
    )
    await state.set_state(SearchStates.waiting_for_query)


@dp.message(SearchStates.waiting_for_query)
async def process_search(message: types.Message, state: FSMContext):
    await state.clear()
    query = message.text.strip().lower()
    user_id = message.from_user.id
    premium = is_premium(user_id)
    limit = PREMIUM_LIMIT if premium else FREE_LIMIT

    known_game = None
    for keyword, game in GAMES_INDEX.items():
        if keyword in query:
            known_game = game
            break

    msg = await message.answer(f"🔎 Ищу: <code>{query}</code>...")
    scripts = await search_scriptblox(query)

    if not scripts:
        text = f"❌ <b>Не найдено:</b> <code>{query}</code>\n\n"
        if known_game:
            text += f"Но у меня есть категория: <b>{known_game['name']}</b>"
            kb = [
                [types.InlineKeyboardButton(text=f"📂 Открыть {known_game['name']}", callback_data=known_game["menu"])],
                [types.InlineKeyboardButton(text="🔙 В главное меню", callback_data="menu_main")],
            ]
        else:
            text += "Попробуй другое название."
            kb = [[types.InlineKeyboardButton(text="🔙 В главное меню", callback_data="menu_main")]]
        await msg.edit_text(text, reply_markup=types.InlineKeyboardMarkup(inline_keyboard=kb))
        return

    existing_titles = [v.lower() for v in SEARCH_INDEX.values()]
    fresh = [s for s in scripts if s.get("title", "").lower() not in existing_titles]
    if not fresh:
        fresh = scripts

    total_found = len(fresh)
    shown = fresh[:limit]

    text = f"🌐 <b>Найдено ({total_found}):</b>\n\n"
    for i, s in enumerate(shown, 1):
        title = s.get("title", "Без названия")
        game = s.get("game", {}).get("name", "?")
        code = s.get("script", "")
        text += f"<b>{i}. {title}</b>\n🎮 {game}\n<pre>{code[:200]}...</pre>\n\n"

    if not premium and total_found > FREE_LIMIT:
        text += f"🔒 <i>Показано {FREE_LIMIT} из {total_found}.</i>\n"
        text += f"⭐ <b>Премиум</b> покажет все {PREMIUM_LIMIT} скриптов."
    elif premium and total_found > PREMIUM_LIMIT:
        text += f"<i>...и ещё {total_found - PREMIUM_LIMIT}.</i>"

    kb = []
    if known_game:
        kb.append([types.InlineKeyboardButton(text=f"📂 Открыть {known_game['name']}", callback_data=known_game["menu"])])
    if not premium and total_found > FREE_LIMIT:
        kb.append([types.InlineKeyboardButton(
            text=f"⭐ Купить премиум — {PREMIUM_PRICE_STARS} звёзд",
            callback_data="buy_premium"
        )])
    kb.append([types.InlineKeyboardButton(text="🔙 В главное меню", callback_data="menu_main")])

    await msg.edit_text(text, reply_markup=types.InlineKeyboardMarkup(inline_keyboard=kb))


async def search_scriptblox(query: str):
    url = "https://scriptblox.com/api/script/search"
    params = {"q": query, "mode": "free", "key": 0, "max": 20, "strict": "true"}
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params, headers=headers, timeout=15) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return data.get("result", {}).get("scripts", [])
    except Exception as e:
        print(f"ScriptBlox error: {e}")
    return []


# ============ СЧЁТЧИК ============
@dp.callback_query(F.data == "show_users")
async def show_users(callback: types.CallbackQuery):
    count = len(users)
    prem = len(premium_users)
    await callback.answer(f"👥 Всего: {count}\n⭐ Премиум: {prem}", show_alert=True)


# ============ МЕНЮ КАТЕГОРИЙ ============
@dp.callback_query(F.data == "menu_brookhaven")
async def menu_brookhaven(callback: types.CallbackQuery):
    scripts = {
        "🔥 Redz9999 2026": "code_redz",
        "🚀 Lord-Kaiser":   "code_lord",
        "🌐 LOLA HUB":      "code_lola",
        "🎧 Saiki Music":   "code_saiki",
    }
    buttons = [[types.InlineKeyboardButton(text=t, callback_data=d)] for t, d in scripts.items()]
    buttons.append([types.InlineKeyboardButton(text="🔙 Назад", callback_data="menu_main")])
    await callback.message.edit_text("📜 Brookhaven — доступные сборки:",
        reply_markup=types.InlineKeyboardMarkup(inline_keyboard=buttons))


@dp.callback_query(F.data == "menu_mm2")
async def menu_mm2(callback: types.CallbackQuery):
    scripts = {"🥷 Madara": "code_madara", "🔪 Moondiety": "code_moondiety", "🛡️ God mode": "code_godmode"}
    buttons = [[types.InlineKeyboardButton(text=t, callback_data=d)] for t, d in scripts.items()]
    buttons.append([types.InlineKeyboardButton(text="🔙 Назад", callback_data="menu_main")])
    await callback.message.edit_text("🎮 MM2 — доступные скрипты:",
        reply_markup=types.InlineKeyboardMarkup(inline_keyboard=buttons))


@dp.callback_query(F.data == "menu_bloxfruits")
async def menu_bloxfruits(callback: types.CallbackQuery):
    scripts = {"🎮 Min Gaming": "code_bf_min", "🚀 Redz BETA": "code_bf_redz",
               "🏠 BF Script": "code_bf_basement", "⚡ Auto Farm": "code_bf_autofarm"}
    buttons = [[types.InlineKeyboardButton(text=t, callback_data=d)] for t, d in scripts.items()]
    buttons.append([types.InlineKeyboardButton(text="🔙 Назад", callback_data="menu_main")])
    await callback.message.edit_text("🍇 Blox Fruits — доступные скрипты:",
        reply_markup=types.InlineKeyboardMarkup(inline_keyboard=buttons))


@dp.callback_query(F.data == "menu_99nights")
async def menu_99nights(callback: types.CallbackQuery):
    scripts = {"📜 Script 1": "code_99_1", "📜 Script 2": "code_99_2", "📜 Script 3": "code_99_3"}
    buttons = [[types.InlineKeyboardButton(text=t, callback_data=d)] for t, d in scripts.items()]
    buttons.append([types.InlineKeyboardButton(text="🔙 Назад", callback_data="menu_main")])
    await callback.message.edit_text("🌙 99 Ночей — доступные скрипты:",
        reply_markup=types.InlineKeyboardMarkup(inline_keyboard=buttons))


@dp.callback_query(F.data == "menu_stealanegg")
async def menu_stealanegg(callback: types.CallbackQuery):
    scripts = {"📜 Script 1 (Sabs)": "code_egg_1", "🎧 Lennon Hub V2": "code_egg_2", "🥚 Lennon Auto-Steal": "code_egg_3"}
    buttons = [[types.InlineKeyboardButton(text=t, callback_data=d)] for t, d in scripts.items()]
    buttons.append([types.InlineKeyboardButton(text="🔙 Назад", callback_data="menu_main")])
    await callback.message.edit_text(
        "🥚 Steal an Egg — доступные скрипты:\n\n"
        "🎧 <b>Lennon Hub V2</b> — топовый:\n• Авто-воровство яиц\n• Телепорт к топ-4\n• Delta / Xeno",
        reply_markup=types.InlineKeyboardMarkup(inline_keyboard=buttons))


@dp.callback_query(F.data == "menu_main")
async def menu_main(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    status = "⭐ Премиум" if is_premium(callback.from_user.id) else "🆓 Бесплатно"
    keyboard = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="📜 Script Brookhaven Delta", callback_data="menu_brookhaven")],
        [types.InlineKeyboardButton(text="🎮 MM2", callback_data="menu_mm2")],
        [types.InlineKeyboardButton(text="🍇 Blox Fruits", callback_data="menu_bloxfruits")],
        [types.InlineKeyboardButton(text="🌙 99 Ночей", callback_data="menu_99nights")],
        [types.InlineKeyboardButton(text="🥚 Steal an Egg", callback_data="menu_stealanegg")],
        [types.InlineKeyboardButton(text="🔍 Поиск", callback_data="menu_search")],
        [types.InlineKeyboardButton(text=f"⭐ Премиум ({status})", callback_data="buy_premium")],
        [types.InlineKeyboardButton(text="👥 Пользователи", callback_data="show_users")],
        [types.InlineKeyboardButton(text="💬 Сообщество", url="https://t.me/+LBs19_JzpW0yNmZi")],
    ])
    await callback.message.edit_text(
        f"🔥 Приветствую тебя!\nСтатус: <b>{status}</b>\nВыбери категорию:",
        reply_markup=keyboard,
    )


@dp.callback_query(F.data.startswith("code_"))
async def send_script_code(callback: types.CallbackQuery):
    script_name = callback.data.split("_", 1)[1]
    await callback.answer("Отправляю скрипт в ЛС ✅")
    code_to_send = SCRIPTS_CODES.get(script_name.lower(), "Скрипт не найден.")
    await bot.send_message(chat_id=callback.from_user.id, text=f"✅ Вы выбрали:\n{code_to_send}")


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
