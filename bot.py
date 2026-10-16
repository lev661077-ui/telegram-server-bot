import os
import asyncio
import aiohttp
from aiohttp import web
from aiogram import Bot, Dispatcher, F, types
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BufferedInputFile

TOKEN = os.getenv("BOT_TOKEN")

bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
dp = Dispatcher(storage=MemoryStorage())

# --- Счётчик пользователей ---
USERS_FILE = "users.txt"

def load_users():
    if os.path.exists(USERS_FILE):
        with open(USERS_FILE, "r") as f:
            return set(line.strip() for line in f if line.strip())
    return set()

def save_users():
    with open(USERS_FILE, "w") as f:
        for uid in users:
            f.write(f"{uid}\n")

users = load_users()


# --- Состояние для поиска ---
class SearchStates(StatesGroup):
    waiting_for_query = State()


# --- Категории (для поиска по игре) ---
GAMES_INDEX = {
    "brookhaven":  {"name": "📜 Brookhaven", "menu": "menu_brookhaven"},
    "брукхейвен":  {"name": "📜 Brookhaven", "menu": "menu_brookhaven"},
    "брухавен":    {"name": "📜 Brookhaven", "menu": "menu_brookhaven"},
    "mm2":         {"name": "🎮 MM2", "menu": "menu_mm2"},
    "мурдер":      {"name": "🎮 MM2", "menu": "menu_mm2"},
    "murder":      {"name": "🎮 MM2", "menu": "menu_mm2"},
    "blox":        {"name": "🍇 Blox Fruits", "menu": "menu_bloxfruits"},
    "блокс":       {"name": "🍇 Blox Fruits", "menu": "menu_bloxfruits"},
    "99":          {"name": "🌙 99 Ночей", "menu": "menu_99nights"},
    "ночей":       {"name": "🌙 99 Ночей", "menu": "menu_99nights"},
    "steal":       {"name": "🥚 Steal an Egg", "menu": "menu_stealanegg"},
    "egg":         {"name": "🥚 Steal an Egg", "menu": "menu_stealanegg"},
    "стил":        {"name": "🥚 Steal an Egg", "menu": "menu_stealanegg"},
    "яйц":         {"name": "🥚 Steal an Egg", "menu": "menu_stealanegg"},
}

