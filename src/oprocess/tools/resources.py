"""MCP Resource implementations — registered via register_resources(mcp).

PRD v2.0 §4.2 requires 5 resources:
- oprocess://process/{id}
- oprocess://category/list
- oprocess://role/{role_name}
- oprocess://audit/session/{session_id}
- oprocess://schema/sqlite

Plus the existing oprocess://stats (retained for convenience).

Note: oprocess://role/{role_name} uses real-time semantic search.
The `role_mappings` table is reserved for future caching layer.
"""

from __future__ import annotations

import re

from fastmcp.exceptions import ResourceError

from oprocess.db.connection import SCHEMA_SQL, get_shared_connection
from oprocess.db.queries import (
    count_kpis,
    count_processes,
    get_process,
    get_processes_by_level,
    search_processes,
)
from oprocess.governance.audit import get_session_log
from oprocess.tools.serialization import to_json

_PROCESS_ID_RE = re.compile(r"^\d+(\.\d+)*$")
_SESSION_ID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$",
    re.IGNORECASE,
)


def _validate_process_id(process_id: str) -> None:
    """Validate process_id URI parameter format."""
    if not _PROCESS_ID_RE.match(process_id):
        msg = f"Invalid process ID format: {process_id}"
        raise ResourceError(msg)


def _validate_session_id(session_id: str) -> None:
    """Validate session_id URI parameter format (UUID4)."""
    if not _SESSION_ID_RE.match(session_id):
        msg = f"Invalid session ID format: {session_id}"
        raise ResourceError(msg)


def register_resources(mcp) -> None:
    """Register all MCP resource endpoints."""

    @mcp.resource("oprocess://process/{process_id}", mime_type="application/json")
    def get_process_resource(process_id: str) -> str:
        """Get complete information for a single process node."""
        _validate_process_id(process_id)
        conn = get_shared_connection()
        process = get_process(conn, process_id)
        if not process:
            msg = f"Process {process_id} not found"
            raise ResourceError(msg)
        return to_json(process)

    @mcp.resource("oprocess://category/list", mime_type="application/json")
    def get_category_list() -> str:
        """Get all top-level (L1) process categories."""
        conn = get_shared_connection()
        processes = get_processes_by_level(conn, level=1)
        return to_json([
            {
                "id": p["id"],
                "name_zh": p["name_zh"],
                "name_en": p["name_en"],
                "domain": p["domain"],
            }
            for p in processes
        ])

    @mcp.resource("oprocess://role/{role_name}", mime_type="application/json")
    def get_role_mapping(role_name: str) -> str:
        """Get process mappings for a role name via semantic search.

        Uses real-time search; role_mappings table reserved for caching.
        """
        conn = get_shared_connection()
        results = search_processes(
            conn, role_name, lang="zh", limit=10,
        )
        return to_json([
            {
                "process_id": r["id"],
                "name_zh": r["name_zh"],
                "name_en": r["name_en"],
                "score": r.get("score"),
            }
            for r in results
        ])

    @mcp.resource("oprocess://audit/session/{session_id}", mime_type="application/json")
    def get_audit_session(session_id: str) -> str:
        """Get audit log entries for a specific session."""
        _validate_session_id(session_id)
        conn = get_shared_connection()
        return to_json(get_session_log(conn, session_id))

    @mcp.resource("oprocess://schema/sqlite", mime_type="text/plain")
    def get_schema() -> str:
        """Get the current SQLite schema definition."""
        return SCHEMA_SQL.strip()

    @mcp.resource("oprocess://stats", mime_type="application/json")
    def get_stats() -> str:
        """Get O'Process framework statistics."""
        conn = get_shared_connection()
        return to_json({
            "total_processes": count_processes(conn),
            "total_kpis": count_kpis(conn),
            "version": "0.3.0",
            "sources": [
                "APQC PCF 7.4", "ITIL 4", "SCOR 12.0", "AI-era",
            ],
        })
