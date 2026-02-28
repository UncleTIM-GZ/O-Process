"""Direct tests for MCP tool registration functions via mcp.call_tool().

These tests exercise the tool functions end-to-end through the MCP layer,
validating input validation, JSON response structure, and error handling.

Requires the production database at data/oprocess.db. Tests skip otherwise.
"""

from __future__ import annotations

import asyncio
import json
import sqlite3
from pathlib import Path
from unittest.mock import patch

import pytest

from oprocess.db.connection import init_schema
from oprocess.server import mcp

REAL_DB = Path("data/oprocess.db")


@pytest.fixture(autouse=True)
def _reset_gateways():
    """Reset the shared gateway singleton between tests."""
    import oprocess.gateway as gw

    old = gw._shared_gateway
    gw._shared_gateway = None
    yield
    gw._shared_gateway = old


@pytest.fixture
def _thread_safe_conn():
    """Patch shared connection to be thread-safe for mcp.call_tool()."""
    if not REAL_DB.exists():
        pytest.skip("Production database not found at data/oprocess.db")
    conn = sqlite3.connect(str(REAL_DB), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        import sqlite_vec

        conn.enable_load_extension(True)
        sqlite_vec.load(conn)
        conn.enable_load_extension(False)
    except (ImportError, Exception):
        pass
    init_schema(conn)
    with patch(
        "oprocess.db.connection.get_shared_connection", return_value=conn,
    ):
        yield conn
    conn.close()


def _call(tool_name: str, args: dict | None = None) -> dict:
    """Synchronous helper to call an MCP tool and parse JSON result."""
    result = asyncio.run(mcp.call_tool(tool_name, args or {}))
    text = result.content[0].text
    return json.loads(text)


class TestHealthCheckTool:
    """Health check (renamed from ping to avoid MCP built-in conflict)."""

    def test_returns_status_ok(self, _thread_safe_conn):
        data = _call("health_check")
        assert data["status"] == "ok"
        assert data["server"] == "O'Process"

    def test_returns_counts(self, _thread_safe_conn):
        data = _call("health_check")
        assert data["total_processes"] >= 2325
        assert data["total_kpis"] >= 3910

    def test_vec_available_field(self, _thread_safe_conn):
        """P5-7: health_check reports sqlite-vec availability."""
        data = _call("health_check")
        assert "vec_available" in data
        assert isinstance(data["vec_available"], bool)

    def test_semantic_search_field(self, _thread_safe_conn):
        """health_check reports semantic search availability."""
        data = _call("health_check")
        assert "semantic_search_available" in data
        assert isinstance(data["semantic_search_available"], bool)


class TestSearchProcessTool:
    def test_returns_valid_structure(self, _thread_safe_conn):
        data = _call("search_process", {"query": "供应链"})
        assert "result" in data
        assert "provenance_chain" in data
        assert "session_id" in data
        assert "response_ms" in data

    def test_returns_results(self, _thread_safe_conn):
        data = _call("search_process", {"query": "战略"})
        results = data["result"]
        assert isinstance(results, list)
        assert len(results) > 0

    def test_lang_en(self, _thread_safe_conn):
        data = _call(
            "search_process", {"query": "strategy", "lang": "en"},
        )
        assert "result" in data

    def test_with_limit(self, _thread_safe_conn):
        data = _call("search_process", {"query": "管理", "limit": 3})
        results = data["result"]
        assert len(results) <= 3


class TestGetProcessTreeTool:
    def test_valid_id(self, _thread_safe_conn):
        data = _call("get_process_tree", {"process_id": "1.0"})
        assert data["result"] is not None
        assert data["result"]["id"] == "1.0"

    def test_with_depth(self, _thread_safe_conn):
        data = _call(
            "get_process_tree",
            {"process_id": "1.0", "max_depth": 2},
        )
        assert "children" in data["result"]

    def test_not_found_raises(self, _thread_safe_conn):
        """P0-1: get_process_tree must raise ToolError for invalid IDs."""
        with pytest.raises(Exception):
            _call("get_process_tree", {"process_id": "99.99"})


class TestGetKpiSuggestionsTool:
    def test_returns_kpis(self, _thread_safe_conn):
        data = _call("get_kpi_suggestions", {"process_id": "1.0"})
        result = data["result"]
        assert "kpis" in result
        assert "count" in result
        assert isinstance(result["kpis"], list)

    def test_provenance_present(self, _thread_safe_conn):
        data = _call("get_kpi_suggestions", {"process_id": "1.0"})
        assert len(data["provenance_chain"]) >= 1

    def test_not_found_raises(self, _thread_safe_conn):
        with pytest.raises(Exception):
            _call("get_kpi_suggestions", {"process_id": "99.99"})


class TestCompareProcessesTool:
    def test_compare_two(self, _thread_safe_conn):
        data = _call(
            "compare_processes",
            {"process_ids": "1.0, 8.0"},
        )
        assert data["result"] is not None


class TestGetResponsibilitiesTool:
    def test_json_format(self, _thread_safe_conn):
        data = _call(
            "get_responsibilities",
            {"process_id": "1.0", "output_format": "json"},
        )
        result = data["result"]
        assert "process" in result
        assert "hierarchy" in result

    def test_markdown_format(self, _thread_safe_conn):
        data = _call(
            "get_responsibilities",
            {"process_id": "1.0", "output_format": "markdown"},
        )
        assert isinstance(data["result"], str)
        assert "#" in data["result"]

    def test_provenance_present(self, _thread_safe_conn):
        data = _call("get_responsibilities", {"process_id": "1.0"})
        assert len(data["provenance_chain"]) >= 1


class TestMapRoleToProcessesTool:
    def test_returns_results(self, _thread_safe_conn):
        data = _call(
            "map_role_to_processes",
            {"role_description": "IT经理"},
        )
        assert "result" in data
        assert isinstance(data["result"], list)


class TestExportResponsibilityDocTool:
    def test_single_process(self, _thread_safe_conn):
        data = _call(
            "export_responsibility_doc",
            {"process_ids": "1.0"},
        )
        assert data["result"] is not None
        assert len(data["provenance_chain"]) >= 1

    def test_multiple_processes(self, _thread_safe_conn):
        data = _call(
            "export_responsibility_doc",
            {"process_ids": "1.0, 8.0"},
        )
        assert data["result"] is not None
