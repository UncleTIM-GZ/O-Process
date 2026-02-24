"""SQLite database connection management."""

from __future__ import annotations

import atexit
import logging
import sqlite3
from pathlib import Path

from oprocess.db.embedder import GEMINI_DIM

logger = logging.getLogger(__name__)

DEFAULT_DB_PATH = Path("data/oprocess.db")

_shared_conn: sqlite3.Connection | None = None


def get_connection(db_path: Path | None = None) -> sqlite3.Connection:
    """Get a SQLite connection with WAL mode and row factory."""
    path = db_path or DEFAULT_DB_PATH
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    _load_sqlite_vec(conn)
    return conn


def _load_sqlite_vec(conn: sqlite3.Connection) -> None:
    """Load sqlite-vec extension if available."""
    try:
        import sqlite_vec

        conn.enable_load_extension(True)
        sqlite_vec.load(conn)
        conn.enable_load_extension(False)
    except ImportError:
        pass  # sqlite-vec not installed
    except Exception as exc:
        logger.debug("Failed to load sqlite-vec: %s", type(exc).__name__)


def get_shared_connection(
    db_path: Path | None = None,
) -> sqlite3.Connection:
    """Get or create shared SQLite connection (singleton).

    For process-lifetime use by MCP tools/resources.
    Tests should use get_connection() with tmp_path instead.
    """
    global _shared_conn
    if _shared_conn is not None:
        return _shared_conn
    _shared_conn = get_connection(db_path)
    init_schema(_shared_conn)
    atexit.register(_close_shared)
    return _shared_conn


def _close_shared() -> None:
    """Close shared connection on process exit."""
    global _shared_conn
    if _shared_conn is not None:
        try:
            _shared_conn.close()
        except sqlite3.ProgrammingError:
            pass  # Thread-safety error during shutdown — harmless
        _shared_conn = None


def init_schema(conn: sqlite3.Connection) -> None:
    """Create all tables if they don't exist, then apply migrations."""
    conn.executescript(SCHEMA_SQL)
    _create_vec_table(conn)
    _migrate_audit_request_id(conn)


def _create_vec_table(conn: sqlite3.Connection) -> None:
    """Create sqlite-vec virtual table for vector search."""
    try:
        conn.execute(
            "CREATE VIRTUAL TABLE IF NOT EXISTS vec_processes "
            f"USING vec0(process_id TEXT PRIMARY KEY, embedding float[{GEMINI_DIM}])",
        )
        conn.commit()
    except Exception as exc:
        logger.debug("sqlite-vec unavailable: %s", type(exc).__name__)


def check_vec_available(conn: sqlite3.Connection) -> bool:
    """Check if sqlite-vec extension is loaded and functional."""
    try:
        conn.execute("SELECT vec_version()")
        return True
    except Exception:
        return False


def _migrate_audit_request_id(conn: sqlite3.Connection) -> None:
    """Add request_id column + unique index if missing (v0.2.0)."""
    cols = {
        row[1]
        for row in conn.execute(
            "PRAGMA table_info(session_audit_log)",
        ).fetchall()
    }
    if "request_id" not in cols:
        conn.execute(
            "ALTER TABLE session_audit_log ADD COLUMN request_id TEXT",
        )
    conn.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_audit_request_id "
        "ON session_audit_log(request_id) "
        "WHERE request_id IS NOT NULL",
    )
    conn.commit()


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
    governance_ext TEXT DEFAULT '{}',
    request_id TEXT
);

CREATE INDEX IF NOT EXISTS idx_audit_session ON session_audit_log(session_id);
CREATE INDEX IF NOT EXISTS idx_audit_timestamp ON session_audit_log(timestamp);

CREATE TABLE IF NOT EXISTS role_mappings (
    role_name TEXT NOT NULL,
    process_id TEXT NOT NULL,
    confidence REAL,
    created_at TEXT DEFAULT (datetime('now')),
    PRIMARY KEY (role_name, process_id),
    FOREIGN KEY (process_id) REFERENCES processes(id)
);

CREATE INDEX IF NOT EXISTS idx_role_mappings_role ON role_mappings(role_name);

CREATE TRIGGER IF NOT EXISTS no_update_audit
BEFORE UPDATE ON session_audit_log
BEGIN SELECT RAISE(ABORT, 'audit log is append-only'); END;

CREATE TRIGGER IF NOT EXISTS no_delete_audit
BEFORE DELETE ON session_audit_log
BEGIN SELECT RAISE(ABORT, 'audit log is append-only'); END;
"""
