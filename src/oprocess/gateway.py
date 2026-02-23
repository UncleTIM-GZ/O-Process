"""ToolGatewayInterface — mediates all tool execution.

Every MCP tool invocation passes through the gateway, which:
1. Logs the call to SessionAuditLog
2. Measures response time
3. Wraps results in ToolResponse
"""

from __future__ import annotations

import sqlite3
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from oprocess.governance.audit import log_invocation


@dataclass
class ToolResponse:
    """Standard response envelope for all tools."""

    result: Any
    provenance_chain: list[dict] = field(default_factory=list)
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
    """Gateway that wraps, times, and audit-logs calls."""

    def __init__(
        self,
        session_id: str | None = None,
        audit_conn: sqlite3.Connection | None = None,
    ) -> None:
        super().__init__(session_id)
        self.audit_conn = audit_conn

    def execute(
        self,
        tool_name: str,
        func: Callable[..., Any],
        **kwargs: Any,
    ) -> ToolResponse:
        """Execute with timing and optional audit logging."""
        start = time.monotonic()
        error_msg = None
        result = None
        try:
            result = func(**kwargs)
        except Exception as exc:
            error_msg = str(exc)
            raise
        finally:
            elapsed_ms = int((time.monotonic() - start) * 1000)
            if self.audit_conn is not None:
                log_invocation(
                    self.audit_conn,
                    session_id=self.session_id,
                    tool_name=tool_name,
                    input_params={
                        k: v
                        for k, v in kwargs.items()
                        if not isinstance(v, sqlite3.Connection)
                    },
                    output_summary=(
                        f"{len(result)} results"
                        if isinstance(result, list)
                        else None
                    ),
                    response_ms=elapsed_ms,
                    error=error_msg,
                )

        return ToolResponse(
            result=result,
            session_id=self.session_id,
            response_ms=elapsed_ms,
        )
