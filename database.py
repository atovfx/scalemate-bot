"""
Database module for Scalemate Bot — SQLite storage for tasks, notes, reminders & preferences.
"""

import sqlite3
import os
from datetime import datetime

DB_PATH = os.getenv("DATABASE_PATH", "scalemate.db")


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db():
    conn = get_connection()
    c = conn.cursor()

    c.execute("""
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            done INTEGER DEFAULT 0,
            created_at TEXT DEFAULT (datetime('now')),
            done_at TEXT
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS notes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            content TEXT NOT NULL,
            tag TEXT DEFAULT 'general',
            created_at TEXT DEFAULT (datetime('now'))
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS reminders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            chat_id INTEGER NOT NULL,
            message TEXT NOT NULL,
            remind_at TEXT NOT NULL,
            sent INTEGER DEFAULT 0,
            created_at TEXT DEFAULT (datetime('now'))
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS user_prefs (
            user_id INTEGER PRIMARY KEY,
            model TEXT DEFAULT 'gpt-4o',
            system_prompt TEXT DEFAULT 'Tu es Scalemate, un assistant personnel intelligent et stylé. Tu réponds de manière concise, claire et bien formatée. Tu utilises des emojis avec parcimonie pour rendre les messages agréables.'
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS conversations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            created_at TEXT DEFAULT (datetime('now'))
        )
    """)

    conn.commit()
    conn.close()


# ── Tasks ──────────────────────────────────────────────

def add_task(user_id: int, title: str) -> int:
    conn = get_connection()
    c = conn.cursor()
    c.execute("INSERT INTO tasks (user_id, title) VALUES (?, ?)", (user_id, title))
    conn.commit()
    task_id = c.lastrowid
    conn.close()
    return task_id


def get_tasks(user_id: int, show_done: bool = False):
    conn = get_connection()
    if show_done:
        rows = conn.execute(
            "SELECT * FROM tasks WHERE user_id = ? ORDER BY done ASC, created_at DESC",
            (user_id,),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM tasks WHERE user_id = ? AND done = 0 ORDER BY created_at DESC",
            (user_id,),
        ).fetchall()
    conn.close()
    return rows


def complete_task(user_id: int, task_id: int) -> bool:
    conn = get_connection()
    c = conn.cursor()
    c.execute(
        "UPDATE tasks SET done = 1, done_at = datetime('now') WHERE id = ? AND user_id = ?",
        (task_id, user_id),
    )
    conn.commit()
    changed = c.rowcount > 0
    conn.close()
    return changed


def delete_task(user_id: int, task_id: int) -> bool:
    conn = get_connection()
    c = conn.cursor()
    c.execute("DELETE FROM tasks WHERE id = ? AND user_id = ?", (task_id, user_id))
    conn.commit()
    changed = c.rowcount > 0
    conn.close()
    return changed


# ── Notes ──────────────────────────────────────────────

def add_note(user_id: int, content: str, tag: str = "general") -> int:
    conn = get_connection()
    c = conn.cursor()
    c.execute(
        "INSERT INTO notes (user_id, content, tag) VALUES (?, ?, ?)",
        (user_id, content, tag),
    )
    conn.commit()
    note_id = c.lastrowid
    conn.close()
    return note_id


def get_notes(user_id: int, tag: str = None):
    conn = get_connection()
    if tag:
        rows = conn.execute(
            "SELECT * FROM notes WHERE user_id = ? AND tag = ? ORDER BY created_at DESC",
            (user_id, tag),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM notes WHERE user_id = ? ORDER BY created_at DESC",
            (user_id,),
        ).fetchall()
    conn.close()
    return rows


def delete_note(user_id: int, note_id: int) -> bool:
    conn = get_connection()
    c = conn.cursor()
    c.execute("DELETE FROM notes WHERE id = ? AND user_id = ?", (note_id, user_id))
    conn.commit()
    changed = c.rowcount > 0
    conn.close()
    return changed


# ── Reminders ──────────────────────────────────────────

def add_reminder(user_id: int, chat_id: int, message: str, remind_at: str) -> int:
    conn = get_connection()
    c = conn.cursor()
    c.execute(
        "INSERT INTO reminders (user_id, chat_id, message, remind_at) VALUES (?, ?, ?, ?)",
        (user_id, chat_id, message, remind_at),
    )
    conn.commit()
    reminder_id = c.lastrowid
    conn.close()
    return reminder_id


def get_pending_reminders():
    conn = get_connection()
    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    rows = conn.execute(
        "SELECT * FROM reminders WHERE sent = 0 AND remind_at <= ?", (now,)
    ).fetchall()
    conn.close()
    return rows


def mark_reminder_sent(reminder_id: int):
    conn = get_connection()
    conn.execute("UPDATE reminders SET sent = 1 WHERE id = ?", (reminder_id,))
    conn.commit()
    conn.close()


def get_user_reminders(user_id: int):
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM reminders WHERE user_id = ? AND sent = 0 ORDER BY remind_at ASC",
        (user_id,),
    ).fetchall()
    conn.close()
    return rows


def delete_reminder(user_id: int, reminder_id: int) -> bool:
    conn = get_connection()
    c = conn.cursor()
    c.execute(
        "DELETE FROM reminders WHERE id = ? AND user_id = ?", (reminder_id, user_id)
    )
    conn.commit()
    changed = c.rowcount > 0
    conn.close()
    return changed


# ── User Preferences ──────────────────────────────────

def get_user_model(user_id: int) -> str:
    conn = get_connection()
    row = conn.execute(
        "SELECT model FROM user_prefs WHERE user_id = ?", (user_id,)
    ).fetchone()
    conn.close()
    if row:
        return row["model"]
    return "gpt-4o"


def set_user_model(user_id: int, model: str):
    conn = get_connection()
    conn.execute(
        """INSERT INTO user_prefs (user_id, model) VALUES (?, ?)
           ON CONFLICT(user_id) DO UPDATE SET model = excluded.model""",
        (user_id, model),
    )
    conn.commit()
    conn.close()


def get_system_prompt(user_id: int) -> str:
    conn = get_connection()
    row = conn.execute(
        "SELECT system_prompt FROM user_prefs WHERE user_id = ?", (user_id,)
    ).fetchone()
    conn.close()
    if row:
        return row["system_prompt"]
    return "Tu es Scalemate, un assistant personnel intelligent et stylé. Tu réponds de manière concise, claire et bien formatée."


# ── Conversation History ──────────────────────────────

def save_message(user_id: int, role: str, content: str):
    conn = get_connection()
    conn.execute(
        "INSERT INTO conversations (user_id, role, content) VALUES (?, ?, ?)",
        (user_id, role, content),
    )
    # Keep only the last 20 messages per user
    conn.execute("""
        DELETE FROM conversations WHERE id NOT IN (
            SELECT id FROM conversations WHERE user_id = ?
            ORDER BY created_at DESC LIMIT 20
        ) AND user_id = ?
    """, (user_id, user_id))
    conn.commit()
    conn.close()


def get_conversation(user_id: int):
    conn = get_connection()
    rows = conn.execute(
        "SELECT role, content FROM conversations WHERE user_id = ? ORDER BY created_at ASC",
        (user_id,),
    ).fetchall()
    conn.close()
    return [{"role": row["role"], "content": row["content"]} for row in rows]


def clear_conversation(user_id: int):
    conn = get_connection()
    conn.execute("DELETE FROM conversations WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()
