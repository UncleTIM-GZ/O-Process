"""Tests for MCP Resources."""

from __future__ import annotations

import asyncio
import json
from unittest.mock import patch

import pytest
from fastmcp import FastMCP
from fastmcp.exceptions import ResourceError

from oprocess.db.connection import SCHEMA_SQL
from oprocess.db.queries import get_processes_by_level, search_processes
from oprocess.governance.audit import get_session_log, hash_input, log_invocation
from oprocess.tools.resources import register_resources
from oprocess.tools.serialization import to_json
from oprocess.validators import validate_process_id, validate_session_id


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
        validate_process_id("1.0", resource=True)
        validate_process_id("1.1.2.3", resource=True)

    def test_invalid_process_id(self):
        with pytest.raises(ResourceError):
            validate_process_id("abc", resource=True)
        with pytest.raises(ResourceError):
            validate_process_id("", resource=True)
        with pytest.raises(ResourceError):
            validate_process_id("1..0", resource=True)

    def test_valid_session_id(self):
        validate_session_id("a1b2c3d4-e5f6-4a7b-8c9d-0e1f2a3b4c5d", resource=True)

    def test_invalid_session_id(self):
        with pytest.raises(ResourceError):
            validate_session_id("not-a-uuid", resource=True)
        with pytest.raises(ResourceError):
            validate_session_id("12345678", resource=True)


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
        session_id = "a1b2c3d4-e5f6-4a7b-8c9d-0e1f2a3b4c5d"
        log_invocation(
            db_conn,
            session_id=session_id,
            tool_name="search_process",
            input_hash=hash_input({"query": "test"}),
            lang="zh",
            response_ms=10,
        )
        logs = get_session_log(db_conn, session_id)
        assert len(logs) == 1
        assert logs[0]["tool_name"] == "search_process"

    def test_empty_session(self, db_conn):
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


class TestVecAvailable:
    """P5-7: check_vec_available reports extension status."""

    def test_without_vec(self, populated_db):
        from oprocess.db.connection import check_vec_available

        result = check_vec_available(populated_db)
        assert isinstance(result, bool)


# -- P6-6: Resource endpoint integration tests via FastMCP read_resource --


def _read(app: FastMCP, uri: str) -> str:
    """Synchronous helper to call app.read_resource and extract text."""
    result = asyncio.run(app.read_resource(uri))
    return result.contents[0].content


@pytest.fixture
def _thread_safe_populated_db(tmp_path):
    """Test DB with check_same_thread=False for async read_resource."""
    import sqlite3 as _sqlite3

    from oprocess.db.connection import init_schema

    db_path = tmp_path / "test_res.db"
    conn = _sqlite3.connect(str(db_path), check_same_thread=False)
    conn.row_factory = _sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    init_schema(conn)

    processes = [
        ("1.0", 1, None, "operating", "制定愿景与战略", "Develop Vision and Strategy",
         "为组织确立方向和愿景", "Establishing a direction and vision",
         "Strategy", '["PCF:1.0"]', '["strategy"]', '[]', 1),
        ("1.1", 2, "1.0", "operating", "定义业务概念", "Define business concept",
         "定义业务概念和长期愿景", "Define the business concept",
         "Business", '["PCF:1.1"]', '["strategy"]', '[]', 1),
        ("8.0", 1, None, "management_support", "管理信息技术", "Manage IT",
         "管理信息技术", "Manage IT",
         "IT", '["PCF:8.0"]', '["it"]', '[]', 1),
    ]
    conn.executemany(
        """INSERT INTO processes
        (id, level, parent_id, domain, name_zh, name_en,
         description_zh, description_en, ai_context,
         source, tags, kpi_refs, provenance_eligible)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        processes,
    )
    kpis = [
        ("kpi.1.0.01", "1.0", "战略执行率", "Strategy execution rate",
         "%", None, "Process Efficiency", None, "higher_is_better"),
    ]
    conn.executemany(
        """INSERT INTO kpis
        (id, process_id, name_zh, name_en, unit, formula,
         category, scor_attribute, direction)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        kpis,
    )
    conn.commit()
    yield conn
    conn.close()


