"""SQLite audit log for usage stats.

Logs search, ask, index, and delete operations with timestamp, namespace,
and hashed API key.  The database lives at ``~/.locallens/audit.db``.
"""

import logging
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from app.auth import hash_key

logger = logging.getLogger(__name__)

_DB_PATH = Path.home() / ".locallens" / "audit.db"
_lock = threading.Lock()
_conn: sqlite3.Connection | None = None


def _get_conn() -> sqlite3.Connection:
    global _conn
    if _conn is None:
        _DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        _conn = sqlite3.connect(str(_DB_PATH), check_same_thread=False)
        _conn.execute("PRAGMA journal_mode=WAL")
        _conn.execute("""
            CREATE TABLE IF NOT EXISTS audit_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                operation TEXT NOT NULL,
                namespace TEXT NOT NULL DEFAULT 'default',
                api_key_hash TEXT,
                detail TEXT
            )
        """)
        _conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_audit_ts ON audit_log(timestamp)
        """)
        _conn.commit()
    return _conn


def log(
    operation: str,
    namespace: str = "default",
    api_key: Optional[str] = None,
    detail: Optional[str] = None,
) -> None:
    """Write an audit record."""
    ts = datetime.now(timezone.utc).isoformat()
    key_hash = hash_key(api_key) if api_key else None
    with _lock:
        conn = _get_conn()
        conn.execute(
            "INSERT INTO audit_log (timestamp, operation, namespace, api_key_hash, detail) VALUES (?, ?, ?, ?, ?)",
            (ts, operation, namespace, key_hash, detail),
        )
        conn.commit()


def query(
    page: int = 1,
    page_size: int = 50,
    operation: Optional[str] = None,
    namespace: Optional[str] = None,
) -> dict:
    """Return paginated audit log entries.

    Returns ``{"entries": [...], "total": int, "page": int, "page_size": int}``.
    """
    with _lock:
        conn = _get_conn()
        where_parts: list[str] = []
        params: list = []
        if operation:
            where_parts.append("operation = ?")
            params.append(operation)
        if namespace:
            where_parts.append("namespace = ?")
            params.append(namespace)

        where = ""
        if where_parts:
            where = "WHERE " + " AND ".join(where_parts)

        total = conn.execute(f"SELECT COUNT(*) FROM audit_log {where}", params).fetchone()[0]

        offset = (page - 1) * page_size
        rows = conn.execute(
            f"SELECT id, timestamp, operation, namespace, api_key_hash, detail FROM audit_log {where} ORDER BY id DESC LIMIT ? OFFSET ?",
            params + [page_size, offset],
        ).fetchall()

    entries = [
        {
            "id": r[0],
            "timestamp": r[1],
            "operation": r[2],
            "namespace": r[3],
            "api_key_hash": r[4],
            "detail": r[5],
        }
        for r in rows
    ]
    return {"entries": entries, "total": total, "page": page, "page_size": page_size}
