import os
import uuid
import time
import logging
import sys
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    MessageHandler,
    CommandHandler,
    ContextTypes,
    filters,
)
from pymongo import MongoClient

# ===== LOGGING =====
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ===== ENVIRONMENT VARIABLES SAFETY =====
try:
    BOT_TOKEN = os.environ.get("BOT_TOKEN")
    if not BOT_TOKEN:
        raise ValueError("BOT_TOKEN not set")
    ADMIN_ID = int(os.environ.get("ADMIN_ID"))
    CHANNEL_ID = int(os.environ.get("CHANNEL_ID"))
    MONGO_URI = os.environ.get("MONGO_URI")
    if not MONGO_URI:
        raise ValueError("MONGO_URI not set")
except Exception as e:
    logger.error(f"Environment variable error: {e}")
    sys.exit(1)

SHORTENER_LINK = "https://your-shortener-link-here"
UNLOCK_SECONDS = 3 * 60 * 60  # 3 hours
REFERRAL_REQUIRED = 3
COOLDOWN_SECONDS = 5

# ===== DATABASE =====
try:
    mongo = MongoClient(MONGO_URI)
    db = mongo["telegram_files"]
    files_col = db["files"]
    users_col = db["users"]
except Exception as e:
    logger.error(f"MongoDB connection error: {e}")
    sys.exit(1)

# ===== HELPER FUNCTIONS =====
def remaining_time(expires_at):
    remaining = expires_at - int(time.time())
    if remaining <= 0:
        return None
    h = remaining // 3600
    m = (remaining % 3600) // 60
    return f"{h}h {m}m"

def has_access(user_id):
    user = users_col.find_one({"user_id": user_id})
    if not user or "expires_at" not in user:
        return None
    if user["expires_at"] <= int(time.time()):
        return None
    return user["expires_at"]

def check_cooldown(user_id):
    now = int(time.time())
    user = users_col.find_one({"user_id": user_id})
    if user and user.get("last_action", 0) + COOLDOWN_SECONDS > now:
        return False
    users_col.update_one(
        {"user_id": user_id},
        {"$set": {"last_action": now}},
        upsert=True
    )
    return True

# ===== COMMANDS =====
async def time
