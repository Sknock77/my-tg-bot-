import os
import logging
import gzip
import json
import glob
import asyncio
from fastapi import FastAPI, Request, Response
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

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
    logger.error("FATAL: A required environment variable is not set.")
    exit()

WEBHOOK_URL = f"{RENDER_EXTERNAL_URL}/webhook"

# --- Data Loading ---
user_data_by_mobile = {}
user_data_by_email = {}

def load_and_index_data():
    logger.info("Starting data load...")
    data_files = glob.glob("data/*.json.gz")
    if not data_files:
        logger.warning("No data files found in 'data/' directory.")
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
    logger.info(f"Successfully indexed {len(all_records)} records.")

# --- Telegram Bot Setup ---
tg_app = Application.builder().token(BOT_TOKEN).build()

# --- Bot Handlers ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Bot is running. Use /search <mobile_or_email>.")

async def search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usage: `/search 9876543210`", parse_mode='MarkdownV2')
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

# Register handlers
tg_app.add_handler(CommandHandler("start", start))
tg_app.add_handler(CommandHandler("search", search))

# --- FastAPI Web Server ---
# The lifespan function handles startup and shutdown events
async def lifespan(app: FastAPI):
    # On startup
    load_and_index_data()
    await tg_app.initialize()
    await tg_app.bot.set_webhook(url=WEBHOOK_URL, allowed_updates=Update.ALL_TYPES)
    logger.info(f"Webhook set successfully to {WEBHOOK_URL}")
    yield
    # On shutdown
    await tg_app.bot.delete_webhook()
    await tg_app.shutdown()
    logger.info("Bot shutdown complete.")

app = FastAPI(lifespan=lifespan)

@app.get("/")
def index():
    return {"status": "Bot is running!"}

@app.post("/webhook")
async def webhook(request: Request):
    """The main webhook endpoint that receives updates from Telegram."""
    try:
        data = await request.json()
        update = Update.de_json(data, tg_app.bot)
        await tg_app.process_update(update)
        return Response(status_code=200)
    except Exception as e:
        logger.error(f"Error in webhook: {e}")
        return Response(status_code=500)
