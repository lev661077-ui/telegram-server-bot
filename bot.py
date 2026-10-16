# telegram-server-bot
import os
from aiogram import Bot, Dispatcher, F, types
from aiogram.client.default import DefaultBotProperties

TOKEN = os.getenv("BOT_TOKEN")

bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
dp = Dispatcher()


@dp.message(F.text == "/start")
async def start(message: types.Message):
    keyboard = [
        [types.InlineKeyboardButton(text="📜 Script Brookhaven Delta", callback_data="open_scripts")]
    ]
    await message.answer(
        "🔥 Приветствую тебя!\nВыбери нужный скрипт:",
        reply_markup=types.InlineKeyboardMarkup(inline_keyboard=keyboard),
    )


@dp.callback_query(F.data == "open_scripts")
async def show_scripts_list(callback: types.CallbackQuery):
    scripts_buttons = {
        "🔥 Redz9999 2026": "code_redz",
        "🚀 Lord-Kaiser":   "code_lord",
        "🌐 LOLA HUB":      "code_lola",
        "🎧 Saiki Music":   "code_saiki",
    }

    inline_buttons = []
    for text, data in scripts_buttons.items():
        inline_buttons.append([types.InlineKeyboardButton(text=text, callback_data=data)])

    await callback.message.edit_text(
        "Доступные сборки:",
        reply_markup=types.InlineKeyboardMarkup(inline_keyboard=inline_buttons),
    )


@dp.callback_query(F.data.startswith("code_"))
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

    await bot.send_message(
        chat_id=callback.from_user.id,
        text=f"✅ Вы выбрали:\n{code_to_send}",
    )


if __name__ == "__main__":
    dp.run_polling(bot)
