"""
Слой работы с базой данных (SQLite).
Хранит:
- события расписания (events)
- поездки (trips) и их пункты маршрута (trip_items)
"""

import sqlite3
from contextlib import contextmanager
from datetime import datetime

DB_PATH = "assistant.db"


@contextmanager
def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    with get_conn() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id INTEGER NOT NULL,
                title TEXT NOT NULL,
                event_dt TEXT NOT NULL,      -- ISO datetime "YYYY-MM-DD HH:MM"
                reminded INTEGER DEFAULT 0,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS trips (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id INTEGER NOT NULL,
                destination TEXT NOT NULL,
                start_date TEXT NOT NULL,   -- YYYY-MM-DD
                end_date TEXT NOT NULL,     -- YYYY-MM-DD
                notes TEXT DEFAULT '',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS trip_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                trip_id INTEGER NOT NULL,
                item_dt TEXT NOT NULL,      -- ISO datetime "YYYY-MM-DD HH:MM"
                description TEXT NOT NULL,
                FOREIGN KEY (trip_id) REFERENCES trips(id) ON DELETE CASCADE
            )
            """
        )


# ---------- EVENTS ----------

def add_event(chat_id: int, title: str, event_dt: datetime) -> int:
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO events (chat_id, title, event_dt) VALUES (?, ?, ?)",
            (chat_id, title, event_dt.strftime("%Y-%m-%d %H:%M")),
        )
        return cur.lastrowid


def list_events(chat_id: int, upcoming_only: bool = True):
    with get_conn() as conn:
        if upcoming_only:
            now = datetime.now().strftime("%Y-%m-%d %H:%M")
            rows = conn.execute(
                "SELECT * FROM events WHERE chat_id=? AND event_dt>=? ORDER BY event_dt ASC",
                (chat_id, now),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM events WHERE chat_id=? ORDER BY event_dt ASC",
                (chat_id,),
            ).fetchall()
        return rows


def list_events_for_date(chat_id: int, day):
    """События на конкретный календарный день (datetime.date)."""
    with get_conn() as conn:
        start = day.strftime("%Y-%m-%d 00:00")
        end = day.strftime("%Y-%m-%d 23:59")
        rows = conn.execute(
            "SELECT * FROM events WHERE chat_id=? AND event_dt>=? AND event_dt<=? ORDER BY event_dt ASC",
            (chat_id, start, end),
        ).fetchall()
        return rows


def delete_event(chat_id: int, event_id: int) -> bool:
    with get_conn() as conn:
        cur = conn.execute(
            "DELETE FROM events WHERE id=? AND chat_id=?", (event_id, chat_id)
        )
        return cur.rowcount > 0


def get_due_unreminded_events(window_minutes: int = 60):
    """События, которые наступят в ближайшие window_minutes и о которых ещё не напоминали."""
    with get_conn() as conn:
        now = datetime.now()
        rows = conn.execute(
            "SELECT * FROM events WHERE reminded=0 AND event_dt >= ? ORDER BY event_dt ASC",
            (now.strftime("%Y-%m-%d %H:%M"),),
        ).fetchall()
        due = []
        for r in rows:
            dt = datetime.strptime(r["event_dt"], "%Y-%m-%d %H:%M")
            delta_min = (dt - now).total_seconds() / 60
            if 0 <= delta_min <= window_minutes:
                due.append(r)
        return due


def mark_reminded(event_id: int):
    with get_conn() as conn:
        conn.execute("UPDATE events SET reminded=1 WHERE id=?", (event_id,))


# ---------- TRIPS ----------

def add_trip(chat_id: int, destination: str, start_date: str, end_date: str, notes: str = "") -> int:
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO trips (chat_id, destination, start_date, end_date, notes) VALUES (?, ?, ?, ?, ?)",
            (chat_id, destination, start_date, end_date, notes),
        )
        return cur.lastrowid


def list_trips(chat_id: int):
    with get_conn() as conn:
        return conn.execute(
            "SELECT * FROM trips WHERE chat_id=? ORDER BY start_date ASC", (chat_id,)
        ).fetchall()


def get_trip(chat_id: int, trip_id: int):
    with get_conn() as conn:
        return conn.execute(
            "SELECT * FROM trips WHERE id=? AND chat_id=?", (trip_id, chat_id)
        ).fetchone()


def delete_trip(chat_id: int, trip_id: int) -> bool:
    with get_conn() as conn:
        conn.execute("DELETE FROM trip_items WHERE trip_id=?", (trip_id,))
        cur = conn.execute(
            "DELETE FROM trips WHERE id=? AND chat_id=?", (trip_id, chat_id)
        )
        return cur.rowcount > 0


def add_trip_item(trip_id: int, item_dt: datetime, description: str) -> int:
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO trip_items (trip_id, item_dt, description) VALUES (?, ?, ?)",
            (trip_id, item_dt.strftime("%Y-%m-%d %H:%M"), description),
        )
        return cur.lastrowid


def list_trip_items(trip_id: int):
    with get_conn() as conn:
        return conn.execute(
            "SELECT * FROM trip_items WHERE trip_id=? ORDER BY item_dt ASC", (trip_id,)
        ).fetchall()
