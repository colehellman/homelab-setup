"""
SQLite state tracking: run log and alert dedup.
DB lives at /var/lib/homelab-agent/state.db
"""

import hashlib
import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

DB_PATH = os.environ.get("AGENT_DB_PATH", "/var/lib/homelab-agent/state.db")


def _connect() -> sqlite3.Connection:
    Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with _connect() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS runs (
                id      INTEGER PRIMARY KEY AUTOINCREMENT,
                ts      DATETIME DEFAULT CURRENT_TIMESTAMP,
                mode    TEXT NOT NULL,
                success INTEGER NOT NULL DEFAULT 1,
                summary TEXT
            );

            CREATE TABLE IF NOT EXISTS alerts_seen (
                fingerprint TEXT PRIMARY KEY,
                first_seen  DATETIME NOT NULL,
                last_seen   DATETIME NOT NULL,
                count       INTEGER NOT NULL DEFAULT 1
            );
        """)


def log_run(mode: str, success: bool, summary: str) -> int:
    with _connect() as conn:
        cur = conn.execute(
            "INSERT INTO runs (mode, success, summary) VALUES (?, ?, ?)",
            (mode, int(success), summary)
        )
        return cur.lastrowid


def is_duplicate_alert(labels: dict, window_minutes: int = 60) -> bool:
    """Return True if we've seen this alert fingerprint within the last N minutes."""
    fp = hashlib.sha256(json.dumps(labels, sort_keys=True).encode()).hexdigest()
    with _connect() as conn:
        row = conn.execute(
            """SELECT last_seen FROM alerts_seen
               WHERE fingerprint = ?
               AND datetime(last_seen) > datetime('now', ?)""",
            (fp, f"-{window_minutes} minutes")
        ).fetchone()
        if row:
            conn.execute(
                "UPDATE alerts_seen SET last_seen = CURRENT_TIMESTAMP, count = count + 1 WHERE fingerprint = ?",
                (fp,)
            )
            return True
        conn.execute(
            """INSERT INTO alerts_seen (fingerprint, first_seen, last_seen)
               VALUES (?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
               ON CONFLICT(fingerprint) DO UPDATE
               SET last_seen = CURRENT_TIMESTAMP, count = count + 1""",
            (fp,)
        )
        return False


def recent_runs(mode: str, limit: int = 5) -> list[dict]:
    with _connect() as conn:
        rows = conn.execute(
            "SELECT ts, success, summary FROM runs WHERE mode = ? ORDER BY ts DESC LIMIT ?",
            (mode, limit)
        ).fetchall()
        return [dict(r) for r in rows]
