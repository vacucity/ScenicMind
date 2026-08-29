from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from typing import Any, Iterator

from .settings import DATABASE_PATH


def json_dumps(value: Any) -> str:
    def fallback(item: Any):
        if hasattr(item, "item"):
            return item.item()
        if hasattr(item, "isoformat"):
            return item.isoformat()
        raise TypeError(f"Object of type {type(item).__name__} is not JSON serializable")

    return json.dumps(value, ensure_ascii=False, default=fallback)


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


@contextmanager
def connection() -> Iterator[sqlite3.Connection]:
    db = sqlite3.connect(DATABASE_PATH, timeout=30)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys = ON")
    try:
        yield db
        db.commit()
    finally:
        db.close()


def initialize_database() -> None:
    with connection() as db:
        db.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE COLLATE NOCASE,
                email TEXT NOT NULL UNIQUE COLLATE NOCASE,
                password_hash TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS sessions (
                token_hash TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                created_at TEXT NOT NULL,
                expires_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS analyses (
                id TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                file_name TEXT NOT NULL,
                stored_path TEXT NOT NULL,
                status TEXT NOT NULL,
                error TEXT,
                created_at TEXT NOT NULL,
                completed_at TEXT,
                result_json TEXT,
                importance_json TEXT
            );
            CREATE INDEX IF NOT EXISTS analyses_user_created_idx
                ON analyses(user_id, created_at DESC);
            """
        )


def user_by_username(username: str) -> sqlite3.Row | None:
    with connection() as db:
        return db.execute("SELECT * FROM users WHERE username = ? COLLATE NOCASE", (username,)).fetchone()


def user_by_email(email: str) -> sqlite3.Row | None:
    with connection() as db:
        return db.execute("SELECT * FROM users WHERE email = ? COLLATE NOCASE", (email,)).fetchone()


def create_user(username: str, email: str, password_hash: str) -> sqlite3.Row:
    with connection() as db:
        cursor = db.execute(
            "INSERT INTO users(username, email, password_hash, created_at) VALUES (?, ?, ?, ?)",
            (username, email, password_hash, utc_now()),
        )
        return db.execute("SELECT * FROM users WHERE id = ?", (cursor.lastrowid,)).fetchone()


def create_session(user_id: int, token_hash: str) -> None:
    created_at = datetime.now(UTC)
    expires_at = created_at + timedelta(days=7)
    with connection() as db:
        db.execute(
            "INSERT OR REPLACE INTO sessions(token_hash, user_id, created_at, expires_at) VALUES (?, ?, ?, ?)",
            (token_hash, user_id, created_at.isoformat(), expires_at.isoformat()),
        )


def delete_session(token_hash: str) -> None:
    with connection() as db:
        db.execute("DELETE FROM sessions WHERE token_hash = ?", (token_hash,))


def user_by_session(token_hash: str) -> sqlite3.Row | None:
    with connection() as db:
        row = db.execute(
            """
            SELECT users.* FROM sessions
            JOIN users ON users.id = sessions.user_id
            WHERE sessions.token_hash = ? AND sessions.expires_at > ?
            """,
            (token_hash, utc_now()),
        ).fetchone()
        return row


def create_analysis(analysis_id: str, user_id: int, file_name: str, stored_path: str) -> None:
    with connection() as db:
        db.execute(
            """INSERT INTO analyses(id, user_id, file_name, stored_path, status, created_at)
               VALUES (?, ?, ?, ?, 'processing', ?)""",
            (analysis_id, user_id, file_name, stored_path, utc_now()),
        )


def complete_analysis(analysis_id: str, result: dict[str, Any], importance: dict[str, Any]) -> None:
    with connection() as db:
        db.execute(
            """UPDATE analyses SET status='completed', completed_at=?, result_json=?, importance_json=?
               WHERE id=?""",
            (utc_now(), json_dumps(result), json_dumps(importance), analysis_id),
        )


def fail_analysis(analysis_id: str, error: str) -> None:
    with connection() as db:
        db.execute(
            "UPDATE analyses SET status='failed', completed_at=?, error=? WHERE id=?",
            (utc_now(), error[:1000], analysis_id),
        )


def analysis_by_id(analysis_id: str, user_id: int) -> sqlite3.Row | None:
    with connection() as db:
        return db.execute(
            "SELECT * FROM analyses WHERE id=? AND user_id=?", (analysis_id, user_id)
        ).fetchone()


def latest_analysis(user_id: int) -> sqlite3.Row | None:
    with connection() as db:
        return db.execute(
            "SELECT * FROM analyses WHERE user_id=? ORDER BY created_at DESC LIMIT 1", (user_id,)
        ).fetchone()
