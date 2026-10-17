import os,asyncio,re,random,string,aiohttp
from datetime import datetime,timedelta
from aiohttp import web
from aiogram import Bot,Dispatcher,F,types
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State,StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import LabeledPrice,PreCheckoutQuery

TOKEN=os.getenv("BOT_TOKEN")

# 1-й - Твой ID (Админ)
ADMIN_ID = 8996403397
# 2-й - Спонсор (без Премиума, только промокоды)
SPONSOR_ID = 6814321871 

P_PRICE,F_PRICE,FREE_L,PREM_L=30,10,5,15
ROLL_PRICE = 5 # РУЛЕТКА ТЕПЕРЬ СТОИТ 5 ЗВЕЗД

bot=Bot(token=TOKEN,default=DefaultBotProperties(parse_mode="HTML"))
dp=Dispatcher(storage=MemoryStorage())
UF,PF,FF,TF,DF,SF,PRF,SPF="u.txt","p.txt","f.txt","t.txt","d.txt","s.txt","pr.txt","sp.txt"

def ls(f):return set(l.strip() for l in open(f)) if os.path.exists(f) else set()
def ss(f,d):
    with open(f,"w") as file:
        for i in d:file.write(f"{i}\n")
def ld(f,c):
    d={}
    if os.path.exists(f):
        for l in open(f):
            p=l.strip().split("|")
            if len(p)==c:d[p[0]]=p[1:]
    return d
def sd(f,d):
    with open(f,"w") as file:
        for k,v in d.items():file.write(f"{k}|"+"|".join(str(x) for x in v)+"\n")
def lsp():
    d={}
    if os.path.exists(SPF):
        for l in open(SPF):
            p=l.strip().split("|")
            if len(p)==3:d[p[0]]={"level":p[1],"last_claimed":p[2]}
    return d
def ssp(d):
    with open(SPF,"w") as file:
        for u,v in d.items():file.write(f"{u}|{v['level']}|{v['last_claimed']}\n")

users,prem=ls(UF),ls(PF)
frz,dis=ls(FF),ls(DF)

def is_p(u):return str(u) == str(ADMIN_ID) or str(u) in prem
def has_sp(u):
    if is_p(u):return True
    t=ld(TF,1)
    if str(u) in t:
        try:
            if datetime.fromisoformat(t[str(u)][0])>datetime.now():return True
        except:pass
    return False
def has_f(u):return str(u) == str(ADMIN_ID) or str(u) in prem or str(u) in frz
def gen():return "PROMO-"+"".join(random.choices(string.ascii_uppercase+string.digits,k=8))

class SS(StatesGroup):wait=State()
class PS(StatesGroup):wait=State()
class DS(StatesGroup):wait=State()

SC={
    "redz":"loadstring(game:HttpGet('https://pastebin.com/raw/1r7cEW7G'))()",
    "lord":"loadstring(game:HttpGet(\"https://raw.githubusercontent.com/SUPREMEAURA350/KAISER-VERSION-2-/refs/heads/main/Kaiserspam\"))()",
    "lola":"loadstring(game:HttpGet(\"https://raw.githubusercontent.com/niriel015/Painel-LolaHub/refs/heads/main/Lola-hub-ne-pai\"))()",
    "saiki":"loadstring(game:HttpGet(\"https://raw.githubusercontent.com/SaikiWithTheBanHammer/ScriptBlox/main/LifeIsDisasterIndeedLol\"))()",
    "madara":"loadstring(game:HttpGet(\"https://raw.githubusercontent.com/IsThisMe01/Project-Madara/refs/heads/main/mm22.lua\"))()",
    "moondiety":"loadstring(game:HttpGet(\"https://scriptblox.com/raw/Murder-Mystery-2-KEYLESS-InstaWin-AutoFarm-Kill-all-XRay-nd-more-by-Moondiety-48644\"))()",
    "godmode":"loadstring(game:HttpGet(\"https://pastefy.app/a2dAk154/raw\"))()",
    "bf_min":"loadstring(game:HttpGet(\"https://raw.githubusercontent.com/LuaCrack/Min/refs/heads/main/MinXt2Eng\"))()",
    "bf_redz":"local Settings = { JoinTeam = \"Pirates\", Translator = true }\ngetgenv().BETA_VERSION = true\nloadstring(game:HttpGet(\"https://raw.githubusercontent.com/tlredz/Scripts/refs/heads/main/main.luau\"))(Settings)",
    "bf_basement":"loadstring(game:HttpGet(\"https://raw.githubusercontent.com/Cazzanos/The-basement/main/Basement%20hub\",true))()",
    "bf_autofarm":"loadstring(game:HttpGetAsync(\"https://raw.githubusercontent.com/indexeduu/BF-NewVer/refs/heads/main/V3New.lua\"))()",
    "99_1":"loadstring(game:HttpGet(\"https://api.luarmor.net/files/v3/loaders/705e9a93cc18214fb77ab95686a8dba9.lua\"))()",
    "99_2":"KEY - 111222HHH\n\nloadstring(game:HttpGet(\"https://raw.githubusercontent.com/caomod2077/Script/refs/heads/main/FoxnameHub.lua\"))()",
    "99_3":"loadstring(game:HttpGet(\"https://ntt-hub.xyz/api/repo?id1=main&id2=lua\"))()",
    "egg_1":"loadstring(game:HttpGet(\"https://raw.githubusercontent.com/sabscrip-arch/srver/refs/heads/main/Stealanegg\"))()",
    "egg_2":"loadstring(game:HttpGet(\"https://raw.githubusercontent.com/lennonxscripts/lennonhubv2/refs/heads/main/stealaneggv2\"))()",
}

