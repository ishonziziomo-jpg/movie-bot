import logging
import asyncio
import aiosqlite
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
import os

# =======================
# 🔹 Bot sozlamalari
# =======================
API_TOKEN = os.getenv("8349162113:AAHeQwAWwLkL84ExX62BmeCnUgztnjVglcA")
ADMIN_ID = 6493383873

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

bot = Bot(token=API_TOKEN)
dp = Dispatcher()
DB_PATH = "/data/database.db"

# =======================
# 🔹 FSM States
# =======================
class AdminStates(StatesGroup):
    waiting_text = State()
    waiting_broadcast = State()
    waiting_button_add = State()
    waiting_button_del = State()

# =======================
# 🔹 Database init
# =======================
async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
        CREATE TABLE IF NOT EXISTS users(
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            last_name TEXT,
            join_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)
        await db.execute("""
        CREATE TABLE IF NOT EXISTS texts(
            key TEXT PRIMARY KEY,
            value TEXT
        )
        """)
        await db.execute("""
        CREATE TABLE IF NOT EXISTS buttons(
            key TEXT PRIMARY KEY,
            text TEXT,
            action_type TEXT,
            action_key TEXT
        )
        """)
        
        # Boshlang'ich ma'lumotlar
        await db.execute("""
        INSERT OR IGNORE INTO buttons (key, text, action_type, action_key) 
        VALUES 
            ('info', 'ℹ Ma''lumot', 'text', 'info'),
            ('help', '❓ Yordam', 'text', 'help'),
            ('contact', '📞 Aloqa', 'text', 'contact'),
            ('rules', '📚 Qoidalar', 'text', 'rules')
        """)
        
        await db.execute("""
        INSERT OR IGNORE INTO texts (key, value) 
        VALUES 
            ('info', '🤖 Aviator Turbo Bot\\n\\nBu bot orqali turli xizmatlardan foydalanishingiz mumkin.'),
            ('help', '🆘 Yordam kerak bo''lsa, admin bilan bog''laning.'),
            ('contact', '📞 Biz bilan bog''laning:\\nTelegram: @admin\\nEmail: info@example.com'),
            ('rules', '📚 Foydalanish qoidalari:\\n1. Qonunlarga rioya qiling\\n2. Spam yubormang\\n3. Botni noto''g''ri ishlatmang')
        """)
        
        await db.commit()
    logger.info("✅ Database initialized")

# =======================
# 🔹 Admin tekshiruv
# =======================
async def is_admin(user_id):
    return user_id == ADMIN_ID

# =======================
# 🔹 START HANDLER
# =======================
@dp.message(Command("start"))
async def start_handler(message: types.Message):
    user_id = message.from_user.id
    username = message.from_user.username or "Noma'lum"
    first_name = message.from_user.first_name or "Noma'lum"

    try:
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                "INSERT OR REPLACE INTO users(user_id, username, first_name, last_name) VALUES (?, ?, ?, ?)",
                (user_id, username, first_name, "")
            )
            await db.commit()
    except Exception as e:
        logger.error(f"Database error: {e}")

    # Tugmalarni yuklash
    kb = InlineKeyboardMarkup(inline_keyboard=[])
    buttons = []
    
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute("SELECT text, key FROM buttons") as cursor:
                async for row in cursor:
                    buttons.append(InlineKeyboardButton(text=row[0], callback_data=row[1]))
    except Exception as e:
        logger.error(f"Tugmalarni yuklashda xato: {e}")

    # Admin tugmasini qo'shamiz
    if await is_admin(user_id):
        buttons.append(InlineKeyboardButton(text="⚙ Admin", callback_data="settings"))

    # Tugmalarni qatorlarga ajratamiz
    for i in range(0, len(buttons), 2):
        kb.inline_keyboard.append(buttons[i:i+2])

    await message.answer("🤖 Aviator Turbo Botga Xush kelibsiz!", reply_markup=kb)

# =======================
# 🔹 ADMIN PANEL HANDLERS
# =======================
@dp.callback_query(F.data == "settings")
async def admin_panel_handler(query: types.CallbackQuery):
    if not await is_admin(query.from_user.id):
        await query.answer("🚫 Siz admin emassiz!", show_alert=True)
        return

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✏ Matnlarni o'zgartirish", callback_data="admin_texts")],
        [InlineKeyboardButton(text="🔘 Tugmalarni boshqarish", callback_data="admin_buttons")],
        [InlineKeyboardButton(text="📢 Broadcast xabar", callback_data="admin_broadcast")],
        [InlineKeyboardButton(text="📊 Statistika", callback_data="admin_stats")],
        [InlineKeyboardButton(text="🔙 Orqaga", callback_data="main_menu")]
    ])
    await query.message.edit_text("⚙ Admin Panel", reply_markup=kb)

