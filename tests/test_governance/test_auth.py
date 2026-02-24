"""Tests for Bearer token authentication and Origin validation."""

from __future__ import annotations

import asyncio
import os

from oprocess.auth import (
    BearerAuthMiddleware,
    get_allowed_origins,
    get_api_key,
    verify_origin,
    verify_token,
)


class TestVerifyToken:
    def test_no_key_configured_allows_any(self, monkeypatch):
        monkeypatch.delenv("OPROCESS_API_KEY", raising=False)
        assert verify_token("anything") is True
        assert verify_token("") is True

    def test_correct_token(self, monkeypatch):
        monkeypatch.setenv("OPROCESS_API_KEY", "secret-123")
        assert verify_token("secret-123") is True

    def test_wrong_token(self, monkeypatch):
        monkeypatch.setenv("OPROCESS_API_KEY", "secret-123")
        assert verify_token("wrong") is False

    def test_empty_token_rejected(self, monkeypatch):
        monkeypatch.setenv("OPROCESS_API_KEY", "secret-123")
        assert verify_token("") is False


class TestGetApiKey:
    def test_returns_none_when_unset(self, monkeypatch):
        monkeypatch.delenv("OPROCESS_API_KEY", raising=False)
        assert get_api_key() is None

    def test_returns_none_for_empty(self, monkeypatch):
        monkeypatch.setenv("OPROCESS_API_KEY", "")
        assert get_api_key() is None

    def test_returns_key(self, monkeypatch):
        monkeypatch.setenv("OPROCESS_API_KEY", "my-key")
        assert get_api_key() == "my-key"


class TestGetAllowedOrigins:
    """P6-7: Coverage for get_allowed_origins()."""

    def test_returns_none_when_unset(self, monkeypatch):
        monkeypatch.delenv("OPROCESS_ALLOWED_ORIGINS", raising=False)
        assert get_allowed_origins() is None

    def test_returns_none_for_empty(self, monkeypatch):
        monkeypatch.setenv("OPROCESS_ALLOWED_ORIGINS", "")
        assert get_allowed_origins() is None

    def test_returns_none_for_whitespace(self, monkeypatch):
        monkeypatch.setenv("OPROCESS_ALLOWED_ORIGINS", "   ")
        assert get_allowed_origins() is None

    def test_single_origin(self, monkeypatch):
        monkeypatch.setenv(
            "OPROCESS_ALLOWED_ORIGINS", "http://localhost:3000",
        )
        result = get_allowed_origins()
        assert result == {"http://localhost:3000"}

    def test_multiple_origins(self, monkeypatch):
        monkeypatch.setenv(
            "OPROCESS_ALLOWED_ORIGINS",
            "http://localhost:3000, https://app.example.com",
        )
        result = get_allowed_origins()
        assert result == {
            "http://localhost:3000",
            "https://app.example.com",
        }

    def test_strips_trailing_slash(self, monkeypatch):
        monkeypatch.setenv(
            "OPROCESS_ALLOWED_ORIGINS", "http://example.com/",
        )
        result = get_allowed_origins()
        assert result == {"http://example.com"}


class TestVerifyOrigin:
    """P6-7: Coverage for verify_origin()."""

    def test_no_config_allows_any(self, monkeypatch):
        monkeypatch.delenv("OPROCESS_ALLOWED_ORIGINS", raising=False)
        assert verify_origin("http://evil.com") is True

    def test_no_origin_header_allowed(self, monkeypatch):
        monkeypatch.setenv(
            "OPROCESS_ALLOWED_ORIGINS", "http://localhost:3000",
        )
        assert verify_origin(None) is True

    def test_allowed_origin_passes(self, monkeypatch):
        monkeypatch.setenv(
            "OPROCESS_ALLOWED_ORIGINS", "http://localhost:3000",
        )
        assert verify_origin("http://localhost:3000") is True

    def test_disallowed_origin_rejected(self, monkeypatch):
        monkeypatch.setenv(
            "OPROCESS_ALLOWED_ORIGINS", "http://localhost:3000",
        )
        assert verify_origin("http://evil.com") is False

    def test_trailing_slash_normalized(self, monkeypatch):
        monkeypatch.setenv(
            "OPROCESS_ALLOWED_ORIGINS", "http://localhost:3000",
        )
        assert verify_origin("http://localhost:3000/") is True


