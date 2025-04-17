import os
import yt_dlp
import time
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import asyncio

# إعداد دالة لتحديد مسار التنزيل (استخدام /tmp على Railway)
def get_download_path():
    return '/tmp/'

# دالة تنزيل الملفات باستخدام yt-dlp
def download_media(url, media_type='video', video_quality=None):
    save_path = get_download_path()  # تحديد مسار التنزيل
    timestamp = time.strftime("%Y%m%d-%H%M%S")  # إضافة طابع زمني لتجنب التكرار
    try:
        if media_type == 'audio':  # صوت
            ydl_opts = {
                'format': 'bestaudio/best',
                'outtmpl': os.path.join(save_path, f'%(title)s_{timestamp}.%(ext)s'),
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': '192',
                }],
            }
        elif media_type == 'video':  # فيديو
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
                'outtmpl': os.path.join(save_path, f'%(title)s_{timestamp}.%(ext)s'),
            }
        else:
            return "Invalid media type."

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            print(f"Downloading {media_type} from {url}...")
            info_dict = ydl.extract_info(url, download=True)

            # تقصير اسم الملف إلى 50 حرفًا كحد أقصى
            file_name = ydl.prepare_filename(info_dict)
            shortened_file_name = os.path.join(
                os.path.dirname(file_name),
                f"{os.path.splitext(os.path.basename(file_name))[0][:50]}{os.path.splitext(file_name)[1]}"
            )

            # إعادة تسمية الملف إذا كان طويلًا
            if file_name != shortened_file_name:
                os.rename(file_name, shortened_file_name)
                file_name = shortened_file_name

            print(f"File downloaded successfully to {file_name}")
            return file_name  # إرجاع مسار الملف
    except yt_dlp.utils.DownloadError as e:
        if "Facebook" in str(e):
            return "Error: Failed to download from Facebook. Make sure the link is valid and accessible."
        return f"Error during download: {e}"
    except Exception as e:
        return f"Error during download: {e}"

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
                await update.message.reply_text("✅ Audio downloaded successfully!")
                with open(file_path, 'rb') as file:
                    await update.message.reply_audio(file)
                os.remove(file_path)  # حذف الملف بعد الإرسال
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
                await update.message.reply_text(f"✅ Video ({text}) downloaded successfully!")
                with open(file_path, 'rb') as file:
                    await update.message.reply_video(file)
                os.remove(file_path)  # حذف الملف بعد الإرسال
            bot_state.__init__()
        else:
            await update.message.reply_text("Invalid video quality choice. Please select a valid option.")

# استجابة لأمر /subscribers
async def subscribers(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id
    try:
        member_count = await context.bot.get_chat_member_count(chat_id)
        await update.message.reply_text(f"Total subscribers: {member_count}")
    except Exception as e:
        await update.message.reply_text(f"Failed to fetch subscriber count: {e}")

# إيقاف Webhook إذا كان قيد التشغيل
async def stop_webhook_if_running(application):
    try:
        await application.bot.delete_webhook()
        print("Webhook stopped successfully.")
    except Exception as e:
        print(f"Failed to stop webhook: {e}")

# نقطة البداية
def main():
    # أدخل API Token الخاص بك هنا (من متغيرات البيئة)
    API_TOKEN = os.getenv('API_TOKEN')
    if not API_TOKEN:
        raise ValueError("API_TOKEN is not set in environment variables.")

    application = Application.builder().token(API_TOKEN).build()

    # إيقاف Webhook إذا كان قيد التشغيل
    asyncio.run(stop_webhook_if_running(application))

    # إضافة معالجات الأوامر
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("subscribers", subscribers))  # إضافة معالج /subscribers
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # بدء البوت
    application.run_polling()

if __name__ == '__main__':
    main()
