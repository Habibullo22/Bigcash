import asyncio
import random
import time
from typing import Dict, Tuple

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

COOLDOWN_SECONDS = 24 * 60 * 60         # claim 24 soatda 1 marta
CAR_ACTIVE_SECONDS = 30 * 24 * 60 * 60  # 30 kun aktiv

ROI_MIN = 10
ROI_MAX = 25

# risk: ehtimolliklar
RISK_PROB_NEG = 0.10   # 10% -5%
RISK_PROB_ZERO = 0.15  # 15% 0%
NEG_ROI_PERCENT = -5

MIN_TOPUP = 20_000
MIN_WITHDRAW = 50_000

UPGRADE_COST_MULT = 0.35
UPGRADE_INCOME_BONUS = 0.12

# Mashinalar (coin narx + daily_base)
CARS = [
    {"id": 1, "key": "cobalt",  "level": 1, "price": 35_000,  "daily_base": 20_000},
    {"id": 2, "key": "malibu",  "level": 2, "price": 70_000,  "daily_base": 42_000},
    {"id": 3, "key": "tracker", "level": 3, "price": 140_000, "daily_base": 90_000},
    {"id": 4, "key": "tahoe",   "level": 4, "price": 280_000, "daily_base": 190_000},
]

# Promo kodlar (1 martalik)
PROMOS = {
    "START10": 10_000,
    "BONUS25": 25_000,
}

# ======================
# I18N
# ======================
LANGS = ["uz", "ru", "en"]

