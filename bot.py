import os
import time
import json
import shutil
import yt_dlp
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# Set up download directory
DOWNLOAD_PATH = os.path.join(os.getcwd(), 'downloads')
if not os.path.exists(DOWNLOAD_PATH):
    os.makedirs(DOWNLOAD_PATH)

# User data storage
USERS_FILE = 'bot_users.json'

def load_users():
    """Load users from the JSON file"""
    if os.path.exists(USERS_FILE):
        try:
            with open(USERS_FILE, 'r') as f:
                return json.load(f)
        except json.JSONDecodeError:
            return {'users': [], 'total_count': 0}
    return {'users': [], 'total_count': 0}

def save_users(users_data):
    """Save users to the JSON file"""
    with open(USERS_FILE, 'w') as f:
        json.dump(users_data, f)

def track_user(user_id, username, first_name):
    """Track a user who interacted with the bot and return total count."""
    users_data = load_users()
    
    if str(user_id) not in users_data.get('users', []):
        users_data.setdefault('users', []).append(str(user_id))
        users_data['total_count'] = len(users_data['users'])
    
    user_info = {
        'username': username or '',
        'first_name': first_name or '',
        'last_activity': time.strftime("%Y-%m-%d %H:%M:%S")
    }
    users_data[str(user_id)] = user_info
    
    save_users(users_data)
    return users_data.get('total_count', 0)

def get_user_count():
    """Get the total number of unique users"""
    users_data = load_users()
    return users_data.get('total_count', 0)

def is_playlist(url):
    """Check if a URL is a playlist using yt-dlp."""
    try:
        with yt_dlp.YoutubeDL({'extract_flat': True, 'quiet': True}) as ydl:
            info = ydl.extract_info(url, download=False, process=False)
            return 'entries' in info and info.get('_type') == 'playlist'
    except Exception:
        return False

