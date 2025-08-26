import os
import asyncio
import logging
from flask import Flask, request
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters

# --- Logging Setup ---
# It's good practice to have logging to see what your bot is doing
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# --- Environment Variables ---
# Make sure these are set in your Render environment
BOT_TOKEN = os.environ.get("BOT_TOKEN")
RENDER_EXTERNAL_URL = os.environ.get("RENDER_EXTERNAL_URL")

if not BOT_TOKEN:
    logger.error("FATAL: BOT_TOKEN environment variable is not set.")
    exit()

if not RENDER_EXTERNAL_URL:
    logger.error("FATAL: RENDER_EXTERNAL_URL environment variable is not set.")
    exit()

WEBHOOK_URL = f"{RENDER_EXTERNAL_URL}/webhook"


# --- Bot Handlers ---
async def start(update: Update, context):
    """Handler for the /start command."""
    await update.message.reply_text("Hello! I am your bot, running on Render!")

async def echo(update: Update, context):
    """Handler to echo user messages."""
    await update.message.reply_text(f"You said: {update.message.text}")


# --- Main Application Setup ---
# We build the Application object first
tg_app = Application.builder().token(BOT_TOKEN).build()

# Register handlers
tg_app.add_handler(CommandHandler("start", start))
tg_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, echo))

# This function is run once when the server starts
async def setup():
    """Sets the webhook with Telegram."""
    await tg_app.initialize()
    await tg_app.bot.set_webhook(url=WEBHOOK_URL, allowed_updates=Update.ALL_TYPES)
    logger.info(f"Webhook set successfully to {WEBHOOK_URL}")

# --- Flask Web Server ---
app = Flask(__name__)

@app.route("/")
def index():
    """A simple health check page."""
    return "Bot is alive and listening!"

@app.route("/webhook", methods=["POST"])
async def webhook():
    """The main webhook endpoint that receives updates from Telegram."""
    try:
        json_data = request.get_json(force=True)
        update = Update.de_json(json_data, tg_app.bot)
        await tg_app.process_update(update)
        return "ok", 200
    except Exception as e:
        logger.error(f"Error in webhook: {e}")
        return "error", 500

# Run the setup function once before the first request
# This ensures the webhook is set when the application starts
with app.app_context():
    asyncio.run(setup())

# Note: For production, Render will use its own server (like Gunicorn).
# The if __name__ == "__main__" block is for local testing.
if __name__ == "__main__":
    app.run(port=int(os.environ.get("PORT", 8080)))
