import os
import yt_dlp
import time
import asyncio
import queue
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# تحديد مسار التنزيل
DOWNLOAD_PATH = os.path.join(os.getcwd(), 'downloads')
if not os.path.exists(DOWNLOAD_PATH):
    os.makedirs(DOWNLOAD_PATH)

# حالة البوت
class BotState:
    def __init__(self):
        self.url = None
        self.media_type = None  # audio, video, photo, file, playlist, direct_link

bot_state = BotState()

# قائمة انتظار لتحديثات التقدم
progress_queue = queue.Queue()

# دالة تنزيل الوسائط مع رسائل تفاعلية
async def download_media_with_progress(update: Update, context: ContextTypes.DEFAULT_TYPE, url, media_type='video'):
    timestamp = time.strftime("%Y%m%d-%H%M%S")
    progress_message = None

    def progress_hook(d):
        if d['status'] == 'downloading':
            percent = d.get('_percent_str', '0%').strip()
            # إرسال تحديث التقدم إلى قائمة الانتظار
            progress_queue.put(percent)

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
            ydl_opts = {
                'format': 'bestvideo+bestaudio/best',
                'outtmpl': os.path.join(DOWNLOAD_PATH, f'video_{timestamp}.%(ext)s'),
                'merge_output_format': 'mp4',
                'progress_hooks': [progress_hook],
            }
        elif media_type == 'photo':
            ydl_opts = {
                'format': 'best',
                'outtmpl': os.path.join(DOWNLOAD_PATH, f'photo_{timestamp}.%(ext)s'),
                'progress_hooks': [progress_hook],
            }
        elif media_type == 'file':
            ydl_opts = {
                'format': 'best',
                'outtmpl': os.path.join(DOWNLOAD_PATH, f'file_{timestamp}.%(ext)s'),
                'progress_hooks': [progress_hook],
            }
        elif media_type == 'playlist':
            ydl_opts = {
                'format': 'bestvideo+bestaudio/best',
                'outtmpl': os.path.join(DOWNLOAD_PATH, f'playlist_{timestamp}/%(title)s.%(ext)s'),
                'merge_output_format': 'mp4',
                'noplaylist': False,  # تمكين تنزيل القوائم
                'progress_hooks': [progress_hook],
            }
        elif media_type == 'direct_link':
            ydl_opts = {
                'format': 'best',
                'outtmpl': os.path.join(DOWNLOAD_PATH, f'direct_{timestamp}.%(ext)s'),
                'progress_hooks': [progress_hook],
            }
        else:
            return "Invalid media type."

        # إرسال رسالة البداية
        progress_message = await update.message.reply_text("⏳ Downloading... 0%")

        # معالجة تحديثات التقدم في الخلفية
        async def handle_progress_updates():
            last_percent = None  # لتخزين آخر نسبة مئوية تم تحديثها
            while True:
                try:
                    # الحصول على تحديث التقدم من قائمة الانتظار
                    percent = progress_queue.get_nowait()
                    # التحقق مما إذا كانت النسبة المئوية قد تغيرت
                    if percent != last_percent:
                        await context.bot.edit_message_text(
                            chat_id=update.message.chat_id,
                            message_id=progress_message.message_id,
                            text=f"⏳ Downloading... {percent}"
                        )
                        last_percent = percent  # تحديث آخر نسبة مئوية
                except queue.Empty:
                    break  # إنهاء الحلقة إذا كانت قائمة الانتظار فارغة
                await asyncio.sleep(0.5)  # تأخير قصير لتجنب الضغط على الحلقة الحدثية

        # تشغيل مهمة تحديث الرسائل التفاعلية
        asyncio.create_task(handle_progress_updates())

        # تنفيذ عملية التنزيل
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info_dict = ydl.extract_info(url, download=True)
            file_name = ydl.prepare_filename(info_dict)
            if media_type == 'audio':
                converted_file = os.path.splitext(file_name)[0] + '.mp3'
                if os.path.exists(converted_file):
                    return converted_file
                else:
                    return "Error: Conversion failed."
            elif media_type == 'playlist':
                return "✅ Playlist downloaded successfully!"
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

