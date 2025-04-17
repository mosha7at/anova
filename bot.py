import os
import yt_dlp
from sys import platform
import time
import re
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# إعداد دالة لتحديد مسار التنزيل بناءً على نظام التشغيل
def get_download_path():
    if platform == "android":  # إذا كان النظام Android
        return '/storage/emulated/0/Download/'
    elif platform == "win32":  # إذا كان النظام Windows
        return os.path.expanduser("~/Downloads/")
    else:  # لأنظمة أخرى مثل Linux وmacOS
        return os.path.expanduser("~/Downloads/")

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
                '144p': '144',
                '240p': '240',
                '360p': '360',
                '480p': '480',
                '720p': '720',
                '1080p': '1080',
            }
            selected_quality = format_map.get(video_quality, 'best')
            ydl_opts = {
                'format': f'bestvideo[height<={selected_quality}]+bestaudio/best',
                'outtmpl': os.path.join(save_path, f'%(title)s_{timestamp}.%(ext)s'),
            }
        else:
            return "Invalid media type."

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            print(f"Downloading {media_type} from {url}...")
            info_dict = ydl.extract_info(url, download=True)
            file_name = ydl.prepare_filename(info_dict)

            # إصلاح مسار الملف إذا تم تغيير الامتداد بواسطة postprocessor
            if media_type == 'audio':
                file_name = os.path.splitext(file_name)[0] + '.mp3'

            print(f"File downloaded successfully to {file_name}")
            return file_name  # إرجاع مسار الملف
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
        "Please enter the URL of the media you want to download (YouTube, TikTok, Instagram, etc.):",
        reply_markup=ReplyKeyboardRemove()
    )

# استجابة لإدخال الرسائل
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()

    if bot_state.url is None:
        # التحقق من صحة الرابط باستخدام التعبيرات النمطية
        platforms_regex = (
            r'(https?://)?(www\.)?'  # http أو https (اختياري)
            r'(youtube\.com|youtu\.be|tiktok\.com|instagram\.com)'  # الأنماط المدعومة
            r'(/.*)?'  # باقي الرابط
        )
        match = re.match(platforms_regex, text)
        if not match:
            await update.message.reply_text(
                "Invalid URL. Please enter a valid link from YouTube, TikTok, or Instagram."
            )
            return
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
                await update.message.reply_text(file_path)
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
                await update.message.reply_text(file_path)
            else:
                await update.message.reply_text(f"✅ Video ({text}) downloaded successfully!")
                with open(file_path, 'rb') as file:
                    await update.message.reply_video(file)
                os.remove(file_path)  # حذف الملف بعد الإرسال
            bot_state.__init__()
        else:
            await update.message.reply_text("Invalid video quality choice. Please select a valid option.")

# نقطة البداية
def main():
    # أدخل API Token الخاص بك هنا
    API_TOKEN = '8102684495:AAEt7tulbJnCy9xIos9b5Kf9OwwGqf3UqMI'

    application = Application.builder().token(API_TOKEN).build()

    # إضافة معالجات الأوامر
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # بدء البوت
    application.run_polling()

if __name__ == '__main__':
    main()
