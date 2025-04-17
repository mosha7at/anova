import os
import yt_dlp
import time
import asyncio
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# تحديد مسار التنزيل (داخل المشروع بدلاً من /tmp/)
DOWNLOAD_PATH = os.path.join(os.getcwd(), 'downloads')
if not os.path.exists(DOWNLOAD_PATH):
    os.makedirs(DOWNLOAD_PATH)

# حالة البوت
class BotState:
    def __init__(self):
        self.url = None
        self.media_type = None
        self.video_quality = None

bot_state = BotState()

# دالة تنزيل الوسائط مع رسائل تفاعلية
async def download_media_with_progress(update: Update, context: ContextTypes.DEFAULT_TYPE, url, media_type='video', video_quality=None):
    timestamp = time.strftime("%Y%m%d-%H%M%S")
    progress_message = None

    def progress_hook(d):
        nonlocal progress_message
        if d['status'] == 'downloading':
            percent = d.get('_percent_str', '0%').strip()
            if progress_message:
                # تحديث الرسالة الحالية باستخدام الحلقة الحدث
                try:
                    loop = asyncio.get_event_loop()
                    loop.run_until_complete(
                        context.bot.edit_message_text(
                            chat_id=update.message.chat_id,
                            message_id=progress_message.message_id,
                            text=f"⏳ Downloading... {percent}"
                        )
                    )
                except Exception as e:
                    print(f"Error updating progress message: {e}")

    try:
        if media_type == 'audio':
            ydl_opts = {
                'format': 'bestaudio/best',
                'outtmpl': os.path.join(DOWNLOAD_PATH, f'audio_{timestamp}.%(ext)s'),
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                }],
                'progress_hooks': [progress_hook],
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
                'outtmpl': os.path.join(DOWNLOAD_PATH, f'video_{timestamp}.%(ext)s'),
                'merge_output_format': 'mp4',
                'progress_hooks': [progress_hook],
            }
        else:
            return "Invalid media type."

        # إرسال رسالة البداية
        progress_message = await update.message.reply_text("⏳ Downloading... 0%")

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info_dict = ydl.extract_info(url, download=True)
            file_name = ydl.prepare_filename(info_dict)

            if media_type == 'audio':
                converted_file = os.path.splitext(file_name)[0] + '.mp3'
                if os.path.exists(converted_file):
                    return converted_file
                else:
                    return "Error: Conversion failed."
            else:
                return file_name

    except Exception as e:
        if progress_message:
            await context.bot.edit_message_text(
                chat_id=update.message.chat_id,
                message_id=progress_message.message_id,
                text=f"❌ Error during download: {e}"
            )
        return f"Error during download: {e}"

# استجابة لأمر /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    bot_state.__init__()  # إعادة تهيئة الحالة
    await update.message.reply_text(
        "Welcome to the Media Downloader!\n\n"
        "Please enter the URL of the media you want to download:",
        reply_markup=ReplyKeyboardRemove()
    )

# معالجة الرسائل النصية
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()

    # إذا تم الضغط على زر "Cancel"
    if text.lower() in ['cancel', 'close', '❌ cancel']:
        bot_state.__init__()
        await update.message.reply_text(
            "Operation canceled. Please enter a new URL to start again.",
            reply_markup=ReplyKeyboardRemove()
        )
        return

    if bot_state.url is None:
        bot_state.url = text
        keyboard = [["🎧 Audio", "🎬 Video"], ["❌ Cancel"]]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)
        await update.message.reply_text("Choose media type:", reply_markup=reply_markup)
    elif bot_state.media_type is None:
        if text.lower() in ['🎧 audio', 'audio']:
            bot_state.media_type = 'audio'
            await update.message.reply_text("⏳ Starting audio download...")
            file_path = await download_media_with_progress(update, context, bot_state.url, media_type='audio')
            if file_path.startswith("Error"):
                await update.message.reply_text("❌ Failed to download the media. Please check the link and try again.")
            else:
                if os.path.exists(file_path):
                    await update.message.reply_text("✅ Audio downloaded successfully!")
                    with open(file_path, 'rb') as file:
                        await update.message.reply_audio(file)
                    os.remove(file_path)  # حذف الملف بعد الإرسال
                else:
                    await update.message.reply_text("❌ File not found after download. Please try again.")
            bot_state.__init__()
        elif text.lower() in ['🎬 video', 'video']:
            bot_state.media_type = 'video'
            # عرض أزرار الجودات الثابتة
            keyboard = [
                ["🎥 144p", "🎥 240p"],
                ["🎥 360p", "🎥 480p"],
                ["🎥 720p", "🎥 1080p"],
                ["❌ Cancel"]
            ]
            reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)
            await update.message.reply_text("Select video quality:", reply_markup=reply_markup)
        else:
            await update.message.reply_text("Invalid choice. Please choose '🎧 Audio' or '🎬 Video'.")
    elif bot_state.video_quality is None:
        # قائمة الجودات المدعومة
        supported_qualities = ["144p", "240p", "360p", "480p", "720p", "1080p"]
        if text in [f"🎥 {q}" for q in supported_qualities]:
            bot_state.video_quality = text.replace("🎥 ", "")  # استخراج الجودة المختارة
            await update.message.reply_text(f"⏳ Starting video download ({text})...")
            file_path = await download_media_with_progress(update, context, bot_state.url, media_type='video', video_quality=bot_state.video_quality)
            if file_path.startswith("Error"):
                await update.message.reply_text("❌ Failed to download the media. Please check the link and try again.")
            else:
                if os.path.exists(file_path):
                    await update.message.reply_text(f"✅ Video ({text}) downloaded successfully!")
                    with open(file_path, 'rb') as file:
                        await update.message.reply_video(file)
                    os.remove(file_path)  # حذف الملف بعد الإرسال
                else:
                    await update.message.reply_text("❌ File not found after download. Please try again.")
            bot_state.__init__()
        else:
            await update.message.reply_text("Invalid video quality choice. Please select a valid option.")

# نقطة البداية
def main():
    API_TOKEN = os.getenv('API_TOKEN')
    if not API_TOKEN:
        raise ValueError("API_TOKEN is not set in environment variables.")

    application = Application.builder().token(API_TOKEN).build()

    # إضافة معالجات الأوامر
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # بدء البوت
    application.run_polling()

if __name__ == '__main__':
    main()
