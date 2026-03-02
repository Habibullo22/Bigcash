import asyncio
import time
from typing import Dict, Optional, Tuple

import aiosqlite
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command
from aiogram.utils.keyboard import ReplyKeyboardBuilder, InlineKeyboardBuilder

# ======================
# CONFIG
# ======================
TOKEN = "8621200093:AAGHIYeRuf3mvrA4rrtWm7c4qHJEINtmzGk"
ADMIN_ID = 5815294733  # o'zingizning Telegram ID

DB_PATH = "avto_game.db"

COOLDOWN_SECONDS = 24 * 60 * 60          # claim 24 soatda 1 marta
CAR_ACTIVE_SECONDS = 30 * 24 * 60 * 60   # 30 kun aktiv

MIN_TOPUP = 20_000
MIN_WITHDRAW = 50_000

# Rekvizitlar (o'zingiz to'ldirasiz)
PAYMENT_REKV = {
    "humo":   "🟦 HUMO rekvizit:\n\nKarta: 8600 **** **** ****\nIsm: XXXXX XXXXX",
    "uzcard": "🟩 UZCARD rekvizit:\n\nKarta: 8600 **** **** ****\nIsm: XXXXX XXXXX",
    "visa":   "💳 VISA rekvizit:\n\nCard: 4000 **** **** ****\nName: XXXXX XXXXX",
}

# ======================
# CARS (fixed daily claim)
# price: sotib olish narxi (coin)
# month_claim: 30 kunda jami olinadigan coin (fixed)
# daily_claim: avtomatik hisoblanadi: month_claim // 30 (qoldiqni oxirgi kunda qo'shish mumkin)
# ======================
CARS = [
    {"id": 1, "name": "🚙 Cobalt",  "price": 35_000,  "month_claim": 50_000},
    {"id": 2, "name": "🚗 Malibu",  "price": 70_000,  "month_claim": 100_000},
    {"id": 3, "name": "🚘 Tracker", "price": 140_000, "month_claim": 210_000},
    {"id": 4, "name": "🚙 Tahoe",   "price": 280_000, "month_claim": 450_000},
]

for c in CARS:
    c["daily_claim"] = c["month_claim"] // 30

# ======================
# I18N (3 til)
# ======================
LANGS = ["uz", "ru", "en"]

