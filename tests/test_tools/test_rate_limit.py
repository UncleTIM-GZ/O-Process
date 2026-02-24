"""Tests for RateLimitMiddleware."""

from __future__ import annotations

from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest
from mcp.shared.exceptions import McpError

from oprocess.tools.rate_limit import RateLimitMiddleware


def _make_context(client_id: str | None = None):
    """Create a mock MiddlewareContext."""
    ctx = MagicMock()
    if client_id:
        ctx.fastmcp_context.client_id = client_id
    else:
        ctx.fastmcp_context = None
    return ctx


class TestRateLimitMiddleware:
    def test_allows_normal_calls(self):
        rl = RateLimitMiddleware(max_calls=5, window_seconds=60)
        for _ in range(5):
            rl._check_rate("client1")

    def test_blocks_over_limit(self):
        rl = RateLimitMiddleware(max_calls=3, window_seconds=60)
        for _ in range(3):
            rl._check_rate("client1")
        with pytest.raises(McpError):
            rl._check_rate("client1")

    def test_separate_clients(self):
        rl = RateLimitMiddleware(max_calls=2, window_seconds=60)
        rl._check_rate("client1")
        rl._check_rate("client1")
        # client2 should still be allowed
        rl._check_rate("client2")
        # client1 is now over limit
        with pytest.raises(McpError):
            rl._check_rate("client1")

    def test_window_expiry_restores_access(self):
        rl = RateLimitMiddleware(max_calls=2, window_seconds=60)
        # Manually inject old timestamps
        past = datetime.now() - timedelta(seconds=120)
        rl._calls["client1"] = [past, past]
        # Old calls should be pruned
        rl._check_rate("client1")

    def test_get_client_id_from_context(self):
        rl = RateLimitMiddleware()
        ctx = _make_context("test-client")
        assert rl._get_client_id(ctx) == "test-client"

    def test_get_client_id_default(self):
        rl = RateLimitMiddleware()
        ctx = _make_context(None)
        assert rl._get_client_id(ctx) == "_default"

    @pytest.mark.anyio
    async def test_on_call_tool_passes_through(self):
        rl = RateLimitMiddleware(max_calls=10, window_seconds=60)
        ctx = _make_context("c1")
        call_next = AsyncMock(return_value="result")
        result = await rl.on_call_tool(ctx, call_next)
        assert result == "result"
        call_next.assert_awaited_once_with(ctx)

    @pytest.mark.anyio
    async def test_on_call_tool_blocks_over_limit(self):
        rl = RateLimitMiddleware(max_calls=1, window_seconds=60)
        ctx = _make_context("c1")
        call_next = AsyncMock(return_value="result")
        await rl.on_call_tool(ctx, call_next)
        with pytest.raises(McpError):
            await rl.on_call_tool(ctx, call_next)
