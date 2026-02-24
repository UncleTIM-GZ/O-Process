"""Per-client rate limiter for MCP tool calls.

Implements MCP Spec MUST: "Servers MUST rate limit tool invocations."
Uses FastMCP Middleware to intercept tool calls before execution.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from datetime import datetime, timedelta

from fastmcp.server.middleware import CallNext, Middleware, MiddlewareContext
from mcp import types as mt
from mcp.shared.exceptions import McpError
from mcp.types import ErrorData

logger = logging.getLogger("oprocess")

_RATE_LIMIT_CODE = -32000


class RateLimitMiddleware(Middleware):
    """Per-client rate limiter for MCP tool calls."""

    def __init__(
        self,
        max_calls: int = 60,
        window_seconds: int = 60,
    ) -> None:
        self.max_calls = max_calls
        self.window = timedelta(seconds=window_seconds)
        self._calls: dict[str, list[datetime]] = defaultdict(list)

    def _get_client_id(self, context: MiddlewareContext) -> str:
        """Extract client identifier from middleware context."""
        if context.fastmcp_context and context.fastmcp_context.client_id:
            return context.fastmcp_context.client_id
        return "_default"

    def _check_rate(self, client_id: str) -> None:
        """Check and enforce rate limit for a client."""
        now = datetime.now()
        cutoff = now - self.window
        calls = self._calls[client_id]
        # Prune expired entries
        self._calls[client_id] = [t for t in calls if t > cutoff]
        if len(self._calls[client_id]) >= self.max_calls:
            logger.warning(
                "rate_limit.exceeded",
                extra={"client_id": client_id},
            )
            raise McpError(
                ErrorData(
                    code=_RATE_LIMIT_CODE,
                    message=(
                        f"Rate limit exceeded: {self.max_calls} calls "
                        f"per {self.window.seconds}s"
                    ),
                ),
            )
        self._calls[client_id].append(now)

    async def on_call_tool(
        self,
        context: MiddlewareContext[mt.CallToolRequestParams],
        call_next: CallNext,
    ):
        """Intercept tool calls to enforce rate limits."""
        client_id = self._get_client_id(context)
        self._check_rate(client_id)
        return await call_next(context)
