"""
Tiny local SQLite store. Its only job: remember which reminders have
already been sent so the agent never nags you twice for the same
event + offset, even across restarts.
"""
import sqlite3
import threading
from contextlib import contextmanager


class Storage:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self._lock = threading.Lock()
        self._init_schema()

    @contextmanager
    def _conn(self):
        conn = sqlite3.connect(self.db_path)
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def _init_schema(self):
        with self._lock, self._conn() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS sent_reminders (
                    item_id TEXT NOT NULL,
                    offset_minutes INTEGER NOT NULL,
                    sent_at TEXT NOT NULL,
                    PRIMARY KEY (item_id, offset_minutes)
                )
                """
            )

    def already_sent(self, item_id: str, offset_minutes: int) -> bool:
        with self._lock, self._conn() as conn:
            row = conn.execute(
                "SELECT 1 FROM sent_reminders WHERE item_id = ? AND offset_minutes = ?",
                (item_id, offset_minutes),
            ).fetchone()
            return row is not None

    def mark_sent(self, item_id: str, offset_minutes: int):
        with self._lock, self._conn() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO sent_reminders (item_id, offset_minutes, sent_at) "
                "VALUES (?, ?, datetime('now'))",
                (item_id, offset_minutes),
            )

    def cleanup_older_than(self, days: int = 30):
        """Housekeeping so the table doesn't grow forever."""
        with self._lock, self._conn() as conn:
            conn.execute(
                "DELETE FROM sent_reminders WHERE sent_at < datetime('now', ?)",
                (f"-{days} days",),
            )
