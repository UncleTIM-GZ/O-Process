"""ToolGatewayInterface — mediates all tool execution.

Every MCP tool invocation passes through the gateway, which:
1. Logs the call to SessionAuditLog
2. Measures response time
3. Wraps results in ToolResponse
"""

from __future__ import annotations

import logging
import sqlite3
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from oprocess.governance.audit import hash_input, log_invocation

logger = logging.getLogger("oprocess")


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
        self.session_id = session_id or str(uuid.uuid4())

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

        logger.info(
            "tool.execute",
            extra={
                "tool": tool_name,
                "session_id": self.session_id,
                "ms": elapsed_ms,
            },
        )

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
        result = None
        error_info: str | None = None
        try:
            result = func(**kwargs)
        except Exception as exc:
            error_info = str(exc)
            raise
        finally:
            elapsed_ms = int((time.monotonic() - start) * 1000)
            if self.audit_conn is not None:
                serializable = {
                    k: v
                    for k, v in kwargs.items()
                    if not isinstance(v, sqlite3.Connection)
                }
                gov_ext = (
                    {"error": error_info} if error_info else None
                )
                log_invocation(
                    self.audit_conn,
                    session_id=self.session_id,
                    tool_name=tool_name,
                    input_hash=hash_input(serializable),
                    lang=kwargs.get("lang"),
                    response_ms=elapsed_ms,
                    governance_ext=gov_ext,
                )
            logger.info(
                "tool.execute",
                extra={
                    "tool": tool_name,
                    "session_id": self.session_id,
                    "ms": elapsed_ms,
                    "error": error_info,
                },
            )

        return ToolResponse(
            result=result,
            session_id=self.session_id,
            response_ms=elapsed_ms,
        )


_shared_gateway: PassthroughGateway | None = None


def get_shared_gateway() -> PassthroughGateway:
    """Return the process-wide gateway singleton.

    Both registry.py and search.py share this instance so that
    all tool calls within a session use the same session_id.
    """
    global _shared_gateway
    if _shared_gateway is None:
        from oprocess.db.connection import get_shared_connection

        conn = get_shared_connection()
        _shared_gateway = PassthroughGateway(audit_conn=conn)
    return _shared_gateway