@dp.callback_query(F.data == "admin_stats")
async def admin_stats_handler(query: types.CallbackQuery):
    if not await is_admin(query.from_user.id):
        return
    
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute("SELECT COUNT(*) FROM users") as cursor:
                user_count = (await cursor.fetchone())[0]
            
            async with db.execute("SELECT COUNT(*) FROM buttons") as cursor:
                button_count = (await cursor.fetchone())[0]
            
            async with db.execute("SELECT COUNT(*) FROM texts") as cursor:
                text_count = (await cursor.fetchone())[0]
        
        stats_text = f"""
📊 **Bot Statistika**

👥 Foydalanuvchilar: {user_count}
🔘 Tugmalar: {button_count}
📝 Matnlar: {text_count}
🕐 Platforma: Railway
        """
        
        await query.message.edit_text(stats_text)
    except Exception as e:
        await query.message.edit_text(f"❌ Statistika yuklashda xato: {e}")

@dp.callback_query(F.data == "admin_texts")
async def admin_texts_handler(query: types.CallbackQuery, state: FSMContext):
    if not await is_admin(query.from_user.id):
        return
    
    # Mavjud matnlarni ko'rsatish
    texts_list = "📝 **Mavjud matnlar:**\n\n"
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute("SELECT key, value FROM texts") as cursor:
                async for row in cursor:
                    texts_list += f"• `{row[0]}`: {row[1][:30]}...\n"
    except Exception as e:
        texts_list = f"❌ Matnlarni yuklashda xato: {e}"
    
    texts_list += "\n✏ **Yangilash formati:** `kalit|yangi matn`\nMisol: `info|Yangi ma'lumot`"
    
    await query.message.answer(texts_list)
    await state.set_state(AdminStates.waiting_text)

@dp.callback_query(F.data == "admin_buttons")
async def admin_buttons_handler(query: types.CallbackQuery):
    if not await is_admin(query.from_user.id):
        return

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Tugma qo'shish", callback_data="add_button")],
        [InlineKeyboardButton(text="🗑 Tugmani o'chirish", callback_data="del_button")],
        [InlineKeyboardButton(text="🔙 Orqaga", callback_data="settings")]
    ])
    await query.message.edit_text("🔘 Tugmalarni Boshqarish", reply_markup=kb)

@dp.callback_query(F.data == "admin_broadcast")
async def admin_broadcast_handler(query: types.CallbackQuery, state: FSMContext):
    if not await is_admin(query.from_user.id):
        return
    
    await query.message.answer("📢 Broadcast xabar matnini yuboring:")
    await state.set_state(AdminStates.waiting_broadcast)

@dp.callback_query(F.data == "add_button")
async def add_button_handler(query: types.CallbackQuery, state: FSMContext):
    if not await is_admin(query.from_user.id):
        return
    
    await query.message.answer(
        "➕ **Tugma qo'shish formati:**\n"
        "`tugma matni|action_type|action_key`\n\n"
        "📋 **Misol:**\n"
        "`Bonus|text|bonus`\n"
        "`Rasmlar|media|gallery`\n\n"
        "ℹ **action_type:** `text` yoki `media`"
    )
    await state.set_state(AdminStates.waiting_button_add)

@dp.callback_query(F.data == "del_button")
async def del_button_handler(query: types.CallbackQuery, state: FSMContext):
    if not await is_admin(query.from_user.id):
        return
    
    # Mavjud tugmalarni ko'rsatish
    buttons_list = "🔘 **Mavjud tugmalar:**\n\n"
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute("SELECT key, text FROM buttons") as cursor:
                async for row in cursor:
                    buttons_list += f"• `{row[0]}` - {row[1]}\n"
    except Exception as e:
        buttons_list = f"❌ Tugmalarni yuklashda xato: {e}"
    
    buttons_list += "\n🗑 **O'chirish uchun** tugma kalitini yuboring"
    
    await query.message.answer(buttons_list)
    await state.set_state(AdminStates.waiting_button_del)

@dp.callback_query(F.data == "main_menu")
async def main_menu_handler(query: types.CallbackQuery):
    await start_handler(query.message)

# =======================
# 🔹 STATE HANDLERS
# =======================
@dp.message(AdminStates.waiting_text)
async def process_text_change(message: types.Message, state: FSMContext):
    if not await is_admin(message.from_user.id):
        await state.clear()
        return

    try:
        if "|" in message.text:
            key, value = message.text.split("|", 1)
            key = key.strip()
            value = value.strip()
            
            if not key or not value:
                await message.answer("❌ Kalit yoki matn bo'sh bo'lmasligi kerak")
                return
            
            async with aiosqlite.connect(DB_PATH) as db:
                await db.execute(
                    "INSERT OR REPLACE INTO texts(key, value) VALUES (?, ?)",
                    (key, value)
                )
                await db.commit()
            
            logger.info(f"✅ Matn yangilandi: {key}")
            await message.answer(f"✅ Matn yangilandi: `{key}`")
        else:
            await message.answer("❌ Format xato. Misol: `info|Yangi ma'lumot`")
    except Exception as e:
        logger.error(f"❌ Matn yangilashda xato: {e}")
        await message.answer(f"❌ Xato: {e}")
    
    await state.clear()

