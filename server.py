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

# --- Data Loading and Indexing from Local 'data' Folder ---
user_data_by_mobile = {}
user_data_by_email = {}

def load_and_index_data():
    """
    Loads data from all .json.gz files in the 'data/' directory
    and indexes it by mobile number and email.
    """
    data_files = glob.glob("data/*.json.gz")
    if not data_files:
        logger.warning("No data files found in the 'data/' directory. Did you create the folder and add your files?")
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

    # Index the loaded records
    for record in all_records:
        if 'Mobile No' in record:
            user_data_by_mobile[str(record['Mobile No'])] = record
        if 'Email Contact' in record and record['Email Contact']:
            user_data_by_email[record['Email Contact'].lower()] = record

    logger.info(f"Successfully loaded and indexed {len(all_records)} records from {len(data_files)} files.")

# --- Bot Handlers ---
async def start(update: Update, context):
    """Handler for the /start command."""
    await update.message.reply_text("Hello! I am ready to search. Use /search <mobile_or_email>.")

async def search(update: Update, context):
    """Handler for the /search command."""
    if not context.args:
        await update.message.reply_text("Usage: `/search 9876543210`")
        return

    query = context.args[0].lower()
    result = user_data_by_mobile.get(query) or user_data_by_email.get(query)

    if result:
        message = "✅ **User Data Found**\n\n"
        for key, value in result.items():
            # Escape special characters for MarkdownV2
            key_safe = str(key).replace('-', '\\-').replace('.', '\\.')
            value_safe = str(value).replace('-', '\\-').replace('.', '\\.')
            message += f"*{key_safe}:* `{value_safe}`\n"
        await update.message.reply_text(message, parse_mode='MarkdownV2')
    else:
        await update.message.reply_text("❌ No record found for that query.")

# --- Main Application Setup ---
tg_app = Application.builder().token(BOT_TOKEN).build()
tg_app.add_handler(CommandHandler("start", start))
tg_app.add_handler(CommandHandler("search", search))

async def setup():
    """Sets the webhook with Telegram."""
    await tg_app.initialize()
    await tg_app.bot.set_webhook(url=WEBHOOK_URL, allowed_updates=Update.ALL_TYPES)
    logger.info(f"Webhook set successfully to {WEBHOOK_URL}")

# --- Flask Web Server ---
app = Flask(__name__)

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

# --- Corrected Application Startup ---
# This new block correctly handles the asyncio event loop
# when running with a production server like Gunicorn.
if __name__ != "__main__":
    # When run by Gunicorn, load data and set up the webhook
    load_and_index_data()
    # Get the current event loop or create a new one
    loop = asyncio.get_event_loop()
    # Schedule the setup task to run in the existing loop
    loop.run_until_complete(setup())


if __name__ == "__main__":
    # This block is for local development testing only
    load_and_index_data()
    asyncio.run(setup())
    app.run(port=int(os.environ.get("PORT", 8080)))