# --- Названия скриптов из нашей базы (для фильтра) ---
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
    # Brookhaven
    "redz":      "<pre>loadstring(game:HttpGet('https://pastebin.com/raw/1r7cEW7G'))()</pre>",
    "lord":      "<pre>loadstring(game:HttpGet(\"https://raw.githubusercontent.com/SUPREMEAURA350/KAISER-VERSION-2-/refs/heads/main/Kaiserspam\"))()</pre>",
    "lola":      "<pre>loadstring(game:HttpGet(\"https://raw.githubusercontent.com/niriel015/Painel-LolaHub/refs/heads/main/Lola-hub-ne-pai\"))()</pre>",
    "saiki":     "<pre>loadstring(game:HttpGet(\"https://raw.githubusercontent.com/SaikiWithTheBanHammer/ScriptBlox/main/LifeIsDisasterIndeedLol\"))()</pre>",

    # MM2
    "madara":    "<pre>loadstring(game:HttpGet(\"https://raw.githubusercontent.com/IsThisMe01/Project-Madara/refs/heads/main/mm22.lua\"))()</pre>",
    "moondiety": "<pre>loadstring(game:HttpGet(\"https://scriptblox.com/raw/Murder-Mystery-2-KEYLESS-InstaWin-AutoFarm-Kill-all-XRay-nd-more-by-Moondiety-48644\"))()</pre>",
    "godmode":   "<pre>loadstring(game:HttpGet(\"https://pastefy.app/a2dAk154/raw\"))()</pre>",

    # Blox Fruits
    "bf_min":      "<pre>loadstring(game:HttpGet(\"https://raw.githubusercontent.com/LuaCrack/Min/refs/heads/main/MinXt2Eng\"))()</pre>",
    "bf_redz":     "<pre>local Settings = {\n    JoinTeam = \"Pirates\";\n    Translator = true;\n}\ngetgenv().BETA_VERSION = true\nloadstring(game:HttpGet(\"https://raw.githubusercontent.com/tlredz/Scripts/refs/heads/main/main.luau\"))(Settings)</pre>",
    "bf_basement": "<pre>loadstring(game:HttpGet(\"https://raw.githubusercontent.com/Cazzanos/The-basement/main/Basement%20hub\", true))()</pre>",
    "bf_autofarm": "<pre>loadstring(game:HttpGetAsync(\"https://raw.githubusercontent.com/indexeduu/BF-NewVer/refs/heads/main/V3New.lua\"))()</pre>",

    # 99 Ночей
    "99_1": "<pre>loadstring(game:HttpGet(\"https://api.luarmor.net/files/v3/loaders/705e9a93cc18214fb77ab95686a8dba9.lua\"))()</pre>",
    "99_2": "<pre>KEY - 111222HHH\n\nloadstring(game:HttpGet(\"https://raw.githubusercontent.com/caomod2077/Script/refs/heads/main/FoxnameHub.lua\"))()</pre>",
    "99_3": "<pre>loadstring(game:HttpGet(\"https://ntt-hub.xyz/api/repo?id1=main&id2=lua\"))()</pre>",

    # Steal an Egg
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
        save_users()

    keyboard = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="📜 Script Brookhaven Delta", callback_data="menu_brookhaven")],
        [types.InlineKeyboardButton(text="🎮 MM2", callback_data="menu_mm2")],
        [types.InlineKeyboardButton(text="🍇 Blox Fruits", callback_data="menu_bloxfruits")],
        [types.InlineKeyboardButton(text="🌙 99 Ночей", callback_data="menu_99nights")],
        [types.InlineKeyboardButton(text="🥚 Steal an Egg", callback_data="menu_stealanegg")],
        [types.InlineKeyboardButton(text="🔍 Поиск", callback_data="menu_search")],
        [types.InlineKeyboardButton(text="👥 Пользователи", callback_data="show_users")],
        [types.InlineKeyboardButton(text="💬 Сообщество", url="https://t.me/+LBs19_JzpW0yNmZi")],
    ])
    await message.answer(
        "🔥 Приветствую тебя!\nВыбери категорию скриптов:",
        reply_markup=keyboard,
    )


# ============ ПОИСК ============
@dp.callback_query(F.data == "menu_search")
async def menu_search(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.edit_text(
        "🔍 <b>Поиск скриптов</b>\n\n"
        "Напиши название игры или скрипта.\n"
        "Например: <code>brookhaven</code>, <code>mm2</code>, <code>redz</code>\n\n"
        "Найду до 10 бесплатных скриптов без ключа.",
        reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[
            [types.InlineKeyboardButton(text="❌ Отмена", callback_data="menu_main")]
        ]),
    )
    await state.set_state(SearchStates.waiting_for_query)


@dp.message(SearchStates.waiting_for_query)
async def process_search(message: types.Message, state: FSMContext):
    await state.clear()
    query = message.text.strip().lower()

    # 1. Если ввели игру — показываем категорию
    for keyword, game in GAMES_INDEX.items():
        if keyword in query:
            await message.answer(
                f"🎮 Нашёл категорию: <b>{game['name']}</b>\n\n"
                f"Хочешь открыть меню или поискать свежие скрипты в интернете?",
                reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[
                    [types.InlineKeyboardButton(text=f"📂 Открыть {game['name']}", callback_data=game["menu"])],
                    [types.InlineKeyboardButton(text="🌐 Искать в интернете", callback_data=f"websearch_{query}")],
                    [types.InlineKeyboardButton(text="🔙 В главное меню", callback_data="menu_main")],
                ]),
            )
            return

    # 2. Иначе — сразу ищем в ScriptBlox
    await do_web_search(message, query)


