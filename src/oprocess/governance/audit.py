"""SessionAuditLog — append-only audit trail for tool invocations.

Failures in audit logging MUST NOT affect the main tool flow.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone


def log_invocation(
    conn: sqlite3.Connection,
    session_id: str,
    tool_name: str,
    input_params: dict,
    output_summary: str | None = None,
    response_ms: int | None = None,
    error: str | None = None,
) -> None:
    """Append an audit log entry. Never raises."""
    try:
        conn.execute(
            """INSERT INTO audit_log
            (session_id, timestamp, tool_name, input_params,
             output_summary, response_ms, error)
            VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                session_id,
                datetime.now(timezone.utc).isoformat(),
                tool_name,
                json.dumps(input_params, ensure_ascii=False),
                output_summary,
                response_ms,
                error,
            ),
        )
        conn.commit()
    except Exception:
        pass  # Audit failures must not affect main flow


def get_session_log(
    conn: sqlite3.Connection, session_id: str
) -> list[dict]:
    """Retrieve all audit entries for a session."""
    rows = conn.execute(
        """SELECT * FROM audit_log
        WHERE session_id = ?
        ORDER BY timestamp""",
        (session_id,),
    ).fetchall()
    return [dict(r) for r in rows]


def get_recent_logs(
    conn: sqlite3.Connection, limit: int = 50
) -> list[dict]:
    """Retrieve recent audit entries across all sessions."""
    rows = conn.execute(
        "SELECT * FROM audit_log ORDER BY timestamp DESC LIMIT ?",
        (limit,),
    ).fetchall()
    return [dict(r) for r in rows]
