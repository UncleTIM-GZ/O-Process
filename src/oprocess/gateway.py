"""ToolGatewayInterface — mediates all tool execution.

Every MCP tool invocation passes through the gateway, which:
1. Logs the call to SessionAuditLog
2. Measures response time
3. Wraps results in ToolResponse
"""

from __future__ import annotations

import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ToolResponse:
    """Standard response envelope for all tools."""

    result: Any
    provenance_chain: list[str] = field(default_factory=list)
    session_id: str = ""
    response_ms: int = 0


class ToolGatewayInterface:
    """Base gateway interface for tool execution."""

    def __init__(self, session_id: str | None = None) -> None:
        self.session_id = session_id or str(uuid.uuid4())[:8]

    def execute(
        self,
        tool_name: str,
        func: Callable[..., Any],
        **kwargs: Any,
    ) -> ToolResponse:
        """Execute a tool function through the gateway."""
        start = time.monotonic()
        result = func(**kwargs)
        elapsed_ms = int((time.monotonic() - start) * 1000)

        return ToolResponse(
            result=result,
            session_id=self.session_id,
            response_ms=elapsed_ms,
        )


class PassthroughGateway(ToolGatewayInterface):
    """Minimal gateway that just wraps and times calls."""

    pass
