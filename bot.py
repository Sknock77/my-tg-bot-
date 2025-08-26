import os, io, re, json, gzip, time
from typing import Dict, Any
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from telegram.error import BadRequest

BOT_TOKEN = os.environ.get("BOT_TOKEN")
CHANNEL_ID = int(os.environ.get("CHANNEL_ID"))

ALLOWED_USER_IDS = set()  # optional restriction
SHARD_PREFIX = 4
MANIFEST_CACHE_TTL = 600
SHARD_CACHE_TTL = 600

_manifest_cache: Dict[str, Any] = {"data": None, "ts": 0}
_shard_cache: Dict[str, Any] = {}

def digits_only(s: str) -> str:
    return re.sub(r"\D", "", str(s or ""))

async def load_manifest(context: ContextTypes.DEFAULT_TYPE) -> Dict[str, Any]:
    now = time.time()
    if _manifest_cache["data"] and now - _manifest_cache["ts"] < MANIFEST_CACHE_TTL:
        return _manifest_cache["data"]

    bot = context.bot
    chat = await bot.get_chat(CHANNEL_ID)
    pm = chat.pinned_message
    if not pm or not pm.document:
        raise RuntimeError("Pinned manifest.json not found in the channel")

    file = await bot.get_file(pm.document.file_id)
    bio = io.BytesIO()
    await file.download_to_memory(out=bio)
    bio.seek(0)
    manifest = json.loads(bio.read().decode("utf-8"))

    _manifest_cache["data"] = manifest
    _manifest_cache["ts"] = now
    return manifest

async def load_shard(context: ContextTypes.DEFAULT_TYPE, shard: str) -> Dict[str, Any]:
    now = time.time()
    entry = _shard_cache.get(shard)
    if entry and now - entry["ts"] < SHARD_CACHE_TTL:
        return entry["data"]

    manifest = await load_manifest(context)
    info = manifest["shards"].get(shard)
    if not info:
        return {}

    file = await context.bot.get_file(info["file_id"])
    bio = io.BytesIO()
    await file.download_to_memory(out=bio)
    bio.seek(0)
    data = json.loads(gzip.decompress(bio.read()).decode("utf-8"))

    _shard_cache[shard] = {"data": data, "ts": now}
    return data

async def search_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if ALLOWED_USER_IDS and user_id not in ALLOWED_USER_IDS:
        await update.message.reply_text("You are not authorized to use this bot.")
        return

    if not context.args:
        await update.message.reply_text("Usage: /search <phone>")
        return

    query = digits_only(" ".join(context.args))
    if len(query) < 7:
        await update.message.reply_text("Please provide a valid phone number (7+ digits).")
        return

    shard = query[:SHARD_PREFIX]
    try:
        shard_map = await load_shard(context, shard)
    except BadRequest:
        await update.message.reply_text(f"Shard not available for prefix {shard}.")
        return

    rec = shard_map.get(query)

    if rec:
        # Full record as formatted JSON
        await update.message.reply_text(
            json.dumps(rec, ensure_ascii=False, indent=2)
        )
    else:
        await update.message.reply_text("Not found.")

async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Send /search <phone>. Example: /search 9711102028")

def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start_cmd))
    app.add_handler(CommandHandler("search", search_cmd))
 # app.run_polling()
