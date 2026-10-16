import os
from aiogram import Bot, Dispatcher, types, executor
from aiohttp import web
import asyncio

TOKEN = os.getenv("BOT_TOKEN")

bot = Bot(token=TOKEN, parse_mode="HTML")
dp = Dispatcher()


@dp.message_handler(commands=["start"])
async def start(message: types.Message):
    keyboard = types.InlineKeyboardMarkup(row_width=1)
    keyboard.add(types.InlineKeyboardButton(text="📜 Script Brookhaven Delta", callback_data="open_scripts"))
    await message.answer(
        "🔥 Приветствую тебя!\nВыбери нужный скрипт:",
        reply_markup=keyboard,
    )


@dp.callback_query_handler(lambda c: c.data == "open_scripts")
async def show_scripts_list(callback: types.CallbackQuery):
    scripts_buttons = {
        "🔥 Redz9999 2026": "code_redz",
        "🚀 Lord-Kaiser":   "code_lord",
        "🌐 LOLA HUB":      "code_lola",
        "🎧 Saiki Music":   "code_saiki",
    }
    keyboard = types.InlineKeyboardMarkup(row_width=1)
    for text, data in scripts_buttons.items():
        keyboard.add(types.InlineKeyboardButton(text=text, callback_data=data))
    await callback.message.edit_text("Доступные сборки:", reply_markup=keyboard)


@dp.callback_query_handler(lambda c: c.data.startswith("code_"))
async def send_script_code(callback: types.CallbackQuery):
    script_name = callback.data.split("_")[1]

    SCRIPTS_CODES = {
        "redz":  "<pre>loadstring(game:HttpGet('https://pastebin.com/raw/1r7cEW7G'))()</pre>",
        "lord":  "<pre>loadstring(game:HttpGet(\"https://raw.githubusercontent.com/SUPREMEAURA350/KAISER-VERSION-2-/refs/heads/main/Kaiserspam\"))()</pre>",
        "lola":  "<pre>loadstring(game:HttpGet(\"https://raw.githubusercontent.com/niriel015/Painel-LolaHub/refs/heads/main/Lola-hub-ne-pai\"))()</pre>",
        "saiki": "<pre>loadstring(game:HttpGet(\"https://raw.githubusercontent.com/SaikiWithTheBanHammer/ScriptBlox/main/LifeIsDisasterIndeedLol\"))()</pre>",
    }
    await callback.answer("Отправляю скрипт в ЛС ✅")
    code_to_send = SCRIPTS_CODES.get(script_name.lower(), "Скрипт не найден.")
    await bot.send_message(chat_id=callback.from_user.id, text=f"✅ Вы выбрали:\n{code_to_send}")


# --- Мини-веб-сервер для Render ---
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


async def on_startup(dp):
    asyncio.create_task(start_web())


if __name__ == "__main__":
    executor.start_polling(dp, on_startup=on_startup, skip_updates=True)
