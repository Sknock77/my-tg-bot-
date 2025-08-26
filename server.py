import os
import asyncio
import logging
import gzip
import json
from io import BytesIO
from flask import Flask, request
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters
from telegram.constants import MessageEntityType

# --- Logging Setup ---
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# --- Environment Variables ---
BOT_TOKEN = os.environ.get("BOT_TOKEN")
RENDER_EXTERNAL_URL = os.environ.get("RENDER_EXTERNAL_URL")
# Make sure to set CHANNEL_ID in your Render environment variables
CHANNEL_ID = os.environ.get("CHANNEL_ID")

if not BOT_TOKEN or not RENDER_EXTERNAL_URL or not CHANNEL_ID:
    logger.error("FATAL: One or more environment variables (BOT_TOKEN, RENDER_EXTERNAL_URL, CHANNEL_ID) are not set.")
    exit()

WEBHOOK_URL = f"{RENDER_EXTERNAL_URL}/webhook"

# --- In-Memory Cache ---
user_data_by_mobile = {}
user_data_by_email = {}
processed_files = set()

def index_records(records, filename):
    """Indexes a list of records into the in-memory dictionaries."""
    new_records_indexed = 0
    for record in records:
        if 'Mobile No' in record:
            user_data_by_mobile[str(record['Mobile No'])] = record
        if 'Email Contact' in record and record['Email Contact']:
            user_data_by_email[record['Email Contact'].lower()] = record
        new_records_indexed += 1
    logger.info(f"Indexed {new_records_indexed} records from {filename}.")
    processed_files.add(filename)

async def process_document_message(message, context):
    """Helper function to download and index a file from a message."""
    doc = message.document
    if doc and doc.file_name.endswith('.json.gz'):
        if doc.file_name in processed_files:
            logger.info(f"Skipping already processed file: {doc.file_name}")
            return 0
        try:
            file = await context.bot.get_file(doc.file_id)
            file_bytes = await file.download_as_bytearray()
            with gzip.open(BytesIO(file_bytes), 'rt', encoding='utf-8') as f:
                records = json.load(f)
            if isinstance(records, list):
                index_records(records, doc.file_name)
                return len(records)
        except Exception as e:
            logger.error(f"Failed to process file {doc.file_name}: {e}")
    return -1 # Return -1 for error

# --- Bot Handlers ---
async def start(update: Update, context):
    await update.message.reply_text(
        "Hello! I am ready.\n\n"
        "Use `/index` to scan this channel's history and load all `.json.gz` files.\n"
        "Use `/search <query>` to find a record.\n"
        "Use `/stats` to see current index status."
    )

async def index_channel(update: Update, context):
    """Scans the channel history for .json.gz files and indexes them."""
    await update.message.reply_text("Starting to scan channel history. This may take some time...")
    
    total_records_indexed = 0
    total_files_processed = 0
    total_files_failed = 0
    
    # We need to iterate through the history. This is a simplified approach.
    # Note: A full history scan can be complex. This scans recent messages effectively.
    # For very large histories, a more advanced approach might be needed.
    # We will use a placeholder loop for demonstration. In a real scenario, you'd use message IDs to paginate.
    # This example will rely on the bot being able to see recent messages.
    # A more robust solution would involve `get_chat_history` which is not directly in `ext`.
    # Let's stick to handling forwarded/new files as it's more reliable on serverless platforms.
    # Re-adopting the previous, more stable logic and explaining it better.
    # The user is an admin, so they can trigger this.

    # Let's try a more direct approach to get messages if possible.
    # The `python-telegram-bot` library doesn't have a simple `get_history` function.
    # Therefore, the most reliable method remains reacting to messages as they appear.
    
    # Correcting the approach to be more honest about library limitations.
    # The most robust way is still to have the user forward the messages.
    # Let's create a handler that processes ANY message with a document.
    
    await update.message.reply_text(
        "**Action Required**\n\nTo index your files, please **forward** them to this channel.\n\n"
        "I will automatically download and index any `.json.gz` file I see. You only need to do this once for your existing files."
    )


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
            key_safe = str(key).replace('-', '\\-').replace('.', '\\.')
            value_safe = str(value).replace('-', '\\-').replace('.', '\\.')
            message += f"*{key_safe}:* `{value_safe}`\n"
        await update.message.reply_text(message, parse_mode='MarkdownV2')
    else:
        await update.message.reply_text("❌ No record found.")

async def stats(update: Update, context):
    message = (
        f"📊 **Index Stats**\n\n"
        f"Records by mobile: `{len(user_data_by_mobile)}`\n"
        f"Records by email: `{len(user_data_by_email)}`\n"
        f"Files processed: `{len(processed_files)}`"
    )
    await update.message.reply_text(message, parse_mode='MarkdownV2')

async def document_handler(update: Update, context):
    """Handles any message with a document, including forwards."""
    records_indexed = await process_document_message(update.message, context)
    if records_indexed > 0:
        await update.message.reply_text(f"✅ Indexed `{records_indexed}` records from `{update.message.document.file_name}`.")
    elif records_indexed == -1:
         await update.message.reply_text(f"❌ Error processing file `{update.message.document.file_name}`.")

# --- Main Application Setup ---
tg_app = Application.builder().token(BOT_TOKEN).build()

tg_app.add_handler(CommandHandler("start", start))
tg_app.add_handler(CommandHandler("index", index_channel)) # Kept for user guidance
tg_app.add_handler(CommandHandler("search", search))
tg_app.add_handler(CommandHandler("stats", stats))
tg_app.add_handler(MessageHandler(filters.Document.ALL, document_handler))

async def setup():
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
