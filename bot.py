import os, asyncio, re, random, string, aiohttp, csv, io
from datetime import datetime, timedelta
from aiohttp import web
from aiogram import Bot, Dispatcher, F, types
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import LabeledPrice, PreCheckoutQuery, BufferedInputFile

TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = 123456789  # ВСТАВЬ СВОЙ ID
SPONSOR_ID = 111111111  # ВСТАВЬ ID СПОНСОРА
P_PRICE, F_PRICE, FREE_L, PREM_L, ROLL_PRICE = 30, 10, 5, 15, 5
SUB_PRICE = 100

bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
dp = Dispatcher(storage=MemoryStorage())
UF, PF, FF, TF, DF, SF, PRF, SPF, SUBF, SFF = "u.txt", "p.txt", "f.txt", "t.txt", "d.txt", "s.txt", "pr.txt", "sp.txt", "sub.txt", "sf.txt"

last_search = {}

def ls(f):
    return set(l.strip() for l in open(f)) if os.path.exists(f) else set()

def ss(f, d):
    with open(f, "w", encoding="utf-8") as file:
        for i in d: file.write(f"{i}\n")

def ld(f, c):
    d = {}
    if os.path.exists(f):
        with open(f, "r", encoding="utf-8") as file:
            for l in file:
                p = l.strip().split("|")
                if len(p) == c: d[p[0]] = p[1:]
    return d

def sd(f, d):
    with open(f, "w", encoding="utf-8") as file:
        for k, v in d.items(): file.write(f"{k}|" + "|".join(str(x) for x in v) + "\n")

def lsp():
    d = {}
    if os.path.exists(SPF):
        with open(SPF, "r", encoding="utf-8") as file:
            for l in file:
                p = l.strip().split("|")
                if len(p) == 3: d[p[0]] = {"level": p[1], "last_claimed": p[2]}
    return d

def ssp(d):
    with open(SPF, "w", encoding="utf-8") as file:
        for u, v in d.items(): file.write(f"{u}|{v['level']}|{v['last_claimed']}\n")

users, prem = ls(UF), ls(PF)
frz, dis = ls(FF), ls(DF)

def is_p(u):
    return str(u) == str(ADMIN_ID) or str(u) in prem

def has_sp(u):
    if is_p(u): return True
    t = ld(TF, 2)
    if str(u) in t:
        try:
            if datetime.fromisoformat(t[str(u)][0]) > datetime.now(): return True
        except: pass
    return False

def has_f(u):
    return str(u) == str(ADMIN_ID) or str(u) in prem or str(u) in frz

def gen():
    return "PROMO-" + "".join(random.choices(string.ascii_uppercase + string.digits, k=8))

def add_promo(u, pt, v, d=3):
    pr = ld(PRF, 6)
    act = [k for k, v_ in pr.items() if v_[2] == u and v_[3] == "no" and (v_[4] == "inf" or datetime.fromisoformat(v_[4]) > datetime.now())]
    if len(act) >= 10 and str(u) != str(ADMIN_ID): return None
    c = gen()
    exp = (datetime.now() + timedelta(days=d)).isoformat() if d > 0 else "inf"
    pr[c] = [pt, str(v), str(u), "no", exp]
    sd(PRF, pr)
    return c

def get_active_promos(u):
    pr = ld(PRF, 6)
    return {k: v for k, v in pr.items() if v[2] == u and v[3] == "no" and (v[4] == "inf" or datetime.fromisoformat(v[4]) > datetime.now())}

class SS(StatesGroup): wait = State()
class PS(StatesGroup): wait = State()
class DS(StatesGroup): wait = State()
class FS(StatesGroup): wait_name = State(); wait_query = State()

