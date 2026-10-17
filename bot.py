import os, asyncio, re, random, string, aiohttp
from datetime import datetime, timedelta
from aiohttp import web
from aiogram import Bot, Dispatcher, F, types
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import LabeledPrice, PreCheckoutQuery

TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = 123456789  # ВСТАВЬ СВОЙ ID
SPONSOR_ID = 111111111  # ВСТАВЬ ID СПОНСОРА
P_PRICE, F_PRICE, FREE_L, PREM_L, ROLL_PRICE = 30, 10, 5, 15, 5
SUB_PRICE = 100

bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
dp = Dispatcher(storage=MemoryStorage())
UF, PF, FF, TF, DF, SF, PRF, SPF, SUBF = "u.txt", "p.txt", "f.txt", "t.txt", "d.txt", "s.txt", "pr.txt", "sp.txt", "sub.txt"

def ls(f): return set(l.strip() for l in open(f)) if os.path.exists(f) else set()
def ss(f, d):
    with open(f, "w") as file:
        for i in d: file.write(f"{i}\n")
def ld(f, c):
    d = {}
    if os.path.exists(f):
        for l in open(f):
            p = l.strip().split("|")
            if len(p) == c: d[p[0]] = p[1:]
    return d
def sd(f, d):
    with open(f, "w") as file:
        for k, v in d.items(): file.write(f"{k}|" + "|".join(str(x) for x in v) + "\n")
def lsp():
    d = {}
    if os.path.exists(SPF):
        for l in open(SPF):
            p = l.strip().split("|")
            if len(p) == 3: d[p[0]] = {"level": p[1], "last_claimed": p[2]}
    return d
def ssp(d):
    with open(SPF, "w") as file:
        for u, v in d.items(): file.write(f"{u}|{v['level']}|{v['last_claimed']}\n")

users, prem = ls(UF), ls(PF)
frz, dis = ls(FF), ls(DF)

def is_p(u): return str(u) == str(ADMIN_ID) or str(u) in prem
def has_sp(u):
    if is_p(u): return True
    t = ld(TF, 1)
    if str(u) in t:
        try:
            if datetime.fromisoformat(t[str(u)][0]) > datetime.now(): return True
        except: pass
    return False
def has_f(u): return str(u) == str(ADMIN_ID) or str(u) in prem or str(u) in frz
def gen(): return "PROMO-" + "".join(random.choices(string.ascii_uppercase + string.digits, k=8))

class SS(StatesGroup): wait = State()
class PS(StatesGroup): wait = State()
class DS(StatesGroup): wait = State()

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
        [types.InlineKeyboardButton(text="🎲 Рулетка (5⭐)", callback_data="roul")],
        [types.InlineKeyboardButton(text="🛒 Магазин", callback_data="shop")],
        [types.InlineKeyboardButton(text=f"💎 Подписка{sub_st}", callback_data="sub_menu")],
        [types.InlineKeyboardButton(text="🎁 Промокод", callback_data="ep")],
        [types.InlineKeyboardButton(text=f"💎 Спонсор{s}", callback_data="dm")],
        [types.InlineKeyboardButton(text=f"⭐ Премиум ({st})", callback_data="bp")],
        [types.InlineKeyboardButton(text="👥 Юзеры", callback_data="su")],
        [types.InlineKeyboardButton(text="💬 Соцсети", url="https://t.me/+LBs19_JzpW0yNmZi")]
    ])

