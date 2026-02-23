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

import json
import sqlite3
from pathlib import Path

from oprocess.db.connection import SCHEMA_SQL, get_connection, init_schema
from oprocess.db.queries import (
    count_kpis,
    count_processes,
    get_process,
    get_processes_by_level,
    search_processes,
)
from oprocess.governance.audit import get_session_log

DB_PATH = Path("data/oprocess.db")


def _get_conn() -> sqlite3.Connection:
    conn = get_connection(DB_PATH)
    init_schema(conn)
    return conn


def _to_json(data: object) -> str:
    return json.dumps(data, ensure_ascii=False, indent=2)


def register_resources(mcp) -> None:
    """Register all MCP resource endpoints."""

    @mcp.resource("oprocess://process/{process_id}")
    def get_process_resource(process_id: str) -> str:
        """Get complete information for a single process node."""
        conn = _get_conn()
        try:
            process = get_process(conn, process_id)
            if not process:
                return _to_json(
                    {"error": f"Process {process_id} not found"},
                )
            return _to_json(process)
        finally:
            conn.close()

    @mcp.resource("oprocess://category/list")
    def get_category_list() -> str:
        """Get all top-level (L1) process categories."""
        conn = _get_conn()
        try:
            processes = get_processes_by_level(conn, level=1)
            return _to_json([
                {
                    "id": p["id"],
                    "name_zh": p["name_zh"],
                    "name_en": p["name_en"],
                    "domain": p["domain"],
                }
                for p in processes
            ])
        finally:
            conn.close()

    @mcp.resource("oprocess://role/{role_name}")
    def get_role_mapping(role_name: str) -> str:
        """Get process mappings for a role name via semantic search.

        Uses real-time search; role_mappings table reserved for caching.
        """
        conn = _get_conn()
        try:
            results = search_processes(
                conn, role_name, lang="zh", limit=10,
            )
            return _to_json([
                {
                    "process_id": r["id"],
                    "name_zh": r["name_zh"],
                    "name_en": r["name_en"],
                    "score": r.get("score"),
                }
                for r in results
            ])
        finally:
            conn.close()

    @mcp.resource("oprocess://audit/session/{session_id}")
    def get_audit_session(session_id: str) -> str:
        """Get audit log entries for a specific session."""
        conn = _get_conn()
        try:
            return _to_json(get_session_log(conn, session_id))
        finally:
            conn.close()

    @mcp.resource("oprocess://schema/sqlite")
    def get_schema() -> str:
        """Get the current SQLite schema definition."""
        return SCHEMA_SQL.strip()

    @mcp.resource("oprocess://stats")
    def get_stats() -> str:
        """Get O'Process framework statistics."""
        conn = _get_conn()
        try:
            return _to_json({
                "total_processes": count_processes(conn),
                "total_kpis": count_kpis(conn),
                "version": "0.1.0",
                "sources": [
                    "APQC PCF 7.4", "ITIL 4", "SCOR 12.0", "AI-era",
                ],
            })
        finally:
            conn.close()