SC = {
    "redz": "loadstring(game:HttpGet('https://pastebin.com/raw/1r7cEW7G'))()",
    "lord": "loadstring(game:HttpGet(\"https://raw.githubusercontent.com/SUPREMEAURA350/KAISER-VERSION-2-/refs/heads/main/Kaiserspam\"))()",
    "lola": "loadstring(game:HttpGet(\"https://raw.githubusercontent.com/niriel015/Painel-LolaHub/refs/heads/main/Lola-hub-ne-pai\"))()",
    "saiki": "loadstring(game:HttpGet(\"https://raw.githubusercontent.com/SaikiWithTheBanHammer/ScriptBlox/main/LifeIsDisasterIndeedLol\"))()",
    "madara": "loadstring(game:HttpGet(\"https://raw.githubusercontent.com/IsThisMe01/Project-Madara/refs/heads/main/mm22.lua\"))()",
    "moondiety": "loadstring(game:HttpGet(\"https://scriptblox.com/raw/Murder-Mystery-2-KEYLESS-InstaWin-AutoFarm-Kill-all-XRay-nd-more-by-Moondiety-48644\"))()",
    "godmode": "loadstring(game:HttpGet(\"https://pastefy.app/a2dAk154/raw\"))()",
    "bf_min": "loadstring(game:HttpGet(\"https://raw.githubusercontent.com/LuaCrack/Min/refs/heads/main/MinXt2Eng\"))()",
    "bf_redz": "local Settings = { JoinTeam = \"Pirates\", Translator = true }\ngetgenv().BETA_VERSION = true\nloadstring(game:HttpGet(\"https://raw.githubusercontent.com/tlredz/Scripts/refs/heads/main/main.luau\"))(Settings)",
    "bf_basement": "loadstring(game:HttpGet(\"https://raw.githubusercontent.com/Cazzanos/The-basement/main/Basement%20hub\", true))()",
    "bf_autofarm": "loadstring(game:HttpGetAsync(\"https://raw.githubusercontent.com/indexeduu/BF-NewVer/refs/heads/main/V3New.lua\"))()",
    "99_1": "loadstring(game:HttpGet(\"https://api.luarmor.net/files/v3/loaders/705e9a93cc18214fb77ab95686a8dba9.lua\"))()",
    "99_2": "KEY - 111222HHH\n\nloadstring(game:HttpGet(\"https://raw.githubusercontent.com/caomod2077/Script/refs/heads/main/FoxnameHub.lua\"))()",
    "99_3": "loadstring(game:HttpGet(\"https://ntt-hub.xyz/api/repo?id1=main&id2=lua\"))()",
    "egg_1": "loadstring(game:HttpGet(\"https://raw.githubusercontent.com/sabscrip-arch/srver/refs/heads/main/Stealanegg\"))()",
    "egg_2": "loadstring(game:HttpGet(\"https://raw.githubusercontent.com/lennonxscripts/lennonhubv2/refs/heads/main/stealaneggv2\"))()",
    "egg_3": "loadstring(game:HttpGet(\"https://raw.githubusercontent.com/lennonxscripts/lennonhubv2/refs/heads/main/stealaneggv2\"))()"
}

def kb(u):
    st = "⭐ Премиум" if is_p(u) else "🆓 Бесплатно"
    sp = lsp()
    s = " 🌟" if str(u) in sp and sp[str(u)]["level"] == "gold" else (" 🥉" if str(u) in sp and sp[str(u)]["level"] == "bronze" else "")
    sub = ld(SUBF, 2)
    sub_st = " ✅" if str(u) in sub else ""
    return types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="📜 Brookhaven", callback_data="mbh")],
        [types.InlineKeyboardButton(text="🎮 MM2", callback_data="mmm")],
        [types.InlineKeyboardButton(text="🍇 Blox Fruits", callback_data="mbf")],
        [types.InlineKeyboardButton(text="🌙 99 Ночей", callback_data="m99")],
        [types.InlineKeyboardButton(text="🥚 Steal an Egg", callback_data="meg")],
        [types.InlineKeyboardButton(text="🔍 Поиск", callback_data="ms")],
        [types.InlineKeyboardButton(text="📁 Мои фильтры", callback_data="sf_menu")],
        [types.InlineKeyboardButton(text="🎲 Рулетка (5⭐)", callback_data="roul")],
        [types.InlineKeyboardButton(text="🛒 Магазин", callback_data="shop")],
        [types.InlineKeyboardButton(text=f"💎 Подписка{sub_st}", callback_data="sub_menu")],
        [types.InlineKeyboardButton(text="🎁 Промокод", callback_data="ep")],
        [types.InlineKeyboardButton(text=f"💎 Спонсор{s}", callback_data="dm")],
        [types.InlineKeyboardButton(text=f"⭐ Премиум ({st})", callback_data="bp")],
        [types.InlineKeyboardButton(text="👥 Юзеры", callback_data="su")],
        [types.InlineKeyboardButton(text="💬 Соцсети", url="https://t.me/+LBs19_JzpW0yNmZi")]
    ])  # <--- Закрываем клавиатуру и ставим Enter

