import hashlib
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS documents (
    sha256       TEXT PRIMARY KEY,
    path         TEXT NOT NULL,
    path_history TEXT NOT NULL DEFAULT '[]',
    masked_path  TEXT,
    scanned_at   TEXT NOT NULL,
    gate_result  TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS annotations (
    sha256     TEXT PRIMARY KEY REFERENCES documents(sha256),
    doc_type   TEXT,
    summary    TEXT,
    comments   TEXT,
    facts      TEXT,
    updated_at TEXT
);
"""


def file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def connect(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    return conn


def lookup(conn: sqlite3.Connection, sha256: str) -> sqlite3.Row | None:
    return conn.execute(
        "SELECT * FROM documents WHERE sha256 = ?", (sha256,)).fetchone()


def record(conn: sqlite3.Connection, sha256: str, path: str,
           masked_path: str | None, gate_result: str) -> None:
    """Insert or update the row for this hash. A changed path goes to path_history."""
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    row = lookup(conn, sha256)
    if row is None:
        conn.execute(
            "INSERT INTO documents (sha256, path, masked_path, scanned_at, gate_result)"
            " VALUES (?, ?, ?, ?, ?)",
            (sha256, path, masked_path, now, gate_result))
    else:
        history = json.loads(row["path_history"])
        if row["path"] != path:
            history.append(row["path"])
        conn.execute(
            "UPDATE documents SET path = ?, path_history = ?, masked_path = ?,"
            " scanned_at = ?, gate_result = ? WHERE sha256 = ?",
            (path, json.dumps(history), masked_path, now, gate_result, sha256))
    conn.commit()
