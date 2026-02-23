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
        gw = PassthroughGateway(session_id="test-123")
        resp = gw.execute("test", lambda: None)
        assert resp.session_id == "test-123"

    def test_base_gateway_execute(self):
        gw = ToolGatewayInterface(session_id="base-1")
        resp = gw.execute("t", lambda x: x * 2, x=5)
        assert resp.result == 10
        assert resp.session_id == "base-1"

    def test_passthrough_with_audit(self, db_conn):
        from oprocess.governance.audit import get_session_log

        gw = PassthroughGateway(
            session_id="audit-test", audit_conn=db_conn,
        )
        resp = gw.execute(
            "search", lambda query, lang: [query], query="q", lang="zh",
        )
        assert resp.result == ["q"]
        logs = get_session_log(db_conn, "audit-test")
        assert len(logs) == 1
        assert logs[0]["tool_name"] == "search"

    def test_passthrough_error_with_audit(self, db_conn):
        from oprocess.governance.audit import get_session_log

        gw = PassthroughGateway(
            session_id="err-test", audit_conn=db_conn,
        )

        def failing():
            msg = "boom"
            raise ValueError(msg)

        with pytest.raises(ValueError, match="boom"):
            gw.execute("bad_tool", failing)

        logs = get_session_log(db_conn, "err-test")
        assert len(logs) == 1


class TestToolResponse:
    def test_defaults(self):
        resp = ToolResponse(result={"data": 1})
        assert resp.result == {"data": 1}
        assert resp.provenance_chain == []
        assert resp.session_id == ""
        assert resp.response_ms == 0
