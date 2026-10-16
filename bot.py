import os
import asyncio
from aiohttp import web
from aiogram import Bot, Dispatcher, F, types
from aiogram.client.default import DefaultBotProperties

TOKEN = os.getenv("BOT_TOKEN")

bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
dp = Dispatcher()


# ============ ГЛАВНОЕ МЕНЮ ============
@dp.message(F.text == "/start")
async def start(message: types.Message):
    keyboard = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="📜 Script Brookhaven Delta", callback_data="menu_brookhaven")],
        [types.InlineKeyboardButton(text="🎮 MM2", callback_data="menu_mm2")],
    ])
    await message.answer(
        "🔥 Приветствую тебя!\nВыбери категорию скриптов:",
        reply_markup=keyboard,
    )


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


# ============ ВОЗВРАТ В ГЛАВНОЕ МЕНЮ ============
@dp.callback_query(F.data == "menu_main")
async def menu_main(callback: types.CallbackQuery):
    keyboard = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="📜 Script Brookhaven Delta", callback_data="menu_brookhaven")],
        [types.InlineKeyboardButton(text="🎮 MM2", callback_data="menu_mm2")],
    ])
    await callback.message.edit_text(
        "🔥 Приветствую тебя!\nВыбери категорию скриптов:",
        reply_markup=keyboard,
    )


# ============ ВЫДАЧА КОДА ============
@dp.callback_query(F.data.startswith("code_"))
async def send_script_code(callback: types.CallbackQuery):
    script_name = callback.data.split("_", 1)[1]

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
    }

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
