import os
from flask import Flask, request
from telegram import Update
from telegram.ext import Application
from bot import register_handlers   # <--- import handler registrar

BOT_TOKEN = os.environ.get("BOT_TOKEN")
WEBHOOK_URL = os.environ.get("RENDER_EXTERNAL_URL") + "/webhook"

app = Flask(__name__)

tg_app = Application.builder().token(BOT_TOKEN).build()

# Register handlers from bot.py
register_handlers(tg_app)

@app.route("/")
def index():
    return "Bot is alive!"

@app.route("/webhook", methods=["POST"])
async def webhook():
    update = Update.de_json(request.get_json(force=True), tg_app.bot)
    await tg_app.process_update(update)
    return "ok"

if name == "__main__":
    import asyncio

    async def set_webhook():
        await tg_app.bot.set_webhook(WEBHOOK_URL)

    asyncio.get_event_loop().run_until_complete(set_webhook())
    tg_app.run_webhook(
        listen="0.0.0.0",
        port=int(os.environ.get("PORT", 5000)),
        webhook_url=WEBHOOK_URL
    )
