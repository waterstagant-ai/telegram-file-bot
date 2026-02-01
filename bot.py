# bot.py
import os
from dotenv import load_dotenv
from pymongo import MongoClient
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

# Load environment variables
load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
MONGO_URL = os.getenv("MONGO_URL")
CHANNEL_ID = os.getenv("CHANNEL_ID")  # Example: -1003510118476

# Connect to MongoDB
client = MongoClient(MONGO_URL)
db = client["telegram_bot_db"]  # Database name
users_collection = db["users"]  # Collection name

# Create Telegram bot application
app = Application.builder().token(BOT_TOKEN).build()

# Helper function to save user in MongoDB
def save_user(user):
    users_collection.update_one(
        {"user_id": user.id},
        {"$set": {"username": user.username, "first_name": user.first_name}},
        upsert=True
    )

# /start command
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    save_user(user)

    # Proper channel link
    channel_link = f"https://t.me/c/{str(CHANNEL_ID)[4:]}"  # remove -100 prefix

    keyboard = [
        [InlineKeyboardButton("Visit Channel", url=channel_link)],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        f"Hello {user.first_name}! Your data has been saved in MongoDB.\n\nType /help to see available commands.",
        reply_markup=reply_markup
    )

# /help command
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    save_user(user)

    help_text = (
        "Available Commands:\n"
        "/start - Start the bot and save your data\n"
        "/help - Show this help message"
    )
    await update.message.reply_text(help_text)

# Save any message sender to MongoDB
async def save_all_users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    save_user(user)

# Handlers
app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("help", help_command))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, save_all_users))

# Run bot
if __name__ == "__main__":
    print("Bot is running...")
    app.run_polling()
