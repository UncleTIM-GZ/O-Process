"""Tests for MCP Resources."""

from __future__ import annotations

import json

import pytest
from fastmcp.exceptions import ResourceError

from oprocess.db.connection import SCHEMA_SQL
from oprocess.db.queries import get_processes_by_level, search_processes
from oprocess.governance.audit import hash_input, log_invocation
from oprocess.tools.resources import _validate_process_id, _validate_session_id
from oprocess.tools.serialization import to_json


class TestProcessResource:
    def test_existing_process(self, populated_db):
        from oprocess.db.queries import get_process

        result = get_process(populated_db, "1.0")
        assert result is not None
        output = to_json(result)
        parsed = json.loads(output)
        assert parsed["id"] == "1.0"
        assert parsed["name_zh"] == "制定愿景与战略"

    def test_missing_process(self, populated_db):
        from oprocess.db.queries import get_process

        result = get_process(populated_db, "99.99")
        assert result is None


class TestResourceValidation:
    """P2-4: URI parameter validation."""

    def test_valid_process_id(self):
        _validate_process_id("1.0")
        _validate_process_id("1.1.2.3")

    def test_invalid_process_id(self):
        with pytest.raises(ResourceError):
            _validate_process_id("abc")
        with pytest.raises(ResourceError):
            _validate_process_id("")
        with pytest.raises(ResourceError):
            _validate_process_id("1..0")

    def test_valid_session_id(self):
        _validate_session_id("a1b2c3d4-e5f6-4a7b-8c9d-0e1f2a3b4c5d")

    def test_invalid_session_id(self):
        with pytest.raises(ResourceError):
            _validate_session_id("not-a-uuid")
        with pytest.raises(ResourceError):
            _validate_session_id("12345678")


class TestCategoryList:
    def test_returns_level1_only(self, populated_db):
        categories = get_processes_by_level(populated_db, level=1)
        assert len(categories) >= 2  # 1.0 and 8.0
        for cat in categories:
            assert cat["level"] == 1

    def test_category_fields(self, populated_db):
        categories = get_processes_by_level(populated_db, level=1)
        for cat in categories:
            assert "id" in cat
            assert "name_zh" in cat
            assert "name_en" in cat
            assert "domain" in cat


class TestRoleMapping:
    def test_search_returns_results(self, populated_db):
        results = search_processes(
            populated_db, "战略", lang="zh", limit=10,
        )
        assert len(results) >= 1

    def test_result_fields(self, populated_db):
        results = search_processes(
            populated_db, "IT", lang="en", limit=5,
        )
        for r in results:
            assert "id" in r
            assert "name_zh" in r
            assert "name_en" in r


class TestAuditSessionResource:
    def test_returns_session_logs(self, db_conn):
        # Use a valid UUID4 session_id
        session_id = "a1b2c3d4-e5f6-4a7b-8c9d-0e1f2a3b4c5d"
        log_invocation(
            db_conn,
            session_id=session_id,
            tool_name="search_process",
            input_hash=hash_input({"query": "test"}),
            lang="zh",
            response_ms=10,
        )
        from oprocess.governance.audit import get_session_log

        logs = get_session_log(db_conn, session_id)
        assert len(logs) == 1
        assert logs[0]["tool_name"] == "search_process"

    def test_empty_session(self, db_conn):
        from oprocess.governance.audit import get_session_log

        logs = get_session_log(db_conn, "nonexistent")
        assert logs == []


class TestSchemaResource:
    def test_returns_schema_sql(self):
        schema = SCHEMA_SQL.strip()
        assert "CREATE TABLE" in schema
        assert "session_audit_log" in schema
        assert "role_mappings" in schema
        assert "processes" in schema


class TestStatsResource:
    def test_stats_fields(self, populated_db):
        from oprocess.db.queries import count_kpis, count_processes

        stats = {
            "total_processes": count_processes(populated_db),
            "total_kpis": count_kpis(populated_db),
        }
        assert stats["total_processes"] >= 4
        assert stats["total_kpis"] >= 2
