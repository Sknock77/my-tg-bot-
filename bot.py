# bot.py
from telegram.ext import CommandHandler, MessageHandler, filters

# --- Handlers ---

async def start(update, context):
    await update.message.reply_text("✅ Bot is alive on webhook!")

async def echo(update, context):
    await update.message.reply_text(update.message.text)

# --- Register handlers into app ---
def register_handlers(app):
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, echo))