def kb(u):
    st="⭐ Премиум" if is_p(u) else "🆓 Бесплатно"
    sp=lsp()
    s=" 🌟" if str(u) in sp and sp[str(u)]["level"]=="gold" else (" 🥉" if str(u) in sp and sp[str(u)]["level"]=="bronze" else "")
    return types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="📜 Brookhaven",callback_data="mbh")],
        [types.InlineKeyboardButton(text="🎮 MM2",callback_data="mmm")],
        [types.InlineKeyboardButton(text="🍇 Blox Fruits",callback_data="mbf")],
        [types.InlineKeyboardButton(text="🌙 99 Ночей",callback_data="m99")],
        [types.InlineKeyboardButton(text="🥚 Steal an Egg",callback_data="meg")],
        [types.InlineKeyboardButton(text="🔍 Поиск",callback_data="ms")],
        [types.InlineKeyboardButton(text="🎲 Рулетка (5⭐)",callback_data="roul")],
        [types.InlineKeyboardButton(text="🛒 Магазин",callback_data="shop")],
        [types.InlineKeyboardButton(text="🎁 Промокод",callback_data="ep")],
        [types.InlineKeyboardButton(text=f"💎 Спонсор{s}",callback_data="dm")],
        [types.InlineKeyboardButton(text=f"⭐ Премиум ({st})",callback_data="bp")],
        [types.InlineKeyboardButton(text="👥 Юзеры",callback_data="su")],
        [types.InlineKeyboardButton(text="💬 Соцсети",url="https://t.me/+LBs19_JzpW0yNmZi")],
    ])

@dp.message(F.text=="/start")
async def start(m,state):
    await state.clear()
    u=str(m.from_user.id)
    n=u not in users
    if n:users.add(u);ss(UF,users)
    t="🔥 <b>Привет!</b>\n\n"
    if n:
        c=gen();pr=ld(PRF,4);pr[c]=["trial","5",u,"no"];sd(PRF,pr) # 5 ДНЕЙ
        t+=f"🎁 <b>Ты новичок! Держи подарок:</b>\nПромокод на 5 дней рулетки: <code>{c}</code>\n\n"
    
    if u == str(SPONSOR_ID):
        sp_data = lsp()
        if u not in sp_data:
            sp_data[u] = {"level": "gold", "last_claimed": "2000-01-01T00:00:00"}
            ssp(sp_data)

    sp=lsp()
    if u in sp:
        l,la=sp[u]["level"],datetime.fromisoformat(sp[u]["last_claimed"]) if sp[u]["last_claimed"] else datetime(2000,1,1)
        now,pr,rg=datetime.now(),ld(PRF,4),False
        
        if l=="gold" and (now-la).days>=1:
            for _ in range(random.randint(1, 2)):
                c=gen();pr[c]=[random.choice(["trial","discount"]),"3" if random.random()>0.5 else "50",u,"no"]
            sp[u]["last_claimed"],rg=now.isoformat(),True
            t+="🌟 <b>Спонсор!</b>\nТвои промокоды на сегодня готовы. Напиши /mycodes.\n\n"
        elif l=="bronze" and (now-la).days>=3:
            c=gen();pr[c]=[random.choice(["trial","discount"]),"3" if random.random()>0.5 else "50",u,"no"]
            sp[u]["last_claimed"],rg=now.isoformat(),True
            t+="🥉 <b>Бронзовый спонсор!</b>\nТвой промокод готов. Напиши /mycodes.\n\n"
        if rg:ssp(sp);sd(PRF,pr)
    await m.answer(t+"Выбери категорию:",reply_markup=kb(u))

