import os
import json
from datetime import date, time
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
import matplotlib.pyplot as plt
from reportlab.platypus import SimpleDocTemplate, Paragraph

# 🔐 TOKEN (Railway env variable)
TOKEN = os.getenv("BOT_TOKEN")

FILE = "data.json"

# ---------------- DATA FUNCTIONS ----------------
def load():
    try:
        with open(FILE) as f:
            return json.load(f)
    except:
        return {}

def save(data):
    with open(FILE, "w") as f:
        json.dump(data, f)

def calc_stats(records):
    total = len(records)
    present = list(records.values()).count("present")
    percent = (present / total) * 100 if total else 0
    return total, present, percent

# ---------------- COMMANDS ----------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id

    # ⏰ Daily Reminder 9 AM
    context.job_queue.run_daily(
        daily_reminder,
        time=time(hour=9, minute=0),
        chat_id=chat_id
    )

    await update.message.reply_text(
        "✅ Bot started!\n⏰ Daily reminder set (9 AM)\n\nUse:\n/present\n/absent\n/stats"
    )

async def daily_reminder(context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_message(
        chat_id=context.job.chat_id,
        text="⏰ Aaj attendance mark karo!"
    )

async def mark(update: Update, context: ContextTypes.DEFAULT_TYPE, status):
    user = str(update.effective_user.id)
    today = str(date.today())

    data = load()

    if user not in data:
        data[user] = {}

    data[user][today] = status
    save(data)

    await update.message.reply_text(f"✅ {today} marked as {status}")

async def present(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await mark(update, context, "present")

async def absent(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await mark(update, context, "absent")

async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = str(update.effective_user.id)
    data = load()

    if user not in data:
        await update.message.reply_text("❌ No data yet")
        return

    total, present, percent = calc_stats(data[user])

    # ⚠️ Leave warning
    max_bunk = int(total * 0.25)
    used_bunk = total - present
    left = max_bunk - used_bunk

    msg = f"""
📊 Attendance: {percent:.2f}%
Present: {present}/{total}

⚠️ Bunk left: {left}
"""
    await update.message.reply_text(msg)

async def graph(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = str(update.effective_user.id)
    data = load()

    if user not in data:
        await update.message.reply_text("No data")
        return

    records = data[user]

    values = [1 if v == "present" else 0 for v in records.values()]

    plt.plot(values)
    plt.title("Attendance Graph")
    plt.savefig("graph.png")
    plt.close()

    await update.message.reply_photo(photo=open("graph.png", "rb"))

async def pdf(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = str(update.effective_user.id)
    data = load()

    if user not in data:
        await update.message.reply_text("No data")
        return

    total, present, percent = calc_stats(data[user])

    doc = SimpleDocTemplate("report.pdf")
    content = [
        Paragraph(f"Attendance: {percent:.2f}%"),
        Paragraph(f"Present: {present}/{total}")
    ]
    doc.build(content)

    await update.message.reply_document(document=open("report.pdf", "rb"))

# ---------------- MAIN ----------------
app = ApplicationBuilder().token(TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("present", present))
app.add_handler(CommandHandler("absent", absent))
app.add_handler(CommandHandler("stats", stats))
app.add_handler(CommandHandler("graph", graph))
app.add_handler(CommandHandler("pdf", pdf))

print("🤖 Bot running...")
app.run_polling()