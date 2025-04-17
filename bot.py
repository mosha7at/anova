import os
import yt_dlp
import time
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

# استجابة لأمر /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    bot_state.__init__()  # إعادة تهيئة الحالة
    await update.message.reply_text(
        "Welcome to the Media Downloader!\n"
        "Please enter the URL of the media you want to download:",
        reply_markup=ReplyKeyboardRemove()
    )

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
                    resolution = f.get('resolution', '')
                    if resolution and resolution != 'audio only':
                        height = int(resolution.split('x')[1])  # استخراج الارتفاع من الدقة
                        if height in [144, 240, 360, 480, 720, 1080]:
                            quality_options.append(f"{height}p")
                
                # التحقق مما إذا كانت هناك جودات متاحة
                if not quality_options:
                    await update.message.reply_text("❌ No available qualities found for this video.")
                    return
                
                # إزالة الجودات المكررة وفرزها تصاعديًا
                quality_options = sorted(set(quality_options), key=lambda x: int(x[:-1]))
                quality_options.append("❌ Cancel")  # إضافة زر الإلغاء
                
                # عرض الجودات كقائمة منبثقة
                keyboard = [quality_options[i:i + 3] for i in range(0, len(quality_options), 3)]
                reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)
                await update.message.reply_text("Choose video quality:", reply_markup=reply_markup)
                
                # حفظ الخيارات المتاحة في الحالة
                bot_state.available_qualities = {q: q for q in quality_options}
        
        # عند اختيار الجودة
        elif media_type == 'selected_video':
            selected_quality = update.message.text.strip()
            if selected_quality in bot_state.available_qualities:
                if selected_quality == "❌ Cancel":
                    bot_state.__init__()
                    await update.message.reply_text(
                        "Operation canceled. Please enter a new URL to start again.",
                        reply_markup=ReplyKeyboardRemove()
                    )
                    return
                
                # تحويل الجودة المختارة إلى ارتفاع بالبكسل
                selected_height = int(selected_quality[:-1])
                
                # تنزيل الفيديو بالجودة المحددة أو الأقرب لها
                ydl_opts = {
                    'format': f"bestvideo[height<={selected_height}]+bestaudio/best",
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
        if text.lower() in ['🎬 video', 'video']:
            bot_state.media_type = 'video'
            await download_media_with_quality_choice(update, context, bot_state.url, media_type='video')
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
