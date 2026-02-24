"""Tests for MCP server tool functions."""

from __future__ import annotations

import pytest

from oprocess.gateway import (
    PassthroughGateway,
    ToolGatewayInterface,
    ToolResponse,
)


class TestGateway:
    def test_passthrough(self):
        gw = PassthroughGateway()
        resp = gw.execute("test", lambda: {"hello": "world"})
        assert isinstance(resp, ToolResponse)
        assert resp.result == {"hello": "world"}
        assert resp.response_ms >= 0
        assert resp.session_id

    def test_session_id(self):
        sid = "a1b2c3d4-e5f6-4a7b-8c9d-0e1f2a3b4c5d"
        gw = PassthroughGateway(session_id=sid)
        resp = gw.execute("test", lambda: None)
        assert resp.session_id == sid

    def test_session_id_full_uuid(self):
        """P2-6: Gateway generates full UUID4 session_id."""
        gw = PassthroughGateway()
        # Full UUID4 is 36 chars (8-4-4-4-12 with dashes)
        assert len(gw.session_id) == 36
        assert gw.session_id.count("-") == 4

    def test_base_gateway_execute(self):
        sid = "b1b2c3d4-e5f6-4a7b-8c9d-0e1f2a3b4c5d"
        gw = ToolGatewayInterface(session_id=sid)
        resp = gw.execute("t", lambda x: x * 2, x=5)
        assert resp.result == 10
        assert resp.session_id == sid

    def test_passthrough_with_audit(self, db_conn):
        from oprocess.governance.audit import get_session_log

        sid = "c1b2c3d4-e5f6-4a7b-8c9d-0e1f2a3b4c5d"
        gw = PassthroughGateway(
            session_id=sid, audit_conn=db_conn,
        )
        resp = gw.execute(
            "search", lambda query, lang: [query], query="q", lang="zh",
        )
        assert resp.result == ["q"]
        logs = get_session_log(db_conn, sid)
        assert len(logs) == 1
        assert logs[0]["tool_name"] == "search"

    def test_passthrough_error_with_audit(self, db_conn):
        from oprocess.governance.audit import get_session_log

        sid = "d1b2c3d4-e5f6-4a7b-8c9d-0e1f2a3b4c5d"
        gw = PassthroughGateway(
            session_id=sid, audit_conn=db_conn,
        )

        def failing():
            msg = "boom"
            raise ValueError(msg)

        with pytest.raises(ValueError, match="boom"):
            gw.execute("bad_tool", failing)

        logs = get_session_log(db_conn, sid)
        assert len(logs) == 1


class TestHealthCheckTool:
    def test_health_check_registered(self):
        import asyncio

        from oprocess.server import mcp

        tools = asyncio.run(mcp.list_tools())
        names = {t.name for t in tools}
        assert "health_check" in names

    def test_health_check_description(self):
        import asyncio

        from oprocess.server import mcp

        tools = asyncio.run(mcp.list_tools())
        hc = next(t for t in tools if t.name == "health_check")
        assert "health" in hc.description.lower()


class TestMultiTransport:
    def test_valid_transports(self):
        from oprocess.server import _VALID_TRANSPORTS

        assert "stdio" in _VALID_TRANSPORTS
        assert "sse" in _VALID_TRANSPORTS
        assert "streamable-http" in _VALID_TRANSPORTS

    def test_main_exists(self):
        from oprocess.server import main

        assert callable(main)

    def test_main_stdio_default(self, monkeypatch):
        """main() with no args → stdio transport."""
        from unittest.mock import MagicMock

        from oprocess import server

        mock_run = MagicMock()
        monkeypatch.setattr(server.mcp, "run", mock_run)
        monkeypatch.setattr("sys.argv", ["oprocess"])
        server.main()
        mock_run.assert_called_once_with(transport="stdio")

    def test_main_sse_transport(self, monkeypatch):
        """main() with --transport sse → sse with host/port/middleware."""
        from unittest.mock import MagicMock

        from oprocess import server

        mock_run = MagicMock()
        monkeypatch.setattr(server.mcp, "run", mock_run)
        monkeypatch.setattr(
            "sys.argv",
            ["oprocess", "--transport", "sse", "--port", "9000"],
        )
        server.main()
        mock_run.assert_called_once()
        call_kwargs = mock_run.call_args.kwargs
        assert call_kwargs["transport"] == "sse"
        assert call_kwargs["host"] == "127.0.0.1"
        assert call_kwargs["port"] == 9000
        assert "middleware" in call_kwargs


class TestStructuredLogging:
    def test_gateway_logs_tool_execute(self, caplog):
        import logging

        sid = "e1b2c3d4-e5f6-4a7b-8c9d-0e1f2a3b4c5d"
        with caplog.at_level(logging.INFO, logger="oprocess"):
            gw = ToolGatewayInterface(session_id=sid)
            gw.execute("my_tool", lambda: 42)
        assert any("tool.execute" in r.message for r in caplog.records)
        log = next(r for r in caplog.records if "tool.execute" in r.message)
        assert log.tool == "my_tool"
        assert log.session_id == sid
        assert hasattr(log, "ms")

    def test_passthrough_logs_tool_execute(self, caplog):
        import logging

        sid = "f1b2c3d4-e5f6-4a7b-8c9d-0e1f2a3b4c5d"
        with caplog.at_level(logging.INFO, logger="oprocess"):
            gw = PassthroughGateway(session_id=sid)
            gw.execute("search", lambda: [])
        assert any("tool.execute" in r.message for r in caplog.records)

    def test_log_level_env(self, monkeypatch):
        from oprocess.server import _configure_logging

        monkeypatch.setenv("LOG_LEVEL", "DEBUG")
        _configure_logging()
        import logging

        oprocess_logger = logging.getLogger("oprocess")
        assert oprocess_logger.getEffectiveLevel() <= logging.DEBUG


class TestToolResponse:
    def test_defaults(self):
        resp = ToolResponse(result={"data": 1})
        assert resp.result == {"data": 1}
        assert resp.provenance_chain == []
        assert resp.session_id == ""
        assert resp.response_ms == 0
