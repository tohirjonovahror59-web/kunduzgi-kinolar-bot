import asyncio
import logging
import sqlite3
import html
import time
from typing import Any, Awaitable, Callable, Dict

from aiogram import Bot, Dispatcher, BaseMiddleware, F
from aiogram.types import Message, BufferedInputFile
from aiogram.filters import Command, CommandStart
from aiogram.exceptions import TelegramBadRequest
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

# ---------------------------------------------------------
# SOZLAMALAR
# ---------------------------------------------------------
BOT_TOKEN = "8956064394:AAHatwbsgN_tsVq8LRVPdeZzlFkHXP57Nak"
ADMIN_ID = 6236519402  # Telegram ID

logging.basicConfig(level=logging.INFO)

# ---------------------------------------------------------
# XAVFSIZLIK: Anti-Flood (Rate-Limiting) Middleware
# ---------------------------------------------------------
class ThrottlingMiddleware(BaseMiddleware):
    def __init__(self, limit: float = 0.5):
        self.limit = limit
        self.user_timestamps = {}

    async def __call__(
        self,
        handler: Callable[[Message, Dict[str, Any]], Awaitable[Any]],
        event: Message,
        data: Dict[str, Any]
    ) -> Any:
        user_id = event.from_user.id
        current_time = time.time()
        
        last_time = self.user_timestamps.get(user_id, 0)
        if current_time - last_time < self.limit:
            await event.answer("⚠️ Iltimos, so'rovlarni juda tez-tez yubormang!")
            return
        
        self.user_timestamps[user_id] = current_time
        save_or_update_user(user_id)
        return await handler(event, data)

