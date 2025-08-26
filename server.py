import os
import asyncio
from flask import Flask, request
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters

# --- Environment Variables ---
# It's crucial to set these in your deployment environment (e.g., Render, Heroku)
BOT_TOKEN = os.environ.get("BOT_TOKEN")
# Example: "https://your-app-name.onrender.com"
RENDER_EXTERNAL_URL = os.environ.get("RENDER_EXTERNAL_URL")
WEBHOOK_URL = f"{RENDER_EXTERNAL_URL}/webhook"

# --- Bot Handlers ---
# Define your command and message handlers here
async def start(update: Update, context):
    """Sends a message when the command /start is issued."""
    await update.message.reply_text("Hello! I am a webhook bot running on Flask.")

async def echo(update: Update, context):
    """Echo the user's message."""
    await update.message.reply_text(f"You said: {update.message.text}")

# --- Flask App Setup ---
app = Flask(__name__)

# Build the Telegram Application
# We don't run polling or a webhook server here, just build the app object
tg_app = Application.builder().token(BOT_TOKEN).build()
tg_app.add_handler(CommandHandler("start", start))
tg_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, echo))

@app.route("/")
def index():
    """A simple page to confirm the bot is online."""
    return "Bot is alive and listening!"

@app.route("/webhook", methods=["POST"])
async def webhook():
    """
    This is the main webhook endpoint. It receives updates from Telegram.
    """
    if request.is_json:
        json_data = request.get_json(force=True)
        try:
            # Create an Update object from the JSON data
            update = Update.de_json(json_data, tg_app.bot)
            # Process the update with the application
            await tg_app.process_update(update)
            return "ok", 200
        except Exception as e:
            print(f"Error processing update: {e}")
            return "error", 500
    else:
        return "bad request", 400


async def setup():
    """
    Sets the webhook with Telegram. This should be run once when the app starts.
    """
    # We need to wait for the application to be fully initialized
    await tg_app.initialize()
    await tg_app.bot.set_webhook(url=WEBHOOK_URL, allowed_updates=Update.ALL_TYPES)
    print(f"Webhook set to {WEBHOOK_URL}")


if __name__ == "__main__":
    # The setup needs to be run in an async context
    asyncio.run(setup())

    # This part is for local development.
    # For production, use a proper WSGI server like Gunicorn or Waitress.
    # Example: gunicorn app:app
    print("Starting Flask app...")
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
