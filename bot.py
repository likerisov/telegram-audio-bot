import os
import asyncio
import logging
import tempfile
import shutil
from flask import Flask
from threading import Thread
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from yt_dlp import YoutubeDL

BOT_TOKEN = os.environ.get("BOT_TOKEN")

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Flask для UptimeRobot
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is running!"

def download_audio(url: str, output_dir: str) -> str:
    ydl_opts = {
        'format': 'bestaudio/best',
        'outtmpl': os.path.join(output_dir, '%(title)s.%(ext)s'),
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }],
        'quiet': True,
        'no_warnings': True,
        # Обход защиты YouTube
        'extractor_args': {
            'youtube': {
                'player_client': ['android', 'web'],
            }
        },
        # Заголовки как у браузера
        'http_headers': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-us,en;q=0.5',
        }
    }
    
    with YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        base = ydl.prepare_filename(info)
        mp3_path = os.path.splitext(base)[0] + '.mp3'
        
        if not os.path.isfile(mp3_path):
            mp3_files = [f for f in os.listdir(output_dir) if f.endswith('.mp3')]
            if not mp3_files:
                raise FileNotFoundError("MP3 не создан")
            mp3_path = os.path.join(output_dir, mp3_files[0])
        
        return mp3_path

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🎵 Привет! Отправь ссылку на видео (YouTube, TikTok и др.), "
        "и я пришлю MP3!"
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text.strip()
    
    if not url.startswith(('http://', 'https://')):
        await update.message.reply_text("❌ Отправьте ссылку на видео")
        return
    
    temp_dir = tempfile.mkdtemp()
    msg = await update.message.reply_text("⏳ Скачиваю...")
    
    try:
        loop = asyncio.get_running_loop()
        mp3_path = await loop.run_in_executor(None, download_audio, url, temp_dir)
        
        if os.path.getsize(mp3_path) > 50 * 1024 * 1024:
            await msg.edit_text("❌ Файл > 50 МБ")
        else:
            with open(mp3_path, 'rb') as audio:
                await update.message.reply_audio(
                    audio=audio,
                    title=os.path.basename(mp3_path)
                )
            await msg.delete()
    except Exception as e:
        await msg.edit_text(f"❌ Ошибка: {str(e)[:100]}")
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)

def run_flask():
    app.run(host='0.0.0.0', port=10000)

def main():
    Thread(target=run_flask, daemon=True).start()
    
    application = Application.builder().token(BOT_TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    logger.info("Бот запущен!")
    application.run_polling()

if __name__ == "__main__":
    main()