@pytest.fixture
def resource_app(_thread_safe_populated_db):
    """FastMCP app with resources registered against thread-safe test DB."""
    app = FastMCP("test-resources")
    with patch(
        "oprocess.tools.resources.get_shared_connection",
        return_value=_thread_safe_populated_db,
    ):
        register_resources(app)
        yield app, _thread_safe_populated_db


class TestEndpointGetProcessResource:
    """P6-6: test get_process_resource handler."""

    def test_existing_process(self, resource_app):
        app, conn = resource_app
        with patch(
            "oprocess.tools.resources.get_shared_connection",
            return_value=conn,
        ):
            text = _read(app, "oprocess://process/1.0")
            parsed = json.loads(text)
            assert parsed["id"] == "1.0"
            assert parsed["name_zh"] == "制定愿景与战略"

    def test_missing_process_raises(self, resource_app):
        app, conn = resource_app
        with patch(
            "oprocess.tools.resources.get_shared_connection",
            return_value=conn,
        ):
            with pytest.raises(ResourceError, match="not found"):
                _read(app, "oprocess://process/99.99")

    def test_invalid_id_raises(self, resource_app):
        app, conn = resource_app
        with patch(
            "oprocess.tools.resources.get_shared_connection",
            return_value=conn,
        ):
            with pytest.raises(ResourceError, match="Invalid process ID"):
                _read(app, "oprocess://process/abc")


class TestEndpointCategoryList:
    def test_returns_categories(self, resource_app):
        app, conn = resource_app
        with patch(
            "oprocess.tools.resources.get_shared_connection",
            return_value=conn,
        ):
            text = _read(app, "oprocess://category/list")
            parsed = json.loads(text)
            assert isinstance(parsed, list)
            assert len(parsed) >= 2
            for cat in parsed:
                assert "id" in cat
                assert "name_zh" in cat


class TestEndpointRoleMapping:
    def test_returns_results(self, resource_app):
        app, conn = resource_app
        with patch(
            "oprocess.tools.resources.get_shared_connection",
            return_value=conn,
        ):
            text = _read(app, "oprocess://role/IT经理")
            parsed = json.loads(text)
            assert isinstance(parsed, list)

    def test_empty_role_raises(self, resource_app):
        app, conn = resource_app
        with patch(
            "oprocess.tools.resources.get_shared_connection",
            return_value=conn,
        ):
            with pytest.raises(ResourceError, match="cannot be empty"):
                _read(app, "oprocess://role/%20%20")


class TestEndpointAuditSession:
    def test_returns_audit_logs(self, resource_app):
        app, conn = resource_app
        session_id = "a1b2c3d4-e5f6-4a7b-8c9d-0e1f2a3b4c5d"
        log_invocation(
            conn,
            session_id=session_id,
            tool_name="test_tool",
            input_hash=hash_input({"q": "test"}),
            lang="zh",
            response_ms=5,
        )
        with patch(
            "oprocess.tools.resources.get_shared_connection",
            return_value=conn,
        ):
            text = _read(
                app,
                f"oprocess://audit/session/{session_id}",
            )
            parsed = json.loads(text)
            assert isinstance(parsed, list)
            assert len(parsed) == 1

    def test_invalid_session_raises(self, resource_app):
        app, conn = resource_app
        with patch(
            "oprocess.tools.resources.get_shared_connection",
            return_value=conn,
        ):
            with pytest.raises(ResourceError, match="Invalid session ID"):
                _read(app, "oprocess://audit/session/bad-id")


class TestEndpointSchema:
    def test_returns_sql(self, resource_app):
        app, _conn = resource_app
        text = _read(app, "oprocess://schema/sqlite")
        assert "CREATE TABLE" in text
        assert "processes" in text


class TestEndpointStats:
    def test_returns_version_and_counts(self, resource_app):
        app, conn = resource_app
        with patch(
            "oprocess.tools.resources.get_shared_connection",
            return_value=conn,
        ):
            text = _read(app, "oprocess://stats")
            parsed = json.loads(text)
            assert parsed["version"] == "0.3.0"
            assert parsed["total_processes"] >= 3
