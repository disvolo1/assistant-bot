"""
Telegram-бот личного ассистента: расписание + напоминания + планирование поездок.

Запуск: python bot.py
Требуется переменная окружения BOT_TOKEN (см. README.md).
"""

import os
import logging
from datetime import datetime

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
)

import db

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

DT_FMT = "%d.%m.%Y %H:%M"
D_FMT = "%d.%m.%Y"


# ---------------------------------------------------------------------------
# Общие команды
# ---------------------------------------------------------------------------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Привет! Я твой ассистент по расписанию и поездкам.\n\n"
        "Расписание:\n"
        "/add_event 25.07.2026 14:30 Съёмка в студии\n"
        "/schedule — список ближайших событий\n"
        "/del_event <id> — удалить событие\n\n"
        "Поездки:\n"
        "/add_trip Дубай 25.07.2026 30.07.2026 Основная съёмка\n"
        "/trips — список поездок\n"
        "/trip <id> — детали поездки\n"
        "/add_stop <trip_id> 26.07.2026 09:00 Трансфер в отель\n"
        "/del_trip <id> — удалить поездку\n\n"
        "/help — показать это сообщение ещё раз"
    )


async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await start(update, context)


# ---------------------------------------------------------------------------
# Расписание
# ---------------------------------------------------------------------------

