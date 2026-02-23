"""Tests for MCP server tool functions."""

from __future__ import annotations

from oprocess.gateway import PassthroughGateway, ToolResponse


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


class TestToolResponse:
    def test_defaults(self):
        resp = ToolResponse(result={"data": 1})
        assert resp.result == {"data": 1}
        assert resp.provenance_chain == []
        assert resp.session_id == ""
        assert resp.response_ms == 0