@dp.message(F.text=="/mycodes")
async def my_codes(m):
    u=str(m.from_user.id);pr=ld(PRF,4)
    if u == str(ADMIN_ID):
        act={k:v for k,v in pr.items() if v[3]=="no"}
        if not act:return await m.answer("В базе нет активных промокодов.")
        t="👑 <b>Все активные промокоды (Админ):</b>\n\n"+"".join([f"<code>{c}</code> — {'💰 Скидка' if i[0]=='discount' else '⭐ Триал'}\n" for c,i in act.items()])
        return await m.answer(t)
    act={k:v for k,v in pr.items() if v[2]==u and v[3]=="no"}
    if not act:return await m.answer("Нет активных промокодов.")
    t="🎁 <b>Твои промокоды:</b>\n\n"+"".join([f"<code>{c}</code> — {'💰 Скидка 50%' if i[0]=='discount' else f'⭐ Рулетка на {i[1]} дней'}\n" for c,i in act.items()])
    await m.answer(t+"\nАктивируй в меню.",reply_markup=kb(u))

@dp.callback_query(F.data.startswith("c_"))
async def c(cb):
    n=cb.data.split("_",1)[1];u=cb.from_user.id
    
    if n=="frz":
        if not has_f(u):
            await cb.answer("❄️ Платный!",show_alert=True)
            await bot.send_message(u,"❄️ <b>Заморозка</b>\nСтоимость: 10⭐",reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[[types.InlineKeyboardButton(text="⭐ Купить",callback_data="bf")]]))
            return
        await cb.answer("Отправляю ✅")
        text = "❄️ <b>Заморозка</b>\n\n<pre>loadstring(game:HttpGet(\"https://cdn.sourceb.in/bins/9MHwJQNJkm/0\"))()</pre>\n\nРезервный:\n<pre>loadstring(game:HttpGet('https://raw.githubusercontent.com/txnic255/MM2-FREEZE-TRADE-V5.5-NEWEST-GUI-SCRIPT-/refs/heads/main/SCRIPT%20V5.5%20GUI%20AND%20SCRIPT'))()</pre>"
        await bot.send_message(u, text)
        return
    code = SC.get(n)
    if not code:
        await cb.answer("❌ Ошибка", show_alert=True)
        return
    await cb.answer("Отправляю ✅")
    await bot.send_message(u, f"✅ <b>Твой скрипт:</b>\n\n<pre>{code}</pre>")

@dp.callback_query(F.data=="dm")
async def dm(cb):
    b=[[types.InlineKeyboardButton(text=f"{a}⭐",callback_data=f"d_{a}") for a in [10,25,50]],[types.InlineKeyboardButton(text=f"{a}⭐",callback_data=f"d_{a}") for a in [100,250,500]],[types.InlineKeyboardButton(text="1000⭐",callback_data="d_1000")],[types.InlineKeyboardButton(text="✏️ Своя",callback_data="dc")],[types.InlineKeyboardButton(text="🔙 Назад",callback_data="mm")]]
    await cb.message.edit_text("💎 <b>Стать спонсором</b>\n\nВыбери сумму:",reply_markup=types.InlineKeyboardMarkup(inline_keyboard=b))
    await cb.answer()
@dp.callback_query(F.data.startswith("d_") & ~F.data.in_({"dm","dc"}))
async def pd(cb):
    a=int(cb.data.split("_")[1]);await si(cb.from_user.id,a);await cb.answer()
@dp.callback_query(F.data=="dc")
async def dc(cb,state):
    await cb.message.edit_text("💎 Введи сумму (1-1000):",reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[[types.InlineKeyboardButton(text="❌ Отмена",callback_data="dm")]]))
    await state.set_state(DS.wait)