@dp.message(AdminStates.waiting_broadcast)
async def process_broadcast(message: types.Message, state: FSMContext):
    if not await is_admin(message.from_user.id):
        await state.clear()
        return

    await message.answer("📢 Broadcast boshlandi...")
    
    success_count = 0
    fail_count = 0
    
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute("SELECT user_id FROM users") as cursor:
                users = []
                async for row in cursor:
                    users.append(row[0])
        
        for user_id in users:
            try:
                await bot.send_message(user_id, message.text)
                success_count += 1
                await asyncio.sleep(0.1)
            except Exception as e:
                fail_count += 1
                logger.error(f"Xabar yuborishda xato {user_id}: {e}")
    
        logger.info(f"✅ Broadcast yakunlandi: {success_count} muvaffaqiyatli, {fail_count} xato")
        await message.answer(
            f"✅ Broadcast yakunlandi!\n\n"
            f"✅ Muvaffaqiyatli: {success_count}\n"
            f"❌ Xatolar: {fail_count}"
        )
    except Exception as e:
        logger.error(f"❌ Broadcastda xato: {e}")
        await message.answer(f"❌ Broadcastda xato: {e}")
    
    await state.clear()

@dp.message(AdminStates.waiting_button_add)
async def process_button_add(message: types.Message, state: FSMContext):
    if not await is_admin(message.from_user.id):
        await state.clear()
        return

    try:
        if "|" in message.text:
            parts = message.text.split("|")
            if len(parts) != 3:
                await message.answer("❌ Format xato! Masalan: `Bonus|text|bonus`")
                return
            
            text, action_type, action_key = [p.strip() for p in parts]
            
            if action_type not in ["text", "media"]:
                await message.answer("❌ Action type faqat 'text' yoki 'media' bo'lishi kerak")
                return
            
            async with aiosqlite.connect(DB_PATH) as db:
                await db.execute(
                    "INSERT OR REPLACE INTO buttons(key, text, action_type, action_key) VALUES (?, ?, ?, ?)",
                    (action_key, text, action_type, action_key)
                )
                await db.commit()
            
            logger.info(f"✅ Tugma qo'shildi: {text} -> {action_key}")
            await message.answer(f"✅ Tugma qo'shildi: **{text}**")
        else:
            await message.answer("❌ Format xato! Masalan: `Bonus|text|bonus`")
    except Exception as e:
        logger.error(f"❌ Tugma qo'shishda xato: {e}")
        await message.answer(f"❌ Xato: {e}")
    
    await state.clear()

@dp.message(AdminStates.waiting_button_del)
async def process_button_del(message: types.Message, state: FSMContext):
    if not await is_admin(message.from_user.id):
        await state.clear()
        return

    key = message.text.strip()
    
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            # Tugma mavjudligini tekshiramiz
            async with db.execute("SELECT text FROM buttons WHERE key=?", (key,)) as cursor:
                button = await cursor.fetchone()
            
            if not button:
                await message.answer(f"❌ Tugma topilmadi: `{key}`")
                return
            
            await db.execute("DELETE FROM buttons WHERE key=?", (key,))
            await db.commit()
        
        logger.info(f"✅ Tugma o'chirildi: {key}")
        await message.answer(f"✅ Tugma o'chirildi: `{key}`")
    except Exception as e:
        logger.error(f"❌ Tugmani o'chirishda xato: {e}")
        await message.answer(f"❌ Xato: {e}")
    
    await state.clear()

# =======================
# 🔹 USER BUTTON HANDLERS
# =======================
@dp.callback_query()
async def user_button_handler(query: types.CallbackQuery):
    data = query.data
    
    # Admin tugmalarini boshqa handlerlar boshqaradi
    if data in ["settings", "admin_texts", "admin_buttons", "admin_broadcast", 
                "add_button", "del_button", "main_menu", "admin_stats"]:
        return
    
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            # Tugma ma'lumotlarini olish
            async with db.execute(
                "SELECT action_type, action_key FROM buttons WHERE key=?", 
                (data,)
            ) as cursor:
                button_data = await cursor.fetchone()
            
            if not button_data:
                await query.answer("❌ Tugma topilmadi", show_alert=True)
                return
            
            action_type, action_key = button_data
            
            if action_type == "text":
                async with db.execute("SELECT value FROM texts WHERE key=?", (action_key,)) as cursor:
                    text_data = await cursor.fetchone()
                    if text_data:
                        await query.message.answer(text_data[0])
                        await query.answer()
                    else:
                        await query.answer("❌ Matn topilmadi", show_alert=True)
    
    except Exception as e:
        logger.error(f"❌ User button handler xato: {e}")
        await query.answer("❌ Xato yuz berdi", show_alert=True)

# =======================
# 🔹 MAIN - Polling
# =======================
async def main():
    try:
        await init_db()
        logger.info("🤖 Bot ishga tushmoqda...")
        await dp.start_polling(bot)
    except Exception as e:
        logger.error(f"❌ Bot ishga tushmadi: {e}")

if __name__ == "__main__":
    try:
        print("🚀 Aviator Turbo Bot ishga tushdi...")
        asyncio.run(main())
    except KeyboardInterrupt:
        print("❌ Bot to'xtatildi")
    except Exception as e:
        print(f"💥 Kutilmagan xato: {e}")
