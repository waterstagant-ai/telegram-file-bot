# bot.py
import os
from dotenv import load_dotenv
from pymongo import MongoClient
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Application, CommandHandler, ContextTypes

# Load environment variables from .env
load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
MONGO_URL = os.getenv("MONGO_URL")
CHANNEL_ID = os.getenv("CHANNEL_ID")  # Example: -1003510118476

# Connect to MongoDB
client = MongoClient(MONGO_URL)
db = client["telegram_bot_db"]  # Database name
collection = db["users"]        # Collection name

# Create Telegram bot application
app = Application.builder().token(BOT_TOKEN).build()

# /start command
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user

    # Save user info in MongoDB
    collection.update_one(
        {"user_id": user.id},
        {"$set": {"username": user.username, "first_name": user.first_name}},
        upsert=True
    )

    # Proper channel link for numeric ID
    channel_link = f"https://t.me/c/{str(CHANNEL_ID)[4:]}"  # remove -100 prefix

    # Inline keyboard example
    keyboard = [
        [InlineKeyboardButton("Visit Channel", url=channel_link)],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        f"Hello {user.first_name}! Your data is saved in MongoDB.",
        reply_markup=reply_markup
    )

# Add /start handler
app.add_handler(CommandHandler("start", start))

# Run bot
if __name__ == "__main__":
    print("Bot is running...")
    app.run_polling()