@dp.message(DS.wait)
async def pcd(m,state):
    await state.clear()
    try:
        a=int(m.text)
        if a<1 or a>1000:raise ValueError
        await si(m.from_user.id,a)
    except:await m.answer("❌ Неверно.")
async def si(u,a):
    await bot.send_invoice(chat_id=u,title="💎 Поддержка",description=f"Донат {a}⭐",payload=f"d_{a}",provider_token="",currency="XTR",prices=[LabeledPrice(label="Донат",amount=a)])

def gs():
    it=[]
    for _ in range(10):
        t=random.choice(["discount","trial3","trial5"]);p=3 if t=="discount" else (7 if t=="trial3" else 10)
        it.append(f"{gen()}|{t}|{p}|no|{datetime.now().isoformat()}")
    with open(SF,"w") as f:f.write("\n".join(it))
def gsh():
    it=[]
    if os.path.exists(SF):
        for l in open(SF):
            p=l.strip().split("|")
            if len(p)==5:it.append({"code":p[0],"type":p[1],"price":int(p[2]),"bought":p[3],"created":p[4]})
    return it

@dp.callback_query(F.data=="shop")
async def shop(cb):
    u=cb.from_user.id
    if not os.path.exists(SF) or (datetime.now()-datetime.fromtimestamp(os.path.getmtime(SF))).seconds>30:gs()
    it=gsh();k=[]
    for i in it:
        if i["bought"]=="yes":continue
        ti="💰 Скидка 50%" if i["type"]=="discount" else ("⭐ Рулетка 3д" if i["type"]=="trial3" else "⭐ Рулетка 5д")
        if str(u) == str(ADMIN_ID):
            k.append([types.InlineKeyboardButton(text=f"👑 {ti} — {i['price']}⭐",callback_data=f"freebp_{i['code']}")])
        else:
            k.append([types.InlineKeyboardButton(text=f"{ti} — {i['price']}⭐",callback_data=f"bp_{i['code']}")])
    k.extend([[types.InlineKeyboardButton(text="🔄 Обновить",callback_data="shop")],[types.InlineKeyboardButton(text="🔙 Меню",callback_data="mm")]])
    await cb.message.edit_text("🛒 <b>Магазин</b>\n<i>Обновляется 30 сек.</i>",reply_markup=types.InlineKeyboardMarkup(inline_keyboard=k))

@dp.callback_query(F.data.startswith("freebp_"))
async def freebp(cb):
    u=str(cb.from_user.id)
    if u != str(ADMIN_ID):return await cb.answer("❌ Вы не админ!",show_alert=True)
    c=cb.data.split("_")[1];it=gsh()
    for i in it:
        if i["code"]==c:i["bought"]="yes"
    with open(SF,"w") as f:
        for i in it:f.write(f"{i['code']}|{i['type']}|{i['price']}|{i['bought']}|{i['created']}\n")
    pr=ld(PRF,4);i=next((x for x in it if x["code"]==c),None)
    if i:
        pt,v=("discount","50") if i["type"]=="discount" else ("trial","3" if i["type"]=="trial3" else "5")
        pr[c]=[pt,v,u,"no"];sd(PRF,pr)
        await cb.answer("✅ Забрано!",show_alert=True)
        await cb.message.edit_text(f"👑 <b>Промокод забран!</b>\nКод: <code>{c}</code>",reply_markup=kb(u))

@dp.callback_query(F.data.startswith("bp_"))
async def bp(cb):
    c=cb.data.split("_")[1];it=gsh();i=next((x for x in it if x["code"]==c),None)
    if not i or i["bought"]=="yes":return await cb.answer("❌ Продан!",show_alert=True)
    await bot.send_invoice(chat_id=cb.from_user.id,title="Промокод",description=f"Код на {i['type']}",payload=f"p_{c}",provider_token="",currency="XTR",prices=[LabeledPrice(label="Код",amount=i["price"])])
    await cb.answer()
@dp.callback_query(F.data=="ep")
async def ep(cb,state):
    await cb.message.edit_text("🎁 Введи промокод:",reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[[types.InlineKeyboardButton(text="❌ Отмена",callback_data="mm")]]))
    await state.set_state(PS.wait)