T: Dict[str, Dict[str, str]] = {
    "uz": {
        "hello": "🚗 Avto Biznes Game\n\nBu o‘yin ichidagi coin tizimi. Daromad *kafolat emas* (random + risk).",
        "menu": "Menyu:",
        "choose_lang": "🌐 Tilni tanlang:",
        "lang_set": "✅ Til o‘rnatildi!",
        "balance": "💰 Balans: {bal} coin",
        "cars": "🚗 Moshinalar ro‘yxati:",
        "garage_empty": "🚫 Garage bo‘sh. '🚗 Moshinalar' dan sotib oling.",
        "garage": "🏠 Garage:",
        "cooldown_ready": "✅ Tayyor",
        "cooldown_left": "⏳ {h} soat {m} daqiqa",
        "expired": "⛔ Muddat tugagan (30 kun).",
        "active_left": "🗓 Qoldi: {d} kun",
        "already_have": "Sizda bu mashina bor ✅",
        "not_found": "Topilmadi",
        "no_money": "Balans yetarli emas ❌",
        "bought": "✅ Sotib olindi: {car}\n🗓 Aktiv muddat: 30 kun\nEndi '🏠 Garage' dan claim qiling.",
        "no_car": "Sizda bu mashina yo‘q",
        "too_early": "Vaqti hali kelmagan ⏳ {h} soat",
        "claim_expired": "⛔ Bu mashinaning 30 kunlik muddati tugagan.",
        "claim_ok": "✅ Claim muvaffaqiyatli!\n{car} (L{lvl})\n🎲 Bugungi ROI: {roi}%\n💵 Tushdi: {earned} coin",
        "upgrade_ok": "⬆️ Upgrade bo‘ldi!\n{car} -> L{lvl}\n💸 Sarflandi: {cost} coin",
        "topup_title": "➕ Hisob to‘ldirish (coin)\nMinimal: {min} coin\n\nSummani yozing (masalan: 20000).",
        "withdraw_title": "➖ Pul yechish (coin)\nMinimal: {min} coin\n\nSummani yozing (masalan: 50000).",
        "min_fail": "❌ Minimaldan kam.",
        "sent_admin": "✅ So‘rov adminga yuborildi.",
        "withdraw_insufficient": "❌ Balans yetarli emas.",
        "promo_ask": "🎁 Promo kodni yozing (masalan: START10).",
        "promo_bad": "❌ Promo kod xato yoki ishlatilgan.",
        "promo_ok": "🎁 Promo aktiv! +{amt} coin qo‘shildi.",
        "stats": "📊 Statistika:\n👤 Siz: claim={c} | topup={t} | withdraw={w}\n💰 Balans: {b} coin",
        "admin_only": "❌ Faqat admin uchun.",
        "approved": "✅ Tasdiqlandi.",
        "rejected": "❌ Rad etildi.",
        "only_num": "❌ Faqat son yozing.",
    },
    "ru": {
        "hello": "🚗 Авто Бизнес Game\n\nЭто игровая система coin. Доход *не гарантирован* (рандом + риск).",
        "menu": "Меню:",
        "choose_lang": "🌐 Выберите язык:",
        "lang_set": "✅ Язык установлен!",
        "balance": "💰 Баланс: {bal} coin",
        "cars": "🚗 Список машин:",
        "garage_empty": "🚫 Гараж пуст. Купите в '🚗 Машины'.",
        "garage": "🏠 Гараж:",
        "cooldown_ready": "✅ Готово",
        "cooldown_left": "⏳ {h} ч {m} мин",
        "expired": "⛔ Срок истёк (30 дней).",
        "active_left": "🗓 Осталось: {d} дней",
        "already_have": "У вас уже есть эта машина ✅",
        "not_found": "Не найдено",
        "no_money": "Недостаточно средств ❌",
        "bought": "✅ Куплено: {car}\n🗓 Активно: 30 дней\nТеперь claim в '🏠 Гараж'.",
        "no_car": "У вас нет этой машины",
        "too_early": "Рано ⏳ {h} ч",
        "claim_expired": "⛔ У этой машины закончился срок (30 дней).",
        "claim_ok": "✅ Claim успешно!\n{car} (L{lvl})\n🎲 ROI сегодня: {roi}%\n💵 Начислено: {earned} coin",
        "upgrade_ok": "⬆️ Улучшение успешно!\n{car} -> L{lvl}\n💸 Потрачено: {cost} coin",
        "topup_title": "➕ Пополнение (coin)\nМинимум: {min} coin\n\nВведите сумму (например: 20000).",
        "withdraw_title": "➖ Вывод (coin)\nМинимум: {min} coin\n\nВведите сумму (например: 50000).",
        "min_fail": "❌ Меньше минимума.",
        "sent_admin": "✅ Заявка отправлена админу.",
        "withdraw_insufficient": "❌ Недостаточно баланса.",
        "promo_ask": "🎁 Введите промокод (например: START10).",
        "promo_bad": "❌ Промокод неверный или уже использован.",
        "promo_ok": "🎁 Промо активирован! +{amt} coin.",
        "stats": "📊 Статистика:\n👤 Вы: claim={c} | topup={t} | withdraw={w}\n💰 Баланс: {b} coin",
        "admin_only": "❌ Только для админа.",
        "approved": "✅ Одобрено.",
        "rejected": "❌ Отклонено.",
        "only_num": "❌ Только число.",
    },
    "en": {
        "hello": "🚗 Auto Business Game\n\nThis is an in-game coin system. Earnings are *not guaranteed* (random + risk).",
        "menu": "Menu:",
        "choose_lang": "🌐 Choose language:",
        "lang_set": "✅ Language set!",
        "balance": "💰 Balance: {bal} coin",
        "cars": "🚗 Car list:",
        "garage_empty": "🚫 Garage is empty. Buy from '🚗 Cars'.",
        "garage": "🏠 Garage:",
        "cooldown_ready": "✅ Ready",
        "cooldown_left": "⏳ {h}h {m}m",
        "expired": "⛔ Expired (30 days).",
        "active_left": "🗓 Left: {d} days",
        "already_have": "You already own this car ✅",
        "not_found": "Not found",
        "no_money": "Not enough balance ❌",
        "bought": "✅ Purchased: {car}\n🗓 Active: 30 days\nNow claim in '🏠 Garage'.",
        "no_car": "You don’t have this car",
        "too_early": "Too early ⏳ {h}h",
        "claim_expired": "⛔ This car expired (30 days).",
        "claim_ok": "✅ Claim success!\n{car} (L{lvl})\n🎲 Today ROI: {roi}%\n💵 Earned: {earned} coin",
        "upgrade_ok": "⬆️ Upgrade success!\n{car} -> L{lvl}\n💸 Spent: {cost} coin",
        "topup_title": "➕ Top up (coin)\nMinimum: {min} coin\n\nType amount (e.g. 20000).",
        "withdraw_title": "➖ Withdraw (coin)\nMinimum: {min} coin\n\nType amount (e.g. 50000).",
        "min_fail": "❌ Below minimum.",
        "sent_admin": "✅ Request sent to admin.",
        "withdraw_insufficient": "❌ Insufficient balance.",
        "promo_ask": "🎁 Enter promo code (e.g. START10).",
        "promo_bad": "❌ Invalid or already used promo code.",
        "promo_ok": "🎁 Promo activated! +{amt} coin.",
        "stats": "📊 Stats:\n👤 You: claim={c} | topup={t} | withdraw={w}\n💰 Balance: {b} coin",
        "admin_only": "❌ Admin only.",
        "approved": "✅ Approved.",
        "rejected": "❌ Rejected.",
        "only_num": "❌ Only number.",
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
  level INTEGER NOT NULL DEFAULT 1,
  bought_at INTEGER NOT NULL DEFAULT 0,
  last_claim_at INTEGER NOT NULL DEFAULT 0,
  PRIMARY KEY (user_id, car_id)
);

CREATE TABLE IF NOT EXISTS promo_used (
  user_id INTEGER NOT NULL,
  code TEXT NOT NULL,
  used_at INTEGER NOT NULL,
  PRIMARY KEY(user_id, code)
);

CREATE TABLE IF NOT EXISTS stats (
  user_id INTEGER PRIMARY KEY,
  claims INTEGER NOT NULL DEFAULT 0,
  topups INTEGER NOT NULL DEFAULT 0,
  withdraws INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS requests (
  req_id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER NOT NULL,
  type TEXT NOT NULL, -- topup|withdraw
  amount INTEGER NOT NULL,
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
        now = int(time.time())
        await db_exec("INSERT INTO users(user_id, lang, balance, created_at) VALUES(?,?,?,?)", uid, "uz", 0, now)
        await db_exec("INSERT OR IGNORE INTO stats(user_id) VALUES(?)", uid)
    else:
        await db_exec("INSERT OR IGNORE INTO stats(user_id) VALUES(?)", uid)

async def get_lang(uid: int) -> str:
    row = await db_fetchone("SELECT lang FROM users WHERE user_id=?", uid)
    return row[0] if row and row[0] in LANGS else "uz"

async def set_lang(uid: int, lang: str):
    if lang not in LANGS:
        lang = "uz"
    await db_exec("UPDATE users SET lang=? WHERE user_id=?", lang, uid)

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
    return await db_fetchall("SELECT car_id, level, bought_at, last_claim_at FROM garage WHERE user_id=? ORDER BY car_id", uid)

async def inc_stat(uid: int, field: str):
    if field not in ("claims", "topups", "withdraws"):
        return
    await db_exec(f"UPDATE stats SET {field} = {field} + 1 WHERE user_id=?", uid)

async def get_stats(uid: int) -> Tuple[int, int, int]:
    row = await db_fetchone("SELECT claims, topups, withdraws FROM stats WHERE user_id=?", uid)
    if not row:
        return (0, 0, 0)
    return int(row[0]), int(row[1]), int(row[2])

async def promo_is_used(uid: int, code: str) -> bool:
    row = await db_fetchone("SELECT 1 FROM promo_used WHERE user_id=? AND code=?", uid, code)
    return bool(row)

async def mark_promo_used(uid: int, code: str):
    await db_exec("INSERT INTO promo_used(user_id, code, used_at) VALUES(?,?,?)", uid, code, int(time.time()))

async def create_request(uid: int, rtype: str, amount: int) -> int:
    now = int(time.time())
    await db_exec(
        "INSERT INTO requests(user_id, type, amount, status, created_at) VALUES(?,?,?,?,?)",
        uid, rtype, amount, "pending", now
    )
    rid = await db_fetchone(
        "SELECT req_id FROM requests WHERE user_id=? AND created_at=? ORDER BY req_id DESC LIMIT 1",
        uid, now
    )
    return int(rid[0]) if rid else -1

# ======================
# CAR NAMES (3 til)
# ======================
CAR_NAMES = {
    "cobalt":  {"uz": "🚙 Cobalt",  "ru": "🚙 Cobalt",  "en": "🚙 Cobalt"},
    "malibu":  {"uz": "🚗 Malibu",  "ru": "🚗 Malibu",  "en": "🚗 Malibu"},
    "tracker": {"uz": "🚘 Tracker", "ru": "🚘 Tracker", "en": "🚘 Tracker"},
    "tahoe":   {"uz": "🚙 Tahoe",   "ru": "🚙 Tahoe",   "en": "🚙 Tahoe"},
}

def car_name(car_key: str, lang: str) -> str:
    return CAR_NAMES.get(car_key, {}).get(lang, car_key)

# ======================
# KEYBOARDS
# ======================
def kb_main(lang: str) -> types.ReplyKeyboardMarkup:
    kb = ReplyKeyboardBuilder()
    labels = {
        "uz": ["🚗 Moshinalar", "🏠 Garage", "💰 Balans", "🎁 Promo", "📊 Statistika", "➕ Hisob to‘ldirish", "➖ Pul yechish", "🌐 Til"],
        "ru": ["🚗 Машины", "🏠 Гараж", "💰 Баланс", "🎁 Промо", "📊 Статистика", "➕ Пополнить", "➖ Вывод", "🌐 Язык"],
        "en": ["🚗 Cars", "🏠 Garage", "💰 Balance", "🎁 Promo", "📊 Stats", "➕ Top up", "➖ Withdraw", "🌐 Language"],
    }[lang]
    for t in labels:
        kb.button(text=t)
    kb.adjust(2, 2, 2, 2)
    return kb.as_markup(resize_keyboard=True)

def kb_lang() -> types.InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="🇺🇿 O‘zbek", callback_data="lang:uz")
    kb.button(text="🇷🇺 Русский", callback_data="lang:ru")
    kb.button(text="🇬🇧 English", callback_data="lang:en")
    kb.adjust(1)
    return kb.as_markup()

def kb_cars(lang: str) -> types.InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for c in CARS:
        nm = car_name(c["key"], lang)
        kb.button(
            text=f"{nm} | L{c['level']} | {fmt(c['price'])} coin",
            callback_data=f"buy:{c['id']}",
        )
    kb.adjust(1)
    return kb.as_markup()

def kb_garage(items, lang: str) -> types.InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for car_id, lvl, bought_at, last_claim_at in items:
        car = next(x for x in CARS if x["id"] == car_id)
        nm = car_name(car["key"], lang)
        kb.button(text=f"✅ Claim: {nm} (L{lvl})", callback_data=f"claim:{car_id}")
        kb.button(text=f"⬆️ Upgrade: {nm} (L{lvl})", callback_data=f"upg:{car_id}")
    kb.adjust(1)
    return kb.as_markup()

def kb_admin_req(req_id: int, rtype: str) -> types.InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="✅ Approve", callback_data=f"adm:ok:{rtype}:{req_id}")
    kb.button(text="❌ Reject", callback_data=f"adm:no:{rtype}:{req_id}")
    kb.adjust(2)
    return kb.as_markup()

# ======================
# BOT
# ======================
bot = Bot(TOKEN)
dp = Dispatcher()

pending_mode: Dict[int, str] = {}  # uid -> topup|withdraw|promo

def is_btn(text: str, lang: str, key: str) -> bool:
    mapping = {
        "cars": {"uz": "🚗 Moshinalar", "ru": "🚗 Машины", "en": "🚗 Cars"},
        "garage": {"uz": "🏠 Garage", "ru": "🏠 Гараж", "en": "🏠 Garage"},
        "balance": {"uz": "💰 Balans", "ru": "💰 Баланс", "en": "💰 Balance"},
        "promo": {"uz": "🎁 Promo", "ru": "🎁 Промо", "en": "🎁 Promo"},
        "stats": {"uz": "📊 Statistika", "ru": "📊 Статистика", "en": "📊 Stats"},
        "topup": {"uz": "➕ Hisob to‘ldirish", "ru": "➕ Пополнить", "en": "➕ Top up"},
        "withdraw": {"uz": "➖ Pul yechish", "ru": "➖ Вывод", "en": "➖ Withdraw"},
        "lang": {"uz": "🌐 Til", "ru": "🌐 Язык", "en": "🌐 Language"},
    }
    return text == mapping[key][lang]

async def on_startup():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.executescript(INIT_SQL)
        await db.commit()

# ======================
# COMMANDS
# ======================
@dp.message(Command("start"))
async def start(m: types.Message):
    uid = m.from_user.id
    await ensure_user(uid)
    lang = await get_lang(uid)
    await m.answer(T[lang]["hello"])
    await m.answer(T[lang]["menu"], reply_markup=kb_main(lang))

@dp.message(Command("pending"))
async def admin_pending(m: types.Message):
    if m.from_user.id != ADMIN_ID:
        lang = await get_lang(m.from_user.id)
        return await m.answer(T[lang]["admin_only"])

    rows = await db_fetchall(
        "SELECT req_id, user_id, type, amount FROM requests WHERE status='pending' ORDER BY req_id DESC LIMIT 30"
    )
    if not rows:
        return await m.answer("🟢 Pending yo‘q.")
    for req_id, user_id, rtype, amount in rows:
        await m.answer(
            f"🧾 Request #{req_id}\nUser: {user_id}\nType: {rtype}\nAmount: {fmt(int(amount))} coin",
            reply_markup=kb_admin_req(int(req_id), rtype)
        )

# ======================
# CALLBACKS: LANG
# ======================
@dp.callback_query(F.data.startswith("lang:"))
async def lang_set_cb(cb: types.CallbackQuery):
    uid = cb.from_user.id
    await ensure_user(uid)
    lang = cb.data.split(":")[1]
    await set_lang(uid, lang)
    lang = await get_lang(uid)
    await cb.message.answer(T[lang]["lang_set"], reply_markup=kb_main(lang))
    await cb.answer()

# ======================
# CALLBACKS: BUY / CLAIM / UPGRADE
# ======================
@dp.callback_query(F.data.startswith("buy:"))
async def buy_car(cb: types.CallbackQuery):
    uid = cb.from_user.id
    await ensure_user(uid)
    lang = await get_lang(uid)

    car_id = int(cb.data.split(":")[1])
    car = next((x for x in CARS if x["id"] == car_id), None)
    if not car:
        return await cb.answer(T[lang]["not_found"], show_alert=True)

    if await has_car(uid, car_id):
        return await cb.answer(T[lang]["already_have"], show_alert=True)

    ok = await sub_balance(uid, car["price"])
    if not ok:
        return await cb.answer(T[lang]["no_money"], show_alert=True)

    now = int(time.time())
    await db_exec(
        "INSERT INTO garage(user_id, car_id, level, bought_at, last_claim_at) VALUES(?,?,?,?,?)",
        uid, car_id, 1, now, 0
    )

    nm = car_name(car["key"], lang)
    await cb.message.answer(T[lang]["bought"].format(car=nm))
    await cb.answer()

@dp.callback_query(F.data.startswith("claim:"))
async def claim(cb: types.CallbackQuery):
    uid = cb.from_user.id
    await ensure_user(uid)
    lang = await get_lang(uid)

    car_id = int(cb.data.split(":")[1])
    row = await db_fetchone("SELECT level, bought_at, last_claim_at FROM garage WHERE user_id=? AND car_id=?", uid, car_id)
    if not row:
        return await cb.answer(T[lang]["no_car"], show_alert=True)

    lvl, bought_at, last_claim_at = int(row[0]), int(row[1]), int(row[2])
    now = int(time.time())

    # 30 kun muddat tekshir
    if now - bought_at > CAR_ACTIVE_SECONDS:
        return await cb.answer(T[lang]["claim_expired"], show_alert=True)

    # cooldown
    if now - last_claim_at < COOLDOWN_SECONDS:
        left = COOLDOWN_SECONDS - (now - last_claim_at)
        return await cb.answer(T[lang]["too_early"].format(h=left // 3600), show_alert=True)

    car = next(x for x in CARS if x["id"] == car_id)
    nm = car_name(car["key"], lang)

    bonus_mult = 1.0 + (lvl - 1) * UPGRADE_INCOME_BONUS

    r = random.random()
    if r < RISK_PROB_NEG:
        roi_percent = NEG_ROI_PERCENT
    elif r < RISK_PROB_NEG + RISK_PROB_ZERO:
        roi_percent = 0
    else:
        roi_percent = random.randint(ROI_MIN, ROI_MAX)

    earned = int(car["daily_base"] * (roi_percent / 100.0) * bonus_mult)

    if earned < 0:
        bal = await get_balance(uid)
        take = min(bal, abs(earned))
        await sub_balance(uid, take)
        earned_show = f"-{fmt(take)}"
    else:
        await add_balance(uid, earned)
        earned_show = fmt(earned)

    await db_exec("UPDATE garage SET last_claim_at=? WHERE user_id=? AND car_id=?", now, uid, car_id)
    await inc_stat(uid, "claims")

    await cb.message.answer(
        T[lang]["claim_ok"].format(car=nm, lvl=lvl, roi=roi_percent, earned=earned_show)
    )
    await cb.answer()

@dp.callback_query(F.data.startswith("upg:"))
async def upgrade(cb: types.CallbackQuery):
    uid = cb.from_user.id
    await ensure_user(uid)
    lang = await get_lang(uid)

    car_id = int(cb.data.split(":")[1])
    row = await db_fetchone("SELECT level FROM garage WHERE user_id=? AND car_id=?", uid, car_id)
    if not row:
        return await cb.answer(T[lang]["no_car"], show_alert=True)

    lvl = int(row[0])
    car = next(x for x in CARS if x["id"] == car_id)
    cost = int(car["price"] * UPGRADE_COST_MULT * lvl)

    ok = await sub_balance(uid, cost)
    if not ok:
        return await cb.answer(T[lang]["no_money"], show_alert=True)

    await db_exec("UPDATE garage SET level = level + 1 WHERE user_id=? AND car_id=?", uid, car_id)
    nm = car_name(car["key"], lang)
    await cb.message.answer(T[lang]["upgrade_ok"].format(car=nm, lvl=lvl + 1, cost=fmt(cost)))
    await cb.answer()

# ======================
# CALLBACKS: ADMIN APPROVE / REJECT
# ======================
@dp.callback_query(F.data.startswith("adm:"))
async def admin_decide(cb: types.CallbackQuery):
    if cb.from_user.id != ADMIN_ID:
        return await cb.answer("Admin only", show_alert=True)

    _, action, rtype, req_id_s = cb.data.split(":")
    req_id = int(req_id_s)

    row = await db_fetchone("SELECT user_id, type, amount, status FROM requests WHERE req_id=?", req_id)
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
                await bot.send_message(uid, "❌ Withdraw rejected: insufficient balance.")
                await cb.message.edit_text(cb.message.text + "\n\n❌ Auto-rejected (insufficient user balance).")
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

# ======================
# TEXT MENU + STATES
# ======================
@dp.message()
async def handle_text(m: types.Message):
    uid = m.from_user.id
    await ensure_user(uid)
    lang = await get_lang(uid)
    text = (m.text or "").strip()

    # STATE INPUTS
    mode = pending_mode.get(uid)
    if mode:
        if mode == "promo":
            pending_mode.pop(uid, None)
            code = text.upper()
            if code not in PROMOS or await promo_is_used(uid, code):
                return await m.answer(T[lang]["promo_bad"])
            amt = int(PROMOS[code])
            await add_balance(uid, amt)
            await mark_promo_used(uid, code)
            return await m.answer(T[lang]["promo_ok"].format(amt=fmt(amt)))

        if not text.isdigit():
            pending_mode.pop(uid, None)
            return await m.answer(T[lang]["only_num"])

        amount = int(text)
        pending_mode.pop(uid, None)

        if mode == "topup":
            if amount < MIN_TOPUP:
                return await m.answer(T[lang]["min_fail"])
            req_id = await create_request(uid, "topup", amount)
            await inc_stat(uid, "topups")
            await bot.send_message(
                ADMIN_ID,
                f"🧾 TOPUP Request #{req_id}\nUser: {uid}\nAmount: {fmt(amount)} coin",
                reply_markup=kb_admin_req(req_id, "topup")
            )
            return await m.answer(T[lang]["sent_admin"])

        if mode == "withdraw":
            if amount < MIN_WITHDRAW:
                return await m.answer(T[lang]["min_fail"])
            bal = await get_balance(uid)
            if bal < amount:
                return await m.answer(T[lang]["withdraw_insufficient"])
            req_id = await create_request(uid, "withdraw", amount)
            await inc_stat(uid, "withdraws")
            await bot.send_message(
                ADMIN_ID,
                f"💸 WITHDRAW Request #{req_id}\nUser: {uid}\nAmount: {fmt(amount)} coin\nBalance: {fmt(bal)} coin",
                reply_markup=kb_admin_req(req_id, "withdraw")
            )
            return await m.answer(T[lang]["sent_admin"])

    # MENU BUTTONS
    if is_btn(text, lang, "lang"):
        return await m.answer(T[lang]["choose_lang"], reply_markup=kb_lang())

    if is_btn(text, lang, "balance"):
        b = await get_balance(uid)
        return await m.answer(T[lang]["balance"].format(bal=fmt(b)))

    if is_btn(text, lang, "cars"):
        lines = [T[lang]["cars"]]
        for c in CARS:
            nm = car_name(c["key"], lang)
            lines.append(f"- {nm} | L{c['level']} | {fmt(c['price'])} coin")
        return await m.answer("\n".join(lines), reply_markup=kb_cars(lang))

    if is_btn(text, lang, "garage"):
        items = await get_garage(uid)
        if not items:
            return await m.answer(T[lang]["garage_empty"])

        now = int(time.time())
        msg = [T[lang]["garage"]]
        for car_id, lvl, bought_at, last_claim_at in items:
            car = next(x for x in CARS if x["id"] == car_id)
            nm = car_name(car["key"], lang)

            # active left
            active_left = max(0, (CAR_ACTIVE_SECONDS - (now - int(bought_at))))
            days_left = active_left // (24 * 60 * 60)
            active_txt = T[lang]["expired"] if active_left == 0 else T[lang]["active_left"].format(d=days_left)

            # cooldown left
            cd_left = max(0, COOLDOWN_SECONDS - (now - int(last_claim_at)))
            if active_left == 0:
                cd_txt = T[lang]["expired"]
            elif cd_left == 0:
                cd_txt = T[lang]["cooldown_ready"]
            else:
                cd_txt = T[lang]["cooldown_left"].format(h=cd_left // 3600, m=(cd_left % 3600) // 60)

            msg.append(f"{nm} | L{lvl} | {active_txt} | Claim: {cd_txt}")

        return await m.answer("\n".join(msg), reply_markup=kb_garage(items, lang))

    if is_btn(text, lang, "promo"):
        pending_mode[uid] = "promo"
        return await m.answer(T[lang]["promo_ask"])

    if is_btn(text, lang, "stats"):
        c, tps, wds = await get_stats(uid)
        b = await get_balance(uid)
        return await m.answer(T[lang]["stats"].format(c=c, t=tps, w=wds, b=fmt(b)))

    if is_btn(text, lang, "topup"):
        pending_mode[uid] = "topup"
        return await m.answer(T[lang]["topup_title"].format(min=fmt(MIN_TOPUP)))

    if is_btn(text, lang, "withdraw"):
        pending_mode[uid] = "withdraw"
        return await m.answer(T[lang]["withdraw_title"].format(min=fmt(MIN_WITHDRAW)))

# ======================
# RUN
# ======================
async def main():
    await on_startup()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