async def do_web_search(message: types.Message, query: str):
    msg = await message.answer(f"🔎 Ищу в ScriptBlox: <code>{query}</code>...")

    scripts = await search_scriptblox(query)

    existing_titles = [v.lower() for v in SEARCH_INDEX.values()]
    fresh_scripts = []
    for s in scripts:
        title = s.get("title", "").lower()
        if not s.get("key", False) and title not in existing_titles:
            fresh_scripts.append(s)

    if not fresh_scripts:
        await msg.edit_text(
            f"❌ <b>Не найдено:</b> <code>{query}</code>\n\n"
            "Попробуй другое название или посмотри в меню.",
            reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[
                [types.InlineKeyboardButton(text="🔙 В главное меню", callback_data="menu_main")]
            ]),
        )
        return

    text = f"🌐 <b>Найдено в ScriptBlox ({len(fresh_scripts)}):</b>\n\n"
    for i, s in enumerate(fresh_scripts[:10], 1):
        title = s.get("title", "Без названия")
        game = s.get("game", {}).get("name", "?")
        code = s.get("script", "")
        text += f"<b>{i}. {title}</b>\n🎮 {game}\n<pre>{code[:200]}...</pre>\n\n"

    if len(fresh_scripts) > 10:
        text += f"<i>...и ещё {len(fresh_scripts) - 10}. Уточни запрос.</i>"

    await msg.edit_text(
        text,
        reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[
            [types.InlineKeyboardButton(text="🔙 В главное меню", callback_data="menu_main")]
        ]),
    )


@dp.callback_query(F.data.startswith("websearch_"))
async def web_search_callback(callback: types.CallbackQuery, state: FSMContext):
    query = callback.data.replace("websearch_", "")
    await callback.answer("Ищу...")
    await do_web_search(callback.message, query)


async def search_scriptblox(query: str):
    """Ищет бесплатные скрипты без ключа на ScriptBlox."""
    url = "https://scriptblox.com/api/script/search"
    params = {
        "q": query,
        "mode": "free",
        "key": 0,
        "max": 20,
        "strict": "false",
    }
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


# ============ СЧЁТЧИК ПОЛЬЗОВАТЕЛЕЙ ============
@dp.callback_query(F.data == "show_users")
async def show_users(callback: types.CallbackQuery):
    count = len(users)
    await callback.answer(f"👥 Всего пользователей: {count}", show_alert=True)


# ============ МЕНЮ BROOKHAVEN ============
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
    await callback.message.edit_text(
        "📜 Brookhaven — доступные сборки:",
        reply_markup=types.InlineKeyboardMarkup(inline_keyboard=buttons),
    )


# ============ МЕНЮ MM2 ============
@dp.callback_query(F.data == "menu_mm2")
async def menu_mm2(callback: types.CallbackQuery):
    scripts = {
        "🥷 Madara":     "code_madara",
        "🔪 Moondiety":  "code_moondiety",
        "🛡️ God mode":   "code_godmode",
    }
    buttons = [[types.InlineKeyboardButton(text=t, callback_data=d)] for t, d in scripts.items()]
    buttons.append([types.InlineKeyboardButton(text="🔙 Назад", callback_data="menu_main")])
    await callback.message.edit_text(
        "🎮 MM2 — доступные скрипты:",
        reply_markup=types.InlineKeyboardMarkup(inline_keyboard=buttons),
    )


# ============ МЕНЮ BLOX FRUITS ============
@dp.callback_query(F.data == "menu_bloxfruits")
async def menu_bloxfruits(callback: types.CallbackQuery):
    scripts = {
        "🎮 Min Gaming":     "code_bf_min",
        "🚀 Redz BETA":      "code_bf_redz",
        "🏠 BF Script":      "code_bf_basement",
        "⚡ Auto Farm":      "code_bf_autofarm",
    }
    buttons = [[types.InlineKeyboardButton(text=t, callback_data=d)] for t, d in scripts.items()]
    buttons.append([types.InlineKeyboardButton(text="🔙 Назад", callback_data="menu_main")])
    await callback.message.edit_text(
        "🍇 Blox Fruits — доступные скрипты:",
        reply_markup=types.InlineKeyboardMarkup(inline_keyboard=buttons),
    )


