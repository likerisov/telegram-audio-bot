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

app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is running!"

def download_audio(url: str, output_dir: str) -> str:
    # Пробуем разные способы обхода
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
        # Способ 1: маскировка под Android
        'extractor_args': {
            'youtube': {
                'player_client': ['android', 'ios', 'web'],
                'player_skip': ['webpage', 'configs'],
            }
        },
        # Способ 2: разные User-Agent
        'http_headers': {
            'User-Agent': 'com.google.android.youtube/19.29.37 (Linux; U; Android 14; en_US)',
            'Accept-Language': 'en-US,en;q=0.9',
        },
        # Способ 3: не проверять сертификаты
        'nocheckcertificate': True,
        # Способ 4: больше попыток
        'retries': 5,
        'fragment_retries': 5,
        'skip_unavailable_fragments': True,
    }
    
    try:
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
    except Exception as e:
        # Если YouTube заблокировал — даём понятную ошибку
        if "Sign in to confirm" in str(e):
            raise Exception("YouTube требует подтверждение. Попробуйте другое видео или соцсеть (TikTok, Vimeo)")
        raise e

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🎵 Привет! Отправь ссылку на видео (YouTube, TikTok, Vimeo и др.), "
        "и я пришлю MP3!\n\n"
        "⚠️ Из-за ограничений YouTube некоторые видео могут не скачиваться. "
        "Попробуйте TikTok или Vimeo."
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
        await msg.edit_text(f"❌ Ошибка: {str(e)[:150]}")
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
