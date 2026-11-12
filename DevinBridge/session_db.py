"""Read-side evidence from Devin's own local stores.

- ``%APPDATA%\\devin\\cli\\sessions.db`` (SQLite/WAL): session rows with
  model, working dir, activity, titles. Read via a bounded read-only WAL connection so the
  live WAL database is never copied or mutated.
- ``%APPDATA%\\devin\\summaries\\<id>.md``: per-session summaries —
  the implementation summary a session produced.

These are independent evidence channels: a coordinator never has to
trust what an agent *said* — it can check what was persisted.
"""
from __future__ import annotations

import os
import shutil
import sqlite3
import tempfile
from pathlib import Path
from typing import Any

CLI_DIR = Path(os.path.expandvars(r"%APPDATA%\devin\cli"))
SUMMARIES_DIR = Path(os.path.expandvars(r"%APPDATA%\devin\summaries"))
SESSIONS_DB = CLI_DIR / "sessions.db"


def _snapshot_db() -> sqlite3.Connection | None:
    """Open Devin's WAL database read-only, with no multi-GB copies."""
    if not SESSIONS_DB.is_file():
        return None
    try:
        db = sqlite3.connect(SESSIONS_DB.as_uri() + '?mode=ro',
                             uri=True, timeout=3)
        db.execute('PRAGMA query_only=ON')
        return db
    except (OSError, sqlite3.Error):
        return None

def list_sessions(limit: int = 50) -> list[dict[str, Any]]:
    db = _snapshot_db()
    if db is None:
        return []
    try:
        rows = db.execute(
            "select id, working_directory, backend_type, model, agent_mode,"
            " created_at, last_activity_at, title, hidden"
            " from sessions order by last_activity_at desc limit ?",
            (limit,)).fetchall()
    except sqlite3.Error:
        return []
    finally:
        db.close()
    cols = ["id", "working_directory", "backend_type", "model",
            "agent_mode", "created_at", "last_activity_at", "title", "hidden"]
    return [dict(zip(cols, r)) for r in rows]


def get_session(session_id: str) -> dict[str, Any] | None:
    for s in list_sessions(limit=1000):
        if s["id"] == session_id:
            return s
    return None


def session_messages(session_id: str, limit: int = 40) -> list[dict[str, Any]]:
    db = _snapshot_db()
    if db is None:
        return []
    try:
        rows = db.execute(
            "select chat_message from message_nodes where session_id=?"
            " order by row_id desc limit ?", (session_id, limit)).fetchall()
    except sqlite3.Error:
        return []
    finally:
        db.close()
    import json as _json
    out = []
    for (blob,) in rows:
        try:
            out.append(_json.loads(blob))
        except ValueError:
            continue
    return out


def session_last_text(session_id: str) -> str:
    """Last assistant/user text content — cheap completion sniffing."""
    for m in session_messages(session_id, limit=10):
        c = str(m.get("content", ""))
        if c.strip():
            return c[:4000]
    return ""


def session_summary(session_id: str) -> str:
    p = SUMMARIES_DIR / f"{session_id}.md"
    try:
        return p.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""
