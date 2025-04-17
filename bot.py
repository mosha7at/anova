import os
import yt_dlp
import asyncio
import time
import logging
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from telegram.error import Conflict

# تكوين نظام تسجيل الأحداث
logging.basicConfig(level=logging.INFO)

# تحديد مسار التنزيل (داخل المشروع بدلاً من /tmp/)
def get_download_path():
    download_path = os.path.join(os.getcwd(), 'downloads')
    if not os.path.exists(download_path):
        os.makedirs(download_path)
    return download_path

# دالة تنظيف الملفات القديمة
def clean_old_files(download_path, max_age_seconds=3600):
    """حذف الملفات القديمة التي تتجاوز عمرها max_age_seconds."""
    now = time.time()
    for filename in os.listdir(download_path):
        file_path = os.path.join(download_path, filename)
        if os.path.isfile(file_path) and (now - os.path.getmtime(file_path)) > max_age_seconds:
            os.remove(file_path)
            logging.info(f"Deleted old file: {file_path}")

# دالة تنزيل الملفات باستخدام yt-dlp
def download_media(url, media_type='video', video_quality=None):
    save_path = get_download_path()
    timestamp = time.strftime("%Y%m%d-%H%M%S")
    try:
        if media_type == 'audio':
            ydl_opts = {
                'format': 'bestaudio/best',
                'outtmpl': os.path.join(save_path, f'%(id)s_{timestamp}.%(ext)s'),
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                }],
            }
        elif media_type == 'video':
            format_map = {
                '144p': 'bestvideo[height<=144]+bestaudio/best',
                '240p': 'bestvideo[height<=240]+bestaudio/best',
                '360p': 'bestvideo[height<=360]+bestaudio/best',
                '480p': 'bestvideo[height<=480]+bestaudio/best',
                '720p': 'bestvideo[height<=720]+bestaudio/best',
                '1080p': 'bestvideo[height<=1080]+bestaudio/best',
            }
            selected_format = format_map.get(video_quality, 'bestvideo+bestaudio/best')
            ydl_opts = {
                'format': selected_format,
                'outtmpl': os.path.join(save_path, f'%(id)s_{timestamp}.%(ext)s'),
            }
        else:
            return "Invalid media type."

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info_dict = ydl.extract_info(url, download=True)
            original_file = ydl.prepare_filename(info_dict)

            if media_type == 'audio':
                converted_file = os.path.splitext(original_file)[0] + '.mp3'
                if os.path.exists(converted_file):
                    os.remove(original_file)  # حذف الملف الأصلي
                    return converted_file
                else:
                    logging.error("Conversion failed. Converted file not found.")
                    return "Error: Conversion failed."
            else:
                return original_file

    except yt_dlp.utils.DownloadError as e:
        logging.error(f"Download error: {e}")
        return f"Error during download: {e}"
    except Exception as e:
        logging.error(f"Unexpected error: {e}")
        return f"Error: {e}"

# حالة البوت
class BotState:
    def __init__(self):
        self.url = None
        self.media_type = None
        self.video_quality = None

bot_state = BotState()

# استجابة لأمر /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    bot_state.__init__()  # إعادة تهيئة الحالة
    await update.message.reply_text(
        "Welcome to the Multi-Platform Media Downloader!\n\n"
        "Please enter the URL of the media you want to download:",
        reply_markup=ReplyKeyboardRemove()
    )

# معالجة الرسائل النصية
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()

    if bot_state.url is None:
        bot_state.url = text
        keyboard = [
            ["🎧 Audio", "🎬 Video"]
        ]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)
        await update.message.reply_text("Choose media type:", reply_markup=reply_markup)
    elif bot_state.media_type is None:
        if text.lower() in ['🎧 audio', 'audio']:
            bot_state.media_type = 'audio'
            await update.message.reply_text("⏳ Downloading audio... Please wait.")
            file_path = download_media(bot_state.url, media_type='audio')
            if file_path.startswith("Error"):
                await update.message.reply_text("❌ Failed to download the media. Please check the link and try again.")
            else:
                # التحقق من وجود الملف قبل فتحه
                if os.path.exists(file_path):
                    # التحقق من حجم الملف
                    file_size = os.path.getsize(file_path)
                    if file_size > 50 * 1024 * 1024:  # أكثر من 50 ميجابايت
                        await update.message.reply_text("⚠️ File size is too large. Cannot send via Telegram.")
                    else:
                        await update.message.reply_text("✅ Audio downloaded successfully!")
                        with open(file_path, 'rb') as file:
                            await update.message.reply_audio(file)
                    os.remove(file_path)  # حذف الملف بعد الإرسال
                else:
                    await update.message.reply_text("❌ File not found after download. Please try again.")
            bot_state.__init__()
        elif text.lower() in ['🎬 video', 'video']:
            bot_state.media_type = 'video'
            keyboard = [
                ["🎥 144p", "🎥 240p"],
                ["🎥 360p", "🎥 480p"],
                ["🎥 720p", "🎥 1080p"]
            ]
            reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)
            await update.message.reply_text("Select video quality:", reply_markup=reply_markup)
        else:
            await update.message.reply_text("Invalid choice. Please choose '🎧 Audio' or '🎬 Video'.")
    elif bot_state.video_quality is None:
        quality_map = {
            "🎥 144p": "144p",
            "🎥 240p": "240p",
            "🎥 360p": "360p",
            "🎥 480p": "480p",
            "🎥 720p": "720p",
            "🎥 1080p": "1080p"
        }
        if text in quality_map:
            bot_state.video_quality = quality_map[text]
            await update.message.reply_text(f"⏳ Downloading video ({text})... Please wait.")
            file_path = download_media(bot_state.url, media_type='video', video_quality=bot_state.video_quality)
            if file_path.startswith("Error"):
                await update.message.reply_text("❌ Failed to download the media. Please check the link and try again.")
            else:
                # التحقق من وجود الملف قبل فتحه
                if os.path.exists(file_path):
                    # التحقق من حجم الملف
                    file_size = os.path.getsize(file_path)
                    if file_size > 50 * 1024 * 1024:  # أكثر من 50 ميجابايت
                        await update.message.reply_text("⚠️ File size is too large. Cannot send via Telegram.")
                    else:
                        await update.message.reply_text(f"✅ Video ({text}) downloaded successfully!")
                        with open(file_path, 'rb') as file:
                            await update.message.reply_video(file)
                    os.remove(file_path)  # حذف الملف بعد الإرسال
                else:
                    await update.message.reply_text("❌ File not found after download. Please try again.")
            bot_state.__init__()
        else:
            await update.message.reply_text("Invalid video quality choice. Please select a valid option.")

# إيقاف Webhook إذا كان قيد التشغيل
async def stop_webhook_if_running(application):
    try:
        await application.bot.delete_webhook()
        logging.info("Webhook stopped successfully.")
    except Exception as e:
        logging.error(f"Failed to stop webhook: {e}")

# نقطة البداية
def main():
    # أدخل API Token الخاص بك هنا (من متغيرات البيئة)
    API_TOKEN = os.getenv('API_TOKEN')
    if not API_TOKEN:
        raise ValueError("API_TOKEN is not set in environment variables.")

    # تنظيف الملفات القديمة عند بدء البرنامج
    clean_old_files(get_download_path())

    # إنشاء حلقة حدث يدوياً
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    application = Application.builder().token(API_TOKEN).build()

    # إيقاف Webhook إذا كان قيد التشغيل
    loop.run_until_complete(stop_webhook_if_running(application))

    # إضافة معالجات الأوامر
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # بدء البوت
    application.run_polling()

if __name__ == '__main__':
    main()
