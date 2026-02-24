"""Bearer token authentication for HTTP transport.

When OPROCESS_API_KEY is set, HTTP requests must include:
    Authorization: Bearer <token>

When not set, all requests are allowed (stdio mode safe).

Origin validation: Only requests from allowed origins (or no Origin header)
are accepted. Configure via OPROCESS_ALLOWED_ORIGINS (comma-separated).
"""

from __future__ import annotations

import hmac
import logging
import os
from collections.abc import Callable
from typing import Any

logger = logging.getLogger("oprocess")


def get_api_key() -> str | None:
    """Read API key from environment. None means auth disabled."""
    return os.environ.get("OPROCESS_API_KEY") or None


def get_allowed_origins() -> set[str] | None:
    """Read allowed origins from environment. None means no restriction."""
    raw = os.environ.get("OPROCESS_ALLOWED_ORIGINS", "").strip()
    if not raw:
        return None
    return {o.strip().rstrip("/") for o in raw.split(",") if o.strip()}


def verify_token(token: str) -> bool:
    """Verify a bearer token against the configured API key.

    Returns True if:
    - No API key configured (auth disabled), or
    - Token matches the configured key.
    """
    expected = get_api_key()
    if not expected:
        return True
    return hmac.compare_digest(token.encode(), expected.encode())


def verify_origin(origin: str | None) -> bool:
    """Verify request Origin header against allowed origins.

    Returns True if:
    - No allowed origins configured (unrestricted), or
    - No Origin header present (same-origin or non-browser), or
    - Origin is in the allowed list.
    """
    allowed = get_allowed_origins()
    if allowed is None:
        return True
    if origin is None:
        return True
    return origin.rstrip("/") in allowed


class BearerAuthMiddleware:
    """ASGI middleware for Bearer token auth + Origin validation.

    Checks Authorization header on every request.
    Skips auth if OPROCESS_API_KEY is not configured.
    Validates Origin header when OPROCESS_ALLOWED_ORIGINS is set.
    """

    def __init__(self, app: Any) -> None:
        self.app = app

    async def __call__(
        self,
        scope: dict[str, Any],
        receive: Callable,
        send: Callable,
    ) -> None:
        if scope["type"] not in ("http", "websocket"):
            await self.app(scope, receive, send)
            return

        headers = dict(scope.get("headers", []))

        # Origin validation (when configured)
        origin = headers.get(b"origin", b"").decode() or None
        if not verify_origin(origin):
            logger.warning(
                "auth.origin_rejected",
                extra={"origin": origin, "path": scope.get("path")},
            )
            await self._send_403(send)
            return

        # Skip bearer auth if no API key configured
        if not get_api_key():
            await self.app(scope, receive, send)
            return

        auth_header = headers.get(b"authorization", b"").decode()

        if auth_header.startswith("Bearer "):
            token = auth_header[7:]
            if verify_token(token):
                await self.app(scope, receive, send)
                return

        logger.warning("auth.rejected", extra={"path": scope.get("path")})
        await self._send_401(send)

    async def _send_401(self, send: Callable) -> None:
        await send({
            "type": "http.response.start",
            "status": 401,
            "headers": [
                [b"content-type", b"application/json"],
                [b"www-authenticate", b"Bearer"],
            ],
        })
        await send({
            "type": "http.response.body",
            "body": b'{"error":"unauthorized","message":"Bearer token required"}',
        })

    async def _send_403(self, send: Callable) -> None:
        await send({
            "type": "http.response.start",
            "status": 403,
            "headers": [
                [b"content-type", b"application/json"],
            ],
        })
        await send({
            "type": "http.response.body",
            "body": b'{"error":"forbidden","message":"Origin not allowed"}',
        })