@dp.message(F.text == "/start")
async def start(m, state):
    await state.clear()
    u = str(m.from_user.id)
    n = u not in users
    if n:
        users.add(u)
        ss(UF, users)
    t = "🔥 <b>Привет!</b>\n\n"
    if n:
        c = gen()
        pr = ld(PRF, 4)
        pr[c] = ["trial", "3", u, "no"]
        sd(PRF, pr)
        t += f"🎁 <b>Ты новичок! Держи подарок:</b>\nПромокод на 3 дня рулетки: <code>{c}</code>\n\n"
    
    subs = ld(SUBF, 2)
    if u in subs:
        last_sub = datetime.fromisoformat(subs[u][0])
        now = datetime.now()
        if (now - last_sub).days >= 2:
            pr = ld(PRF, 4)
            for _ in range(3):
                c = gen()
                r_type = random.choices(["prem", "discount", "trial"], weights=[10, 60, 30])[0]
                if r_type == "prem": pr[c] = ["trial", "1", u, "no"]
                elif r_type == "discount": pr[c] = ["discount", str(random.choice([15, 20, 30, 40, 50])), u, "no"]
                else: pr[c] = ["trial", "5" if random.random() < 0.2 else "3", u, "no"]
            sd(PRF, pr)
            subs[u][0] = now.isoformat()
            sd(SUBF, subs)
            t += "💎 <b>Подписка активна!</b>\nТвои 3 промокода на эти 2 дня готовы. Напиши /mycodes.\n\n"
            
    sp = lsp()
    if u in sp:
        l = sp[u]["level"]
        la = datetime.fromisoformat(sp[u]["last_claimed"]) if sp[u]["last_claimed"] else datetime(2000, 1, 1)
        now = datetime.now()
        pr = ld(PRF, 4)
        rg = False
        if l == "gold" and (now - la).days >= 1:
            for _ in range(random.randint(1, 2)):
                c = gen()
                pr[c] = [random.choice(["trial", "discount"]), "3" if random.random() > 0.5 else "50", u, "no"]
            sp[u]["last_claimed"] = now.isoformat()
            rg = True
            t += "🌟 <b>Спонсор!</b>\nТвои промокоды на сегодня готовы. Напиши /mycodes.\n\n"
        elif l == "bronze" and (now - la).days >= 3:
            c = gen()
            pr[c] = [random.choice(["trial", "discount"]), "3" if random.random() > 0.5 else "50", u, "no"]
            sp[u]["last_claimed"] = now.isoformat()
            rg = True
            t += "🥉 <b>Бронзовый спонсор!</b>\nТвой промокод готов. Напиши /mycodes.\n\n"
        if rg:
            ssp(sp)
            sd(PRF, pr)
            
    await m.answer(t + "Выбери категорию:", reply_markup=kb(u))

@dp.message(F.text == "/mycodes")
async def my_codes(m):
    u = str(m.from_user.id)
    pr = ld(PRF, 4)
    
    if u == str(ADMIN_ID):
        act = {k: v for k, v in pr.items() if v[3] == "no"}
        if not act: return await m.answer("Нет промокодов.")
        text = "👑 <b>Все активные промокоды:</b>\n\n"
        for c, i in act.items():
            if i[0] == 'discount': text += f"<code>{c}</code> — 💰 Скидка {i[1]}%\n"
            else: text += f"<code>{c}</code> — ⭐ Триал {i[1]}д\n"
        return await m.answer(text)
        
    act = {k: v for k, v in pr.items() if v[2] == u and v[3] == "no"}
    if not act: return await m.answer("Нет активных промокодов.")
    
    text = "🎁 <b>Твои промокоды:</b>\n\n"
    for c, i in act.items():
        if i[0] == 'discount': text += f"<code>{c}</code> — 💰 Скидка {i[1]}%\n"
        else: text += f"<code>{c}</code> — ⭐ Рулетка на {i[1]} дней\n"
        
    text += "\nАктивируй в меню."
    await m.answer(text, reply_markup=kb(u))

@dp.callback_query(F.data == "sub_menu")
async def sub_menu(cb):
    u = str(cb.from_user.id)
    subs = ld(SUBF, 2)
    if u in subs:
        text = "💎 <b>Твоя подписка активна!</b>\nКаждые 2 дня ты получаешь 3 промокода.\nСледующее списание 20⭐ через неделю."
        markup = types.InlineKeyboardMarkup(inline_keyboard=[[types.InlineKeyboardButton(text="🔙 Меню", callback_data="mm")]])
        await cb.message.edit_text(text, reply_markup=markup)
    else:
        text = "💎 <b>Подписка</b>\n\nВход: 100⭐\nДалее: 20⭐/нед.\n\nБонус: 3 промокода каждые 2 дня + поиск по 4 сайтам (20 скриптов)!"
        markup = types.InlineKeyboardMarkup(inline_keyboard=[[types.InlineKeyboardButton(text="✅ Оформить за 100⭐", callback_data="buy_sub")], [types.InlineKeyboardButton(text="🔙 Меню", callback_data="mm")]])
        await cb.message.edit_text(text, reply_markup=markup)