# ============ МЕНЮ 99 НОЧЕЙ ============
@dp.callback_query(F.data == "menu_99nights")
async def menu_99nights(callback: types.CallbackQuery):
    scripts = {
        "📜 Script 1": "code_99_1",
        "📜 Script 2": "code_99_2",
        "📜 Script 3": "code_99_3",
    }
    buttons = [[types.InlineKeyboardButton(text=t, callback_data=d)] for t, d in scripts.items()]
    buttons.append([types.InlineKeyboardButton(text="🔙 Назад", callback_data="menu_main")])
    await callback.message.edit_text(
        "🌙 99 Ночей — доступные скрипты:",
        reply_markup=types.InlineKeyboardMarkup(inline_keyboard=buttons),
    )


# ============ МЕНЮ STEAL AN EGG ============
@dp.callback_query(F.data == "menu_stealanegg")
async def menu_stealanegg(callback: types.CallbackQuery):
    scripts = {
        "📜 Script 1 (Sabs)":    "code_egg_1",
        "🎧 Lennon Hub V2":      "code_egg_2",
        "🥚 Lennon Auto-Steal":  "code_egg_3",
    }
    buttons = [[types.InlineKeyboardButton(text=t, callback_data=d)] for t, d in scripts.items()]
    buttons.append([types.InlineKeyboardButton(text="🔙 Назад", callback_data="menu_main")])
    await callback.message.edit_text(
        "🥚 Steal an Egg — доступные скрипты:\n\n"
        "🎧 <b>Lennon Hub V2</b> — топовый скрипт:\n"
        "• Авто-воровство яиц\n"
        "• Телепорт к топ-4 яйцам\n"
        "• Работает на Delta / Xeno",
        reply_markup=types.InlineKeyboardMarkup(inline_keyboard=buttons),
    )


# ============ ВОЗВРАТ В ГЛАВНОЕ МЕНЮ ============
@dp.callback_query(F.data == "menu_main")
async def menu_main(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    keyboard = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="📜 Script Brookhaven Delta", callback_data="menu_brookhaven")],
        [types.InlineKeyboardButton(text="🎮 MM2", callback_data="menu_mm2")],
        [types.InlineKeyboardButton(text="🍇 Blox Fruits", callback_data="menu_bloxfruits")],
        [types.InlineKeyboardButton(text="🌙 99 Ночей", callback_data="menu_99nights")],
        [types.InlineKeyboardButton(text="🥚 Steal an Egg", callback_data="menu_stealanegg")],
        [types.InlineKeyboardButton(text="🔍 Поиск", callback_data="menu_search")],
        [types.InlineKeyboardButton(text="👥 Пользователи", callback_data="show_users")],
        [types.InlineKeyboardButton(text="💬 Сообщество", url="https://t.me/+LBs19_JzpW0yNmZi")],
    ])
    await callback.message.edit_text(
        "🔥 Приветствую тебя!\nВыбери категорию скриптов:",
        reply_markup=keyboard,
    )


# ============ ВЫДАЧА КОДА ============
@dp.callback_query(F.data.startswith("code_"))
async def send_script_code(callback: types.CallbackQuery):
    script_name = callback.data.split("_", 1)[1]
    await callback.answer("Отправляю скрипт в ЛС ✅")
    code_to_send = SCRIPTS_CODES.get(script_name.lower(), "Скрипт не найден.")
    await bot.send_message(
        chat_id=callback.from_user.id,
        text=f"✅ Вы выбрали:\n{code_to_send}",
    )


# ============ ВЕБ-СЕРВЕР ДЛЯ RENDER ============
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
    await asyncio.gather(
        dp.start_polling(bot),
        start_web(),
    )


if __name__ == "__main__":
    asyncio.run(main())