async def add_event(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if len(args) < 3:
        await update.message.reply_text(
            "Формат: /add_event ДД.ММ.ГГГГ ЧЧ:ММ Текст события\n"
            "Пример: /add_event 25.07.2026 14:30 Съёмка в студии"
        )
        return
    date_str, time_str = args[0], args[1]
    title = " ".join(args[2:])
    try:
        event_dt = datetime.strptime(f"{date_str} {time_str}", DT_FMT)
    except ValueError:
        await update.message.reply_text(
            "Не смог разобрать дату/время. Формат: ДД.ММ.ГГГГ ЧЧ:ММ"
        )
        return

    event_id = db.add_event(update.effective_chat.id, title, event_dt)
    await update.message.reply_text(
        f"Добавлено (id {event_id}): {title} — {event_dt.strftime(DT_FMT)}"
    )


async def schedule(update: Update, context: ContextTypes.DEFAULT_TYPE):
    rows = db.list_events(update.effective_chat.id)
    if not rows:
        await update.message.reply_text("Ближайших событий нет.")
        return
    lines = ["Ближайшие события:"]
    for r in rows:
        dt = datetime.strptime(r["event_dt"], "%Y-%m-%d %H:%M")
        lines.append(f"#{r['id']} — {dt.strftime(DT_FMT)} — {r['title']}")
    await update.message.reply_text("\n".join(lines))


async def del_event(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Формат: /del_event <id>")
        return
    try:
        event_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("id должен быть числом.")
        return
    ok = db.delete_event(update.effective_chat.id, event_id)
    await update.message.reply_text("Удалено." if ok else "Событие не найдено.")


# ---------------------------------------------------------------------------
# Поездки
# ---------------------------------------------------------------------------

async def add_trip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if len(args) < 3:
        await update.message.reply_text(
            "Формат: /add_trip Город ДД.ММ.ГГГГ(начало) ДД.ММ.ГГГГ(конец) [заметки]\n"
            "Пример: /add_trip Дубай 25.07.2026 30.07.2026 Основная съёмка"
        )
        return
    destination = args[0]
    try:
        start_date = datetime.strptime(args[1], D_FMT).strftime("%Y-%m-%d")
        end_date = datetime.strptime(args[2], D_FMT).strftime("%Y-%m-%d")
    except ValueError:
        await update.message.reply_text("Не смог разобрать даты. Формат: ДД.ММ.ГГГГ")
        return
    notes = " ".join(args[3:]) if len(args) > 3 else ""

    trip_id = db.add_trip(update.effective_chat.id, destination, start_date, end_date, notes)
    await update.message.reply_text(
        f"Поездка добавлена (id {trip_id}): {destination}, "
        f"{args[1]}–{args[2]}" + (f"\n{notes}" if notes else "")
    )


async def trips(update: Update, context: ContextTypes.DEFAULT_TYPE):
    rows = db.list_trips(update.effective_chat.id)
    if not rows:
        await update.message.reply_text("Поездок пока нет.")
        return
    lines = ["Поездки:"]
    for r in rows:
        sd = datetime.strptime(r["start_date"], "%Y-%m-%d").strftime(D_FMT)
        ed = datetime.strptime(r["end_date"], "%Y-%m-%d").strftime(D_FMT)
        lines.append(f"#{r['id']} — {r['destination']} ({sd}–{ed})")
    await update.message.reply_text("\n".join(lines))


async def trip_detail(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Формат: /trip <id>")
        return
    try:
        trip_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("id должен быть числом.")
        return
    trip = db.get_trip(update.effective_chat.id, trip_id)
    if not trip:
        await update.message.reply_text("Поездка не найдена.")
        return
    sd = datetime.strptime(trip["start_date"], "%Y-%m-%d").strftime(D_FMT)
    ed = datetime.strptime(trip["end_date"], "%Y-%m-%d").strftime(D_FMT)
    lines = [f"Поездка #{trip['id']}: {trip['destination']} ({sd}–{ed})"]
    if trip["notes"]:
        lines.append(f"Заметки: {trip['notes']}")
    items = db.list_trip_items(trip_id)
    if items:
        lines.append("\nМаршрут:")
        for it in items:
            dt = datetime.strptime(it["item_dt"], "%Y-%m-%d %H:%M")
            lines.append(f"  {dt.strftime(DT_FMT)} — {it['description']}")
    else:
        lines.append("\nМаршрут пока пуст. Добавь через /add_stop.")
    await update.message.reply_text("\n".join(lines))


async def add_stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if len(args) < 4:
        await update.message.reply_text(
            "Формат: /add_stop <trip_id> ДД.ММ.ГГГГ ЧЧ:ММ Описание\n"
            "Пример: /add_stop 1 26.07.2026 09:00 Трансфер в отель"
        )
        return
    try:
        trip_id = int(args[0])
    except ValueError:
        await update.message.reply_text("trip_id должен быть числом.")
        return
    trip = db.get_trip(update.effective_chat.id, trip_id)
    if not trip:
        await update.message.reply_text("Поездка не найдена.")
        return
    try:
        item_dt = datetime.strptime(f"{args[1]} {args[2]}", DT_FMT)
    except ValueError:
        await update.message.reply_text("Не смог разобрать дату/время. Формат: ДД.ММ.ГГГГ ЧЧ:ММ")
        return
    description = " ".join(args[3:])
    db.add_trip_item(trip_id, item_dt, description)
    await update.message.reply_text(f"Добавлено в маршрут поездки #{trip_id}: {description}")


async def del_trip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Формат: /del_trip <id>")
        return
    try:
        trip_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("id должен быть числом.")
        return
    ok = db.delete_trip(update.effective_chat.id, trip_id)
    await update.message.reply_text("Удалено." if ok else "Поездка не найдена.")


# ---------------------------------------------------------------------------
# Фоновая проверка напоминаний
# ---------------------------------------------------------------------------

REMINDER_WINDOW_MINUTES = 60  # напомнить, если событие наступит в течение часа


async def check_reminders(context: ContextTypes.DEFAULT_TYPE):
    due = db.get_due_unreminded_events(window_minutes=REMINDER_WINDOW_MINUTES)
    for row in due:
        dt = datetime.strptime(row["event_dt"], "%Y-%m-%d %H:%M")
        try:
            await context.bot.send_message(
                chat_id=row["chat_id"],
                text=f"⏰ Напоминание: {row['title']} в {dt.strftime(DT_FMT)}",
            )
        finally:
            db.mark_reminded(row["id"])


# ---------------------------------------------------------------------------
# Точка входа
# ---------------------------------------------------------------------------

def main():
    token = os.environ.get("BOT_TOKEN")
    if not token:
        raise RuntimeError(
            "Не найден BOT_TOKEN. Установи переменную окружения (см. README.md)."
        )

    db.init_db()

    app = Application.builder().token(token).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))

    app.add_handler(CommandHandler("add_event", add_event))
    app.add_handler(CommandHandler("schedule", schedule))
    app.add_handler(CommandHandler("del_event", del_event))

    app.add_handler(CommandHandler("add_trip", add_trip))
    app.add_handler(CommandHandler("trips", trips))
    app.add_handler(CommandHandler("trip", trip_detail))
    app.add_handler(CommandHandler("add_stop", add_stop))
    app.add_handler(CommandHandler("del_trip", del_trip))

    # Проверять напоминания каждые 5 минут
    app.job_queue.run_repeating(check_reminders, interval=300, first=10)

    logger.info("Бот запущен.")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
