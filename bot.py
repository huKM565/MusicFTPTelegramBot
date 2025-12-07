import asyncio
import logging
import os
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart, Command, CommandObject
from aiogram.utils.keyboard import InlineKeyboardBuilder
from dotenv import load_dotenv
from main import download_audio, upload_via_sftp, search_youtube

# Загрузка переменных окружения
load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
ALLOWED_USER_ID = os.getenv("ALLOWED_USER_ID")

# Настройка логирования
logging.basicConfig(level=logging.INFO)

# Инициализация бота и диспетчера
# Проверка наличия токена
if not BOT_TOKEN:
    logging.error("BOT_TOKEN не найден в переменных окружения (.env)")
    exit(1)

if not ALLOWED_USER_ID:
    logging.warning("ALLOWED_USER_ID не задан в .env. Бот будет доступен всем (не рекомендуется).")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

def is_user_allowed(user_id: int) -> bool:
    if not ALLOWED_USER_ID:
        return True
    return str(user_id) == str(ALLOWED_USER_ID)

@dp.message(CommandStart())
async def cmd_start(message: types.Message):
    if not is_user_allowed(message.from_user.id):
        await message.answer("У вас нет доступа к этому боту.")
        return
    await message.answer(
        "Привет! Доступные команды:\n"
        "`/add_track` <ссылка> - скачать по ссылке\n"
        "`/search` <название> - найти и скачать трек",
        parse_mode="Markdown"
    )

async def process_track_download(message: types.Message, url: str):
    status_msg = await message.answer("⏳ Начинаю скачивание аудио...")

    try:
        # Скачивание аудио (в отдельном потоке, так как yt_dlp синхронный)
        audio_file = await asyncio.to_thread(download_audio, url)
        
        await status_msg.edit_text(f"✅ Скачано: {os.path.basename(audio_file)}\n⏳ Загружаю на FTP...")

        # Загрузка на FTP (в отдельном потоке, так как paramiko синхронный)
        await asyncio.to_thread(upload_via_sftp, audio_file)

        await status_msg.edit_text(f"✅ Готово! Файл {os.path.basename(audio_file)} успешно загружен на FTP.")
        
        # Удаление локального файла после успешной загрузки
        try:
            os.remove(audio_file)
            logging.info(f"Removed local file: {audio_file}")
        except OSError as e:
            logging.error(f"Error removing file: {e}")

    except Exception as e:
        logging.error(f"Error processing URL {url}: {e}")
        await status_msg.edit_text(f"❌ Произошла ошибка: {str(e)}")

@dp.message(Command("search"))
async def cmd_search(message: types.Message, command: CommandObject):
    if not is_user_allowed(message.from_user.id):
        await message.answer("У вас нет доступа к этому боту.")
        return

    if command.args is None:
        await message.answer("Ошибка: введите запрос. Пример: `/search Linkin Park Numb`", parse_mode="Markdown")
        return

    query = command.args.strip()
    status_msg = await message.answer(f"🔎 Ищу: {query}...")

    try:
        results = await asyncio.to_thread(search_youtube, query)
        
        if not results:
            await status_msg.edit_text("Ничего не найдено.")
            return

        builder = InlineKeyboardBuilder()
        
        for i, video in enumerate(results):
            title = video['title']
            vid_id = video.get('id')
            
            # Если id нет (например, старая версия main.py), используем url, но это может быть длинно
            if not vid_id:
                 # Fallback если id не вернулся
                 logging.warning("No video ID found, skipping button generation for this item")
                 continue

            builder.button(text=f"{i+1}. {title[:50]}", callback_data=f"download:{vid_id}")

        builder.adjust(1)
        await status_msg.edit_text(f"Результаты поиска по запросу '{query}':", reply_markup=builder.as_markup())

    except Exception as e:
        logging.error(f"Error searching {query}: {e}")
        await status_msg.edit_text(f"❌ Ошибка поиска: {str(e)}")

@dp.callback_query(F.data.startswith("download:"))
async def on_download_click(callback: types.CallbackQuery):
    if not is_user_allowed(callback.from_user.id):
        await callback.answer("У вас нет доступа к этому боту.", show_alert=True)
        return

    vid_id = callback.data.split(":")[1]
    url = f"https://www.youtube.com/watch?v={vid_id}"
    
    await callback.answer("Запрос принят, начинаю загрузку...")
    # Отправляем сообщение в чат, откуда пришел клик
    await process_track_download(callback.message, url)

@dp.message(Command("add_track"))
async def cmd_add_track(message: types.Message, command: CommandObject):
    if not is_user_allowed(message.from_user.id):
        await message.answer("У вас нет доступа к этому боту.")
        return

    if command.args is None:
        await message.answer("Ошибка: не передана ссылка. Используйте формат: `/add_track <ссылка>`", parse_mode="Markdown")
        return

    url = command.args.strip()
    
    # Простая проверка на ссылку
    if not url.startswith("http"):
        await message.answer("Это не похоже на ссылку. Пожалуйста, отправьте корректную ссылку.")
        return

    await process_track_download(message, url)

async def main():
    logging.info("Запуск бота...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.info("Бот остановлен")