T = {
    "uz": {
        "hello": "🚗 Avto Biznes (GAME)\n\nBu *o‘yin ichidagi coin* tizimi.\nClaim — mashinaga bog‘liq, random emas.",
        "menu": "Menyu:",
        "choose_lang": "🌐 Tilni tanlang:",
        "lang_set": "✅ Til o‘rnatildi!",
        "balance": "💰 Balans: {bal} coin",
        "cars_title": "🚗 Moshinalar:",
        "garage_empty": "🚫 Garage bo‘sh. '🚗 Moshinalar' dan sotib oling.",
        "garage_title": "🏠 Garage:",
        "buy_ok": "✅ Sotib olindi: {car}\n🗓 Aktiv: 30 kun\nKunlik: {daily} coin",
        "already_have": "Sizda bu mashina bor ✅",
        "no_money": "Balans yetarli emas ❌",
        "claim_ready": "✅ Tayyor",
        "claim_wait": "⏳ {h} soat {m} daqiqa",
        "expired": "⛔ Muddat tugagan (30 kun).",
        "claim_expired": "⛔ Bu mashinaning 30 kunlik muddati tugagan.",
        "claim_ok": "✅ Claim!\n{car}\n💵 Tushdi: {amt} coin",
        "topup_start": "➕ Hisob to‘ldirish\nSummani yozing (min {min}):",
        "withdraw_start": "➖ Pul yechish\nSummani yozing (min {min}):",
        "only_num": "❌ Faqat son yozing.",
        "min_fail": "❌ Minimaldan kam.",
        "choose_pay": "💳 To‘lov turini tanlang:",
        "send_receipt": "📷 Chek (screenshot/foto) yuboring.",
        "sent_admin": "✅ So‘rov adminga yuborildi. Tasdiqlansa balansga tushadi.",
        "choose_w_method": "💳 Qaysi turda yechasiz?",
        "enter_card": "💳 Karta raqamini yozing:",
        "withdraw_sent": "✅ Yechish so‘rovi adminga yuborildi.",
        "promo_ask": "🎁 Promo kodni yozing:",
        "promo_bad": "❌ Promo kod xato yoki tugagan.",
        "promo_ok": "🎁 Promo aktiv! +{amt} coin qo‘shildi.",
        "admin_only": "❌ Faqat admin uchun.",
        "approved": "✅ Tasdiqlandi.",
        "rejected": "❌ Rad etildi.",
        "insufficient": "❌ Balans yetarli emas.",
    },
    "ru": {
        "hello": "🚗 Авто Бизнес (GAME)\n\nЭто *игровые coin*.\nClaim фиксированный, не рандом.",
        "menu": "Меню:",
        "choose_lang": "🌐 Выберите язык:",
        "lang_set": "✅ Язык установлен!",
        "balance": "💰 Баланс: {bal} coin",
        "cars_title": "🚗 Машины:",
        "garage_empty": "🚫 Гараж пуст. Купите в '🚗 Машины'.",
        "garage_title": "🏠 Гараж:",
        "buy_ok": "✅ Куплено: {car}\n🗓 Активно: 30 дней\nВ день: {daily} coin",
        "already_have": "У вас уже есть эта машина ✅",
        "no_money": "Недостаточно средств ❌",
        "claim_ready": "✅ Готово",
        "claim_wait": "⏳ {h}ч {m}м",
        "expired": "⛔ Срок истёк (30 дней).",
        "claim_expired": "⛔ У этой машины закончился срок (30 дней).",
        "claim_ok": "✅ Claim!\n{car}\n💵 Начислено: {amt} coin",
        "topup_start": "➕ Пополнение\nВведите сумму (мин {min}):",
        "withdraw_start": "➖ Вывод\nВведите сумму (мин {min}):",
        "only_num": "❌ Только число.",
        "min_fail": "❌ Меньше минимума.",
        "choose_pay": "💳 Выберите способ оплаты:",
        "send_receipt": "📷 Отправьте чек (скрин/фото).",
        "sent_admin": "✅ Заявка отправлена админу. После подтверждения coin начислятся.",
        "choose_w_method": "💳 Как будете выводить?",
        "enter_card": "💳 Введите номер карты:",
        "withdraw_sent": "✅ Заявка на вывод отправлена админу.",
        "promo_ask": "🎁 Введите промокод:",
        "promo_bad": "❌ Промокод неверный или закончился.",
        "promo_ok": "🎁 Промо активирован! +{amt} coin.",
        "admin_only": "❌ Только для админа.",
        "approved": "✅ Одобрено.",
        "rejected": "❌ Отклонено.",
        "insufficient": "❌ Недостаточно баланса.",
    },
    "en": {
        "hello": "🚗 Auto Business (GAME)\n\nThis uses *in-game coins*.\nClaim is fixed (not random).",
        "menu": "Menu:",
        "choose_lang": "🌐 Choose language:",
        "lang_set": "✅ Language set!",
        "balance": "💰 Balance: {bal} coin",
        "cars_title": "🚗 Cars:",
        "garage_empty": "🚫 Garage is empty. Buy in '🚗 Cars'.",
        "garage_title": "🏠 Garage:",
        "buy_ok": "✅ Purchased: {car}\n🗓 Active: 30 days\nDaily: {daily} coin",
        "already_have": "You already own this car ✅",
        "no_money": "Not enough balance ❌",
        "claim_ready": "✅ Ready",
        "claim_wait": "⏳ {h}h {m}m",
        "expired": "⛔ Expired (30 days).",
        "claim_expired": "⛔ This car expired (30 days).",
        "claim_ok": "✅ Claim!\n{car}\n💵 Earned: {amt} coin",
        "topup_start": "➕ Top up\nEnter amount (min {min}):",
        "withdraw_start": "➖ Withdraw\nEnter amount (min {min}):",
        "only_num": "❌ Only number.",
        "min_fail": "❌ Below minimum.",
        "choose_pay": "💳 Choose payment method:",
        "send_receipt": "📷 Send receipt (screenshot/photo).",
        "sent_admin": "✅ Request sent to admin. Coins will be added after approval.",
        "choose_w_method": "💳 Choose withdraw method:",
        "enter_card": "💳 Enter card number:",
        "withdraw_sent": "✅ Withdraw request sent to admin.",
        "promo_ask": "🎁 Enter promo code:",
        "promo_bad": "❌ Invalid promo code or no uses left.",
        "promo_ok": "🎁 Promo activated! +{amt} coin.",
        "admin_only": "❌ Admin only.",
        "approved": "✅ Approved.",
        "rejected": "❌ Rejected.",
        "insufficient": "❌ Insufficient balance.",
    }
}