# ---------------------------------------------------------
# MA'LUMOTLAR BAZASI
# ---------------------------------------------------------
def init_db():
    conn = sqlite3.connect("movies.db")
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS movies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT UNIQUE NOT NULL,
            file_id TEXT NOT NULL,
            title TEXT NOT NULL
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            last_active INTEGER NOT NULL
        )
    """)
    conn.commit()
    conn.close()

def save_or_update_user(user_id: int):
    conn = sqlite3.connect("movies.db")
    cursor = conn.cursor()
    current_time = int(time.time())
    cursor.execute("""
        INSERT INTO users (user_id, last_active) VALUES (?, ?)
        ON CONFLICT(user_id) DO UPDATE SET last_active = excluded.last_active
    """, (user_id, current_time))
    conn.commit()
    conn.close()

def get_stats():
    conn = sqlite3.connect("movies.db")
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM users")
    total_users = cursor.fetchone()[0]

    one_month_ago = int(time.time()) - (30 * 86400)
    cursor.execute("SELECT COUNT(*) FROM users WHERE last_active >= ?", (one_month_ago,))
    monthly_users = cursor.fetchone()[0]

    conn.close()
    return total_users, monthly_users

def add_movie_to_db(code: str, file_id: str, title: str) -> bool:
    try:
        conn = sqlite3.connect("movies.db")
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO movies (code, file_id, title) VALUES (?, ?, ?)",
            (code.strip(), file_id, title.strip())
        )
        conn.commit()
        conn.close()
        return True
    except sqlite3.IntegrityError:
        return False

def delete_movie_from_db(code: str) -> bool:
    conn = sqlite3.connect("movies.db")
    cursor = conn.cursor()
    cursor.execute("DELETE FROM movies WHERE code = ?", (code.strip(),))
    rows_affected = cursor.rowcount
    conn.commit()
    conn.close()
    return rows_affected > 0

def get_movie_from_db(code: str):
    conn = sqlite3.connect("movies.db")
    cursor = conn.cursor()
    cursor.execute("SELECT file_id, title FROM movies WHERE code = ?", (code.strip(),))
    row = cursor.fetchone()
    conn.close()
    return row

# ---------------------------------------------------------
# BOT HANDLERLARI
# ---------------------------------------------------------
dp = Dispatcher()
bot = Bot(
    token=BOT_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN)
)

dp.message.middleware(ThrottlingMiddleware(limit=0.5))

@dp.message(CommandStart())
async def cmd_start(message: Message):
    user_name = html.escape(message.from_user.first_name)
    await message.answer(
        f"Assalomu alaykum, {user_name}!\n\n"
        f"🎬 **Kino Botiga xush kelibsiz.**\n"
        f"Kino ko'rish uchun uning **kodini** yuboring (masalan: `101`)."
    )

@dp.message(Command("add"))
async def cmd_add_movie(message: Message):
    if message.from_user.id != ADMIN_ID:
        return

    if not message.video:
        await message.answer("❌ Xatolik: Ushbu buyruqni kino **videosiga caption (izoh)** sifatida yuboring.\nFormat: `/add <kod> <nomi>`")
        return

    args = message.caption.split(maxsplit=2) if message.caption else []
    if len(args) < 3:
        await message.answer("❌ Noto'g'ri format. Misol: `/add 101 Garri Potter`")
        return

    code = html.escape(args[1])
    title = html.escape(args[2])
    file_id = message.video.file_id

    if add_movie_to_db(code, file_id, title):
        await message.answer(f"✅ **Kino muvaffaqiyatli saqlandi!**\n\n📌 Kod: `{code}`\n🎬 Nomi: {title}")
    else:
        await message.answer(f"⚠️ `{code}` kodi bilan allaqachon kino saqlangan. Boshqa kod tanlang.")

@dp.message(Command("del"))
async def cmd_delete_movie(message: Message):
    if message.from_user.id != ADMIN_ID:
        return

    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.answer("❌ Noto'g'ri format. Misol: `/del 101`")
        return

    code = html.escape(args[1])
    if delete_movie_from_db(code):
        await message.answer(f"🗑 **`{code}` kodli kino muvaffaqiyatli o'chirildi!**")
    else:
        await message.answer(f"🔍 Kechirasiz, `{code}` kodi bo'yicha kino topilmadi.")

@dp.message(Command("stats"))
async def cmd_stats(message: Message):
    if message.from_user.id != ADMIN_ID:
        return

    total_users, monthly_users = get_stats()
    await message.answer(
        f"📊 **Bot Statistikasi:**\n\n"
        f"👥 Umumiy foydalanuvchilar: **{total_users}** ta\n"
        f"🔥 Oxirgi 1 oyda foydalanganlar: **{monthly_users}** ta"
    )

@dp.message(Command("setphoto"))
async def cmd_set_photo(message: Message):
    if message.from_user.id != ADMIN_ID:
        return

    if not message.photo:
        await message.answer("❌ Xatolik: Ushbu buyruqni **rasmga caption (izoh)** sifatida yuboring!\n\n📌 **Qanday yuboriladi:** Rasmni tanlang, подпись (caption) joyiga `/setphoto` deb yozing va yuboring.")
        return

    photo = message.photo[-1]
    file = await bot.get_file(photo.file_id)
    photo_bytes = await bot.download_file(file.file_path)

    try:
        await bot.set_my_profile_photo(photo=BufferedInputFile(photo_bytes.read(), filename="avatar.jpg"))
        await message.answer("✅ **Bot avatarkasi muvaffaqiyatli o'zgartirildi!**")
    except Exception as e:
        await message.answer(f"❌ Rasmni o'rnatishda xatolik: {e}")

@dp.message(F.text & ~F.text.startswith("/"))
async def handle_movie_code(message: Message):
    code = html.escape(message.text.strip())
    
    movie = get_movie_from_db(code)
    if movie:
        file_id, title = movie
        try:
            await message.answer_video(
                video=file_id,
                caption=f"🎬 **{title}**\n\n🍿 Yoqimli tomosha!"
            )
        except TelegramBadRequest:
            await message.answer("❌ Videoni yuklashda xatolik yuz berdi.")
    else:
        await message.answer("🔍 Kechirasiz, ushbu kod bo'yicha hech qanday kino topilmadi.")

# ---------------------------------------------------------
# BOTNI ISHGA TUSHIRISH
# ---------------------------------------------------------
async def main():
    init_db()
    print("Bot ishga tushmoqda...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Bot to'xtatildi.")