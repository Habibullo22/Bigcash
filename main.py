import asyncio
import random
import time
from dataclasses import dataclass
from typing import Optional

import aiosqlite
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command
from aiogram.utils.keyboard import ReplyKeyboardBuilder, InlineKeyboardBuilder

# =====================
# CONFIG
# =====================
TOKEN = "8621200093:AAGHIYeRuf3mvrA4rrtWm7c4qHJEINtmzGk"
ADMIN_ID = 5815294733  # o'zingni telegram id

DB_PATH = "game.db"
COOLDOWN_SECONDS = 24 * 60 * 60  # 24 soat

# Kunlik daromad foizi (random, kafolat emas)
ROI_MIN = 10
ROI_MAX = 25

MIN_TOPUP = 20_000
MIN_WITHDRAW = 50_000

# =====================
# CARS (level bo'yicha)
# price = sotib olish narxi (coin)
# daily_base = kunlik bazaviy daromad (coin) -> ustiga ROI% qo'llanadi
# =====================
CARS = [
    {"id": 1, "name": "🚙 Cobalt",   "level": 1, "price": 35_000,  "daily_base": 2_000},
    {"id": 2, "name": "🚗 Malibu",   "level": 2, "price": 70_000,  "daily_base": 4_200},
    {"id": 3, "name": "🚘 Tracker",  "level": 3, "price": 140_000, "daily_base": 9_000},
    {"id": 4, "name": "🚙 Tahoe",    "level": 4, "price": 280_000, "daily_base": 19_000},
]

UPGRADE_COST_MULT = 0.35   # upgrade narxi = price * 0.35
UPGRADE_INCOME_BONUS = 0.12  # upgrade daromadni +12% qiladi

# =====================
# DB INIT
# =====================
INIT_SQL = """
CREATE TABLE IF NOT EXISTS users (
  user_id INTEGER PRIMARY KEY,
  balance INTEGER NOT NULL DEFAULT 0,
  created_at INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS garage (
  user_id INTEGER NOT NULL,
  car_id INTEGER NOT NULL,
  level INTEGER NOT NULL DEFAULT 1,
  last_claim_at INTEGER NOT NULL DEFAULT 0,
  PRIMARY KEY (user_id, car_id)
);
"""

# =====================
# HELPERS
# =====================
def main_menu_kb() -> types.ReplyKeyboardMarkup:
    kb = ReplyKeyboardBuilder()
    kb.button(text="🚗 Moshinalar")
    kb.button(text="🏠 Garage")
    kb.button(text="💰 Balans")
    kb.button(text="➕ Hisob to‘ldirish")
    kb.button(text="➖ Pul yechish")
    kb.adjust(2, 2, 1)
    return kb.as_markup(resize_keyboard=True)

def cars_inline_kb() -> types.InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for c in CARS:
        kb.button(
            text=f"{c['name']} | L{c['level']} | {c['price']:,} coin".replace(",", " "),
            callback_data=f"buy:{c['id']}",
        )
    kb.adjust(1)
    return kb.as_markup()

def garage_inline_kb(user_has: list[tuple[int,int,int]]) -> types.InlineKeyboardMarkup:
    """
    user_has: list of (car_id, level, last_claim_at)
    """
    kb = InlineKeyboardBuilder()
    for car_id, lvl, last_claim_at in user_has:
        car = next(x for x in CARS if x["id"] == car_id)
        kb.button(text=f"✅ Claim: {car['name']} (L{lvl})", callback_data=f"claim:{car_id}")
        kb.button(text=f"⬆️ Upgrade: {car['name']} (L{lvl})", callback_data=f"upg:{car_id}")
    kb.adjust(1)
    return kb.as_markup()

async def db_exec(query: str, *params):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(query, params)
        await db.commit()

async def db_fetchone(query: str, *params):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(query, params) as cur:
            return await cur.fetchone()

async def db_fetchall(query: str, *params):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(query, params) as cur:
            return await cur.fetchall()

async def ensure_user(user_id: int):
    row = await db_fetchone("SELECT user_id FROM users WHERE user_id=?", user_id)
    if not row:
        await db_exec(
            "INSERT INTO users(user_id, balance, created_at) VALUES(?,?,?)",
            user_id, 0, int(time.time())
        )

async def get_balance(user_id: int) -> int:
    row = await db_fetchone("SELECT balance FROM users WHERE user_id=?", user_id)
    return int(row[0]) if row else 0

async def add_balance(user_id: int, amount: int):
    await db_exec("UPDATE users SET balance = balance + ? WHERE user_id=?", amount, user_id)

async def sub_balance(user_id: int, amount: int) -> bool:
    bal = await get_balance(user_id)
    if bal < amount:
        return False
    await db_exec("UPDATE users SET balance = balance - ? WHERE user_id=?", amount, user_id)
    return True

