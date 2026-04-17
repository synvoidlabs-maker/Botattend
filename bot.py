import os
import firebase_admin
from firebase_admin import credentials, firestore
from datetime import datetime, date
from calendar import monthrange
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, CallbackQueryHandler

# ---------- FIREBASE INIT ----------
cred = credentials.Certificate("firebase.json")
firebase_admin.initialize_app(cred)
db = firestore.client()

TOKEN = os.getenv("BOT_TOKEN")

# ---------- UTILS ----------
def is_sunday(d):
    return datetime.strptime(d, "%Y-%m-%d").weekday() == 6

async def auto_delete(context: ContextTypes.DEFAULT_TYPE):
    chat_id, msg_id = context.job.data
    try:
        await context.bot.delete_message(chat_id, msg_id)
    except:
        pass

async def send_auto_delete(update, context, text, keyboard=None):
    msg = await update.effective_chat.send_message(
        text, reply_markup=keyboard
    )
    context.job_queue.run_once(
        auto_delete, 20, data=(msg.chat_id, msg.message_id)
    )

# ---------- START ----------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Present", callback_data="present")],
        [InlineKeyboardButton("❌ Absent", callback_data="absent")],
        [InlineKeyboardButton("🎉 Holiday", callback_data="holiday_today")],
        [InlineKeyboardButton("📅 Calendar", callback_data="calendar")],
        [InlineKeyboardButton("📊 Stats", callback_data="stats")]
    ])

    await send_auto_delete(update, context, "📲 AttendX Panel", keyboard)

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
            await send_auto_delete(update, context, "❌ Sunday excluded")
            return

        if today in data["records"]:
            await send_auto_delete(update, context, "⚠️ Already submitted")
            return

        data["records"][today] = {"status": query.data, "time": now}
        doc.set(data)

        await send_auto_delete(update, context, f"✅ {query.data} at {now}")

    # ---------- HOLIDAY ----------
    elif query.data == "holiday_today":
        data["holidays"].append(today)
        doc.set(data)

        await send_auto_delete(update, context, f"🎉 Holiday set ({today})")

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

            row.append(InlineKeyboardButton(emoji+str(d), callback_data=f"day_{d_str}"))

            if len(row) == 7:
                buttons.append(row)
                row = []

        if row:
            buttons.append(row)

        await query.edit_message_text(
            "📅 Calendar View",
            reply_markup=InlineKeyboardMarkup(buttons)
        )

    # ---------- DATE ACTION ----------
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
            data["holidays"].append(d)
        else:
            data["records"][d] = {"status": action, "time": now}

        doc.set(data)

        await send_auto_delete(update, context, f"✅ {action} set for {d}")

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

        await send_auto_delete(
            update, context,
            f"📊 {percent:.2f}%\nPresent: {present}/{total}"
        )

# ---------- MAIN ----------
app = ApplicationBuilder().token(TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(CallbackQueryHandler(button))

print("🔥 AttendX Firebase Running...")
app.run_polling()