def _run_middleware(headers: dict, api_key: str | None = None):
    """Invoke BearerAuthMiddleware and return captured responses."""
    old_key = os.environ.get("OPROCESS_API_KEY")
    if api_key:
        os.environ["OPROCESS_API_KEY"] = api_key
    else:
        os.environ.pop("OPROCESS_API_KEY", None)

    try:
        responses: list[dict] = []

        async def app(scope, receive, send):
            await send({"type": "http.response.start", "status": 200})
            await send({"type": "http.response.body", "body": b"ok"})

        async def send(msg):
            responses.append(msg)

        scope = {
            "type": "http",
            "headers": [
                (k.encode(), v.encode()) for k, v in headers.items()
            ],
            "path": "/test",
        }

        mw = BearerAuthMiddleware(app)
        asyncio.run(mw(scope, None, send))
        return responses
    finally:
        if old_key is not None:
            os.environ["OPROCESS_API_KEY"] = old_key
        else:
            os.environ.pop("OPROCESS_API_KEY", None)


class TestBearerAuthMiddleware:
    def test_no_key_passes_through(self):
        responses = _run_middleware({})
        assert responses[0]["status"] == 200

    def test_valid_token_passes(self):
        responses = _run_middleware(
            {"authorization": "Bearer secret"}, api_key="secret",
        )
        assert responses[0]["status"] == 200

    def test_missing_token_rejected(self):
        responses = _run_middleware({}, api_key="secret")
        assert responses[0]["status"] == 401

    def test_wrong_token_rejected(self):
        responses = _run_middleware(
            {"authorization": "Bearer wrong"}, api_key="secret",
        )
        assert responses[0]["status"] == 401

    def test_non_http_scope_passes(self):
        """Non-http/websocket scope types are passed through."""
        responses: list[dict] = []

        async def app(scope, receive, send):
            await send({"type": "http.response.start", "status": 200})
            await send({"type": "http.response.body", "body": b"ok"})

        async def send(msg):
            responses.append(msg)

        scope = {"type": "lifespan"}
        mw = BearerAuthMiddleware(app)
        asyncio.run(mw(scope, None, send))
        assert responses[0]["status"] == 200


class TestOriginMiddleware:
    """P6-7: Origin validation through middleware."""

    def test_origin_rejected_returns_403(self, monkeypatch):
        monkeypatch.setenv(
            "OPROCESS_ALLOWED_ORIGINS", "http://localhost:3000",
        )
        responses = _run_middleware({"origin": "http://evil.com"})
        assert responses[0]["status"] == 403

    def test_allowed_origin_passes(self, monkeypatch):
        monkeypatch.setenv(
            "OPROCESS_ALLOWED_ORIGINS", "http://localhost:3000",
        )
        responses = _run_middleware(
            {"origin": "http://localhost:3000"},
        )
        # No API key set → passes through after origin check
        assert responses[0]["status"] == 200

    def test_no_origin_config_passes(self):
        responses = _run_middleware({"origin": "http://anything.com"})
        assert responses[0]["status"] == 200

    def test_403_body_contains_error(self, monkeypatch):
        monkeypatch.setenv(
            "OPROCESS_ALLOWED_ORIGINS", "http://localhost:3000",
        )
        responses = _run_middleware({"origin": "http://evil.com"})
        body_msg = responses[1]
        assert b"forbidden" in body_msg["body"]
        assert b"Origin not allowed" in body_msg["body"]
