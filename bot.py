import os
import json
from datetime import datetime, date
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, CallbackQueryHandler

TOKEN = os.getenv("BOT_TOKEN")
FILE = "data.json"

# ---------- DATA ----------
def load():
    try:
        with open(FILE) as f:
            return json.load(f)
    except:
        return {}

def save(data):
    with open(FILE, "w") as f:
        json.dump(data, f)

def is_sunday(d):
    return datetime.strptime(d, "%Y-%m-%d").weekday() == 6

# ---------- START ----------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("✅ Present", callback_data="present")],
        [InlineKeyboardButton("❌ Absent", callback_data="absent")],
        [InlineKeyboardButton("📊 Stats", callback_data="stats")]
    ]
    await update.message.reply_text(
        "📲 AttendX Panel",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# ---------- MARK ----------
async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user = str(query.from_user.id)
    today = str(date.today())
    now = datetime.now().strftime("%H:%M:%S")

    data = load()

    if user not in data:
        data[user] = {"records": {}, "holidays": []}

    # Sunday check
    if is_sunday(today):
        await query.edit_message_text("❌ Sunday auto excluded")
        return

    # Already submitted
    if today in data[user]["records"]:
        entry = data[user]["records"][today]
        await query.edit_message_text(
            f"⚠️ Already submitted ({entry['status']} at {entry['time']})"
        )
        return

    if query.data in ["present", "absent"]:
        data[user]["records"][today] = {"status": query.data, "time": now}
        save(data)
        await query.edit_message_text(f"✅ {query.data} marked at {now}")

    elif query.data == "stats":
        await stats(update, context)

# ---------- EDIT ----------
async def edit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Send date (YYYY-MM-DD)")

async def handle_edit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = str(update.effective_user.id)
    text = update.message.text

    data = load()

    if user not in data:
        return

    if "edit_date" not in context.user_data:
        context.user_data["edit_date"] = text
        await update.message.reply_text("Send new status (present/absent)")
    else:
        d = context.user_data["edit_date"]
        status = text.lower()
        now = datetime.now().strftime("%H:%M:%S")

        data[user]["records"][d] = {"status": status, "time": now}
        save(data)

        context.user_data.clear()

        await update.message.reply_text(f"✅ Updated {d} → {status}")

# ---------- HOLIDAY ----------
async def holiday(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = str(update.effective_user.id)
    d = context.args[0]

    data = load()

    if user not in data:
        data[user] = {"records": {}, "holidays": []}

    data[user]["holidays"].append(d)
    save(data)

    await update.message.reply_text(f"🎉 Holiday added: {d}")

# ---------- STATS ----------
async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = str(update.effective_user.id)
    data = load()

    if user not in data:
        await update.message.reply_text("No data")
        return

    records = data[user]["records"]
    holidays = data[user]["holidays"]

    total = 0
    present = 0

    for d, v in records.items():
        if is_sunday(d) or d in holidays:
            continue
        total += 1
        if v["status"] == "present":
            present += 1

    percent = (present / total) * 100 if total else 0

    await update.message.reply_text(
        f"📊 {percent:.2f}%\nPresent: {present}/{total}"
    )

# ---------- CALENDAR ----------
async def calendar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = str(update.effective_user.id)
    data = load()

    if user not in data:
        return

    text = "📅 Calendar:\n\n"

    for d, v in sorted(data[user]["records"].items()):
        emoji = "✅" if v["status"] == "present" else "❌"
        text += f"{d} {emoji}\n"

    await update.message.reply_text(text)

# ---------- MAIN ----------
app = ApplicationBuilder().token(TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(CallbackQueryHandler(button))
app.add_handler(CommandHandler("edit", edit))
app.add_handler(CommandHandler("holiday", holiday))
app.add_handler(CommandHandler("stats", stats))
app.add_handler(CommandHandler("calendar", calendar))

from telegram.ext import MessageHandler, filters
app.add_handler(MessageHandler(filters.TEXT, handle_edit))

print("🔥 AttendX Ultimate Running...")
app.run_polling()
