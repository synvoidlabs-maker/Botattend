import os
import json
from datetime import datetime, date, time
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

TOKEN = os.getenv("BOT_TOKEN")
FILE = "data.json"

# ---------------- DATA ----------------
def load():
    try:
        with open(FILE) as f:
            return json.load(f)
    except:
        return {}

def save(data):
    with open(FILE, "w") as f:
        json.dump(data, f)

def calc(records):
    total = len(records)
    present = sum(1 for r in records.values() if r["status"] == "present")
    percent = (present / total) * 100 if total else 0
    return total, present, percent

# ---------------- START ----------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = str(update.effective_user.id)
    today = str(date.today())
    data = load()

    msg = "🤖 AttendX Bot Started\n\n"

    if user in data and today in data[user]:
        entry = data[user][today]
        msg += f"📌 Today: {entry['status']} at {entry['time']}\n\n"
        msg += "Use /edit to change"
    else:
        msg += "❗ Mark attendance:\n/present\n/absent"

    # ⏰ Reminder
    if context.job_queue:
        context.job_queue.run_daily(
            daily_reminder,
            time=time(hour=9, minute=0),
            chat_id=update.effective_chat.id
        )

    await update.message.reply_text(msg)

# ---------------- REMINDER ----------------
async def daily_reminder(context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_message(
        chat_id=context.job.chat_id,
        text="⏰ Aaj attendance mark karo!"
    )

# ---------------- MARK ----------------
async def mark(update: Update, context: ContextTypes.DEFAULT_TYPE, status):
    user = str(update.effective_user.id)
    today = str(date.today())
    now = datetime.now().strftime("%H:%M:%S")

    data = load()

    if user not in data:
        data[user] = {}

    if today in data[user]:
        entry = data[user][today]
        await update.message.reply_text(
            f"⚠️ Already submitted ({entry['status']} at {entry['time']})\nUse /edit"
        )
        return

    data[user][today] = {"status": status, "time": now}
    save(data)

    await update.message.reply_text(f"✅ {status} marked at {now}")

async def present(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await mark(update, context, "present")

async def absent(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await mark(update, context, "absent")

# ---------------- EDIT ----------------
async def edit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = str(update.effective_user.id)
    today = str(date.today())

    data = load()

    if user not in data or today not in data[user]:
        await update.message.reply_text("❌ No entry to edit")
        return

    context.user_data["edit"] = True
    await update.message.reply_text("✏️ Send new status: present / absent")

async def handle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data.get("edit"):
        user = str(update.effective_user.id)
        today = str(date.today())
        text = update.message.text.lower()

        if text not in ["present", "absent"]:
            await update.message.reply_text("❌ Invalid. Send present/absent")
            return

        data = load()
        now = datetime.now().strftime("%H:%M:%S")

        data[user][today] = {"status": text, "time": now}
        save(data)

        context.user_data["edit"] = False

        await update.message.reply_text(f"✅ Updated to {text} at {now}")

# ---------------- STATS ----------------
async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = str(update.effective_user.id)
    data = load()

    if user not in data:
        await update.message.reply_text("No data")
        return

    total, present, percent = calc(data[user])

    max_bunk = int(total * 0.25)
    used = total - present
    left = max_bunk - used

    await update.message.reply_text(
        f"📊 {percent:.2f}%\nPresent: {present}/{total}\n⚠️ Bunk left: {left}"
    )

# ---------------- CALENDAR ----------------
async def calendar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = str(update.effective_user.id)
    data = load()

    if user not in data:
        await update.message.reply_text("No data")
        return

    text = "📅 Attendance Calendar:\n\n"

    for d, v in sorted(data[user].items()):
        symbol = "✅" if v["status"] == "present" else "❌"
        text += f"{d} : {symbol} ({v['time']})\n"

    await update.message.reply_text(text)

# ---------------- MAIN ----------------
app = ApplicationBuilder().token(TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("present", present))
app.add_handler(CommandHandler("absent", absent))
app.add_handler(CommandHandler("edit", edit))
app.add_handler(CommandHandler("stats", stats))
app.add_handler(CommandHandler("calendar", calendar))
from telegram.ext import MessageHandler, filters
app.add_handler(MessageHandler(filters.TEXT, handle))

print("🤖 AttendX running...")
app.run_polling()
