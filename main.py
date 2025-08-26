import os
import logging
import gzip
import json
import glob
import threading
from flask import Flask
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.environ.get("BOT_TOKEN")
if not BOT_TOKEN:
    logger.error("FATAL: BOT_TOKEN environment variable is not set.")
    exit()

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

def run_bot():
    application = Application.builder().token(BOT_TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("search", search))
    logger.info("Bot is starting to poll...")
    application.run_polling()

app = Flask(__name__)
@app.route("/")
def index():
    return "Web server is running to keep the service alive."

if __name__ == "__main__":
    load_and_index_data()
    bot_thread = threading.Thread(target=run_bot)
    bot_thread.daemon = True
    bot_thread.start()
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
