import sqlite3
from pathlib import Path
from typing import List, Optional
from datetime import datetime

BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / "manager.db"


def now_iso() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


def get_connection() -> sqlite3.Connection:
    first_init = not DB_PATH.exists()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    if first_init:
        init_db(conn)
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS bots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            repo_url TEXT,
            local_path TEXT NOT NULL,
            entrypoint TEXT NOT NULL,
            discord_token TEXT NOT NULL,
            db_uri TEXT,
            status TEXT NOT NULL DEFAULT 'stopped',
            process_pid INTEGER,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )
    conn.commit()


def create_bot(
    name: str,
    local_path: str,
    entrypoint: str,
    discord_token: str,
    repo_url: Optional[str] = None,
    db_uri: Optional[str] = None,
) -> int:
    created = now_iso()
    with get_connection() as conn:
        cursor = conn.execute(
            """
            INSERT INTO bots (
                name, repo_url, local_path, entrypoint,
                discord_token, db_uri, status,
                process_pid, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, 'stopped', NULL, ?, ?)
            """,
            (name, repo_url, local_path, entrypoint, discord_token, db_uri, created, created),
        )
        conn.commit()
        return int(cursor.lastrowid)


def list_bots() -> List[sqlite3.Row]:
    with get_connection() as conn:
        cursor = conn.execute(
            "SELECT * FROM bots ORDER BY name"
        )
        return cursor.fetchall()


def get_bot_by_id(bot_id: int) -> Optional[sqlite3.Row]:
    with get_connection() as conn:
        cursor = conn.execute(
            "SELECT * FROM bots WHERE id = ?",
            (bot_id,),
        )
        row = cursor.fetchone()
        return row


def get_bot_by_name(name: str) -> Optional[sqlite3.Row]:
    with get_connection() as conn:
        cursor = conn.execute(
            "SELECT * FROM bots WHERE name = ?",
            (name,),
        )
        row = cursor.fetchone()
        return row


def update_bot_status_and_pid(
    bot_id: int,
    status: str,
    process_pid: Optional[int],
) -> None:
    updated = now_iso()
    with get_connection() as conn:
        conn.execute(
            """
            UPDATE bots
            SET status = ?, process_pid = ?, updated_at = ?
            WHERE id = ?
            """,
            (status, process_pid, updated, bot_id),
        )
        conn.commit()