async def user_garage(user_id: int):
    return await db_fetchall("SELECT car_id, level, last_claim_at FROM garage WHERE user_id=? ORDER BY car_id", user_id)

async def has_car(user_id: int, car_id: int) -> bool:
    row = await db_fetchone("SELECT 1 FROM garage WHERE user_id=? AND car_id=?", user_id, car_id)
    return bool(row)

# =====================
# BOT
# =====================
bot = Bot(TOKEN)
dp = Dispatcher()

# Simple state for topup/withdraw text input
pending_mode: dict[int, str] = {}  # user_id -> "topup" | "withdraw"

@dp.message(Command("start"))
async def start(m: types.Message):
    await ensure_user(m.from_user.id)
    await m.answer(
        "🚗 Avto Biznes Game\n\n"
        "Bu o‘yin ichidagi coin tizimi. Daromad *kafolat emas* (random).\n"
        "Menyu orqali davom eting:",
        reply_markup=main_menu_kb()
    )

@dp.message(Command("addbal"))
async def addbal_cmd(m: types.Message):
    # admin test uchun: /addbal 50000
    if m.from_user.id != ADMIN_ID:
        return
    parts = m.text.split()
    if len(parts) != 2 or not parts[1].isdigit():
        return await m.answer("Admin: /addbal 50000")
    amt = int(parts[1])
    await ensure_user(m.from_user.id)
    await add_balance(m.from_user.id, amt)
    await m.answer(f"✅ Balansingizga +{amt:,} coin qo‘shildi.".replace(",", " "))

@dp.message(F.text == "💰 Balans")
async def bal(m: types.Message):
    await ensure_user(m.from_user.id)
    b = await get_balance(m.from_user.id)
    await m.answer(f"💰 Balans: {b:,} coin".replace(",", " "))

@dp.message(F.text == "🚗 Moshinalar")
async def cars(m: types.Message):
    await ensure_user(m.from_user.id)
    lines = ["🚗 Moshinalar ro‘yxati:"]
    for c in CARS:
        lines.append(f"- {c['name']} | Level: {c['level']} | Narx: {c['price']:,} coin".replace(",", " "))
    await m.answer("\n".join(lines), reply_markup=cars_inline_kb())

@dp.callback_query(F.data.startswith("buy:"))
async def buy_car(cb: types.CallbackQuery):
    await ensure_user(cb.from_user.id)
    car_id = int(cb.data.split(":")[1])
    car = next((x for x in CARS if x["id"] == car_id), None)
    if not car:
        return await cb.answer("Topilmadi", show_alert=True)

    if await has_car(cb.from_user.id, car_id):
        return await cb.answer("Sizda bu mashina bor ✅", show_alert=True)

    ok = await sub_balance(cb.from_user.id, car["price"])
    if not ok:
        return await cb.answer("Balans yetarli emas ❌", show_alert=True)

    await db_exec(
        "INSERT INTO garage(user_id, car_id, level, last_claim_at) VALUES(?,?,?,?)",
        cb.from_user.id, car_id, 1, 0
    )
    await cb.message.answer(f"✅ Sotib olindi: {car['name']}\nEndi '🏠 Garage' dan claim qiling.")
    await cb.answer()

@dp.message(F.text == "🏠 Garage")
async def garage(m: types.Message):
    await ensure_user(m.from_user.id)
    items = await user_garage(m.from_user.id)
    if not items:
        return await m.answer("🚫 Garage bo‘sh. '🚗 Moshinalar' dan sotib oling.")
    msg = ["🏠 Garage:"]
    now = int(time.time())
    for car_id, lvl, last_claim_at in items:
        car = next(x for x in CARS if x["id"] == car_id)
        left = max(0, COOLDOWN_SECONDS - (now - int(last_claim_at)))
        if left == 0:
            cd_txt = "✅ Tayyor"
        else:
            cd_txt = f"⏳ {left//3600} soat { (left%3600)//60 } daqiqa"
        msg.append(f"{car['name']} | L{lvl} | Claim: {cd_txt}")
    await m.answer("\n".join(msg), reply_markup=garage_inline_kb(items))