def fmt(n: int) -> str:
    return f"{n:,}".replace(",", " ")

# ======================
# DB
# ======================
INIT_SQL = """
CREATE TABLE IF NOT EXISTS users (
  user_id INTEGER PRIMARY KEY,
  lang TEXT NOT NULL DEFAULT 'uz',
  balance INTEGER NOT NULL DEFAULT 0,
  created_at INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS garage (
  user_id INTEGER NOT NULL,
  car_id INTEGER NOT NULL,
  bought_at INTEGER NOT NULL,
  last_claim_at INTEGER NOT NULL DEFAULT 0,
  claim_days INTEGER NOT NULL DEFAULT 0,
  PRIMARY KEY(user_id, car_id)
);

CREATE TABLE IF NOT EXISTS promos (
  code TEXT PRIMARY KEY,
  amount INTEGER NOT NULL,
  uses_left INTEGER NOT NULL,
  created_at INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS promo_used (
  user_id INTEGER NOT NULL,
  code TEXT NOT NULL,
  used_at INTEGER NOT NULL,
  PRIMARY KEY(user_id, code)
);

CREATE TABLE IF NOT EXISTS requests (
  req_id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER NOT NULL,
  type TEXT NOT NULL,     -- topup | withdraw
  amount INTEGER NOT NULL,
  method TEXT,            -- humo|uzcard|visa
  card TEXT,              -- withdraw card number
  receipt_file_id TEXT,   -- topup receipt
  status TEXT NOT NULL DEFAULT 'pending', -- pending|approved|rejected
  created_at INTEGER NOT NULL,
  decided_at INTEGER
);
"""

async def db_exec(q: str, *p):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(q, p)
        await db.commit()

async def db_fetchone(q: str, *p):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(q, p) as cur:
            return await cur.fetchone()

async def db_fetchall(q: str, *p):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(q, p) as cur:
            return await cur.fetchall()

async def ensure_user(uid: int):
    row = await db_fetchone("SELECT user_id FROM users WHERE user_id=?", uid)
    if not row:
        await db_exec(
            "INSERT INTO users(user_id, lang, balance, created_at) VALUES(?,?,?,?)",
            uid, "uz", 0, int(time.time())
        )

async def get_lang(uid: int) -> str:
    row = await db_fetchone("SELECT lang FROM users WHERE user_id=?", uid)
    return row[0] if row and row[0] in LANGS else "uz"

async def set_lang(uid: int, lang: str):
    await db_exec("UPDATE users SET lang=? WHERE user_id=?", lang if lang in LANGS else "uz", uid)

async def get_balance(uid: int) -> int:
    row = await db_fetchone("SELECT balance FROM users WHERE user_id=?", uid)
    return int(row[0]) if row else 0

async def add_balance(uid: int, amt: int):
    await db_exec("UPDATE users SET balance = balance + ? WHERE user_id=?", amt, uid)

async def sub_balance(uid: int, amt: int) -> bool:
    bal = await get_balance(uid)
    if bal < amt:
        return False
    await db_exec("UPDATE users SET balance = balance - ? WHERE user_id=?", amt, uid)
    return True

async def has_car(uid: int, car_id: int) -> bool:
    row = await db_fetchone("SELECT 1 FROM garage WHERE user_id=? AND car_id=?", uid, car_id)
    return bool(row)

async def get_garage(uid: int):
    return await db_fetchall(
        "SELECT car_id, bought_at, last_claim_at, claim_days FROM garage WHERE user_id=? ORDER BY car_id",
        uid
    )

# promo
async def promo_get(code: str):
    return await db_fetchone("SELECT amount, uses_left FROM promos WHERE code=?", code)

async def promo_dec_use(code: str):
    await db_exec("UPDATE promos SET uses_left = uses_left - 1 WHERE code=? AND uses_left>0", code)

