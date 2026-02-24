"""SessionAuditLog — append-only audit trail for tool invocations.

Failures in audit logging MUST NOT affect the main tool flow.
"""

from __future__ import annotations

import hashlib
import json
import logging
import sqlite3
from datetime import datetime, timezone

from oprocess.validators import validate_session_id

logger = logging.getLogger(__name__)


def hash_input(params: dict) -> str:
    """SHA256 hash of input params, truncated to first 16 hex chars."""
    raw = json.dumps(params, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def log_invocation(
    conn: sqlite3.Connection,
    session_id: str,
    tool_name: str,
    input_hash: str,
    output_node_ids: list[str] | None = None,
    lang: str | None = None,
    response_ms: int | None = None,
    governance_ext: dict | None = None,
    request_id: str | None = None,
) -> None:
    """Append an audit log entry. Never raises.

    If request_id is provided, duplicate request_ids are silently ignored
    (idempotent writes via INSERT OR IGNORE + UNIQUE index).
    """
    try:
        if not validate_session_id(session_id):
            logger.warning(
                "Audit log skipped: invalid session_id format: %s",
                session_id,
            )
            return

        node_ids_json = (
            json.dumps(output_node_ids)
            if output_node_ids is not None
            else None
        )
        gov_json = (
            json.dumps(governance_ext, ensure_ascii=False)
            if governance_ext
            else "{}"
        )
        conn.execute(
            """INSERT OR IGNORE INTO session_audit_log
            (session_id, tool_name, input_hash, output_node_ids,
             lang, response_ms, timestamp, governance_ext, request_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                session_id,
                tool_name,
                input_hash,
                node_ids_json,
                lang,
                response_ms,
                datetime.now(timezone.utc).isoformat(),
                gov_json,
                request_id,
            ),
        )
        conn.commit()
    except Exception:
        logger.warning("Audit log write failed", exc_info=True)


def get_session_log(
    conn: sqlite3.Connection, session_id: str
) -> list[dict]:
    """Retrieve all audit entries for a session."""
    rows = conn.execute(
        """SELECT * FROM session_audit_log
        WHERE session_id = ?
        ORDER BY timestamp""",
        (session_id,),
    ).fetchall()
    return [dict(r) for r in rows]
