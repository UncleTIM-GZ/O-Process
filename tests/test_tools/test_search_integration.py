"""Integration tests for search_processes vector + LIKE fallback."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from oprocess.db.queries import search_processes
from tests.conftest import _make_embedding_list


class TestSearchLikeFallback:
    """When no embedder available, search falls back to LIKE."""

    def test_like_search_zh(self, populated_db):
        with patch("oprocess.db.queries._embedder_checked", False), \
             patch("oprocess.db.queries._embedder", None), \
             patch("oprocess.db.queries.get_embedder", return_value=None):
            results = search_processes(populated_db, "战略")
            assert len(results) > 0
            assert all("score" not in r for r in results)

    def test_like_search_en(self, populated_db):
        with patch("oprocess.db.queries._embedder_checked", False), \
             patch("oprocess.db.queries._embedder", None), \
             patch("oprocess.db.queries.get_embedder", return_value=None):
            results = search_processes(
                populated_db, "Strategy", lang="en",
            )
            assert len(results) > 0


class TestSearchVectorMode:
    """When embedder + vec table available, use vector search."""

    def test_vector_search_returns_scores(self, populated_db_with_vec):
        mock_embedder = MagicMock()
        mock_embedder.embed.return_value = [
            _make_embedding_list("strategy"),
        ]
        with patch("oprocess.db.queries._embedder_checked", True), \
             patch("oprocess.db.queries._embedder", mock_embedder):
            results = search_processes(populated_db_with_vec, "strategy")
            assert len(results) > 0
            assert "score" in results[0]

    def test_vector_search_level_filter(self, populated_db_with_vec):
        mock_embedder = MagicMock()
        mock_embedder.embed.return_value = [
            _make_embedding_list("strategy"),
        ]
        with patch("oprocess.db.queries._embedder_checked", True), \
             patch("oprocess.db.queries._embedder", mock_embedder):
            results = search_processes(
                populated_db_with_vec, "strategy", level=1,
            )
            for r in results:
                assert r["level"] == 1


class TestSearchExceptionFallback:
    """When vector search throws, gracefully fall back to LIKE."""

    def test_embed_exception_fallback(self, populated_db_with_vec):
        mock_embedder = MagicMock()
        mock_embedder.embed.side_effect = RuntimeError("API error")
        with patch("oprocess.db.queries._embedder_checked", True), \
             patch("oprocess.db.queries._embedder", mock_embedder):
            results = search_processes(
                populated_db_with_vec, "战略",
            )
            # Should still return LIKE results (no crash)
            assert isinstance(results, list)