@dp.callback_query(F.data == "buy_sub")
async def buy_sub(cb):
    await bot.send_invoice(chat_id=cb.from_user.id, title="💎 Подписка", description="Доступ к расширенному поиску", payload="sub_access", provider_token="", currency="XTR", prices=[LabeledPrice(label="Подписка", amount=SUB_PRICE)])

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
        text = "❄️ <b>Заморозка</b>\n\n<pre>loadstring(game:HttpGet(\"https://cdn.sourceb.in/bins/9MHwJQNJkm/0\"))()</pre>\n\nРезервный:\n<pre>loadstring(game:HttpGet('https://raw.githubusercontent.com/txnic255/MM2-FREEZE-TRADE-V5.5-NEWEST-GUI-SCRIPT-/refs/heads/main/SCRIPT%20V5.5%20GUI%20AND%20SCRIPT'))()</pre>"
        return await bot.send_message(u, text)
    code = SC.get(n)
    if not code: return await cb.answer("❌ Ошибка", show_alert=True)
    await cb.answer("Отправляю ✅")
    markup = types.InlineKeyboardMarkup(inline_keyboard=[[types.InlineKeyboardButton(text="📋 Скопировать", copy_text=types.CopyTextButton(text=code))]])
    await bot.send_message(u, f"✅ <b>Твой скрипт:</b>\n\n<pre>{code}</pre>", reply_markup=markup)

@dp.callback_query(F.data == "dm")
async def dm(cb):
    b = [
        [types.InlineKeyboardButton(text=f"{a}⭐", callback_data=f"d_{a}") for a in [10, 25, 50]],
        [types.InlineKeyboardButton(text=f"{a}⭐", callback_data=f"d_{a}") for a in [100, 250, 500]],
        [types.InlineKeyboardButton(text="1000⭐", callback_data="d_1000")],
        [types.InlineKeyboardButton(text="✏️ Своя", callback_data="dc")],
        [types.InlineKeyboardButton(text="🔙 Назад", callback_data="mm")]
    ]
    await cb.message.edit_text("💎 <b>Стать спонсором</b>\n\nВыбери сумму:", reply_markup=types.InlineKeyboardMarkup(inline_keyboard=b))

@dp.callback_query(F.data.startswith("d_") & ~F.data.in_({"dm", "dc"}))
async def pd(cb):
    a = int(cb.data.split("_")[1])
    await si(cb.from_user.id, a)
    await cb.answer()

@dp.callback_query(F.data == "dc")
async def dc(cb, state):
    await cb.message.edit_text("💎 Введи сумму (1-1000):", reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[[types.InlineKeyboardButton(text="❌ Отмена", callback_data="dm")]]))
    await state.set_state(DS.wait)

@dp.message(DS.wait)
async def pcd(m, state):
    await state.clear()
    try:
        a = int(m.text)
        if a < 1 or a > 1000: raise ValueError
        await si(m.from_user.id, a)
    except: await m.answer("❌ Неверно.")

async def si(u, a):
    await bot.send_invoice(chat_id=u, title="💎 Поддержка", description=f"Донат {a}⭐", payload=f"d_{a}", provider_token="", currency="XTR", prices=[LabeledPrice(label="Донат", amount=a)])

def gs():
    it = []
    discounts = [5, 10, 15, 20, 30, 50]
    for _ in range(10):
        t = random.choice(["discount", "trial3", "trial5"])
        if t == "discount": it.append(f"{gen()}|discount_{random.choice(discounts)}|3|no|{datetime.now().isoformat()}")
        elif t == "trial3": it.append(f"{gen()}|trial3|7|no|{datetime.now().isoformat()}")
        else: it.append(f"{gen()}|trial5|10|no|{datetime.now().isoformat()}")
    with open(SF, "w") as f: f.write("\n".join(it))

def gsh():
    it = []
    if os.path.exists(SF):
        for l in open(SF):
            p = l.strip().split("|")
            if len(p) == 5: it.append({"code": p[0], "type": p[1], "price": int(p[2]), "bought": p[3], "created": p[4]})
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
    gs()
    await shop(cb)

