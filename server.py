import os
import asyncio
import logging
import gzip
import json
import glob
from flask import Flask, request
from telegram import Update
from telegram.ext import Application, CommandHandler

# --- Logging Setup ---
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# --- Environment Variables ---
BOT_TOKEN = os.environ.get("BOT_TOKEN")
RENDER_EXTERNAL_URL = os.environ.get("RENDER_EXTERNAL_URL")

if not BOT_TOKEN or not RENDER_EXTERNAL_URL:
    logger.error("FATAL: BOT_TOKEN or RENDER_EXTERNAL_URL environment variable is not set.")
    exit()

WEBHOOK_URL = f"{RENDER_EXTERNAL_URL}/webhook"

# --- Data Loading and Indexing ---
user_data_by_mobile = {}
user_data_by_email = {}

def load_and_index_data():
    """Loads data from all .json.gz files in the 'data/' directory."""
    data_files = glob.glob("data/*.json.gz")
    if not data_files:
        logger.warning("No data files found in the 'data/' directory.")
        return

    all_records = []
    for file_path in data_files:
        try:
            with gzip.open(file_path, 'rt', encoding='utf-8') as f:
                records = json.load(f)
                if isinstance(records, list):
                    all_records.extend(records)
        except Exception as e:
            logger.error(f"Failed to load or parse {file_path}: {e}")

    for record in all_records:
        if 'Mobile No' in record:
            user_data_by_mobile[str(record['Mobile No'])] = record
        if 'Email Contact' in record and record['Email Contact']:
            user_data_by_email[record['Email Contact'].lower()] = record

    logger.info(f"Successfully loaded and indexed {len(all_records)} records.")

# --- Telegram Application Setup ---
tg_app = Application.builder().token(BOT_TOKEN).build()

async def setup_bot():
    """Initializes the bot and sets the webhook."""
    await tg_app.initialize()
    await tg_app.bot.set_webhook(url=WEBHOOK_URL, allowed_updates=Update.ALL_TYPES)
    logger.info(f"Webhook set successfully to {WEBHOOK_URL}")

# --- Bot Handlers ---
async def start(update: Update, context):
    await update.message.reply_text("Hello! I am ready to search. Use /search <mobile_or_email>.")

async def search(update: Update, context):
    if not context.args:
        await update.message.reply_text("Usage: `/search 9876543210`")
        return

    query = context.args[0].lower()
    result = user_data_by_mobile.get(query) or user_data_by_email.get(query)

    if result:
        message = "✅ **User Data Found**\n\n"
        for key, value in result.items():
            key_safe = str(key).replace('-', '\\-').replace('.', '\\.')
            value_safe = str(value).replace('-', '\\-').replace('.', '\\.')
            message += f"*{key_safe}:* `{value_safe}`\n"
        await update.message.reply_text(message, parse_mode='MarkdownV2')
    else:
        await update.message.reply_text("❌ No record found for that query.")

# Register handlers with the application
tg_app.add_handler(CommandHandler("start", start))
tg_app.add_handler(CommandHandler("search", search))

# --- Flask Web Server ---
app = Flask(__name__)

@app.before_serving
async def startup():
    """This function runs once before the server starts."""
    load_and_index_data()
    await setup_bot()

@app.route("/")
def index():
    return "Bot is alive and the search engine is loaded!"

@app.route("/webhook", methods=["POST"])
async def webhook():
    """The main webhook endpoint that receives updates from Telegram."""
    try:
        update = Update.de_json(request.get_json(force=True), tg_app.bot)
        await tg_app.process_update(update)
        return "ok", 200
    except Exception as e:
        logger.error(f"Error in webhook: {e}")
        return "error", 500
