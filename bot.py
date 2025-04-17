import os
import yt_dlp
from sys import platform
import time
import re
import requests
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# إعداد دالة لتحديد مسار التنزيل بناءً على نظام التشغيل
def get_download_path():
    if platform == "android":  # إذا كان النظام Android
        return '/storage/emulated/0/Download/'
    elif platform == "win32":  # إذا كان النظام Windows
        return os.path.expanduser("~/Downloads/")
    else:  # لأنظمة أخرى مثل Linux وmacOS (Railway)
        return "/root/Downloads/"  # المسار الافتراضي على Railway

# دالة تنزيل الملفات باستخدام yt-dlp
def download_media(url, media_type='video'):
    save_path = get_download_path()  # تحديد مسار التنزيل
    timestamp = time.strftime("%Y%m%d-%H%M%S")  # إضافة طابع زمني لتجنب التكرار
    try:
        ydl_opts = {
            'format': 'best' if media_type == 'video' else 'bestaudio/best',
            'outtmpl': os.path.join(save_path, f'%(title)s_{timestamp}.%(ext)s'),
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            print(f"Downloading {media_type} from {url}...")
            info_dict = ydl.extract_info(url, download=True)
            file_name = ydl.prepare_filename(info_dict)
            print(f"File downloaded successfully to {file_name}")
            return file_name  # إرجاع مسار الملف
    except Exception as e:
        return f"Error during download: {e}"

# دالة تحويل الفيديو إلى صوت باستخدام CloudConvert API
def convert_to_audio(video_file_path):
    cloudconvert_api_key = os.getenv("CLOUDCONVERT_API_KEY")
    if not cloudconvert_api_key:
        return "ERROR: CloudConvert API Key is not set!"

    # إنشاء مهمة تحويل عبر CloudConvert API
    headers = {"Authorization": f"Bearer {cloudconvert_api_key}"}
    payload = {
        "tasks": {
            "import-file": {
                "operation": "import/upload"
            },
            "convert-file": {
                "operation": "convert",
                "input": "import-file",
                "output_format": "mp3"
            },
            "export-file": {
                "operation": "export/url",
                "input": "convert-file"
            }
        }
    }

    # إرسال الطلب لإنشاء المهمة
    response = requests.post("https://api.cloudconvert.com/v2/jobs", json=payload, headers=headers)
    if response.status_code != 201:
        return f"ERROR: Failed to create conversion job. {response.text}"

    job_data = response.json()
    upload_url = job_data["data"]["tasks"]["import-file"]["result"]["form"]["url"]
    form_data = job_data["data"]["tasks"]["import-file"]["result"]["form"]["parameters"]

    # رفع الملف إلى CloudConvert
    with open(video_file_path, 'rb') as file:
        files = {'file': file}
        upload_response = requests.post(upload_url, data=form_data, files=files)
        if upload_response.status_code != 201:
            return f"ERROR: Failed to upload file. {upload_response.text}"

    # الحصول على رابط التحميل للملف المحول
    job_id = job_data["data"]["id"]
    while True:
        status_response = requests.get(f"https://api.cloudconvert.com/v2/jobs/{job_id}", headers=headers)
        if status_response.status_code != 200:
            return f"ERROR: Failed to check job status. {status_response.text}"
        job_status = status_response.json()["data"]["status"]
        if job_status == "finished":
            export_task = status_response.json()["data"]["tasks"]["export-file"]
            converted_file_url = export_task["result"]["files"][0]["url"]
            break
        elif job_status == "error":
            return "ERROR: Conversion failed."
        time.sleep(5)

    # تنزيل الملف المحول
    audio_response = requests.get(converted_file_url)
    audio_file_path = video_file_path.replace(".mp4", ".mp3")
    with open(audio_file_path, 'wb') as audio_file:
        audio_file.write(audio_response.content)

    return audio_file_path

# حالة البوت
class BotState:
    def __init__(self):
        self.url = None
        self.media_type = None

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
            video_file_path = download_media(bot_state.url, media_type='audio')
            if video_file_path.startswith("Error"):
                await update.message.reply_text(video_file_path)
            else:
                audio_file_path = convert_to_audio(video_file_path)
                if audio_file_path.startswith("Error"):
                    await update.message.reply_text(audio_file_path)
                else:
                    await update.message.reply_text("✅ Audio downloaded successfully!")
                    with open(audio_file_path, 'rb') as file:
                        await update.message.reply_audio(file)
                    os.remove(video_file_path)  # حذف الملف الأصلي
                    os.remove(audio_file_path)  # حذف الملف المحول
            bot_state.__init__()
        elif text.lower() in ['🎬 video', 'video']:
            bot_state.media_type = 'video'
            await update.message.reply_text("⏳ Downloading video... Please wait.")
            file_path = download_media(bot_state.url, media_type='video')
            if file_path.startswith("Error"):
                await update.message.reply_text(file_path)
            else:
                await update.message.reply_text("✅ Video downloaded successfully!")
                with open(file_path, 'rb') as file:
                    await update.message.reply_video(file)
                os.remove(file_path)  # حذف الملف بعد الإرسال
            bot_state.__init__()
        else:
            await update.message.reply_text("Invalid choice. Please choose '🎧 Audio' or '🎬 Video'.")

# نقطة البداية
def main():
    # قراءة API Token من المتغيرات البيئية
    API_TOKEN = os.getenv("API_TOKEN")
    if not API_TOKEN:
        print("ERROR: API_TOKEN is not set!")
        return

    print("Starting bot...")
    # إنشاء التطبيق
    app = Application.builder().token(API_TOKEN).build()

    # إضافة معالجات الأوامر
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # بدء البوت باستخدام Polling
    app.run_polling()

if __name__ == '__main__':
    main()
