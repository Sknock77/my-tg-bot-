import os
import asyncio
import logging
import gzip
import json
from io import BytesIO
from flask import Flask, request
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters

# --- Logging Setup ---
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# --- Environment Variables ---
BOT_TOKEN = os.environ.get("BOT_TOKEN")
RENDER_EXTERNAL_URL = os.environ.get("RENDER_EXTERNAL_URL")

if not BOT_TOKEN:
    logger.error("FATAL: BOT_TOKEN environment variable is not set.")
    exit()
if not RENDER_EXTERNAL_URL:
    logger.error("FATAL: RENDER_EXTERNAL_URL environment variable is not set.")
    exit()

WEBHOOK_URL = f"{RENDER_EXTERNAL_URL}/webhook"

# --- In-Memory Cache ---
# Dictionaries to hold our indexed data for fast lookups
user_data_by_mobile = {}
user_data_by_email = {}
processed_files = set() # To avoid processing the same file twice

def index_records(records, filename):
    """Indexes a list of records into the in-memory dictionaries."""
    new_records_indexed = 0
    for record in records:
        # Index by Mobile Number
        if 'Mobile No' in record:
            mobile_no_str = str(record['Mobile No'])
            user_data_by_mobile[mobile_no_str] = record

        # Index by Email (case-insensitive)
        if 'Email Contact' in record and record['Email Contact']:
            email = record['Email Contact'].lower()
            user_data_by_email[email] = record
        
        new_records_indexed += 1
    
    logger.info(f"Indexed {new_records_indexed} new records from {filename}.")
    processed_files.add(filename)


# --- Bot Handlers ---
async def start(update: Update, context):
    """Handler for the /start command."""
    await update.message.reply_text(
        "Hello! I am ready to search.\n\n"
        "Forward your `.json.gz` files to this channel to add them to the search index.\n\n"
        "Use `/search <mobile_or_email>` to find a record.\n"
        "Use `/stats` to see how many records are indexed."
    )

async def search(update: Update, context):
    """Handler for the /search command."""
    if not context.args:
        await update.message.reply_text("Please provide a mobile number or email to search.\nUsage: `/search 9876543210`")
        return

    query = context.args[0].lower()
    result = user_data_by_mobile.get(query) or user_data_by_email.get(query)

    if result:
        message = "✅ **User Data Found**\n\n"
        # Using a loop to handle potential special characters for MarkdownV2
        for key, value in result.items():
            # Escape special characters for MarkdownV2
            key_safe = str(key).replace('_', '\\_').replace('*', '\\*').replace('[', '\\[').replace(']', '\\]').replace('(', '\\(').replace(')', '\\)').replace('~', '\\~').replace('`', '\\`').replace('>', '\\>').replace('#', '\\#').replace('+', '\\+').replace('-', '\\-').replace('=', '\\=').replace('|', '\\|').replace('{', '\\}').replace('.', '\\.').replace('!', '\\!')
            value_safe = str(value).replace('_', '\\_').replace('*', '\\*').replace('[', '\\[').replace(']', '\\]').replace('(', '\\(').replace(')', '\\)').replace('~', '\\~').replace('`', '\\`').replace('>', '\\>').replace('#', '\\#').replace('+', '\\+').replace('-', '\\-').replace('=', '\\=').replace('|', '\\|').replace('{', '\\}').replace('.', '\\.').replace('!', '\\!')
            message += f"*{key_safe}:* `{value_safe}`\n"
        await update.message.reply_text(message, parse_mode='MarkdownV2')
    else:
        await update.message.reply_text("❌ No record found for that query.")

async def stats(update: Update, context):
    """Handler for the /stats command."""
    message = (
        f"📊 **Current Index Stats**\n\n"
        f"Records indexed by mobile: `{len(user_data_by_mobile)}`\n"
        f"Records indexed by email: `{len(user_data_by_email)}`\n"
        f"Unique files processed: `{len(processed_files)}`"
    )
    await update.message.reply_text(message, parse_mode='MarkdownV2')

async def document_handler(update: Update, context):
    """Handles incoming .json.gz files and indexes them."""
    doc = update.message.document
    if doc and doc.file_name.endswith('.json.gz'):
        if doc.file_name in processed_files:
            logger.info(f"Skipping already processed file: {doc.file_name}")
            # Optionally, notify the user it's a duplicate
            # await update.message.reply_text(f"File '{doc.file_name}' has already been processed.")
            return

        try:
            file = await context.bot.get_file(doc.file_id)
            file_bytes = await file.download_as_bytearray()
            
            with gzip.open(BytesIO(file_bytes), 'rt', encoding='utf-8') as f:
                records = json.load(f)
            
            if isinstance(records, list):
                index_records(records, doc.file_name)
                await update.message.reply_text(f"✅ Successfully indexed `{len(records)}` records from `{doc.file_name}`.")
            else:
                await update.message.reply_text(f"⚠️ File `{doc.file_name}` does not contain a valid list of records.")

        except Exception as e:
            logger.error(f"Failed to process file {doc.file_name}: {e}")
            await update.message.reply_text(f"❌ Error processing file `{doc.file_name}`.")

# --- Main Application Setup ---
tg_app = Application.builder().token(BOT_TOKEN).build()

tg_app.add_handler(CommandHandler("start", start))
tg_app.add_handler(CommandHandler("search", search))
tg_app.add_handler(CommandHandler("stats", stats))
tg_app.add_handler(MessageHandler(filters.Document.ALL, document_handler))

async def setup():
    """Sets the webhook with Telegram."""
    await tg_app.initialize()
    await tg_app.bot.set_webhook(url=WEBHOOK_URL, allowed_updates=Update.ALL_TYPES)
    logger.info(f"Webhook set successfully to {WEBHOOK_URL}")

# --- Flask Web Server ---
app = Flask(__name__)

@app.route("/")
def index():
    return "Bot is alive and listening for files!"

@app.route("/webhook", methods=["POST"])
async def webhook():
    try:
        update = Update.de_json(request.get_json(force=True), tg_app.bot)
        await tg_app.process_update(update)
        return "ok", 200
    except Exception as e:
        logger.error(f"Error in webhook: {e}")
        return "error", 500

with app.app_context():
    asyncio.run(setup())

if __name__ == "__main__":
    app.run(port=int(os.environ.get("PORT", 8080)))
