import os
import yt_dlp
import time
import asyncio
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
        self.available_qualities = {}  # لتخزين الجودات المتاحة

bot_state = BotState()

# دالة تنزيل الوسائط مع اختيار الجودة
async def download_media_with_quality_choice(update: Update, context: ContextTypes.DEFAULT_TYPE, url, media_type='video'):
    try:
        if media_type == 'video':
            # استخراج المعلومات حول الفيديو والجودات المتاحة
            ydl_opts = {
                'listformats': True,
                'quiet': True,
            }
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info_dict = ydl.extract_info(url, download=False)
                formats = info_dict.get('formats', [])
                
                # تجهيز قائمة الجودات
                quality_options = []
                for f in formats:
                    format_note = f.get('format_note', '')
                    resolution = f.get('resolution', '')
                    if format_note and resolution:
                        quality_options.append(f"{format_note} ({resolution})")
                
                # عرض الجودات كقائمة منبثقة
                keyboard = [quality_options[i:i + 3] for i in range(0, len(quality_options), 3)]
                reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)
                await update.message.reply_text("Choose video quality:", reply_markup=reply_markup)
                
                # حفظ الخيارات المتاحة في الحالة
                bot_state.available_qualities = {q.split(' ')[0]: q for q in quality_options}
        
        # عند اختيار الجودة
        elif media_type == 'selected_video':
            selected_quality = update.message.text.strip()
            if selected_quality in bot_state.available_qualities:
                # تنزيل الفيديو بالجودة المحددة
                ydl_opts = {
                    'format': f"bestvideo[height<={selected_quality.split(' ')[0][:-1]}]+bestaudio/best",
                    'outtmpl': os.path.join(DOWNLOAD_PATH, f'video_{time.strftime("%Y%m%d-%H%M%S")}.%(ext)s'),
                    'merge_output_format': 'mp4',
                }
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info_dict = ydl.extract_info(bot_state.url, download=True)
                    file_name = ydl.prepare_filename(info_dict)

                if os.path.exists(file_name):
                    await update.message.reply_text("✅ Video downloaded successfully!")
                    with open(file_name, 'rb') as file:
                        await update.message.reply_video(file)
                    os.remove(file_name)  # حذف الملف بعد الإرسال
                else:
                    await update.message.reply_text("❌ File not found after download. Please try again.")
            else:
                await update.message.reply_text("Invalid quality choice. Please choose a valid option.")

    except Exception as e:
        await update.message.reply_text(f"❌ Error during download: {e}")

# دالة تنزيل الوسائط الأخرى (بدون جودة)
async def download_media(update: Update, context: ContextTypes.DEFAULT_TYPE, url, media_type='audio'):
    try:
        timestamp = time.strftime("%Y%m%d-%H%M%S")
        if media_type == 'audio':
            ydl_opts = {
                'format': 'bestaudio/best',
                'outtmpl': os.path.join(DOWNLOAD_PATH, f'audio_{timestamp}.%(ext)s'),
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                }],
            }
        elif media_type == 'photo':
            ydl_opts = {
                'format': 'best',
                'outtmpl': os.path.join(DOWNLOAD_PATH, f'photo_{timestamp}.%(ext)s'),
            }
        elif media_type == 'file':
            ydl_opts = {
                'format': 'best',
                'outtmpl': os.path.join(DOWNLOAD_PATH, f'file_{timestamp}.%(ext)s'),
            }
        elif media_type == 'playlist':
            ydl_opts = {
                'format': 'bestvideo+bestaudio/best',
                'outtmpl': os.path.join(DOWNLOAD_PATH, f'playlist_{timestamp}/%(title)s.%(ext)s'),
                'merge_output_format': 'mp4',
                'noplaylist': False,  # تمكين تنزيل القوائم
            }
        elif media_type == 'direct_link':
            ydl_opts = {
                'format': 'best',
                'outtmpl': os.path.join(DOWNLOAD_PATH, f'direct_{timestamp}.%(ext)s'),
            }
        else:
            return "Invalid media type."

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
        return f"Error during download: {e}"

# استجابة لأمر /start
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
            file_path = await download_media(update, context, bot_state.url, media_type='audio')
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
            await download_media_with_quality_choice(update, context, bot_state.url, media_type='video')
        
        elif text.lower() in ['🖼️ photo', 'photo']:
            bot_state.media_type = 'photo'
            file_path = await download_media(update, context, bot_state.url, media_type='photo')
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
            file_path = await download_media(update, context, bot_state.url, media_type='file')
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
            result = await download_media(update, context, bot_state.url, media_type='playlist')
            await update.message.reply_text(result)
            bot_state.__init__()
        
        elif text.lower() in ['🔗 direct link', 'direct link']:
            bot_state.media_type = 'direct_link'
            file_path = await download_media(update, context, bot_state.url, media_type='direct_link')
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
    
    # عند اختيار الجودة
    elif bot_state.media_type == 'video' and hasattr(bot_state, 'available_qualities'):
        bot_state.media_type = 'selected_video'
        await download_media_with_quality_choice(update, context, bot_state.url, media_type='selected_video')

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