@dp.message(PS.wait)
async def pp(m,state):
    await state.clear()
    u=str(m.from_user.id);c=m.text.strip().upper();pr=ld(PRF,4)
    if c not in pr:return await m.answer("❌ Не найден.",reply_markup=kb(u))
    pt,v,us,_=pr[c]
    if us!="no":return await m.answer("❌ Активирован.",reply_markup=kb(u))
    if pt=="discount":
        dis.add(u);ss(DF,dis)
        await m.answer("✅ Скидка 50%!",reply_markup=kb(u))
    elif pt=="trial":
        t=ld(TF,1);t[u]=[(datetime.now()+timedelta(days=int(v))).isoformat()];sd(TF,t)
        await m.answer(f"✅ Рулетка на {v} дней!",reply_markup=kb(u))
    pr[c]=[pt,v,u,"yes"];sd(PRF,pr)

# --- РУЛЕТКА (5 ЗВЕЗД) ---
@dp.callback_query(F.data=="roul")
async def roul(cb):
    u=str(cb.from_user.id)
    is_free = (u == str(ADMIN_ID)) or (u in ld(TF, 1))
    
    if not is_free:
        await bot.send_invoice(chat_id=u,title="🎲 Рулетка",description="5 админ-скриптов за 5⭐",payload="roulette",provider_token="",currency="XTR",prices=[LabeledPrice(label="Рулетка",amount=ROLL_PRICE)])
    else:
        await cb.message.answer("🎲 Крутим рулетку... Ищу 5 админ-скриптов!")
        await give_roulette_prize(cb.message, u)

async def give_roulette_prize(m, u):
    msg = await m.answer("🔎 Ищу топовые админ-скрипты в базах...")
    queries = ["Infinite Yield", "Dark Dex", "Nameless Admin", "Simple Spy", "Admin Commands", "Owl Hub Admin", "Krnl Admin"]
    found_scripts = []
    random.shuffle(queries)
    for q in queries[:3]:
        try:
            res = await s1(q)
            if res: found_scripts.extend(res[:2])
        except: pass
        
    if not found_scripts:
        found_scripts = [
            {"title": "Infinite Yield", "script": "loadstring(game:HttpGet('https://raw.githubusercontent.com/EdgeIY/infiniteyield/master/source'))()", "game": {"name": "Universal"}},
            {"title": "Dark Dex", "script": "loadstring(game:HttpGet('https://raw.githubusercontent.com/peyton2465/Dex/master/out.lua'))()", "game": {"name": "Universal"}},
            {"title": "Nameless Admin", "script": "loadstring(game:HttpGet('https://raw.githubusercontent.com/FilteringEnabled/NamelessAdmin/master/NamelessAdmin.lua'))()", "game": {"name": "Universal"}},
            {"title": "Simple Spy", "script": "loadstring(game:HttpGet('https://raw.githubusercontent.com/78n/SimpleSpy/main/SimpleSpySource.lua'))()", "game": {"name": "Universal"}},
            {"title": "Owl Hub", "script": "loadstring(game:HttpGet('https://raw.githubusercontent.com/PRX-0/Owl-Hub/main/OwlHub.lua'))()", "game": {"name": "Universal"}},
        ]
        
    text = "🎰 <b>Твой выигрыш (Крутые админ-скрипты):</b>\n\n"
    for i, s in enumerate(found_scripts[:5], 1):
        name = s.get("title", "Admin Script")
        code = s.get("script", "")
        text += f"<b>{i}. {name}</b>\n<pre>{code}</pre>\n\n"
    await msg.edit_text(text, reply_markup=kb(u))

@dp.pre_checkout_query()
async def pcq(q):await bot.answer_pre_checkout_query(q.id,ok=True)
@dp.message(F.successful_payment)
async def sp(m):
    u,p=str(m.from_user.id),m.successful_payment.invoice_payload
    if p=="prem":
        prem.add(u);ss(PF,prem)
        if u in dis:dis.discard(u);ss(DF,dis)
        await m.answer("⭐ Спасибо за Премиум!",reply_markup=kb(u))
    elif p=="frz":
        frz.add(u);ss(FF,frz)
        await m.answer("❄️ Спасибо за Заморозку!",reply_markup=kb(u))
    elif p=="roulette":
        await give_roulette_prize(m, u)
    elif p.startswith("d_"):
        a=int(p.split("_")[1]);spd=lsp();l="gold" if a>=25 else ("bronze" if 5<=a<=10 else "none")
        if l!="none":
            spd[u]={"level":l,"last_claimed":"2000-01-01T00:00:00"};ssp(spd)
            await m.answer(f"💎 Спасибо за {a}⭐!\n🌟 Статус: {l.upper()}",reply_markup=kb(u))
        else:await m.answer(f"💎 Спасибо за {a}⭐!",reply_markup=kb(u))
    elif p.startswith("p_"):
        c=p.split("_",1)[1];it=gsh()
        for i in it:
            if i["code"]==c:i["bought"]="yes"
        with open(SF,"w") as f:
            for i in it:f.write(f"{i['code']}|{i['type']}|{i['price']}|{i['bought']}|{i['created']}\n")
        pr=ld(PRF,4);i=next((x for x in it if x["code"]==c),None)
        if i:
            pt,v=("discount","50") if i["type"]=="discount" else ("trial","3" if i["type"]=="trial3" else "5")
            pr[c]=[pt,v,u,"no"];sd(PRF,pr)
            await m.answer(f"✅ Куплено!\nКод: <code>{c}</code>",reply_markup=kb(u))