@dp.message(F.text == "/start")  # <--- Декоратор начинается с новой строки
async def start(m, state):
    await state.clear()
    u = str(m.from_user.id)
    n = u not in users
    if n:
        users.add(u); ss(UF, users)
    t = "🔥 <b>Привет!</b>\n\n"
    if n:
        add_promo(u, "trial", 3, 3)
        t += f"🎁 <b>Ты новичок! Держи подарок:</b>\nПромокод на 3 дня рулетки в /mycodes\n\n"
    
    subs = ld(SUBF, 2)
    if u in subs:
        last_sub = datetime.fromisoformat(subs[u][0])
        now = datetime.now()
        if (now - last_sub).days >= 2:
            for _ in range(3):
                r_type = random.choices(["prem", "discount", "trial"], weights=[10, 60, 30])[0]
                if r_type == "prem": add_promo(u, "trial", 1, 1)
                elif r_type == "discount": add_promo(u, "discount", random.choice([15, 20, 30, 40, 50]), 3)
                else: add_promo(u, "trial", 5 if random.random() < 0.2 else 3, 3)
            subs[u][0] = now.isoformat()
            sd(SUBF, subs)
            t += "💎 <b>Подписка активна!</b>\nТвои 3 промокода готовы. Напиши /mycodes.\n\n"
            
    sp = lsp()
    if u in sp:
        l = sp[u]["level"]
        la = datetime.fromisoformat(sp[u]["last_claimed"]) if sp[u]["last_claimed"] else datetime(2000, 1, 1)
        now = datetime.now()
        rg = False
        if l == "gold" and (now - la).days >= 1:
            for _ in range(random.randint(1, 2)):
                add_promo(u, random.choice(["trial", "discount"]), 3 if random.random() > 0.5 else 50, 3)
            sp[u]["last_claimed"] = now.isoformat()
            rg = True
            t += "🌟 <b>Спонсор!</b>\nТвои промокоды готовы. Напиши /mycodes.\n\n"
        elif l == "bronze" and (now - la).days >= 3:
            add_promo(u, random.choice(["trial", "discount"]), 3 if random.random() > 0.5 else 50, 3)
            sp[u]["last_claimed"] = now.isoformat()
            rg = True
            t += "🥉 <b>Бронзовый спонсор!</b>\nТвой промокод готов. Напиши /mycodes.\n\n"
        if rg: ssp(sp)
            
    await m.answer(t + "Выбери категорию:", reply_markup=kb(u))

@dp.message(F.text == "/mycodes")
async def my_codes(m):
    u = str(m.from_user.id)
    act = get_active_promos(u)
    if not act: return await m.answer("Нет активных промокодов.")
    text = "🎁 <b>Твои промокоды:</b>\n\n"
    for c, i in act.items():
        exp = "бессрочно" if i[4] == "inf" else i[4][:10]
        if i[0] == 'discount': text += f"<code>{c}</code> — 💰 Скидка {i[1]}% (до {exp})\n"
        else: text += f"<code>{c}</code> — ⭐ Рулетка {i[1]}д (до {exp})\n"
    await m.answer(text, reply_markup=kb(u))

@dp.callback_query(F.data == "sf_menu")
async def sf_menu(cb):
    u = str(cb.from_user.id)
    sff = ld(SFF, 4)
    my_filters = {k: v for k, v in sff.items() if v[0] == u}
    b = []
    for k, v in my_filters.items():
        b.append([types.InlineKeyboardButton(text=f"🔍 {v[1]}", callback_data=f"sf_use_{k}")])
    b.append([types.InlineKeyboardButton(text="➕ Сохранить новый фильтр", callback_data="sf_add")])
    b.append([types.InlineKeyboardButton(text="🔙 Меню", callback_data="mm")])
    await cb.message.edit_text("📁 <b>Мои фильтры поиска</b>", reply_markup=types.InlineKeyboardMarkup(inline_keyboard=b))

@dp.callback_query(F.data == "sf_add")
async def sf_add(cb, state):
    await cb.message.edit_text("Введи название для фильтра (например: 'ММ2 Автофарм'):")
    await state.set_state(FS.wait_name)

@dp.message(FS.wait_name)
async def sf_name(m, state):
    await state.update_data(name=m.text)
    await m.answer("Теперь введи поисковый запрос:")
    await state.set_state(FS.wait_query)

@dp.message(FS.wait_query)
async def sf_query(m, state):
    data = await state.get_data()
    name = data['name']
    u = str(m.from_user.id)
    sff = ld(SFF, 4)
    key = gen()[:8]
    sff[key] = [u, name, m.text, "no"]
    sd(SFF, sff)
    await state.clear()
    await m.answer(f"✅ Фильтр '{name}' сохранен!", reply_markup=kb(u))

