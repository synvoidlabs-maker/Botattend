import os
import json
import firebase_admin
from firebase_admin import credentials, firestore
from datetime import datetime, date
from calendar import monthrange
from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup,
    ReplyKeyboardMarkup
)
from telegram.ext import (
    ApplicationBuilder, CommandHandler, ContextTypes,
    CallbackQueryHandler, MessageHandler, filters
)

# ---------- FIREBASE ----------
firebase_key = json.loads(os.getenv("FIREBASE_KEY"))
cred = credentials.Certificate(firebase_key)
firebase_admin.initialize_app(cred)
db = firestore.client()

TOKEN = os.getenv("BOT_TOKEN")

# ---------- UTILS ----------
def is_sunday(d):
    return datetime.strptime(d, "%Y-%m-%d").weekday() == 6

def menu():
    return ReplyKeyboardMarkup(
        [
            ["✅ Present", "❌ Absent"],
            ["📅 Calendar", "📊 Stats"],
            ["🎉 Holiday", "📤 Export"]
        ],
        resize_keyboard=True
    )

async def auto_delete(context: ContextTypes.DEFAULT_TYPE):
    chat_id, bot_msg, user_msg = context.job.data
    try:
        await context.bot.delete_message(chat_id, bot_msg)
        await context.bot.delete_message(chat_id, user_msg)
    except:
        pass

async def send_msg(update, context, text, keyboard=None):
    user_msg_id = update.message.message_id if update.message else None

    msg = await update.effective_chat.send_message(text, reply_markup=keyboard)

    if user_msg_id:
        context.job_queue.run_once(
            auto_delete,
            300,
            data=(msg.chat_id, msg.message_id, user_msg_id)
        )

# ---------- START ----------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("📲 AttendX Ready", reply_markup=menu())

# ---------- TEXT HANDLER ----------
async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text

    if text == "✅ Present":
        await mark(update, context, "present")

    elif text == "❌ Absent":
        await mark(update, context, "absent")

    elif text == "🎉 Holiday":
        await holiday_today(update, context)

    elif text == "📊 Stats":
        await stats(update, context)

    elif text == "📅 Calendar":
        await calendar(update, context)

    elif text == "📤 Export":
        await export_data(update, context)

# ---------- MARK ----------
async def mark(update, context, status):
    user = str(update.effective_user.id)
    today = str(date.today())
    now = datetime.now().strftime("%H:%M:%S")

    doc = db.collection("users").document(user)
    data = doc.get().to_dict() or {"records": {}, "holidays": []}

    if is_sunday(today):
        await send_msg(update, context, "❌ Sunday excluded")
        return

    if today in data["records"]:
        entry = data["records"][today]
        await send_msg(update, context,
            f"⚠️ Already ({entry['status']} at {entry['time']})")
        return

    data["records"][today] = {"status": status, "time": now}
    doc.set(data)

    await send_msg(update, context, f"✅ {status} at {now}")

# ---------- HOLIDAY ----------
async def holiday_today(update, context):
    user = str(update.effective_user.id)
    today = str(date.today())

    doc = db.collection("users").document(user)
    data = doc.get().to_dict() or {"records": {}, "holidays": []}

    if today not in data["holidays"]:
        data["holidays"].append(today)
        doc.set(data)

    await send_msg(update, context, f"🎉 Holiday set ({today})")

# ---------- STATS ----------
async def stats(update, context):
    user = str(update.effective_user.id)

    doc = db.collection("users").document(user)
    data = doc.get().to_dict()

    if not data:
        await send_msg(update, context, "No data")
        return

    total = 0
    present = 0

    for d, v in data["records"].items():
        if is_sunday(d) or d in data["holidays"]:
            continue
        total += 1
        if v["status"] == "present":
            present += 1

    percent = (present / total) * 100 if total else 0

    await send_msg(update, context,
        f"📊 {percent:.2f}%\nPresent: {present}/{total}")

# ---------- CALENDAR ----------
async def calendar(update, context):
    user = str(update.effective_user.id)

    doc = db.collection("users").document(user)
    data = doc.get().to_dict() or {"records": {}, "holidays": []}

    year = date.today().year
    month = date.today().month
    days = monthrange(year, month)[1]

    buttons = []
    row = []

    for d in range(1, days + 1):
        d_str = f"{year}-{month:02d}-{d:02d}"

        if d_str in data["records"]:
            emoji = "✅" if data["records"][d_str]["status"] == "present" else "❌"
        elif d_str in data["holidays"]:
            emoji = "🎉"
        elif is_sunday(d_str):
            emoji = "⛔"
        else:
            emoji = "▫️"

        row.append(InlineKeyboardButton(
            emoji + str(d), callback_data=f"day_{d_str}"
        ))

        if len(row) == 7:
            buttons.append(row)
            row = []

    if row:
        buttons.append(row)

    await update.message.reply_text(
        "📅 Calendar",
        reply_markup=InlineKeyboardMarkup(buttons)
    )

# ---------- EXPORT ----------
async def export_data(update, context):
    user = str(update.effective_user.id)

    doc = db.collection("users").document(user)
    data = doc.get().to_dict()

    if not data:
        await send_msg(update, context, "No data")
        return

    file = f"{user}.json"

    with open(file, "w") as f:
        json.dump(data, f)

    await update.message.reply_document(document=open(file, "rb"))

# ---------- MAIN ----------
app = ApplicationBuilder().token(TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(MessageHandler(filters.TEXT, text_handler))
app.add_handler(CallbackQueryHandler(lambda u, c: None))  # placeholder

print("🔥 FINAL BOT RUNNING...")
app.run_polling()
