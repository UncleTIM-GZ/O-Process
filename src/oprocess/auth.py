"""Bearer token authentication for HTTP transport.

When OPROCESS_API_KEY is set, HTTP requests must include:
    Authorization: Bearer <token>

When not set, all requests are allowed (stdio mode safe).
"""

from __future__ import annotations

import logging
import os

logger = logging.getLogger("oprocess")


def get_api_key() -> str | None:
    """Read API key from environment. None means auth disabled."""
    return os.environ.get("OPROCESS_API_KEY") or None


def verify_token(token: str) -> bool:
    """Verify a bearer token against the configured API key.

    Returns True if:
    - No API key configured (auth disabled), or
    - Token matches the configured key.
    """
    expected = get_api_key()
    if not expected:
        return True
    return token == expected


class BearerAuthMiddleware:
    """ASGI middleware for Bearer token auth.

    Checks Authorization header on every request.
    Skips auth if OPROCESS_API_KEY is not configured.
    """

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] not in ("http", "websocket"):
            await self.app(scope, receive, send)
            return

        api_key = get_api_key()
        if not api_key:
            await self.app(scope, receive, send)
            return

        headers = dict(scope.get("headers", []))
        auth_header = headers.get(b"authorization", b"").decode()

        if auth_header.startswith("Bearer "):
            token = auth_header[7:]
            if token == api_key:
                await self.app(scope, receive, send)
                return

        logger.warning("auth.rejected", extra={"path": scope.get("path")})
        await self._send_401(send)

    async def _send_401(self, send):
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
