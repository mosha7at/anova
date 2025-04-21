import os
import time
import json
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from TikTokApi import TikTokApi

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
    """Track a user who interacted with the bot"""
    users_data = load_users()
    
    if str(user_id) not in users_data['users']:
        users_data['users'].append(str(user_id))
        users_data['total_count'] = len(users_data['users'])
    
    user_info = {
        'username': username or '',
        'first_name': first_name or '',
        'last_activity': time.strftime("%Y-%m-%d %H:%M:%S")
    }
    users_data[str(user_id)] = user_info
    
    save_users(users_data)
    return users_data['total_count']

def get_user_count():
    """Get the total number of unique users"""
    users_data = load_users()
    return users_data['total_count']

def download_tiktok_video(video_id):
    """Download TikTok video using TikTokApi"""
    api = TikTokApi()
    video_data = api.video(id=video_id).bytes()
    timestamp = time.strftime("%Y%m%d-%H%M%S")
    file_name = os.path.join(DOWNLOAD_PATH, f'tiktok_video_{timestamp}.mp4')
    with open(file_name, "wb") as f:
        f.write(video_data)
    return file_name

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start command handler"""
    user = update.effective_user
    track_user(user.id, user.username, user.first_name)
    
    context.user_data.clear()
    await update.message.reply_text(
        f"Welcome to the Universal Media Downloader, {user.first_name}! 👋\n\n"
        "Please enter the TikTok video URL you want to download:",
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
    """Handle incoming messages"""
    user = update.effective_user
    track_user(user.id, user.username, user.first_name)
    
    text = update.message.text.strip()

    if text.lower() in ['cancel', 'close', '❌ cancel']:
        context.user_data.clear()
        await update.message.reply_text(
            "Operation canceled. Please enter a new URL to start again.",
            reply_markup=ReplyKeyboardRemove()
        )
        return

    # Extract video ID from the URL
    if "tiktok.com" not in text:
        await update.message.reply_text("❌ Invalid TikTok URL. Please provide a valid TikTok video link.")
        return

    try:
        video_id = text.split("/video/")[1].split("?")[0]
    except IndexError:
        await update.message.reply_text("❌ Unable to extract video ID from the provided URL.")
        return

    status_message = await update.message.reply_text("⏳ Downloading video... Please wait.")

    try:
        file_path = download_tiktok_video(video_id)
        await status_message.edit_text("✅ Video downloaded successfully!")
        if file_path and os.path.exists(file_path):
            with open(file_path, 'rb') as file:
                await update.message.reply_video(file)
            os.remove(file_path)
        else:
            await status_message.edit_text("❌ File not found after download. Please try again.")
    except Exception as e:
        error_message = str(e)
        await status_message.edit_text(f"❌ Error during download: {error_message}")

def main():
    """Run the bot"""
    API_TOKEN = os.getenv('API_TOKEN')
    if not API_TOKEN:
        raise ValueError("API_TOKEN is not set in environment variables.")

    application = Application.builder().token(API_TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("stats", stats))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    print("Bot started!")
    application.run_polling()

if __name__ == '__main__':
    main()
