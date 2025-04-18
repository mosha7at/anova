import os
import yt_dlp
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# تحديد مسار التنزيل (داخل المشروع)
DOWNLOAD_PATH = os.path.join(os.getcwd(), 'downloads')
if not os.path.exists(DOWNLOAD_PATH):
    os.makedirs(DOWNLOAD_PATH)

# دالة تنزيل الوسائط باستخدام yt-dlp
def download_media(url, media_type='video', video_quality=None):
    timestamp = time.strftime("%Y%m%d-%H%M%S")
    try:
        if media_type == 'audio':
            ydl_opts = {
                'format': 'bestaudio/best',
                'outtmpl': os.path.join(DOWNLOAD_PATH, f'audio_{timestamp}.%(ext)s'),
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                }],
            }
        elif media_type == 'video':
            # استخراج جميع التنسيقات المتاحة
            with yt_dlp.YoutubeDL() as ydl:
                info_dict = ydl.extract_info(url, download=False)
                formats = info_dict.get('formats', [])
                available_qualities = set()
                for fmt in formats:
                    height = fmt.get('height')
                    if height:
                        available_qualities.add(f"{height}p")

            # التحقق من صحة الجودة المختارة
            if video_quality and f"{video_quality}p" not in available_qualities:
                return f"Error: The selected quality ({video_quality}p) is not available."

            # اختيار الجودة بناءً على ارتفاع الفيديو
            ydl_opts = {
                'format': f"bestvideo[height<={video_quality}]+bestaudio/best",
                'outtmpl': os.path.join(DOWNLOAD_PATH, f'video_{timestamp}.%(ext)s'),
            }
        else:
            return "Invalid media type."

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info_dict = ydl.extract_info(url, download=True)
            file_name = ydl.prepare_filename(info_dict)

            # إذا كان نوع الملف صوت، فسنعيد اسم الملف بعد التحويل
            if media_type == 'audio':
                converted_file = os.path.splitext(file_name)[0] + '.mp3'
                if os.path.exists(converted_file):
                    return converted_file
                else:
                    return "Error: Conversion failed."
            else:
                return file_name

    except Exception as e:
        # معالجة الأخطاء الناتجة عن الروابط غير المدعومة
        if "Unsupported URL" in str(e) or "Cannot parse data" in str(e):
            return "Error: Unable to download the media. Please ensure the link is valid and try again later."
        return f"Error during download: {e}"

# استجابة لأمر /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()  # إعادة تهيئة حالة المستخدم
    await update.message.reply_text(
        "Welcome to the Universal Media Downloader!\n\n"
        "Please enter the URL of the media you want to download:",
        reply_markup=ReplyKeyboardRemove()
    )

# معالجة الرسائل النصية
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()

    # إذا تم الضغط على زر "Cancel"
    if text.lower() in ['cancel', 'close', '❌ cancel']:
        context.user_data.clear()
        await update.message.reply_text(
            "Operation canceled. Please enter a new URL to start again.",
            reply_markup=ReplyKeyboardRemove()
        )
        return

    user_data = context.user_data
    if 'url' not in user_data:
        user_data['url'] = text
        keyboard = [["🎧 Audio", "🎬 Video"], ["❌ Cancel"]]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)
        await update.message.reply_text("Choose media type:", reply_markup=reply_markup)
    elif 'media_type' not in user_data:
        if text.lower() in ['🎧 audio', 'audio']:
            user_data['media_type'] = 'audio'
            await update.message.reply_text("⏳ Downloading audio... Please wait.")
            file_path = download_media(user_data['url'], media_type='audio')
            if file_path.startswith("Error"):
                await update.message.reply_text(file_path)
            else:
                if os.path.exists(file_path):
                    await update.message.reply_text("✅ Audio downloaded successfully!")
                    with open(file_path, 'rb') as file:
                        await update.message.reply_audio(file)
                    os.remove(file_path)  # حذف الملف بعد الإرسال
                else:
                    await update.message.reply_text("❌ File not found after download. Please try again.")
            context.user_data.clear()
        elif text.lower() in ['🎬 video', 'video']:
            user_data['media_type'] = 'video'
            # استخراج الجودات المتاحة
            try:
                with yt_dlp.YoutubeDL() as ydl:
                    info_dict = ydl.extract_info(user_data['url'], download=False)
                    formats = info_dict.get('formats', [])
                    available_qualities = set()
                    for fmt in formats:
                        height = fmt.get('height')
                        if height:
                            available_qualities.add(f"{height}p")

                    if not available_qualities:
                        await update.message.reply_text(
                            "❌ No available qualities found for this video. "
                            "Please try another link."
                        )
                        context.user_data.clear()
                        return

                    # عرض الجودات المتاحة
                    keyboard = [[f"🎥 {q}"] for q in sorted(available_qualities, key=lambda x: int(x.replace("p", "")))]
                    keyboard.append(["❌ Cancel"])
                    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)
                    await update.message.reply_text("Select video quality:", reply_markup=reply_markup)
            except Exception as e:
                await update.message.reply_text(
                    "❌ Failed to extract video qualities. "
                    "Please ensure the link is valid and try again later."
                )
                context.user_data.clear()
        else:
            await update.message.reply_text("Invalid choice. Please choose '🎧 Audio' or '🎬 Video'.")
    elif 'video_quality' not in user_data:
        # استخراج الجودة المختارة
        selected_quality = text.replace("🎥 ", "")
        if selected_quality.endswith("p"):
            user_data['video_quality'] = int(selected_quality.replace("p", ""))
            await update.message.reply_text(f"⏳ Downloading video ({selected_quality})... Please wait.")
            file_path = download_media(user_data['url'], media_type='video', video_quality=user_data['video_quality'])
            if file_path.startswith("Error"):
                await update.message.reply_text(file_path)
            else:
                if os.path.exists(file_path):
                    await update.message.reply_text(f"✅ Video ({selected_quality}) downloaded successfully!")
                    with open(file_path, 'rb') as file:
                        await update.message.reply_video(file)
                    os.remove(file_path)  # حذف الملف بعد الإرسال
                else:
                    await update.message.reply_text("❌ File not found after download. Please try again.")
            context.user_data.clear()
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
