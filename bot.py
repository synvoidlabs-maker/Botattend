import os
import json
from datetime import datetime, date
from calendar import monthrange
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
        [InlineKeyboardButton("🎉 Holiday", callback_data="holiday_today")],
        [InlineKeyboardButton("📅 Calendar", callback_data="calendar")],
        [InlineKeyboardButton("📊 Stats", callback_data="stats")]
    ]

    await update.message.reply_text(
        "📲 AttendX Panel",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# ---------- BUTTON HANDLER ----------
async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user = str(query.from_user.id)
    today = str(date.today())
    now = datetime.now().strftime("%H:%M:%S")

    data = load()

    if user not in data:
        data[user] = {"records": {}, "holidays": []}

    # ---------- PRESENT / ABSENT ----------
    if query.data in ["present", "absent"]:
        if is_sunday(today):
            await query.edit_message_text("❌ Sunday auto excluded")
            return

        if today in data[user]["records"]:
            entry = data[user]["records"][today]
            await query.edit_message_text(
                f"⚠️ Already submitted ({entry['status']} at {entry['time']})"
            )
            return

        data[user]["records"][today] = {
            "status": query.data,
            "time": now
        }
        save(data)

        await query.edit_message_text(f"✅ {query.data} marked at {now}")

    # ---------- HOLIDAY TODAY ----------
    elif query.data == "holiday_today":
        data[user]["holidays"].append(today)
        save(data)

        await query.edit_message_text(f"🎉 Today marked holiday ({today})")

    # ---------- CALENDAR ----------
    elif query.data == "calendar":
        year = date.today().year
        month = date.today().month
        days = monthrange(year, month)[1]

        buttons = []
        row = []

        for d in range(1, days + 1):
            day_str = f"{year}-{month:02d}-{d:02d}"
            row.append(InlineKeyboardButton(str(d), callback_data=f"day_{day_str}"))

            if len(row) == 7:
                buttons.append(row)
                row = []

        if row:
            buttons.append(row)

        await query.edit_message_text(
            "📅 Select a date",
            reply_markup=InlineKeyboardMarkup(buttons)
        )

    # ---------- DATE CLICK ----------
    elif query.data.startswith("day_"):
        selected_date = query.data.split("_")[1]

        keyboard = [
            [InlineKeyboardButton("✅ Present", callback_data=f"set_present_{selected_date}")],
            [InlineKeyboardButton("❌ Absent", callback_data=f"set_absent_{selected_date}")],
            [InlineKeyboardButton("🎉 Holiday", callback_data=f"set_holiday_{selected_date}")]
        ]

        await query.edit_message_text(
            f"📅 {selected_date}",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    # ---------- APPLY ACTION ----------
    elif query.data.startswith("set_"):
        parts = query.data.split("_")
        action = parts[1]
        selected_date = parts[2]

        if action == "holiday":
            data[user]["holidays"].append(selected_date)
            msg = f"🎉 Holiday set: {selected_date}"

        else:
            data[user]["records"][selected_date] = {
                "status": action,
                "time": now
            }
            msg = f"✅ {action} set for {selected_date}"

        save(data)
        await query.edit_message_text(msg)

    # ---------- STATS ----------
    elif query.data == "stats":
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

        await query.edit_message_text(
            f"📊 {percent:.2f}%\nPresent: {present}/{total}"
        )

# ---------- MAIN ----------
app = ApplicationBuilder().token(TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(CallbackQueryHandler(button))

print("🔥 AttendX Ultimate Running...")
app.run_polling()
