import os
import json
import firebase_admin
from firebase_admin import credentials, firestore
from datetime import datetime, date
from calendar import monthrange
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    CallbackQueryHandler,
)

# ---------- FIREBASE INIT ----------
firebase_env = os.getenv("FIREBASE_KEY")

if not firebase_env:
    raise ValueError("❌ FIREBASE_KEY not found in ENV")

firebase_key = json.loads(firebase_env)

cred = credentials.Certificate(firebase_key)
firebase_admin.initialize_app(cred)
db = firestore.client()

TOKEN = os.getenv("BOT_TOKEN")

if not TOKEN:
    raise ValueError("❌ BOT_TOKEN not found in ENV")

# ---------- UTILS ----------
def is_sunday(d):
    return datetime.strptime(d, "%Y-%m-%d").weekday() == 6

async def auto_delete(context: ContextTypes.DEFAULT_TYPE):
    chat_id, msg_id = context.job.data
    try:
        await context.bot.delete_message(chat_id, msg_id)
    except:
        pass

async def send_msg(update, context, text, keyboard=None):
    msg = await update.effective_chat.send_message(text, reply_markup=keyboard)
    if context.job_queue:
        context.job_queue.run_once(auto_delete, 20, data=(msg.chat_id, msg.message_id))

# ---------- START ----------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Present", callback_data="present")],
        [InlineKeyboardButton("❌ Absent", callback_data="absent")],
        [InlineKeyboardButton("🎉 Holiday", callback_data="holiday_today")],
        [InlineKeyboardButton("📅 Calendar", callback_data="calendar")],
        [InlineKeyboardButton("📊 Stats", callback_data="stats")]
    ])

    await send_msg(update, context, "📲 AttendX Panel", keyboard)

# ---------- BUTTON ----------
async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user = str(query.from_user.id)
    today = str(date.today())
    now = datetime.now().strftime("%H:%M:%S")

    doc = db.collection("users").document(user)
    data = doc.get().to_dict() or {"records": {}, "holidays": []}

    # ---------- PRESENT / ABSENT ----------
    if query.data in ["present", "absent"]:
        if is_sunday(today):
            await send_msg(update, context, "❌ Sunday excluded")
            return

        if today in data["records"]:
            entry = data["records"][today]
            await send_msg(
                update, context,
                f"⚠️ Already submitted ({entry['status']} at {entry['time']})"
            )
            return

        data["records"][today] = {"status": query.data, "time": now}
        doc.set(data)

        await send_msg(update, context, f"✅ {query.data} marked at {now}")

    # ---------- HOLIDAY ----------
    elif query.data == "holiday_today":
        if today not in data["holidays"]:
            data["holidays"].append(today)
            doc.set(data)

        await send_msg(update, context, f"🎉 Holiday set ({today})")

    # ---------- CALENDAR ----------
    elif query.data == "calendar":
        year = date.today().year
        month = date.today().month
        days = monthrange(year, month)[1]

        buttons = []
        row = []

        for d in range(1, days + 1):
            d_str = f"{year}-{month:02d}-{d:02d}"

            if d_str in data["records"]:
                status = data["records"][d_str]["status"]
                emoji = "✅" if status == "present" else "❌"
            elif d_str in data["holidays"]:
                emoji = "🎉"
            elif is_sunday(d_str):
                emoji = "⛔"
            else:
                emoji = "▫️"

            row.append(
                InlineKeyboardButton(emoji + str(d), callback_data=f"day_{d_str}")
            )

            if len(row) == 7:
                buttons.append(row)
                row = []

        if row:
            buttons.append(row)

        await query.edit_message_text(
            "📅 Calendar View",
            reply_markup=InlineKeyboardMarkup(buttons)
        )

    # ---------- DATE CLICK ----------
    elif query.data.startswith("day_"):
        d = query.data.split("_")[1]

        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ Present", callback_data=f"set_present_{d}")],
            [InlineKeyboardButton("❌ Absent", callback_data=f"set_absent_{d}")],
            [InlineKeyboardButton("🎉 Holiday", callback_data=f"set_holiday_{d}")]
        ])

        await query.edit_message_text(f"📅 {d}", reply_markup=keyboard)

    # ---------- APPLY ----------
    elif query.data.startswith("set_"):
        _, action, d = query.data.split("_")

        if action == "holiday":
            if d not in data["holidays"]:
                data["holidays"].append(d)
        else:
            data["records"][d] = {"status": action, "time": now}

        doc.set(data)

        await send_msg(update, context, f"✅ {action} set for {d}")

    # ---------- STATS ----------
    elif query.data == "stats":
        total = 0
        present = 0

        for d, v in data["records"].items():
            if is_sunday(d) or d in data["holidays"]:
                continue
            total += 1
            if v["status"] == "present":
                present += 1

        percent = (present / total) * 100 if total else 0

        await send_msg(
            update, context,
            f"📊 {percent:.2f}%\nPresent: {present}/{total}"
        )

# ---------- MAIN ----------
app = ApplicationBuilder().token(TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(CallbackQueryHandler(button))

print("🔥 AttendX FINAL running...")
app.run_polling()
