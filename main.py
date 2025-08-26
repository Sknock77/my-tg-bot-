import os
import logging
import json
import glob
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
    """Loads and indexes data from all .json files in the 'datajson/' directory."""
    logger.info("Starting data load from .json files...")
    data_files = glob.glob("datajson/*.json")
    
    logger.info(f"Found data files: {data_files}")

    if not data_files:
        logger.warning("No data files found in 'datajson/' directory. Search will not work.")
        return
        
    all_records = []
    for file_path in data_files:
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if isinstance(data, dict):
                    all_records.extend(data.values())
                elif isinstance(data, list):
                    all_records.extend(data)
        except Exception as e:
            logger.error(f"Failed to load or parse {file_path}: {e}")
            
    for record in all_records:
        if 'phone' in record:
            user_data_by_mobile[str(record['phone'])] = record
        if 'email' in record and isinstance(record['email'], str):
            user_data_by_email[record['email'].lower()] = record
            
    logger.info(f"Successfully indexed {len(all_records)} records.")

# --- Telegram Bot Setup ---
tg_app = Application.builder().token(BOT_TOKEN).build()

# --- Bot Handlers ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Bot is running. Use /search, /stats, or /debug.")

async def search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usage: `/search 9876543210`", parse_mode='MarkdownV2')
        return
    query = context.args[0].lower()
    result = user_data_by_mobile.get(query) or user_data_by_email.get(query)
    if result:
        message = "✅ **User Data Found**\n\n"
        for key, value in result.items():
            key_safe = str(key).replace('_', '\\_').replace('-', '\\-').replace('.', '\\.')
            value_safe = str(value).replace('-', '\\-').replace('.', '\\.')
            message += f"*{key_safe}:* `{value_safe}`\n"
        await update.message.reply_text(message, parse_mode='MarkdownV2')
    else:
        await update.message.reply_text("❌ No record found for that query.")

async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Displays the number of records currently loaded in memory."""
    message = (
        f"📊 **Current Index Stats**\n\n"
        f"Records indexed by mobile: `{len(user_data_by_mobile)}`\n"
        f"Records indexed by email: `{len(user_data_by_email)}`"
    )
    await update.message.reply_text(message, parse_mode='MarkdownV2')

async def debug(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Lists files and folders to help diagnose data loading issues."""
    try:
        current_dir_files = os.listdir('.')
        datajson_dir_files = os.listdir('datajson') if os.path.exists('datajson') else "Folder not found"
        
        message = (
            f"🔍 **Debug Info**\n\n"
            f"*Current Directory Contents:*\n`{current_dir_files}`\n\n"
            f"*'datajson' Directory Contents:*\n`{datajson_dir_files}`"
        )
        await update.message.reply_text(message, parse_mode='MarkdownV2')
    except Exception as e:
        await update.message.reply_text(f"Error during debug: {e}")


# Register handlers
tg_app.add_handler(CommandHandler("start", start))
tg_app.add_handler(CommandHandler("search", search))
tg_app.add_handler(CommandHandler("stats", stats))
tg_app.add_handler(CommandHandler("debug", debug))

# --- FastAPI Web Server ---
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

# UPDATED: Allow both GET and HEAD requests for the root endpoint
@app.get("/", methods=["GET", "HEAD"])
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