async def promo_is_used(uid: int, code: str) -> bool:
    row = await db_fetchone("SELECT 1 FROM promo_used WHERE user_id=? AND code=?", uid, code)
    return bool(row)

async def promo_mark_used(uid: int, code: str):
    await db_exec("INSERT INTO promo_used(user_id, code, used_at) VALUES(?,?,?)", uid, code, int(time.time()))

# requests
async def create_request(uid: int, rtype: str, amount: int, method: Optional[str]=None,
                         card: Optional[str]=None, receipt_file_id: Optional[str]=None) -> int:
    now = int(time.time())
    await db_exec(
        "INSERT INTO requests(user_id,type,amount,method,card,receipt_file_id,status,created_at) VALUES(?,?,?,?,?,?,?,?)",
        uid, rtype, amount, method, card, receipt_file_id, "pending", now
    )
    row = await db_fetchone(
        "SELECT req_id FROM requests WHERE user_id=? AND created_at=? ORDER BY req_id DESC LIMIT 1",
        uid, now
    )
    return int(row[0]) if row else -1

# ======================
# KEYBOARDS
# ======================
def kb_main(lang: str) -> types.ReplyKeyboardMarkup:
    kb = ReplyKeyboardBuilder()
    labels = {
        "uz": ["🚗 Moshinalar", "🏠 Garage", "💰 Balans", "🎁 Promo", "➕ Hisob to‘ldirish", "➖ Pul yechish", "🌐 Til"],
        "ru": ["🚗 Машины", "🏠 Гараж", "💰 Баланс", "🎁 Промо", "➕ Пополнить", "➖ Вывод", "🌐 Язык"],
        "en": ["🚗 Cars", "🏠 Garage", "💰 Balance", "🎁 Promo", "➕ Top up", "➖ Withdraw", "🌐 Language"],
    }[lang]
    for t in labels:
        kb.button(text=t)
    kb.adjust(2, 2, 2, 1)
    return kb.as_markup(resize_keyboard=True)

def kb_lang() -> types.InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="🇺🇿 O‘zbek", callback_data="lang:uz")
    kb.button(text="🇷🇺 Русский", callback_data="lang:ru")
    kb.button(text="🇬🇧 English", callback_data="lang:en")
    kb.adjust(1)
    return kb.as_markup()

def kb_cars() -> types.InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for c in CARS:
        kb.button(
            text=f"{c['name']} | {fmt(c['price'])} | {fmt(c['daily_claim'])}/day",
            callback_data=f"buy:{c['id']}"
        )
    kb.adjust(1)
    return kb.as_markup()

def kb_garage(items) -> types.InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for car_id, bought_at, last_claim_at, claim_days in items:
        car = next(x for x in CARS if x["id"] == car_id)
        kb.button(text=f"✅ Claim: {car['name']}", callback_data=f"claim:{car_id}")
    kb.adjust(1)
    return kb.as_markup()

def kb_pay_methods(prefix: str) -> types.InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="🟦 HUMO", callback_data=f"{prefix}:humo")
    kb.button(text="🟩 UZCARD", callback_data=f"{prefix}:uzcard")
    kb.button(text="💳 VISA", callback_data=f"{prefix}:visa")
    kb.adjust(3)
    return kb.as_markup()

def kb_paid(prefix: str) -> types.InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="✅ To‘lov qildim / Оплатил / I paid", callback_data=f"{prefix}:paid")
    kb.adjust(1)
    return kb.as_markup()

def kb_admin_req(req_id: int) -> types.InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="✅ Approve", callback_data=f"adm:ok:{req_id}")
    kb.button(text="❌ Reject", callback_data=f"adm:no:{req_id}")
    kb.adjust(2)
    return kb.as_markup()

# ======================
# STATE (oddiy)
# ======================
# mode:
#   topup_amount -> user summa kiritadi
#   topup_method -> method tanlaydi
#   topup_wait_receipt -> chek kutadi
#   withdraw_amount -> summa
#   withdraw_method -> method
#   withdraw_card -> karta raqami
#   promo -> promo code
user_state: Dict[int, Dict] = {}

def set_state(uid: int, mode: str, data: Optional[dict]=None):
    user_state[uid] = {"mode": mode, "data": data or {}}

def get_state(uid: int) -> Optional[dict]:
    return user_state.get(uid)

