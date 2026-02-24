"""Tests for embedder abstraction."""

from __future__ import annotations

from unittest.mock import patch

from oprocess.db.embedder import (
    EmbedProvider,
    GeminiEmbedder,
    get_embedder,
)


class TestGetEmbedder:
    def test_no_key_returns_none(self):
        with patch.dict("os.environ", {}, clear=True):
            result = get_embedder()
            assert result is None

    def test_google_api_key(self):
        with patch.dict(
            "os.environ", {"GOOGLE_API_KEY": "test-key"}, clear=True,
        ):
            with patch(
                "oprocess.db.embedder.GeminiEmbedder",
            ) as mock_cls:
                mock_cls.return_value = mock_cls
                mock_cls.dim = 768
                result = get_embedder()
                assert result is not None
                mock_cls.assert_called_once_with("test-key")

    def test_gemini_api_key_fallback(self):
        with patch.dict(
            "os.environ", {"GEMINI_API_KEY": "test-key2"}, clear=True,
        ):
            with patch(
                "oprocess.db.embedder.GeminiEmbedder",
            ) as mock_cls:
                mock_cls.return_value = mock_cls
                result = get_embedder()
                assert result is not None
                mock_cls.assert_called_once_with("test-key2")

    def test_init_failure_returns_none(self):
        with patch.dict(
            "os.environ", {"GOOGLE_API_KEY": "bad-key"}, clear=True,
        ):
            with patch(
                "oprocess.db.embedder.GeminiEmbedder",
                side_effect=RuntimeError("init failed"),
            ):
                result = get_embedder()
                assert result is None


class TestEmbedProviderProtocol:
    def test_gemini_is_embed_provider(self):
        """GeminiEmbedder should satisfy EmbedProvider protocol."""
        # isinstance check works better than issubclass for Protocols
        # with @property on Python 3.10
        from unittest.mock import MagicMock

        mock = MagicMock(spec=GeminiEmbedder)
        mock.dim = 768
        mock.embed.return_value = [[0.1] * 768]
        assert isinstance(mock, EmbedProvider)
