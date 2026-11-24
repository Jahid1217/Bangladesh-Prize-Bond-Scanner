"""SQLite storage layer.

WAL mode + short `BEGIN IMMEDIATE` transactions make the single-writer SQLite
database safe when the phone fires several scan requests concurrently.  The
UNIQUE constraint on `bonds.serial` is the final guard against duplicates.
"""

from __future__ import annotations

import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

from .config import settings

SCHEMA_VERSION = 2

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS schema_meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS bonds (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    serial TEXT NOT NULL UNIQUE,
    raw_text TEXT,
    source TEXT NOT NULL CHECK (source IN ('auto', 'manual')),
    confidence REAL,
    note TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_bonds_created_at ON bonds (created_at DESC);

CREATE TABLE IF NOT EXISTS scan_attempts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    serial TEXT,
    bond_id INTEGER REFERENCES bonds (id) ON DELETE SET NULL,
    status TEXT NOT NULL CHECK (
        status IN ('saved', 'duplicate', 'uncertain', 'failed')
    ),
    confidence REAL,
    raw_text TEXT,
    reason TEXT,
    image_path TEXT,
    processing_ms INTEGER,
    variants TEXT,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_attempts_created_at ON scan_attempts (created_at DESC);
CREATE INDEX IF NOT EXISTS idx_attempts_status ON scan_attempts (status);

CREATE TABLE IF NOT EXISTS duplicate_attempts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    serial TEXT NOT NULL,
    bond_id INTEGER REFERENCES bonds (id) ON DELETE SET NULL,
    confidence REAL,
    raw_text TEXT,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_duplicates_created_at ON duplicate_attempts (created_at DESC);

CREATE TABLE IF NOT EXISTS corrections (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    bond_id INTEGER NOT NULL REFERENCES bonds (id) ON DELETE CASCADE,
    old_serial TEXT NOT NULL,
    new_serial TEXT NOT NULL,
    old_confidence REAL,
    note TEXT,
    corrected_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_corrections_bond ON corrections (bond_id);
"""


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class Database:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._init_lock = threading.Lock()
        self._initialised = False

    # -- connections -----------------------------------------------------
    def connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(
            self.path, timeout=15, isolation_level=None, check_same_thread=False
        )
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("PRAGMA busy_timeout=15000")
        return conn

    @contextmanager
    def connection(self) -> Iterator[sqlite3.Connection]:
        self.init()
        conn = self.connect()
        try:
            yield conn
        finally:
            conn.close()

    @contextmanager
    def transaction(self, immediate: bool = False) -> Iterator[sqlite3.Connection]:
        with self.connection() as conn:
            conn.execute("BEGIN IMMEDIATE" if immediate else "BEGIN")
            try:
                yield conn
            except Exception:
                conn.execute("ROLLBACK")
                raise
            else:
                conn.execute("COMMIT")

    def init(self) -> None:
        if self._initialised:
            return
        with self._init_lock:
            if self._initialised:
                return
            with self.connection_raw() as conn:
                conn.executescript(SCHEMA_SQL)
                # Migration for databases created before attempts stored bond_id.
                columns = {
                    row[1]
                    for row in conn.execute("PRAGMA table_info(scan_attempts)").fetchall()
                }
                if "bond_id" not in columns:
                    conn.execute(
                        "ALTER TABLE scan_attempts ADD COLUMN bond_id INTEGER "
                        "REFERENCES bonds (id) ON DELETE SET NULL"
                    )
                conn.execute(
                    """UPDATE scan_attempts
                       SET bond_id = (SELECT id FROM bonds
                                      WHERE bonds.serial = scan_attempts.serial)
                       WHERE bond_id IS NULL AND serial IS NOT NULL"""
                )
                conn.execute(
                    "INSERT INTO schema_meta (key, value) VALUES ('version', ?) "
                    "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                    (str(SCHEMA_VERSION),),
                )
            self._initialised = True

    @contextmanager
    def connection_raw(self) -> Iterator[sqlite3.Connection]:
        """Connection without triggering schema initialisation (bootstrap)."""
        conn = self.connect()
        try:
            yield conn
        finally:
            conn.close()

    def health(self) -> dict:
        try:
            with self.connection() as conn:
                bonds = conn.execute("SELECT COUNT(*) AS n FROM bonds").fetchone()["n"]
                integrity = conn.execute("PRAGMA quick_check").fetchone()[0]
            return {"ok": integrity == "ok", "bonds": bonds, "path": str(self.path)}
        except Exception as exc:  # pragma: no cover - surfaced through /health
            return {"ok": False, "error": str(exc), "path": str(self.path)}


db = Database(settings.database_path)