def clear_state(uid: int):
    user_state.pop(uid, None)

# ======================
# BUTTON TEXT MATCH (3 til)
# ======================
def is_btn(text: str, lang: str, key: str) -> bool:
    m = {
        "cars":     {"uz": "🚗 Moshinalar",      "ru": "🚗 Машины",      "en": "🚗 Cars"},
        "garage":   {"uz": "🏠 Garage",         "ru": "🏠 Гараж",       "en": "🏠 Garage"},
        "balance":  {"uz": "💰 Balans",         "ru": "💰 Баланс",      "en": "💰 Balance"},
        "promo":    {"uz": "🎁 Promo",          "ru": "🎁 Промо",       "en": "🎁 Promo"},
        "topup":    {"uz": "➕ Hisob to‘ldirish","ru": "➕ Пополнить",   "en": "➕ Top up"},
        "withdraw": {"uz": "➖ Pul yechish",     "ru": "➖ Вывод",       "en": "➖ Withdraw"},
        "lang":     {"uz": "🌐 Til",            "ru": "🌐 Язык",        "en": "🌐 Language"},
    }
    return text == m[key][lang]

# ======================
# BOT
# ======================
bot = Bot(TOKEN)
dp = Dispatcher()

@dp.message(Command("start"))
async def start(m: types.Message):
    uid = m.from_user.id
    await ensure_user(uid)
    lang = await get_lang(uid)
    await m.answer(T[lang]["hello"])
    await m.answer(T[lang]["menu"], reply_markup=kb_main(lang))

# -------- Admin: promo create --------
# /promo_create CODE AMOUNT USES
@dp.message(Command("promo_create"))
async def promo_create(m: types.Message):
    if m.from_user.id != ADMIN_ID:
        lang = await get_lang(m.from_user.id)
        return await m.answer(T[lang]["admin_only"])
    parts = m.text.split()
    if len(parts) != 4 or (not parts[2].isdigit()) or (not parts[3].isdigit()):
        return await m.answer("Usage: /promo_create CODE AMOUNT USES\nExample: /promo_create START10 10000 50")
    code = parts[1].upper()
    amount = int(parts[2])
    uses = int(parts[3])
    await db_exec(
        "INSERT OR REPLACE INTO promos(code, amount, uses_left, created_at) VALUES(?,?,?,?)",
        code, amount, uses, int(time.time())
    )
    await m.answer(f"✅ Promo yaratildi: {code} | +{fmt(amount)} | uses={uses}")

# -------- Admin: pending list --------
@dp.message(Command("pending"))
async def pending(m: types.Message):
    if m.from_user.id != ADMIN_ID:
        lang = await get_lang(m.from_user.id)
        return await m.answer(T[lang]["admin_only"])
    rows = await db_fetchall(
        "SELECT req_id,user_id,type,amount,method,card,receipt_file_id FROM requests WHERE status='pending' ORDER BY req_id DESC LIMIT 30"
    )
    if not rows:
        return await m.answer("🟢 Pending yo‘q.")
    for req_id, uid, typ, amount, method, card, receipt in rows:
        txt = (
            f"🧾 Request #{req_id}\n"
            f"User: {uid}\n"
            f"Type: {typ}\n"
            f"Amount: {fmt(int(amount))}\n"
            f"Method: {method}\n"
        )
        if typ == "withdraw":
            txt += f"Card: {card}\n"
        await m.answer(txt, reply_markup=kb_admin_req(int(req_id)))
        # Agar topup bo'lsa va receipt rasm bo'lsa, admin'ga yana rasmni ham yuboramiz
        if typ == "topup" and receipt:
            try:
                await bot.send_photo(ADMIN_ID, receipt, caption=f"Receipt for #{req_id}")
            except Exception:
                pass

