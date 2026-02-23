"""SQLite database connection management."""

from __future__ import annotations

import sqlite3
from pathlib import Path

DEFAULT_DB_PATH = Path("data/oprocess.db")


def get_connection(db_path: Path | None = None) -> sqlite3.Connection:
    """Get a SQLite connection with WAL mode and row factory."""
    path = db_path or DEFAULT_DB_PATH
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_schema(conn: sqlite3.Connection) -> None:
    """Create all tables if they don't exist."""
    conn.executescript(SCHEMA_SQL)


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS processes (
    id TEXT PRIMARY KEY,
    level INTEGER NOT NULL,
    parent_id TEXT,
    domain TEXT NOT NULL,
    name_zh TEXT NOT NULL,
    name_en TEXT NOT NULL,
    description_zh TEXT NOT NULL DEFAULT '',
    description_en TEXT NOT NULL DEFAULT '',
    ai_context TEXT NOT NULL DEFAULT '',
    source TEXT NOT NULL DEFAULT '[]',
    tags TEXT NOT NULL DEFAULT '[]',
    kpi_refs TEXT NOT NULL DEFAULT '[]',
    provenance_eligible INTEGER NOT NULL DEFAULT 1,
    FOREIGN KEY (parent_id) REFERENCES processes(id)
);

CREATE INDEX IF NOT EXISTS idx_processes_parent ON processes(parent_id);
CREATE INDEX IF NOT EXISTS idx_processes_level ON processes(level);
CREATE INDEX IF NOT EXISTS idx_processes_domain ON processes(domain);

CREATE TABLE IF NOT EXISTS kpis (
    id TEXT PRIMARY KEY,
    process_id TEXT NOT NULL,
    name_zh TEXT NOT NULL,
    name_en TEXT NOT NULL,
    unit TEXT,
    formula TEXT,
    category TEXT,
    scor_attribute TEXT,
    direction TEXT,
    FOREIGN KEY (process_id) REFERENCES processes(id)
);

CREATE INDEX IF NOT EXISTS idx_kpis_process ON kpis(process_id);

CREATE TABLE IF NOT EXISTS process_embeddings (
    process_id TEXT PRIMARY KEY,
    embedding BLOB NOT NULL,
    text_hash TEXT NOT NULL,
    FOREIGN KEY (process_id) REFERENCES processes(id)
);

CREATE TABLE IF NOT EXISTS session_audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    tool_name TEXT NOT NULL,
    input_hash TEXT NOT NULL,
    output_node_ids TEXT,
    lang TEXT,
    response_ms INTEGER,
    timestamp TEXT NOT NULL,
    governance_ext TEXT DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_audit_session ON session_audit_log(session_id);
CREATE INDEX IF NOT EXISTS idx_audit_timestamp ON session_audit_log(timestamp);

CREATE TRIGGER IF NOT EXISTS no_update_audit
BEFORE UPDATE ON session_audit_log
BEGIN SELECT RAISE(ABORT, 'audit log is append-only'); END;

CREATE TRIGGER IF NOT EXISTS no_delete_audit
BEFORE DELETE ON session_audit_log
BEGIN SELECT RAISE(ABORT, 'audit log is append-only'); END;
"""