@dp.callback_query(F.data.startswith("freebp_"))
async def freebp(cb):
    u = str(cb.from_user.id)
    if u != str(ADMIN_ID): return await cb.answer("❌ Вы не админ!", show_alert=True)
    c = cb.data.split("_")[1]
    it = gsh()
    for i in it:
        if i["code"] == c: i["bought"] = "yes"
    with open(SF, "w") as f:
        for i in it: f.write(f"{i['code']}|{i['type']}|{i['price']}|{i['bought']}|{i['created']}\n")
    pr = ld(PRF, 4)
    i = next((x for x in it if x["code"] == c), None)
    if i:
        if i["type"].startswith("discount"): pt, v = "discount", i["type"].split("_")[1]
        else: pt, v = "trial", "3" if i["type"] == "trial3" else "5"
        pr[c] = [pt, v, u, "no"]
        sd(PRF, pr)
        await cb.answer("✅ Забрано!", show_alert=True)
        await cb.message.edit_text(f"👑 <b>Промокод забран!</b>\nКод: <code>{c}</code>", reply_markup=kb(u))

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
    pr = ld(PRF, 4)
    if c not in pr: return await m.answer("❌ Не найден.", reply_markup=kb(u))
    pt, v, us, _ = pr[c]
    if us != "no": return await m.answer("❌ Активирован.", reply_markup=kb(u))
    if pt == "discount":
        dis.add(f"{u}|{v}")
        ss(DF, dis)
        await m.answer(f"✅ Скидка {v}%!", reply_markup=kb(u))
    elif pt == "trial":
        t = ld(TF, 1)
        t[u] = [(datetime.now() + timedelta(days=int(v))).isoformat()]
        sd(TF, t)
        await m.answer(f"✅ Рулетка на {v} дней!", reply_markup=kb(u))
    pr[c] = [pt, v, u, "yes"]
    sd(PRF, pr)

@dp.callback_query(F.data == "roul")
async def roul(cb):
    u = str(cb.from_user.id)
    if not ((u == str(ADMIN_ID)) or (u in ld(TF, 1))):
        await bot.send_invoice(chat_id=u, title="🎲 Рулетка", description="5 админ-скриптов за 5⭐", payload="roulette", provider_token="", currency="XTR", prices=[LabeledPrice(label="Рулетка", amount=ROLL_PRICE)])
    else:
        await cb.message.answer("🎲 Крутим рулетку...")
        await give_roulette_prize(cb.message, u)

async def give_roulette_prize(m, u):
    msg = await m.answer("🔎 Ищу...")
    queries = ["Infinite Yield", "Dark Dex", "Nameless Admin", "Simple Spy", "Admin Commands"]
    found = []
    random.shuffle(queries)
    for q in queries[:3]:
        try:
            res = await s1(q)
            if res: found.extend(res[:2])
        except: pass
    if not found:
        found = [
            {"title": "Infinite Yield", "script": "loadstring(game:HttpGet('https://raw.githubusercontent.com/EdgeIY/infiniteyield/master/source'))()"},
            {"title": "Dark Dex", "script": "loadstring(game:HttpGet('https://raw.githubusercontent.com/peyton2465/Dex/master/out.lua'))()"},
            {"title": "Nameless Admin", "script": "loadstring(game:HttpGet('https://raw.githubusercontent.com/FilteringEnabled/NamelessAdmin/master/NamelessAdmin.lua'))()"}
        ]
    text = "🎰 <b>Твой выигрыш:</b>\n\n" + "".join([f"<b>{i}. {s.get('title','?')}</b>\n<pre>{s.get('script','')}</pre>\n\n" for i, s in enumerate(found[:5], 1)])
    await msg.edit_text(text, reply_markup=kb(u))

@dp.pre_checkout_query()
async def pcq(q):
    await bot.answer_pre_checkout_query(q.id, ok=True)

@dp.message(F.successful_payment)
async def sp(m):
    u, p = str(m.from_user.id), m.successful_payment.invoice_payload
    if p == "prem":
        prem.add(u)
        ss(PF, prem)
        for d in list(dis):
            if d.startswith(f"{u}|"): dis.remove(d)
        ss(DF, dis)
        await m.answer("⭐ Спасибо за Премиум!", reply_markup=kb(u))
    elif p == "frz":
        frz.add(u)
        ss(FF, frz)
        await m.answer("❄️ Спасибо!", reply_markup=kb(u))
    elif p == "sub_access":
        subs = ld(SUBF, 2)
        subs[u] = [datetime.now().isoformat()]
        sd(SUBF, subs)
        await m.answer("💎 <b>Подписка оформлена!</b>", reply_markup=kb(u))
    elif p == "roulette":
        await give_roulette_prize(m, u)
    elif p.startswith("d_"):
        a = int(p.split("_")[1])
        spd = lsp()
        l = "gold" if a >= 25 else ("bronze" if 5 <= a <= 10 else "none")
        if l != "none":
            spd[u] = {"level": l, "last_claimed": "2000-01-01T00:00:00"}
            ssp(spd)
            await m.answer(f"💎 Спасибо за {a}⭐!\n🌟 Статус: {l.upper()}", reply_markup=kb(u))
        else:
            await m.answer(f"💎 Спасибо за {a}⭐!", reply_markup=kb(u))
    elif p.startswith("p_"):
        c = p.split("_", 1)[1]
        it = gsh()
        for i in it:
            if i["code"] == c: i["bought"] = "yes"
        with open(SF, "w") as f:
            for i in it: f.write(f"{i['code']}|{i['type']}|{i['price']}|{i['bought']}|{i['created']}\n")
        pr = ld(PRF, 4)
        i = next((x for x in it if x["code"] == c), None)
        if i:
            if i["type"].startswith("discount"): pt, v = "discount", i["type"].split("_")[1]
            else: pt, v = "trial", "3" if i["type"] == "trial3" else "5"
            pr[c] = [pt, v, u, "no"]
            sd(PRF, pr)
            await m.answer(f"✅ Куплено!\nКод: <code>{c}</code>", reply_markup=kb(u))