@dp.callback_query(F.data.startswith("adm:"))
async def admin_decide(cb: types.CallbackQuery):
    if cb.from_user.id != ADMIN_ID:
        return await cb.answer("Admin only", show_alert=True)

    _, action, req_id_s = cb.data.split(":")
    req_id = int(req_id_s)

    row = await db_fetchone(
        "SELECT user_id,type,amount,status FROM requests WHERE req_id=?",
        req_id
    )
    if not row:
        return await cb.answer("Not found", show_alert=True)
    uid, typ, amount, status = int(row[0]), row[1], int(row[2]), row[3]
    if status != "pending":
        return await cb.answer("Already decided", show_alert=True)

    user_lang = await get_lang(uid)

    if action == "ok":
        if typ == "topup":
            await add_balance(uid, amount)
        elif typ == "withdraw":
            ok = await sub_balance(uid, amount)
            if not ok:
                await db_exec("UPDATE requests SET status='rejected', decided_at=? WHERE req_id=?", int(time.time()), req_id)
                await bot.send_message(uid, T[user_lang]["insufficient"])
                await cb.message.edit_text(cb.message.text + "\n\n❌ Auto-rejected (insufficient balance).")
                return await cb.answer("Rejected", show_alert=True)

        await db_exec("UPDATE requests SET status='approved', decided_at=? WHERE req_id=?", int(time.time()), req_id)
        await bot.send_message(uid, T[user_lang]["approved"])
        await cb.message.edit_text(cb.message.text + "\n\n✅ Approved.")
        return await cb.answer("Approved")

    if action == "no":
        await db_exec("UPDATE requests SET status='rejected', decided_at=? WHERE req_id=?", int(time.time()), req_id)
        await bot.send_message(uid, T[user_lang]["rejected"])
        await cb.message.edit_text(cb.message.text + "\n\n❌ Rejected.")
        return await cb.answer("Rejected")

# -------- Language --------
@dp.message(F.text.in_({"🌐 Til", "🌐 Язык", "🌐 Language"}))
async def choose_lang(m: types.Message):
    uid = m.from_user.id
    await ensure_user(uid)
    lang = await get_lang(uid)
    await m.answer(T[lang]["choose_lang"], reply_markup=kb_lang())

@dp.callback_query(F.data.startswith("lang:"))
async def lang_cb(cb: types.CallbackQuery):
    uid = cb.from_user.id
    await ensure_user(uid)
    lang = cb.data.split(":")[1]
    await set_lang(uid, lang)
    lang = await get_lang(uid)
    await cb.message.answer(T[lang]["lang_set"], reply_markup=kb_main(lang))
    await cb.answer()

