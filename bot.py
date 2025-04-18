import os
import time
import yt_dlp
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# Set up download directory
DOWNLOAD_PATH = os.path.join(os.getcwd(), 'downloads')
if not os.path.exists(DOWNLOAD_PATH):
    os.makedirs(DOWNLOAD_PATH)

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
                'noplaylist': True,
            }
        elif media_type == 'video':
            # First extract info to check available formats
            with yt_dlp.YoutubeDL({'quiet': True}) as ydl:
                info = ydl.extract_info(url, download=False)
                formats = info.get('formats', [])
                available_heights = sorted(set(f.get('height', 0) for f in formats if f.get('height')))
                
                # Parse requested height
                requested_height = int(video_quality.replace('p', ''))
                
                # Find closest available height
                if available_heights:
                    if requested_height in available_heights:
                        target_height = requested_height
                    else:
                        # Get closest lower quality, or lowest if none lower exists
                        lower_qualities = [h for h in available_heights if h <= requested_height]
                        target_height = max(lower_qualities) if lower_qualities else min(available_heights)
                else:
                    target_height = requested_height

            # Set up download options with the determined quality
            ydl_opts = {
                'format': f'bestvideo[height<={target_height}]+bestaudio/best',
                'outtmpl': os.path.join(DOWNLOAD_PATH, f'video_{timestamp}.%(ext)s'),
                'noplaylist': True,
            }
        else:
            return "Error: Invalid media type."

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info_dict = ydl.extract_info(url, download=True)
            file_name = ydl.prepare_filename(info_dict)
            
            if media_type == 'audio':
                converted_file = os.path.splitext(file_name)[0] + '.mp3'
                if os.path.exists(converted_file):
                    return converted_file
                return "Error: Audio conversion failed."
            return file_name

    except Exception as e:
        if "Unsupported URL" in str(e) or "Cannot parse data" in str(e):
            return "Error: Unable to download the media. Please ensure the link is valid and try again later."
        return f"Error during download: {e}"

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text(
        "Welcome to the Universal Media Downloader!\n\n"
        "Please enter the URL of the media you want to download:",
        reply_markup=ReplyKeyboardRemove()
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()

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
                    os.remove(file_path)
                else:
                    await update.message.reply_text("❌ File not found after download. Please try again.")
            context.user_data.clear()
        elif text.lower() in ['🎬 video', 'video']:
            user_data['media_type'] = 'video'
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
    elif 'video_quality' not in user_data:
        supported_qualities = ["144p", "240p", "360p", "480p", "720p", "1080p"]
        if text in [f"🎥 {q}" for q in supported_qualities]:
            selected_quality = text.replace("🎥 ", "")
            user_data['video_quality'] = selected_quality
            await update.message.reply_text(f"⏳ Downloading video in {selected_quality} (or closest available quality)... Please wait.")
            
            file_path = download_media(user_data['url'], media_type='video', video_quality=selected_quality)
            if file_path.startswith("Error"):
                await update.message.reply_text(file_path)
            else:
                if os.path.exists(file_path):
                    await update.message.reply_text("✅ Video downloaded successfully!")
                    with open(file_path, 'rb') as file:
                        await update.message.reply_video(file)
                    os.remove(file_path)
                else:
                    await update.message.reply_text("❌ File not found after download. Please try again.")
            context.user_data.clear()
        else:
            await update.message.reply_text("Invalid video quality choice. Please select a valid option.")

def main():
    API_TOKEN = os.getenv('API_TOKEN')
    if not API_TOKEN:
        raise ValueError("API_TOKEN is not set in environment variables.")

    application = Application.builder().token(API_TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.run_polling()

if __name__ == '__main__':
    main()