# دالة استجابة لأمر /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    bot_state.__init__()  # إعادة تهيئة الحالة
    await update.message.reply_text(
        "Welcome to the Media Downloader!\n"
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
        keyboard = [["🎧 Audio", "🎬 Video"], ["🖼️ Photo", "📄 File"], ["🎵 Playlist", "🔗 Direct Link"], ["❌ Cancel"]]
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
            await update.message.reply_text("⏳ Starting video download...")
            file_path = await download_media_with_progress(update, context, bot_state.url, media_type='video')
            if file_path.startswith("Error"):
                await update.message.reply_text("❌ Failed to download the media. Please check the link and try again.")
            else:
                if os.path.exists(file_path):
                    await update.message.reply_text("✅ Video downloaded successfully!")
                    with open(file_path, 'rb') as file:
                        await update.message.reply_video(file)
                    os.remove(file_path)  # حذف الملف بعد الإرسال
                else:
                    await update.message.reply_text("❌ File not found after download. Please try again.")
            bot_state.__init__()

        elif text.lower() in ['🖼️ photo', 'photo']:
            bot_state.media_type = 'photo'
            await update.message.reply_text("⏳ Starting photo download...")
            file_path = await download_media_with_progress(update, context, bot_state.url, media_type='photo')
            if file_path.startswith("Error"):
                await update.message.reply_text("❌ Failed to download the media. Please check the link and try again.")
            else:
                if os.path.exists(file_path):
                    await update.message.reply_text("✅ Photo downloaded successfully!")
                    with open(file_path, 'rb') as file:
                        await update.message.reply_photo(file)
                    os.remove(file_path)  # حذف الملف بعد الإرسال
                else:
                    await update.message.reply_text("❌ File not found after download. Please try again.")
            bot_state.__init__()

        elif text.lower() in ['📄 file', 'file']:
            bot_state.media_type = 'file'
            await update.message.reply_text("⏳ Starting file download...")
            file_path = await download_media_with_progress(update, context, bot_state.url, media_type='file')
            if file_path.startswith("Error"):
                await update.message.reply_text("❌ Failed to download the media. Please check the link and try again.")
            else:
                if os.path.exists(file_path):
                    await update.message.reply_text("✅ File downloaded successfully!")
                    with open(file_path, 'rb') as file:
                        await update.message.reply_document(file)
                    os.remove(file_path)  # حذف الملف بعد الإرسال
                else:
                    await update.message.reply_text("❌ File not found after download. Please try again.")
            bot_state.__init__()

        elif text.lower() in ['🎵 playlist', 'playlist']:
            bot_state.media_type = 'playlist'
            await update.message.reply_text("⏳ Starting playlist download...")
            result = await download_media_with_progress(update, context, bot_state.url, media_type='playlist')
            await update.message.reply_text(result)
            bot_state.__init__()

        elif text.lower() in ['🔗 direct link', 'direct link']:
            bot_state.media_type = 'direct_link'
            await update.message.reply_text("⏳ Starting direct link download...")
            file_path = await download_media_with_progress(update, context, bot_state.url, media_type='direct_link')
            if file_path.startswith("Error"):
                await update.message.reply_text("❌ Failed to download the media. Please check the link and try again.")
            else:
                if os.path.exists(file_path):
                    await update.message.reply_text("✅ Direct link downloaded successfully!")
                    with open(file_path, 'rb') as file:
                        await update.message.reply_document(file)
                    os.remove(file_path)  # حذف الملف بعد الإرسال
                else:
                    await update.message.reply_text("❌ File not found after download. Please try again.")
            bot_state.__init__()

        else:
            await update.message.reply_text("Invalid choice. Please choose a valid option.")

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