@dp.callback_query(F.data.startswith("claim:"))
async def claim(cb: types.CallbackQuery):
    await ensure_user(cb.from_user.id)
    car_id = int(cb.data.split(":")[1])
    row = await db_fetchone(
        "SELECT level, last_claim_at FROM garage WHERE user_id=? AND car_id=?",
        cb.from_user.id, car_id
    )
    if not row:
        return await cb.answer("Sizda bu mashina yo‘q", show_alert=True)

    lvl, last_claim_at = int(row[0]), int(row[1])
    now = int(time.time())
    if now - last_claim_at < COOLDOWN_SECONDS:
        left = COOLDOWN_SECONDS - (now - last_claim_at)
        return await cb.answer(f"Vaqti hali kelmagan ⏳ {left//3600} soat", show_alert=True)

    car = next(x for x in CARS if x["id"] == car_id)

    # Upgrade bonus: har level +12% (L1=0%, L2=12%, L3=24% ...)
    bonus_mult = 1.0 + (lvl - 1) * UPGRADE_INCOME_BONUS

    roi = random.randint(ROI_MIN, ROI_MAX) / 100.0  # 0.10 - 0.25
    earned = int(car["daily_base"] * roi * bonus_mult)

    await add_balance(cb.from_user.id, earned)
    await db_exec(
        "UPDATE garage SET last_claim_at=? WHERE user_id=? AND car_id=?",
        now, cb.from_user.id, car_id
    )

    await cb.message.answer(
        f"✅ Claim muvaffaqiyatli!\n"
        f"{car['name']} (L{lvl})\n"
        f"🎲 Bugungi ROI: {int(roi*100)}%\n"
        f"💵 Tushdi: {earned:,} coin".replace(",", " ")
    )
    await cb.answer()

@dp.callback_query(F.data.startswith("upg:"))
async def upgrade(cb: types.CallbackQuery):
    await ensure_user(cb.from_user.id)
    car_id = int(cb.data.split(":")[1])
    row = await db_fetchone(
        "SELECT level FROM garage WHERE user_id=? AND car_id=?",
        cb.from_user.id, car_id
    )
    if not row:
        return await cb.answer("Sizda bu mashina yo‘q", show_alert=True)

    lvl = int(row[0])
    car = next(x for x in CARS if x["id"] == car_id)
    cost = int(car["price"] * UPGRADE_COST_MULT * lvl)  # level oshgani sari qimmatlashadi

    ok = await sub_balance(cb.from_user.id, cost)
    if not ok:
        return await cb.answer("Balans yetarli emas ❌", show_alert=True)

    await db_exec(
        "UPDATE garage SET level = level + 1 WHERE user_id=? AND car_id=?",
        cb.from_user.id, car_id
    )
    await cb.message.answer(
        f"⬆️ Upgrade bo‘ldi!\n{car['name']} -> L{lvl+1}\n"
        f"💸 Sarflandi: {cost:,} coin".replace(",", " ")
    )
    await cb.answer()

@dp.message(F.text == "➕ Hisob to‘ldirish")
async def topup_start(m: types.Message):
    await ensure_user(m.from_user.id)
    pending_mode[m.from_user.id] = "topup"
    await m.answer(
        f"➕ Hisob to‘ldirish (virtual coin)\n"
        f"Minimal: {MIN_TOPUP:,} coin\n\n"
        f"Summani yozing (masalan: 20000).".replace(",", " ")
    )

@dp.message(F.text == "➖ Pul yechish")
async def withdraw_start(m: types.Message):
    await ensure_user(m.from_user.id)
    pending_mode[m.from_user.id] = "withdraw"
    await m.answer(
        f"➖ Pul yechish (virtual coin)\n"
        f"Minimal: {MIN_WITHDRAW:,} coin\n\n"
        f"Summani yozing (masalan: 50000).".replace(",", " ")
    )

@dp.message(F.text.regexp(r"^\d+$"))
async def handle_amount(m: types.Message):
    uid = m.from_user.id
    mode = pending_mode.get(uid)
    if not mode:
        return

    amount = int(m.text)
    pending_mode.pop(uid, None)

    if mode == "topup":
        if amount < MIN_TOPUP:
            return await m.answer("❌ Minimaldan kam.")
        # Bu joyda real to'lov yo'q — demo sifatida admin tasdiq qilsa qo'shib beradi.
        # Hozircha: admin'ga yuboramiz, admin /addbal bilan qo'shadi.
        await bot.send_message(
            ADMIN_ID,
            f"🧾 TOPUP so‘rovi\nUser: {uid}\nSumma: {amount:,} coin\n"
            f"(Admin: /addbal {amount} deb qo‘shib bering)".replace(",", " ")
        )
        return await m.answer("✅ So‘rov adminga yuborildi. (demo)")

    if mode == "withdraw":
        if amount < MIN_WITHDRAW:
            return await m.answer("❌ Minimal yechishdan kam.")
        bal = await get_balance(uid)
        if bal < amount:
            return await m.answer("❌ Balans yetarli emas.")
        # Demo: balansdan ushlab, adminga yuboramiz
        await sub_balance(uid, amount)
        await bot.send_message(
            ADMIN_ID,
            f"💸 WITHDRAW so‘rovi (demo)\nUser: {uid}\nSumma: {amount:,} coin\n"
            f"Balansdan ushlanib qo‘yildi.".replace(",", " ")
        )
        return await m.answer("✅ Yechish so‘rovi adminga yuborildi. (demo)")

async def on_startup():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.executescript(INIT_SQL)
        await db.commit()

async def main():
    await on_startup()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
