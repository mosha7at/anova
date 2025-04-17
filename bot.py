import os
import yt_dlp
import time
import asyncio
import queue
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

# قائمة انتظار للتعامل مع تحديثات التقدم
progress_queue = queue.Queue()

# دالة تنزيل الوسائط مع رسائل تفاعلية
async def download_media_with_progress(update: Update, context: ContextTypes.DEFAULT_TYPE, url, media_type='video', video_quality=None):
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

        # معالجة تحديثات التقدم في الخلفية
        async def handle_progress_updates():
            while True:
                try:
                    # الحصول على تحديث التقدم من قائمة الانتظار
                    percent = progress_queue.get_nowait()
                    await context.bot.edit_message_text(
                        chat_id=update.message.chat_id,
                        message_id=progress_message.message_id,
                        text=f"⏳ Downloading... {percent}"
                    )
                except queue.Empty:
                    break
                await asyncio.sleep(0.5)  # تأخير قصير لتجنب الضغط على الحلقة الحدثية

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
