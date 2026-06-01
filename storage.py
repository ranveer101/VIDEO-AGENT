import hashlib
import hmac
import json
import secrets
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path


DB_PATH = Path(__file__).resolve().parent / "video_mind.db"
TOKEN_TTL_DAYS = 7


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with get_connection() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                email TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS auth_tokens (
                token TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS analyses (
                id TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL,
                video_name TEXT NOT NULL,
                created_at TEXT NOT NULL,
                status TEXT NOT NULL,
                source TEXT NOT NULL,
                language TEXT NOT NULL,
                content_type TEXT NOT NULL,
                session_id TEXT,
                result_json TEXT,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
            """
        )


def now_label() -> str:
    return datetime.now().strftime("%d %b %Y, %I:%M %p")


def now_iso() -> str:
    return datetime.utcnow().isoformat(timespec="seconds")


def parse_iso(value: str):
    try:
        return datetime.fromisoformat(value)
    except (TypeError, ValueError):
        return None


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 120_000)
    return f"{salt}:{digest.hex()}"


def verify_password(password: str, stored_hash: str) -> bool:
    try:
        salt, digest = stored_hash.split(":", 1)
    except ValueError:
        return False
    test = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 120_000)
    return hmac.compare_digest(test.hex(), digest)


def create_user(name: str, email: str, password: str):
    with get_connection() as conn:
        cursor = conn.execute(
            "INSERT INTO users (name, email, password_hash, created_at) VALUES (?, ?, ?, ?)",
            (name.strip(), email.strip().lower(), hash_password(password), now_label()),
        )
        row = conn.execute(
            "SELECT id, name, email, created_at FROM users WHERE id = ?",
            (cursor.lastrowid,),
        ).fetchone()
        return dict(row) if row else None


def get_user_by_email(email: str):
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM users WHERE email = ?", (email.strip().lower(),)).fetchone()
        return dict(row) if row else None


def get_user_by_id(user_id: int):
    with get_connection() as conn:
        row = conn.execute("SELECT id, name, email, created_at FROM users WHERE id = ?", (user_id,)).fetchone()
        return dict(row) if row else None


def create_token(user_id: int) -> str:
    token = secrets.token_urlsafe(32)
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO auth_tokens (token, user_id, created_at) VALUES (?, ?, ?)",
            (token, user_id, now_iso()),
        )
    return token


def get_user_by_token(token: str):
    if not token:
        return None
    with get_connection() as conn:
        token_row = conn.execute(
            "SELECT created_at FROM auth_tokens WHERE token = ?",
            (token,),
        ).fetchone()
        if not token_row:
            return None

        created_at = parse_iso(token_row["created_at"])
        if created_at and datetime.utcnow() - created_at > timedelta(days=TOKEN_TTL_DAYS):
            conn.execute("DELETE FROM auth_tokens WHERE token = ?", (token,))
            return None

        row = conn.execute(
            """
            SELECT users.id, users.name, users.email, users.created_at
            FROM auth_tokens
            JOIN users ON users.id = auth_tokens.user_id
            WHERE auth_tokens.token = ?
            """,
            (token,),
        ).fetchone()
        return dict(row) if row else None


def delete_token(token: str) -> None:
    with get_connection() as conn:
        conn.execute("DELETE FROM auth_tokens WHERE token = ?", (token,))


def save_analysis(entry: dict) -> None:
    with get_connection() as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO analyses
            (id, user_id, video_name, created_at, status, source, language, content_type, session_id, result_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                entry["id"],
                entry["user_id"],
                entry["video_name"],
                entry["created_at"],
                entry["status"],
                entry["source"],
                entry["language"],
                entry["content_type"],
                entry.get("session_id"),
                json.dumps(entry.get("result")) if entry.get("result") else None,
            ),
        )


def list_recent_analyses(user_id: int, limit: int = 5) -> list[dict]:
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT id, video_name, created_at, status, source, language, content_type, session_id
            FROM analyses
            WHERE user_id = ?
            ORDER BY rowid DESC
            LIMIT ?
            """,
            (user_id, limit),
        ).fetchall()
        return [dict(row) for row in rows]


def get_analysis(user_id: int, analysis_id: str):
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM analyses WHERE user_id = ? AND id = ?",
            (user_id, analysis_id),
        ).fetchone()
        if not row:
            return None
        item = dict(row)
        item["result"] = json.loads(item["result_json"]) if item.get("result_json") else None
        return item