@dp.callback_query(F.data.startswith("sf_use_"))
async def sf_use(cb, state):
    k = cb.data.split("_")[2]
    sff = ld(SFF, 4)
    if k not in sff: return await cb.answer("❌ Не найден.")
    q = sff[k][2]
    await cb.message.answer(f"🔎 Запускаю поиск по фильтру: {q}")
    await state.update_data(query=q)
    await run_search(cb.message, state, str(cb.from_user.id))

@dp.callback_query(F.data == "ms")
async def ms(cb, state):
    subs = ld(SUBF, 2)
    is_sub = str(cb.from_user.id) in subs
    limit = 20 if is_sub else (PREM_L if has_sp(cb.from_user.id) else FREE_L)
    await cb.message.edit_text(f"🔍 Поиск (до {limit}):", reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[[types.InlineKeyboardButton(text="❌ Отмена", callback_data="mm")]]))
    await state.set_state(SS.wait)

@dp.message(SS.wait)
async def ps(m, state):
    await state.update_data(query=m.text.strip().lower())
    await run_search(m, state, str(m.from_user.id))
    await state.clear()

async def run_search(m, state, u):
    data = await state.get_data()
    q = data.get('query', '')
    if not q: return
    
    subs = ld(SUBF, 2)
    is_sub = str(u) in subs
    l = 20 if is_sub else (PREM_L if has_sp(u) else FREE_L)
    
    msg = await m.answer(f"🔎 Ищу: {q}...")
    a = await s1(q)
    if "mm2" in q or "murder" in q: a.extend(await s2()); a.extend(await s3())
    if is_sub: a.extend(await s4())
        
    if not a: return await msg.edit_text("❌ Не найдено.")
        
    s = set()
    f = [x for x in a if x.get("title", "").lower() not in s and not s.add(x.get("title", "").lower())]
    
    text = f"🌐 Найдено ({len(f)}):\n\n"
    csv_data = "Title,Game,Script\n"
    for i, x in enumerate(f[:l], 1):
        title = x.get('title','?')
        game = x.get('game',{}).get('name','?')
        script = x.get('script','')
        text += f"<b>{i}. {title}</b>\n🎮 {game}\n<pre>{script[:150]}...</pre>\n\n"
        csv_data += f'"{title}","{game}","{script.replace(chr(10), " ")}"\n'
        
    last_search[u] = csv_data
    k = []
    if len(f) > 1: k.append([types.InlineKeyboardButton(text="📥 Экспорт в CSV", callback_data="export_csv")])
    k.append([types.InlineKeyboardButton(text="🔙 Меню", callback_data="mm")])
    await msg.edit_text(text, reply_markup=types.InlineKeyboardMarkup(inline_keyboard=k))

@dp.callback_query(F.data == "export_csv")
async def export_csv(cb):
    u = str(cb.from_user.id)
    if u not in last_search: return await cb.answer("❌ Нет данных.")
    file = BufferedInputFile(last_search[u].encode(), filename="scripts.csv")
    await bot.send_document(chat_id=u, document=file, caption="Ваши скрипты в CSV")
    await cb.answer()

@dp.callback_query(F.data.startswith("c_"))
async def c(cb):
    n = cb.data.split("_", 1)[1]
    u = cb.from_user.id
    if n == "frz":
        if not has_f(u):
            await cb.answer("❄️ Платный!", show_alert=True)
            markup = types.InlineKeyboardMarkup(inline_keyboard=[[types.InlineKeyboardButton(text="⭐ Купить", callback_data="bf")]])
            return await bot.send_message(u, "❄️ <b>Заморозка</b>\nСтоимость: 10⭐", reply_markup=markup)
        await cb.answer("Отправляю ✅")
        text = "❄️ <b>Заморозка</b>\n\n<pre>loadstring(game:HttpGet(\"https://cdn.sourceb.in/bins/9MHwJQNJkm/0\"))()</pre>\n<pre>loadstring(game:HttpGet('https://raw.githubusercontent.com/txnic255/MM2-FREEZE-TRADE-V5.5-NEWEST-GUI-SCRIPT-/refs/heads/main/SCRIPT%20V5.5%20GUI%20AND%20SCRIPT'))()</pre>"
        return await bot.send_message(u, text)
    code = SC.get(n)
    if not code: return await cb.answer("❌ Ошибка", show_alert=True)
    await cb.answer("Отправляю ✅")
    markup = types.InlineKeyboardMarkup(inline_keyboard=[[types.InlineKeyboardButton(text="📋 Скопировать", copy_text=types.CopyTextButton(text=code))]])
    await bot.send_message(u, f"✅ <b>Твой скрипт:</b>\n\n<pre>{code}</pre>", reply_markup=markup)