@dp.callback_query(F.data == "bp")
async def bpr(cb):
    if is_p(cb.from_user.id): return await cb.answer("✅ Уже есть!", show_alert=True)
    max_disc = 0
    u = str(cb.from_user.id)
    for d in dis:
        if d.startswith(f"{u}|"): max_disc = max(max_disc, int(d.split("|")[1]))
    pr = int(P_PRICE * (1 - max_disc / 100))
    desc = f"Скидка {max_disc}%" if max_disc > 0 else "15 скриптов"
    await bot.send_invoice(chat_id=cb.from_user.id, title="⭐ Премиум", description=desc, payload="prem", provider_token="", currency="XTR", prices=[LabeledPrice(label="Премиум", amount=pr)])

@dp.callback_query(F.data == "bf")
async def bf(cb):
    if has_f(cb.from_user.id): return await cb.answer("✅ Уже есть!", show_alert=True)
    await bot.send_invoice(chat_id=cb.from_user.id, title="❄️ Заморозка", description="MM2", payload="frz", provider_token="", currency="XTR", prices=[LabeledPrice(label="Заморозка", amount=F_PRICE)])

@dp.callback_query(F.data == "ms")
async def ms(cb, state):
    subs = ld(SUBF, 2)
    is_sub = str(cb.from_user.id) in subs
    limit = 20 if is_sub else (PREM_L if has_sp(cb.from_user.id) else FREE_L)
    await cb.message.edit_text(f"🔍 Поиск (до {limit}):", reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[[types.InlineKeyboardButton(text="❌ Отмена", callback_data="mm")]]))
    await state.set_state(SS.wait)

@dp.message(SS.wait)
async def ps(m, state):
    await state.clear()
    q = m.text.strip().lower()
    u = m.from_user.id
    subs = ld(SUBF, 2)
    is_sub = str(u) in subs
    l = 20 if is_sub else (PREM_L if has_sp(u) else FREE_L)
    msg = await m.answer(f"🔎 Ищу: {q}...")
    a = await s1(q)
    if "mm2" in q or "murder" in q: a.extend(await s2()); a.extend(await s3())
    if is_sub: a.extend(await s4())
    if not a: return await msg.edit_text("❌ Не найдено.", reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[[types.InlineKeyboardButton(text="🔙 Меню", callback_data="mm")]]))
    s = set()
    f = [x for x in a if x.get("title", "").lower() not in s and not s.add(x.get("title", "").lower())]
    k = []
    if not is_sub and not has_sp(u) and len(f) > FREE_L:
        k.extend([[types.InlineKeyboardButton(text="⭐ Премиум", callback_data="bp")], [types.InlineKeyboardButton(text="🛒 Магазин", callback_data="shop")]])
    k.append([types.InlineKeyboardButton(text="🔙 Меню", callback_data="mm")])
    text = f"🌐 Найдено ({len(f)}):\n\n"
    for i, x in enumerate(f[:l], 1):
        text += f"<b>{i}. {x.get('title','?')}</b>\n🎮 {x.get('game',{}).get('name','?')}\n<pre>{x.get('script','')[:200]}...</pre>\n\n"
    await msg.edit_text(text, reply_markup=types.InlineKeyboardMarkup(inline_keyboard=k))

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
                    html = await r.text()
                    m = re.findall(r'<h2[^>]*>(.*?)</h2>', html)
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

async def main():
    app = web.Application()
    app.router.add_get("/", health)
    runner = web.AppRunner(app)
    await runner.setup()
    await web.TCPSite(runner, "0.0.0.0", int(os.getenv("PORT", 8080))).start()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
