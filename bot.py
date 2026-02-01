import os
from pymongo import MongoClient
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

# ---------- CONFIGURATION ----------
# Set these as environment variables in Railway or your local machine
BOT_TOKEN = os.environ.get("BOT_TOKEN")        # Your new bot token
MONGO_URL = os.environ.get("MONGO_URL")        # Your new MongoDB URL
CHANNEL_ID = os.environ.get("CHANNEL_ID")      # Your new Telegram channel ID (for posting data)
# -----------------------------------

# Connect to MongoDB
client = MongoClient(MONGO_URL)
db = client['my_bot_database']       # Database name
collection = db['users']             # Collection name

# ---------- BOT HANDLERS ----------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    username = update.effective_user.username

    # Add user to MongoDB if not exists
    if not collection.find_one({"user_id": user_id}):
        collection.insert_one({"user_id": user_id, "username": username})

    # Send message with inline button
    keyboard = [[InlineKeyboardButton("Visit Channel", url="https://t.me/YourChannelUsername")]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        f"Hello {username}! You are added to the database.",
        reply_markup=reply_markup
    )

async def users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show all users in the database"""
    users = list(collection.find({}, {"_id": 0, "username": 1}))
    if users:
        message = "Registered users:\n" + "\n".join([u.get("username", "Unknown") for u in users])
    else:
        message = "No users found."
    await update.message.reply_text(message)

# ---------- MAIN ----------
if __name__ == "__main__":
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    # Commands
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("users", users))

    print("Bot is running...")
    app.run_polling()
