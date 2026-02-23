"""Tests for Bearer token authentication."""

from __future__ import annotations

import asyncio

from oprocess.auth import get_api_key, verify_token


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


def _run_middleware(headers: dict, api_key: str | None = None):
    """Invoke BearerAuthMiddleware and return captured responses."""
    import os

    from oprocess.auth import BearerAuthMiddleware

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
