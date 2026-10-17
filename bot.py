def main_menu_kb(uid):
    status = "⭐ Премиум" if is_premium(uid) else "🆓 Бесплатно"
    sp_data = load_sponsors()
    sp_status = ""
    if str(uid) in sp_data:
        if sp_data[str(uid)]["level"] == "gold": sp_status = " 🌟"
        elif sp_data[str(uid)]["level"] == "bronze": sp_status = " 🥉"

    return types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="📜 Brookhaven", callback_data="menu_brookhaven")],
        [types.InlineKeyboardButton(text="🎮 MM2", callback_data="menu_mm2")],
        [types.InlineKeyboardButton(text="🍇 Blox Fruits", callback_data="menu_bloxfruits")],
        [types.InlineKeyboardButton(text="🌙 99 Ночей", callback_data="menu_99nights")],
        [types.InlineKeyboardButton(text="🥚 Steal an Egg", callback_data="menu_stealanegg")],
        [types.InlineKeyboardButton(text="🔍 Поиск", callback_data="menu_search")],
        [types.InlineKeyboardButton(text="🛒 Магазин", callback_data="shop")],
        [types.InlineKeyboardButton(text="🎁 Промокод", callback_data="enter_promo")],
        [types.InlineKeyboardButton(text=f"💎 Стать спонсором{sp_status}", callback_data="donate_menu")],
        [types.InlineKeyboardButton(text=f"⭐ Премиум ({status})", callback_data="buy_premium")],
        [types.InlineKeyboardButton(text="👥 Пользователи", callback_data="show_users")],
        [types.InlineKeyboardButton(text="💬 Сообщество", url="https://t.me/+LBs19_JzpW0yNmZi")],
    ])