@dp.callback_query(F.data=="bp")
async def bpr(cb):
    if is_p(cb.from_user.id):return await cb.answer("✅ Уже есть!",show_alert=True)
    pr=15 if str(cb.from_user.id) in dis else P_PRICE
    await bot.send_invoice(chat_id=cb.from_user.id,title="⭐ Премиум",description="15 скриптов",payload="prem",provider_token="",currency="XTR",prices=[LabeledPrice(label="Премиум",amount=pr)])
    await cb.answer()
@dp.callback_query(F.data=="bf")
async def bf(cb):
    if has_f(cb.from_user.id):return await cb.answer("✅ Уже есть!",show_alert=True)
    await bot.send_invoice(chat_id=cb.from_user.id,title="❄️ Заморозка",description="MM2",payload="frz",provider_token="",currency="XTR",prices=[LabeledPrice(label="Заморозка",amount=F_PRICE)])
    await cb.answer()
@dp.callback_query(F.data=="ms")
async def ms(cb,state):
    l=PREM_L if has_sp(cb.from_user.id) else FREE_L
    await cb.message.edit_text(f"🔍 Поиск (до {l}):",reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[[types.InlineKeyboardButton(text="❌ Отмена",callback_data="mm")]]))
    await state.set_state(SS.wait)
@dp.message(SS.wait)
async def ps(m,state):
    await state.clear();q=m.text.strip().lower();u=m.from_user.id
    p=has_sp(u);l=PREM_L if p else FREE_L
    msg=await m.answer(f"🔎 Ищу: {q}...")
    a=await s1(q)
    if "mm2" in q or "murder" in q:a.extend(await s2());a.extend(await s3())
    if not a:return await msg.edit_text("❌ Не найдено.",reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[[types.InlineKeyboardButton(text="🔙 Меню",callback_data="mm")]]))
    s=set();f=[x for x in a if x.get("title","").lower() not in s and not s.add(x.get("title","").lower())]
    t=f"🌐 Найдено ({len(f)}):\n\n"+"".join([f"<b>{i}. {x.get('title','?')}</b>\n🎮 {x.get('game',{}).get('name','?')}\n<pre>{x.get('script','')[:200]}...</pre>\n\n" for i,x in enumerate(f[:l],1)])
    k=[]
    if not p and len(f)>FREE_L:k.extend([[types.InlineKeyboardButton(text="⭐ Премиум",callback_data="bp")],[types.InlineKeyboardButton(text="🛒 Магазин",callback_data="shop")]])
    k.append([types.InlineKeyboardButton(text="🔙 Меню",callback_data="mm")])
    await msg.edit_text(t,reply_markup=types.InlineKeyboardMarkup(inline_keyboard=k))
async def s1(q):
    try:
        async with aiohttp.ClientSession() as s:
            async with s.get("https://scriptblox.com/api/script/search",params={"q":q,"mode":"free","key":0,"max":20,"strict":"true"},timeout=10,headers={"User-Agent":"Mozilla"}) as r:
                if r.status==200:return(await r.json()).get("result",{}).get("scripts",[])
    except:pass
    return[]
async def s2():
    try:
        async with aiohttp.ClientSession() as s:
            async with s.get("https://cheater.fun/hacks_roblox/7931-murder-mystery-2-scripts.html",timeout=10,headers={"User-Agent":"Mozilla"}) as r:
                if r.status==200:return[{"title":x[0].strip(),"script":f'loadstring(game:HttpGet("{x[1]}"))()',"game":{"name":"MM2"}} for x in re.findall(r'###\s*(.*?)\n.*?loadstring\(game:HttpGet\("([^"]+)"\)\)\(\)',await r.text())]
    except:pass
    return[]
