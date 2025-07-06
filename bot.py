import os
import time
import json
import shutil
import yt_dlp
import asyncio
import functools
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

def _blocking_download(url, media_type, video_quality, playlist, job_path):
    """The actual blocking download logic."""
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

                single_file_path = os.path.join(job_path, downloaded_files[0])
                
                if media_type == 'audio':
                    base, ext = os.path.splitext(single_file_path)
                    expected_mp3 = base + '.mp3'
                    if os.path.exists(expected_mp3):
                        if single_file_path != expected_mp3 and os.path.exists(single_file_path):
                           os.remove(single_file_path)
                        return f"Successfully downloaded audio: {title}", expected_mp3
                    elif ext == '.mp3':
                        return f"Successfully downloaded audio: {title}", single_file_path
                    else:
                        raise Exception("Audio conversion failed or file not found.")

                return f"Successfully downloaded: {title}", single_file_path

    except Exception as e:
        error_message = str(e)
        if "is not a valid URL" in error_message or "Unsupported URL" in error_message:
            return "❌ تحقق من الرابط. يبدو أن الرابط الذي أدخلته غير صالح.", None
        return f"❌ Error during download: {error_message}", None

async def download_media(url, media_type='video', video_quality=None, playlist=False):
    """
    Asynchronously download media from a URL by running the blocking download logic in an executor.
    """
    job_id = f"{time.strftime('%Y%m%d-%H%M%S')}_{os.urandom(4).hex()}"
    job_path = os.path.join(DOWNLOAD_PATH, job_id)
    os.makedirs(job_path, exist_ok=True)

    loop = asyncio.get_running_loop()
    
    # Run the blocking download function in a separate thread
    func = functools.partial(_blocking_download, url, media_type, video_quality, playlist, job_path)
    message, result_path = await loop.run_in_executor(None, func)

    # If the download failed, the blocking function returns result_path=None.
    # In that case, we clean up the job directory.
    if not result_path and os.path.exists(job_path):
        await loop.run_in_executor(None, shutil.rmtree, job_path)

    return message, result_path


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

    if state == 'media_type_choice':
        if 'audio' in text.lower():
            user_data['media_type'] = 'audio'
            status_message = await update.message.reply_text("⏳ Your request is being processed...", reply_markup=ReplyKeyboardRemove())
            asyncio.create_task(run_download_and_upload(update, context, status_message))

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

    if state == 'quality_choice':
        quality = text.replace("🎥 ", "").strip()
        user_data['video_quality'] = quality
        status_message = await update.message.reply_text("⏳ Your request is being processed...", reply_markup=ReplyKeyboardRemove())
        asyncio.create_task(run_download_and_upload(update, context, status_message))
        return

async def run_download_and_upload(update, context, status_message):
    """A separate async function to run the download and upload process."""
    user_data = context.user_data
    try:
        await status_message.edit_text("⏳ Downloading... Please wait.")
        message, result_path = await download_media(
            user_data.get('url'),
            media_type=user_data.get('media_type'),
            video_quality=user_data.get('video_quality'),
            playlist=user_data.get('download_playlist', False)
        )
        await handle_download_result(update, status_message, message, result_path, user_data)
    except Exception as e:
        await status_message.edit_text(f"An unexpected error occurred: {e}")
    finally:
        context.user_data.clear()

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