@dp.callback_query(F.data == "dm")
async def dm(cb):
    b = [[types.InlineKeyboardButton(text=f"{a}⭐", callback_data=f"d_{a}") for a in [10, 25, 50]],[types.InlineKeyboardButton(text=f"{a}⭐", callback_data=f"d_{a}") for a in [100, 250, 500]],[types.InlineKeyboardButton(text="1000⭐", callback_data="d_1000")],[types.InlineKeyboardButton(text="✏️ Своя", callback_data="dc")],[types.InlineKeyboardButton(text="🔙 Назад", callback_data="mm")]]
    await cb.message.edit_text("💎 <b>Стать спонсором</b>", reply_markup=types.InlineKeyboardMarkup(inline_keyboard=b))

@dp.callback_query(F.data.startswith("d_") & ~F.data.in_({"dm", "dc"}))
async def pd(cb):
    a = int(cb.data.split("_")[1])
    await bot.send_invoice(chat_id=cb.from_user.id, title="Донат", description=f"{a}⭐", payload=f"d_{a}", provider_token="", currency="XTR", prices=[LabeledPrice(label="Донат", amount=a)])
    await cb.answer()

@dp.callback_query(F.data == "dc")
async def dc(cb, state):
    await cb.message.edit_text("💎 Введи сумму (1-1000):")
    await state.set_state(DS.wait)

@dp.message(DS.wait)
async def pcd(m, state):
    await state.clear()
    try:
        a = int(m.text)
        if a < 1 or a > 1000: raise ValueError
        await bot.send_invoice(chat_id=m.from_user.id, title="Донат", description=f"{a}⭐", payload=f"d_{a}", provider_token="", currency="XTR", prices=[LabeledPrice(label="Донат", amount=a)])
    except: await m.answer("❌ Неверно.")

def gs():
    it = []
    discounts = [5, 10, 15, 20, 30, 50]
    for _ in range(10):
        t = random.choice(["discount", "trial3", "trial5"])
        if t == "discount": it.append(f"{gen()}|discount_{random.choice(discounts)}|3|no|{datetime.now().isoformat()}|inf")
        elif t == "trial3": it.append(f"{gen()}|trial3|7|no|{datetime.now().isoformat()}|inf")
        else: it.append(f"{gen()}|trial5|10|no|{datetime.now().isoformat()}|inf")
    with open(SF, "w", encoding="utf-8") as f: f.write("\n".join(it))

def gsh():
    it = []
    if os.path.exists(SF):
        with open(SF, "r", encoding="utf-8") as file:
            for l in file:
                p = l.strip().split("|")
                if len(p) == 6: it.append({"code": p[0], "type": p[1], "price": int(p[2]), "bought": p[3], "created": p[4], "exp": p[5]})
    return it

@dp.callback_query(F.data == "shop")
async def shop(cb):
    u = cb.from_user.id
    if not os.path.exists(SF): gs()
    it = gsh()
    k = []
    for i in it:
        if i["bought"] == "yes": continue
        if i["type"].startswith("discount"): ti = f"💰 Скидка {i['type'].split('_')[1]}%"
        elif i["type"] == "trial3": ti = "⭐ Рулетка 3д"
        else: ti = "⭐ Рулетка 5д"
        prefix = "👑 " if str(u) == str(ADMIN_ID) else ""
        cb_data = f"freebp_{i['code']}" if str(u) == str(ADMIN_ID) else f"bp_{i['code']}"
        k.append([types.InlineKeyboardButton(text=f"{prefix}{ti} — {i['price']}⭐", callback_data=cb_data)])
    k.extend([[types.InlineKeyboardButton(text="🔄 Обновить", callback_data="refresh_shop")], [types.InlineKeyboardButton(text="🔙 Меню", callback_data="mm")]])
    await cb.message.edit_text("🛒 <b>Магазин</b>", reply_markup=types.InlineKeyboardMarkup(inline_keyboard=k))

@dp.callback_query(F.data == "refresh_shop")
async def refresh_shop(cb):
    gs(); await shop(cb)

