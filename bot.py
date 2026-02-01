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

# ===== PYTHON-TELEGRAM-BOT VERSION CHECK =====
try:
    import telegram
    if not telegram.__version__.startswith("20"):
        logger.error(f"python-telegram-bot version must be 20.x, found {telegram.__version__}")
        sys.exit(1)
except Exception as e:
    logger.error(f"Telegram library import failed: {e}")
    sys.exit(1)

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
async def time_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    expires_at = has_access(user_id)
    if not expires_at:
        await update.message.reply_text("🔒 You don’t have access right now.")
        return
    await update.message.reply_text(f"⏳ Access time left: {remaining_time(expires_at)}")

async def stats_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    total_users = users_col.count_documents({})
    active_users = users_col.count_documents({"expires_at": {"$gt": int(time.time())}})
    total_files = files_col.count_documents({})
    total_referrals = sum(u.get("referrals", 0) for u in users_col.find({}))
    await update.message.reply_text(
        "📊 Bot Stats\n\n"
        f"👥 Total users: {total_users}\n"
        f"🔓 Active users: {active_users}\n"
        f"📂 Files stored: {total_files}\n"
        f"👥 Total referrals: {total_referrals}"
    )

# ===== START / FILE ACCESS =====
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not check_cooldown(user_id):
        return

    args = context.args

    # Referral logic
    if args and args[0].startswith("ref_"):
        referrer = int(args[0].split("_")[1])
        if referrer != user_id:
            users_col.update_one(
                {"user_id": user_id},
                {"$setOnInsert": {"referred_by": referrer, "referrals": 0}},
                upsert=True
            )
            users_col.update_one(
                {"user_id": referrer},
                {"$inc": {"referrals": 1}},
                upsert=True
            )

    # Shortener unlock
    if args and args[0] == "unlock":
        users_col.update_one(
            {"user_id": user_id},
            {"$set": {"expires_at": int(time.time()) + UNLOCK_SECONDS}},
            upsert=True
        )
        await update.message.reply_text("✅ Access unlocked for 3 hours!")
        return

    # File access
    if args:
        file_code = args[0]
        expires_at = has_access(user_id)

        if not expires_at:
            user = users_col.find_one({"user_id": user_id}) or {"referrals": 0}
            referrals = user.get("referrals", 0)
            if referrals >= REFERRAL_REQUIRED:
                users_col.update_one(
                    {"user_id": user_id},
                    {"$set": {"expires_at": int(time.time()) + UNLOCK_SECONDS}},
                    upsert=True
                )
                await update.message.reply_text("🎉 Unlocked via referrals!")
                return

            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("🔓 Unlock via Ad", url=SHORTENER_LINK)],
                [InlineKeyboardButton(f"👥 Refer Friends ({referrals}/{REFERRAL_REQUIRED})",
                                      url=f"https://t.me/{context.bot.username}?start=ref_{user_id}")]
            ])
            await update.message.reply_text(
                "🔒 Access locked. Unlock to view files.",
                reply_markup=keyboard
            )
            return

        # Send protected view-only content
        file_data = files_col.find_one({"code": file_code})
        if not file_data:
            await update.message.reply_text("❌ File not found")
            return

        ftype = file_data.get("type", "document")
        if ftype == "video":
            await context.bot.send_video(
                chat_id=update.effective_chat.id,
                video=file_data["file_id"],
                caption=f"✅ Access granted\n⏳ Time left: {remaining_time(expires_at)}",
                protect_content=True,
                supports_streaming=True
            )
        elif ftype == "photo":
            await context.bot.send_photo(
                chat_id=update.effective_chat.id,
                photo=file_data["file_id"],
                caption=f"✅ Access granted\n⏳ Time left: {remaining_time(expires_at)}",
                protect_content=True
            )
        else:
            await context.bot.send_document(
                chat_id=update.effective_chat.id,
                document=file_data["file_id"],
                caption=f"✅ Access granted\n⏳ Time left: {remaining_time(expires_at)}",
                protect_content=True
            )
        return

    await update.message.reply_text(
        "📂 Secure File Bot\nCommands:\n/time – Check access time"
    )

# ===== ADMIN UPLOAD =====
async def handle_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return

    file = update.message.document or update.message.video or (update.message.photo[-1] if update.message.photo else None)
    if not file:
        return

    # Determine type
    if update.message.video:
        ftype = "video"
        file_id = update.message.video.file_id
    elif update.message.photo:
        ftype = "photo"
        file_id = update.message.photo[-1].file_id
    else:
        ftype = "document"
        file_id = update.message.document.file_id

    # Store permanently in private channel
    await context.bot.send_document(
        chat_id=CHANNEL_ID,
        document=file_id,
        caption="📦 Stored file",
        protect_content=True
    )

    code = uuid.uuid4().hex[:8]
    files_col.insert_one({
        "code": code,
        "file_id": file_id,
        "type": ftype
    })

    link = f"https://t.me/{context.bot.username}?start={code}"
    await update.message.reply_text(
        "✅ File uploaded\nShare link:",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("📥 View File", url=link)]])
    )

# ===== MAIN =====
def main():
    logger.info("Bot starting...")
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("time", time_cmd))
    app.add_handler(CommandHandler("stats", stats_cmd))
    app.add_handler(MessageHandler(filters.Document.ALL | filters.VIDEO | filters.PHOTO, handle_file))
    app.run_polling()

if __name__ == "__main__":
    main()