# -------- Cars / Garage / Balance / Promo / Topup / Withdraw --------
@dp.message()
async def menu(m: types.Message):
    uid = m.from_user.id
    await ensure_user(uid)
    lang = await get_lang(uid)
    text = (m.text or "").strip()

    st = get_state(uid)
    if st:
        mode = st["mode"]
        data = st["data"]

        # PROMO INPUT
        if mode == "promo":
            code = text.upper()
            clear_state(uid)
            promo = await promo_get(code)
            if (not promo) or (await promo_is_used(uid, code)) or int(promo[1]) <= 0:
                return await m.answer(T[lang]["promo_bad"])
            amount = int(promo[0])
            await add_balance(uid, amount)
            await promo_mark_used(uid, code)
            await promo_dec_use(code)
            return await m.answer(T[lang]["promo_ok"].format(amt=fmt(amount)))

        # TOPUP AMOUNT INPUT
        if mode == "topup_amount":
            if not text.isdigit():
                clear_state(uid)
                return await m.answer(T[lang]["only_num"])
            amount = int(text)
            if amount < MIN_TOPUP:
                clear_state(uid)
                return await m.answer(T[lang]["min_fail"])
            data["amount"] = amount
            set_state(uid, "topup_method", data)
            return await m.answer(T[lang]["choose_pay"], reply_markup=kb_pay_methods("topupm"))

        # WITHDRAW AMOUNT INPUT
        if mode == "withdraw_amount":
            if not text.isdigit():
                clear_state(uid)
                return await m.answer(T[lang]["only_num"])
            amount = int(text)
            if amount < MIN_WITHDRAW:
                clear_state(uid)
                return await m.answer(T[lang]["min_fail"])
            bal = await get_balance(uid)
            if bal < amount:
                clear_state(uid)
                return await m.answer(T[lang]["insufficient"])
            data["amount"] = amount
            set_state(uid, "withdraw_method", data)
            return await m.answer(T[lang]["choose_w_method"], reply_markup=kb_pay_methods("withm"))

        # WITHDRAW CARD INPUT
        if mode == "withdraw_card":
            card = text.replace(" ", "")
            if len(card) < 8:
                clear_state(uid)
                return await m.answer(T[lang]["enter_card"])
            amount = int(data["amount"])
            method = data["method"]
            req_id = await create_request(uid, "withdraw", amount, method=method, card=card)
            clear_state(uid)
            # admin notify
            await bot.send_message(
                ADMIN_ID,
                f"💸 WITHDRAW Request #{req_id}\nUser: {uid}\nAmount: {fmt(amount)}\nMethod: {method}\nCard: {card}",
                reply_markup=kb_admin_req(req_id)
            )
            return await m.answer(T[lang]["withdraw_sent"])

        # TOPUP RECEIPT WAIT (photo/doc)
        if mode == "topup_wait_receipt":
            receipt_file_id = None
            if m.photo:
                receipt_file_id = m.photo[-1].file_id
            elif m.document:
                receipt_file_id = m.document.file_id

            if not receipt_file_id:
                return await m.answer(T[lang]["send_receipt"])

            amount = int(data["amount"])
            method = data["method"]
            req_id = await create_request(uid, "topup", amount, method=method, receipt_file_id=receipt_file_id)
            clear_state(uid)

            await bot.send_message(
                ADMIN_ID,
                f"🧾 TOPUP Request #{req_id}\nUser: {uid}\nAmount: {fmt(amount)}\nMethod: {method}",
                reply_markup=kb_admin_req(req_id)
            )
            try:
                await bot.send_photo(ADMIN_ID, receipt_file_id, caption=f"Receipt for TOPUP #{req_id}")
            except Exception:
                pass

            return await m.answer(T[lang]["sent_admin"])

    # MENU ACTIONS
    if is_btn(text, lang, "balance"):
        b = await get_balance(uid)
        return await m.answer(T[lang]["balance"].format(bal=fmt(b)))

    if is_btn(text, lang, "cars"):
        lines = [T[lang]["cars_title"]]
        for c in CARS:
            lines.append(
                f"- {c['name']} | {fmt(c['price'])} coin | {fmt(c['month_claim'])}/oy | {fmt(c['daily_claim'])}/kun"
            )
        return await m.answer("\n".join(lines), reply_markup=kb_cars())

    if is_btn(text, lang, "garage"):
        items = await get_garage(uid)
        if not items:
            return await m.answer(T[lang]["garage_empty"])
        now = int(time.time())
        msg = [T[lang]["garage_title"]]
        for car_id, bought_at, last_claim_at, claim_days in items:
            car = next(x for x in CARS if x["id"] == car_id)
            active_left = max(0, CAR_ACTIVE_SECONDS - (now - int(bought_at)))
            if active_left == 0:
                status = T[lang]["expired"]
            else:
                # cooldown
                cd = max(0, COOLDOWN_SECONDS - (now - int(last_claim_at)))
                if cd == 0:
                    status = T[lang]["claim_ready"]
                else:
                    status = T[lang]["claim_wait"].format(h=cd // 3600, m=(cd % 3600) // 60)
            msg.append(f"{car['name']} | {fmt(car['daily_claim'])}/kun | {status}")
        return await m.answer("\n".join(msg), reply_markup=kb_garage(items))

    if is_btn(text, lang, "promo"):
        set_state(uid, "promo", {})
        return await m.answer(T[lang]["promo_ask"])

    if is_btn(text, lang, "topup"):
        set_state(uid, "topup_amount", {})
        return await m.answer(T[lang]["topup_start"].format(min=fmt(MIN_TOPUP)))

    if is_btn(text, lang, "withdraw"):
        set_state(uid, "withdraw_amount", {})
        return await m.answer(T[lang]["withdraw_start"].format(min=fmt(MIN_WITHDRAW)))

    if is_btn(text, lang, "lang"):
        return await m.answer(T[lang]["choose_lang"], reply_markup=kb_lang())

# -------- Callbacks: BUY / CLAIM --------
@dp.callback_query(F.data.startswith("buy:"))
async def buy(cb: types.CallbackQuery):
    uid = cb.from_user.id
    await ensure_user(uid)
    lang = await get_lang(uid)

    car_id = int(cb.data.split(":")[1])
    car = next((x for x in CARS if x["id"] == car_id), None)
    if not car:
        return await cb.answer(T[lang]["no_money"], show_alert=True)

    if await has_car(uid, car_id):
        return await cb.answer(T[lang]["already_have"], show_alert=True)

    ok = await sub_balance(uid, car["price"])
    if not ok:
        return await cb.answer(T[lang]["no_money"], show_alert=True)

    now = int(time.time())
    await db_exec(
        "INSERT INTO garage(user_id,car_id,bought_at,last_claim_at,claim_days) VALUES(?,?,?,?,?)",
        uid, car_id, now, 0, 0
    )
    await cb.message.answer(
        T[lang]["buy_ok"].format(car=car["name"], daily=fmt(car["daily_claim"]))
    )
    await cb.answer()

@dp.callback_query(F.data.startswith("claim:"))
async def claim(cb: types.CallbackQuery):
    uid = cb.from_user.id
    await ensure_user(uid)
    lang = await get_lang(uid)

    car_id = int(cb.data.split(":")[1])
    row = await db_fetchone(
        "SELECT bought_at,last_claim_at,claim_days FROM garage WHERE user_id=? AND car_id=?",
        uid, car_id
    )
    if not row:
        return await cb.answer(T[lang]["garage_empty"], show_alert=True)

    bought_at, last_claim_at, claim_days = int(row[0]), int(row[1]), int(row[2])
    now = int(time.time())

    # 30 kun aktiv
    if now - bought_at > CAR_ACTIVE_SECONDS:
        return await cb.answer(T[lang]["claim_expired"], show_alert=True)

    # 24h cooldown
    if now - last_claim_at < COOLDOWN_SECONDS:
        left = COOLDOWN_SECONDS - (now - last_claim_at)
        return await cb.answer(T[lang]["claim_wait"].format(h=left // 3600, m=(left % 3600) // 60), show_alert=True)

    car = next(x for x in CARS if x["id"] == car_id)
    amt = int(car["daily_claim"])

    await add_balance(uid, amt)
    await db_exec(
        "UPDATE garage SET last_claim_at=?, claim_days=claim_days+1 WHERE user_id=? AND car_id=?",
        now, uid, car_id
    )
    await cb.message.answer(T[lang]["claim_ok"].format(car=car["name"], amt=fmt(amt)))
    await cb.answer()

# -------- Callbacks: TOPUP method / paid --------
@dp.callback_query(F.data.startswith("topupm:"))
async def topup_method(cb: types.CallbackQuery):
    uid = cb.from_user.id
    await ensure_user(uid)
    lang = await get_lang(uid)

    st = get_state(uid)
    if not st or st["mode"] != "topup_method":
        return await cb.answer("State expired", show_alert=True)

    method = cb.data.split(":")[1]
    st["data"]["method"] = method

    # rekvizit ko'rsatamiz + "to'lov qildim" tugma
    rekv = PAYMENT_REKV.get(method, "Rekvizit topilmadi")
    await cb.message.answer(rekv)
    await cb.message.answer("✅ To‘lovni qiling, keyin tugmani bosing:", reply_markup=kb_paid("topupdone"))
    await cb.answer()

@dp.callback_query(F.data.startswith("topupdone:paid"))
async def topup_paid(cb: types.CallbackQuery):
    uid = cb.from_user.id
    await ensure_user(uid)
    lang = await get_lang(uid)

    st = get_state(uid)
    if not st or st["mode"] != "topup_method":
        return await cb.answer("State expired", show_alert=True)

    # endi chek kutamiz
    set_state(uid, "topup_wait_receipt", st["data"])
    await cb.message.answer(T[lang]["send_receipt"])
    await cb.answer()

# -------- Callbacks: WITHDRAW method --------
@dp.callback_query(F.data.startswith("withm:"))
async def withdraw_method(cb: types.CallbackQuery):
    uid = cb.from_user.id
    await ensure_user(uid)
    lang = await get_lang(uid)

    st = get_state(uid)
    if not st or st["mode"] != "withdraw_method":
        return await cb.answer("State expired", show_alert=True)

    method = cb.data.split(":")[1]
    st["data"]["method"] = method
    set_state(uid, "withdraw_card", st["data"])
    await cb.message.answer(T[lang]["enter_card"])
    await cb.answer()

# ======================
# RUN
# ======================
async def on_startup():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.executescript(INIT_SQL)
        await db.commit()

async def main():
    await on_startup()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