@dp.callback_query(F.data.startswith("freebp_"))
async def freebp(cb):
    u = str(cb.from_user.id)
    if u != str(ADMIN_ID): return await cb.answer("❌ Вы не админ!", show_alert=True)
    c = cb.data.split("_", 1)[1]
    it = gsh()
    item = next((x for x in it if x["code"] == c), None)
    if not item or item["bought"] == "yes": return await cb.answer("❌ Товар не найден.", show_alert=True)
    item["bought"] = "yes"
    with open(SF, "w", encoding="utf-8") as f:
        for x in it: f.write(f"{x['code']}|{x['type']}|{x['price']}|{x['bought']}|{x['created']}|{x.get('exp', 'inf')}\n")
    if item["type"].startswith("discount"): pt, v = "discount", item["type"].split("_", 1)[1]
    else: pt = "trial"; v = "3" if item["type"] == "trial3" else "5"
    promo = add_promo(u, pt, v, 3)
    if not promo: return await cb.answer("❌ Ошибка создания промо.", show_alert=True)
    await cb.answer("✅ Забрано!", show_alert=True)
    await cb.message.edit_text(f"👑 <b>Промокод забран!</b>\nКод: <code>{promo}</code>", reply_markup=kb(u))

@dp.callback_query(F.data.startswith("bp_"))
async def bp(cb):
    c = cb.data.split("_")[1]
    it = gsh()
    i = next((x for x in it if x["code"] == c), None)
    if not i or i["bought"] == "yes": return await cb.answer("❌ Продан!", show_alert=True)
    await bot.send_invoice(chat_id=cb.from_user.id, title="Промокод", description=f"Код на {i['type']}", payload=f"p_{c}", provider_token="", currency="XTR", prices=[LabeledPrice(label="Код", amount=i["price"])])

@dp.callback_query(F.data == "ep")
async def ep(cb, state):
    await cb.message.edit_text("🎁 Введи промокод:", reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[[types.InlineKeyboardButton(text="❌ Отмена", callback_data="mm")]]))
    await state.set_state(PS.wait)

@dp.message(PS.wait)
async def pp(m, state):
    await state.clear()
    u = str(m.from_user.id)
    c = m.text.strip().upper()
    pr = ld(PRF, 6)
    if c not in pr: return await m.answer("❌ Не найден.", reply_markup=kb(u))
    pt, v, us, used, exp = pr[c]
    if used != "no": return await m.answer("❌ Активирован.", reply_markup=kb(u))
    if exp != "inf" and datetime.fromisoformat(exp) < datetime.now(): return await m.answer("❌ Истек срок.", reply_markup=kb(u))
    if pt == "discount":
        dis.add(f"{u}|{v}"); ss(DF, dis)
        await m.answer(f"✅ Скидка {v}%!", reply_markup=kb(u))
    elif pt == "trial":
        t = ld(TF, 2); t[u] = [(datetime.now() + timedelta(days=int(v))).isoformat()]; sd(TF, t)
        await m.answer(f"✅ Рулетка на {v} дней!", reply_markup=kb(u))
    pr[c] = [pt, v, u, "yes", exp]
    sd(PRF, pr)

@dp.callback_query(F.data == "roul")
async def roul(cb):
    u = str(cb.from_user.id)
    if not ((u == str(ADMIN_ID)) or (u in ld(TF, 2))):
        await bot.send_invoice(chat_id=u, title="🎲 Рулетка", description="5 админ-скриптов за 5⭐", payload="roulette", provider_token="", currency="XTR", prices=[LabeledPrice(label="Рулетка", amount=ROLL_PRICE)])
    else:
        await cb.message.answer("🎲 Крутим...")
        await give_roulette_prize(cb.message, u)

async def give_roulette_prize(m, u):
    msg = await m.answer("🔎 Ищу...")
    queries = ["Infinite Yield", "Dark Dex", "Nameless Admin", "Simple Spy"]
    found = []
    random.shuffle(queries)
    for q in queries[:3]:
        try:
            res = await s1(q)
            if res: found.extend(res[:2])
        except: pass
    if not found: found = [{"title": "Infinite Yield", "script": "loadstring(game:HttpGet('https://raw.githubusercontent.com/EdgeIY/infiniteyield/master/source'))()"}]
    text = "🎰 <b>Твой выигрыш:</b>\n\n" + "".join([f"<b>{i}. {s.get('title','?')}</b>\n<pre>{s.get('script','')}</pre>\n\n" for i, s in enumerate(found[:5], 1)])
    await msg.edit_text(text, reply_markup=kb(u))

@dp.pre_checkout_query()
async def pcq(q):
    await bot.answer_pre_checkout_query(q.id, ok=True)