def download_media(url, media_type='video', video_quality=None, playlist=False):
    """
    Download media from a URL.
    For playlists, downloads all items into a new directory and returns the directory path.
    For single files, downloads the file into a new directory and returns the file path.
    """
    job_id = f"{time.strftime('%Y%m%d-%H%M%S')}_{os.urandom(4).hex()}"
    job_path = os.path.join(DOWNLOAD_PATH, job_id)
    os.makedirs(job_path)

    try:
        ydl_opts = {
            'outtmpl': os.path.join(job_path, '%(title)s [%(id)s].%(ext)s'),
            'quiet': True,
            'http_headers': {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            },
            'noplaylist': not playlist,
        }

        if media_type == 'video':
            quality_filter = "best"
            if video_quality:
                height = video_quality.replace('p', '')
                quality_filter = f'bestvideo[height<={height}]+bestaudio/best[height<={height}]'
            ydl_opts['format'] = quality_filter
        
        elif media_type == 'audio':
            ydl_opts.update({
                'format': 'bestaudio/best',
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                }]
            })

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info_dict = ydl.extract_info(url, download=True)
            title = info_dict.get('title', 'Unknown')

            if playlist:
                return f"Successfully downloaded playlist: {title}", job_path
            else:
                downloaded_files = os.listdir(job_path)
                if not downloaded_files:
                    raise Exception("File not found after download.")

                # For single files, the path is the file itself inside the job_path
                single_file_path = os.path.join(job_path, downloaded_files[0])
                
                # Handle audio conversion naming
                if media_type == 'audio':
                    base, ext = os.path.splitext(single_file_path)
                    expected_mp3 = base + '.mp3'
                    if os.path.exists(expected_mp3):
                        # FFMPEG created a new file
                        if single_file_path != expected_mp3 and os.path.exists(single_file_path):
                           os.remove(single_file_path) # remove original
                        return f"Successfully downloaded audio: {title}", expected_mp3
                    elif ext == '.mp3':
                        # Original was already mp3
                        return f"Successfully downloaded audio: {title}", single_file_path
                    else:
                        # Conversion might have failed or file has unexpected extension
                        # We return the job path to allow cleanup
                        raise Exception("Audio conversion failed or file not found.")

                return f"Successfully downloaded: {title}", single_file_path

    except Exception as e:
        if os.path.exists(job_path):
            shutil.rmtree(job_path) # Clean up on error
        error_message = str(e)
        if "is not a valid URL" in error_message or "Unsupported URL" in error_message:
            return "❌ تحقق من الرابط. يبدو أن الرابط الذي أدخلته غير صالح.", None
        return f"❌ Error during download: {error_message}", None


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start command handler"""
    user = update.effective_user
    user_count = track_user(user.id, user.username, user.first_name)
    
    context.user_data.clear()
    await update.message.reply_text(
        f"Welcome to the Universal Media Downloader, {user.first_name}! 👋\n\n"
        f"I can download videos, audio, and entire playlists.\n"
        f"Currently serving {user_count} users.\n\n"
        "Please enter the URL of the media you want to download:",
        reply_markup=ReplyKeyboardRemove()
    )

async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin command to show bot statistics"""
    user_count = get_user_count()
    await update.message.reply_text(
        f"📊 Bot Statistics\n\n"
        f"Total Users: {user_count}"
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle the conversation for downloading media."""
    user = update.effective_user
    track_user(user.id, user.username, user.first_name)
    
    text = update.message.text.strip()
    user_data = context.user_data

    if text.lower() in ['cancel', 'close', '❌ cancel']:
        context.user_data.clear()
        await update.message.reply_text(
            "Operation canceled. Send a new URL to start again.",
            reply_markup=ReplyKeyboardRemove()
        )
        return

    # State 1: Start, waiting for URL
    if 'url' not in user_data:
        url = text
        if is_playlist(url):
            user_data['url'] = url
            user_data['is_playlist'] = True
            keyboard = [["▶️ Playlist", "🎬 Single Video"], ["❌ Cancel"]]
            reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)
            await update.message.reply_text("This is a playlist. Download the entire playlist or just the single video?", reply_markup=reply_markup)
            user_data['state'] = 'playlist_choice'
        else:
            user_data['url'] = url
            user_data['is_playlist'] = False
            keyboard = [["🎧 Audio", "🎬 Video"], ["❌ Cancel"]]
            reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)
            await update.message.reply_text("Choose media type:", reply_markup=reply_markup)
            user_data['state'] = 'media_type_choice'
        return

    state = user_data.get('state')

    # State 2: Playlist choice
    if state == 'playlist_choice':
        if "playlist" in text.lower():
            user_data['download_playlist'] = True
        elif "single" in text.lower():
            user_data['download_playlist'] = False
        else:
            await update.message.reply_text("Invalid choice. Please try again.")
            return
        
        keyboard = [["🎧 Audio", "🎬 Video"], ["❌ Cancel"]]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)
        await update.message.reply_text("Choose media type:", reply_markup=reply_markup)
        user_data['state'] = 'media_type_choice'
        return

    # State 3: Media type choice
    if state == 'media_type_choice':
        if 'audio' in text.lower():
            user_data['media_type'] = 'audio'
            status_message = await update.message.reply_text("⏳ Downloading... Please wait.", reply_markup=ReplyKeyboardRemove())
            
            message, result_path = download_media(
                user_data['url'],
                media_type='audio',
                playlist=user_data.get('download_playlist', False)
            )

            await handle_download_result(update, status_message, message, result_path, user_data)
            context.user_data.clear()

        elif 'video' in text.lower():
            user_data['media_type'] = 'video'
            keyboard = [
                ["🎥 144p", "🎥 240p", "🎥 360p"],
                ["🎥 480p", "🎥 720p", "🎥 1080p"],
                ["❌ Cancel"]
            ]
            reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)
            await update.message.reply_text("Select max video quality:", reply_markup=reply_markup)
            user_data['state'] = 'quality_choice'
        else:
            await update.message.reply_text("Invalid choice. Please choose '🎧 Audio' or '🎬 Video'.")
        return

    # State 4: Video quality choice
    if state == 'quality_choice':
        quality = text.replace("🎥 ", "").strip()
        user_data['video_quality'] = quality
        status_message = await update.message.reply_text("⏳ Downloading... Please wait.", reply_markup=ReplyKeyboardRemove())

        message, result_path = download_media(
            user_data['url'],
            media_type='video',
            video_quality=quality,
            playlist=user_data.get('download_playlist', False)
        )
        
        await handle_download_result(update, status_message, message, result_path, user_data)
        context.user_data.clear()
        return

async def handle_download_result(update, status_message, message, result_path, user_data):
    """Helper to process and send downloaded files."""
    if "Error" in message or not result_path:
        await status_message.edit_text(message)
        return

    await status_message.edit_text(f"✅ {message}\n\n📤 Uploading to Telegram...")

    if os.path.isdir(result_path): # Playlist result
        files_to_send = sorted(os.listdir(result_path))
        await update.message.reply_text(f"Found {len(files_to_send)} files in the playlist. Sending them now...")
        for filename in files_to_send:
            file_path = os.path.join(result_path, filename)
            try:
                with open(file_path, 'rb') as file:
                    if user_data['media_type'] == 'audio':
                        await update.message.reply_audio(file, read_timeout=120, write_timeout=120)
                    else:
                        await update.message.reply_video(file, read_timeout=120, write_timeout=120)
            except Exception as e:
                await update.message.reply_text(f"Could not send file {filename}: {e}")
        shutil.rmtree(result_path) # Clean up directory
    
    elif os.path.isfile(result_path): # Single file result
        try:
            with open(result_path, 'rb') as file:
                if user_data['media_type'] == 'audio':
                    await update.message.reply_audio(file, read_timeout=120, write_timeout=120)
                else:
                    await update.message.reply_video(file, read_timeout=120, write_timeout=120)
            # The file is inside a job directory
            shutil.rmtree(os.path.dirname(result_path))
        except Exception as e:
            await status_message.edit_text(f"❌ Failed to upload file: {e}")
            if os.path.exists(result_path):
                shutil.rmtree(os.path.dirname(result_path))
    else:
        await status_message.edit_text("❌ File not found after download. Please try again.")

def main():
    """Run the bot"""
    API_TOKEN = os.getenv('API_TOKEN')
    if not API_TOKEN:
        raise ValueError("API_TOKEN is not set in environment variables.")

    application = Application.builder().token(API_TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("stats", stats))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    print("Bot started with new features!")
    application.run_polling()

if __name__ == '__main__':
    main()