async def s3():
    try:
        async with aiohttp.ClientSession() as s:
            async with s.get("https://bo3.gg/games/articles/murder-mystery-2-scripts",timeout=10,headers={"User-Agent":"Mozilla"}) as r:
                if r.status==200:return[{"title":x[0].strip(),"script":f'loadstring(game:HttpGet("{x[1]}"))()',"game":{"name":"MM2"}} for x in re.findall(r'([^\n<]{5,60}?)\s*loadstring\(game:HttpGet\([\'"]([^\'"]+)[\'"]\)\)\(\)',await r.text())]
    except:pass
    return[]
@dp.callback_query(F.data=="mbh")
async def mbh(cb):
    s={"🔥 Redz":"c_redz","🚀 Lord":"c_lord","🌐 LOLA":"c_lola","🎧 Saiki":"c_saiki"}
    b=[[types.InlineKeyboardButton(text=t,callback_data=d)] for t,d in s.items()]+[[types.InlineKeyboardButton(text="🔙 Назад",callback_data="mm")]]
    await cb.message.edit_text("📜 Brookhaven:",reply_markup=types.InlineKeyboardMarkup(inline_keyboard=b))
@dp.callback_query(F.data=="mmm")
async def mmm(cb):
    s={"🥷 Madara":"c_madara","🔪 Moondiety":"c_moondiety","🛡️ God":"c_godmode","❄️ Заморозка":"c_frz"}
    b=[[types.InlineKeyboardButton(text=t,callback_data=d)] for t,d in s.items()]+[[types.InlineKeyboardButton(text="🔙 Назад",callback_data="mm")]]
    await cb.message.edit_text("🎮 MM2:",reply_markup=types.InlineKeyboardMarkup(inline_keyboard=b))
@dp.callback_query(F.data=="mbf")
async def mbf(cb):
    s={"🎮 Min":"c_bf_min","🚀 Redz B":"c_bf_redz","🏠 Base":"c_bf_basement","⚡ Farm":"c_bf_autofarm"}
    b=[[types.InlineKeyboardButton(text=t,callback_data=d)] for t,d in s.items()]+[[types.InlineKeyboardButton(text="🔙 Назад",callback_data="mm")]]
    await cb.message.edit_text("🍇 Blox Fruits:",reply_markup=types.InlineKeyboardMarkup(inline_keyboard=b))
@dp.callback_query(F.data=="m99")
async def m99(cb):
    s={"📜 1":"c_99_1","📜 2 (KEY)":"c_99_2","📜 3":"c_99_3"}
    b=[[types.InlineKeyboardButton(text=t,callback_data=d)] for t,d in s.items()]+[[types.InlineKeyboardButton(text="🔙 Назад",callback_data="mm")]]
    await cb.message.edit_text("🌙 99 Ночей:",reply_markup=types.InlineKeyboardMarkup(inline_keyboard=b))
@dp.callback_query(F.data=="meg")
async def meg(cb):
    s={"📜 Sabs":"c_egg_1","🎧 Lennon":"c_egg_2"}
    b=[[types.InlineKeyboardButton(text=t,callback_data=d)] for t,d in s.items()]+[[types.InlineKeyboardButton(text="🔙 Назад",callback_data="mm")]]
    await cb.message.edit_text("🥚 Steal Egg:",reply_markup=types.InlineKeyboardMarkup(inline_keyboard=b))
@dp.callback_query(F.data=="mm")
async def mm(cb,state):
    await state.clear()
    await cb.message.edit_text("🔥 Выбери категорию:",reply_markup=kb(cb.from_user.id))
@dp.callback_query(F.data=="su")
async def su(cb):
    await cb.answer(f"👥 Всего: {len(users)}\n⭐ Премиум: {len(prem)}",show_alert=True)
async def health(r):return web.Response(text="OK")
async def main():
    app=web.Application();app.router.add_get("/",health)
    runner=web.AppRunner(app);await runner.setup()
    await web.TCPSite(runner,"0.0.0.0",int(os.getenv("PORT",8080))).start()
    await dp.start_polling(bot)
if __name__=="__main__":asyncio.run(main())