@dp.message(F.successful_payment)
async def sp(m):
    u, p = str(m.from_user.id), m.successful_payment.invoice_payload
    if p == "prem":
        prem.add(u); ss(PF, prem)
        for d in list(dis):
            if d.startswith(f"{u}|"): dis.remove(d)
        ss(DF, dis)
        await m.answer("⭐ Спасибо за Премиум!", reply_markup=kb(u))
    elif p == "frz":
        frz.add(u); ss(FF, frz)
        await m.answer("❄️ Спасибо!", reply_markup=kb(u))
    elif p == "sub_access":
        subs = ld(SUBF, 2); subs[u] = [datetime.now().isoformat()]; sd(SUBF, subs)
        await m.answer("💎 <b>Подписка оформлена!</b>", reply_markup=kb(u))
    elif p == "roulette": await give_roulette_prize(m, u)
    elif p.startswith("d_"):
        a = int(p.split("_")[1]); spd = lsp(); l = "gold" if a >= 25 else ("bronze" if 5 <= a <= 10 else "none")
        if l != "none":
            spd[u] = {"level": l, "last_claimed": "2000-01-01T00:00:00"}; ssp(spd)
            await m.answer(f"💎 Спасибо за {a}⭐!\n🌟 Статус: {l.upper()}", reply_markup=kb(u))
        else: await m.answer(f"💎 Спасибо за {a}⭐!", reply_markup=kb(u))
    elif p.startswith("p_"):
        c = p.split("_", 1)[1]; it = gsh()
        for i in it:
            if i["code"] == c: i["bought"] = "yes"
        with open(SF, "w", encoding="utf-8") as f:
            for x in it: f.write(f"{x['code']}|{x['type']}|{x['price']}|{x['bought']}|{x['created']}|{x.get('exp', 'inf')}\n")
        i = next((x for x in it if x["code"] == c), None)
        if i:
            pt, v = ("discount", i["type"].split("_")[1]) if i["type"].startswith("discount") else ("trial", "3" if i["type"] == "trial3" else "5")
            add_promo(u, pt, v, 3)
            await m.answer(f"✅ Куплено!\nКод: {c}", reply_markup=kb(u))

@dp.callback_query(F.data == "bp")
async def bpr(cb):
    if is_p(cb.from_user.id): return await cb.answer("✅ Уже есть!", show_alert=True)
    max_disc = 0; u = str(cb.from_user.id)
    for d in dis:
        if d.startswith(f"{u}|"): max_disc = max(max_disc, int(d.split("|")[1]))
    pr = int(P_PRICE * (1 - max_disc / 100))
    await bot.send_invoice(chat_id=cb.from_user.id, title="⭐ Премиум", description=f"Скидка {max_disc}%" if max_disc > 0 else "15 скриптов", payload="prem", provider_token="", currency="XTR", prices=[LabeledPrice(label="Премиум", amount=pr)])

@dp.callback_query(F.data == "bf")
async def bf(cb):
    if has_f(cb.from_user.id): return await cb.answer("✅ Уже есть!", show_alert=True)
    await bot.send_invoice(chat_id=cb.from_user.id, title="❄️ Заморозка", description="MM2", payload="frz", provider_token="", currency="XTR", prices=[LabeledPrice(label="Заморозка", amount=F_PRICE)])

async def s1(q):
    try:
        async with aiohttp.ClientSession() as s:
            async with s.get("https://scriptblox.com/api/script/search", params={"q": q, "mode": "free", "key": 0, "max": 20, "strict": "true"}, timeout=10, headers={"User-Agent": "Mozilla"}) as r:
                if r.status == 200: return (await r.json()).get("result", {}).get("scripts", [])
    except: pass
    return []

async def s2():
    try:
        async with aiohttp.ClientSession() as s:
            async with s.get("https://cheater.fun/hacks_roblox/7931-murder-mystery-2-scripts.html", timeout=10, headers={"User-Agent": "Mozilla"}) as r:
                if r.status == 200: return [{"title": x[0].strip(), "script": f'loadstring(game:HttpGet("{x[1]}"))()', "game": {"name": "MM2"}} for x in re.findall(r'###\s*(.*?)\n.*?loadstring\(game:HttpGet\("([^"]+)"\)\)\(\)', await r.text())]
    except: pass
    return []

async def s3():
    try:
        async with aiohttp.ClientSession() as s:
            async with s.get("https://bo3.gg/games/articles/murder-mystery-2-scripts", timeout=10, headers={"User-Agent": "Mozilla"}) as r:
                if r.status == 200: return [{"title": x[0].strip(), "script": f'loadstring(game:HttpGet("{x[1]}"))()', "game": {"name": "MM2"}} for x in re.findall(r'([^\n<]{5,60}?)\s*loadstring\(game:HttpGet\([\'"]([^\'"]+)[\'"]\)\)\(\)', await r.text())]
    except: pass
    return []

async def s4():
    try:
        async with aiohttp.ClientSession() as s:
            async with s.get("https://deltascripts.org/", timeout=10, headers={"User-Agent": "Mozilla"}) as r:
                if r.status == 200:
                    html = await r.text(); m = re.findall(r'<h2[^>]*>(.*?)</h2>', html)
                    return [{"title": x.strip(), "script": "loadstring(game:HttpGet('https://deltascripts.org/'))()", "game": {"name": "Delta"}} for x in m[:5]]
    except: pass
    return []

@dp.callback_query(F.data == "mbh")
async def mbh(cb):
    b = [[types.InlineKeyboardButton(text=t, callback_data=d)] for t, d in {"🔥 Redz": "c_redz", "🚀 Lord": "c_lord", "🌐 LOLA": "c_lola", "🎧 Saiki": "c_saiki"}.items()] + [[types.InlineKeyboardButton(text="🔙 Назад", callback_data="mm")]]
    await cb.message.edit_text("📜 Brookhaven:", reply_markup=types.InlineKeyboardMarkup(inline_keyboard=b))

@dp.callback_query(F.data == "mmm")
async def mmm(cb):
    b = [[types.InlineKeyboardButton(text=t, callback_data=d)] for t, d in {"🥷 Madara": "c_madara", "🔪 Moondiety": "c_moondiety", "🛡️ God": "c_godmode", "❄️ Заморозка": "c_frz"}.items()] + [[types.InlineKeyboardButton(text="🔙 Назад", callback_data="mm")]]
    await cb.message.edit_text("🎮 MM2:", reply_markup=types.InlineKeyboardMarkup(inline_keyboard=b))

@dp.callback_query(F.data == "mbf")
async def mbf(cb):
    b = [[types.InlineKeyboardButton(text=t, callback_data=d)] for t, d in {"🎮 Min": "c_bf_min", "🚀 Redz B": "c_bf_redz", "🏠 Base": "c_bf_basement", "⚡ Farm": "c_bf_autofarm"}.items()] + [[types.InlineKeyboardButton(text="🔙 Назад", callback_data="mm")]]
    await cb.message.edit_text("🍇 Blox Fruits:", reply_markup=types.InlineKeyboardMarkup(inline_keyboard=b))

@dp.callback_query(F.data == "m99")
async def m99(cb):
    b = [[types.InlineKeyboardButton(text=t, callback_data=d)] for t, d in {"📜 1": "c_99_1", "📜 2 (KEY)": "c_99_2", "📜 3": "c_99_3"}.items()] + [[types.InlineKeyboardButton(text="🔙 Назад", callback_data="mm")]]
    await cb.message.edit_text("🌙 99 Ночей:", reply_markup=types.InlineKeyboardMarkup(inline_keyboard=b))

@dp.callback_query(F.data == "meg")
async def meg(cb):
    b = [[types.InlineKeyboardButton(text=t, callback_data=d)] for t, d in {"📜 Sabs": "c_egg_1", "🎧 Lennon V2": "c_egg_2", "🥚 Lennon Auto": "c_egg_3"}.items()] + [[types.InlineKeyboardButton(text="🔙 Назад", callback_data="mm")]]
    await cb.message.edit_text("🥚 Steal Egg:", reply_markup=types.InlineKeyboardMarkup(inline_keyboard=b))

@dp.callback_query(F.data == "mm")
async def mm(cb, state):
    await state.clear()
    await cb.message.edit_text("🔥 Выбери категорию:", reply_markup=kb(cb.from_user.id))

@dp.callback_query(F.data == "su")
async def su(cb):
    await cb.answer(f"👥 Всего: {len(users)}\n⭐ Премиум: {len(prem)}", show_alert=True)

async def health(r):
    return web.Response(text="OK")

async def on_startup(app):
    webhook_url = os.getenv(
        "RENDER_EXTERNAL_URL",
        "https://telegram-server-bot-b5v3.onrender.com"
    ).rstrip("/") + "/webhook"

    await bot.set_webhook(webhook_url)
    print(f"Вебхук установлен: {webhook_url}")

def main():
    app = web.Application()
    
    from aiogram.webhook.aiohttp_server import SimpleRequestHandler
    webhook_requests_handler = SimpleRequestHandler(dispatcher=dp, bot=bot)
    webhook_requests_handler.register(app, path="/webhook")
    
    app.router.add_get("/", health)
    app.on_startup.append(on_startup)
    
    port = int(os.getenv("PORT", 8080))
    web.run_app(app, host="0.0.0.0", port=port)

if __name__ == "__main__":
    main()
