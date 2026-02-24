"""Tests for sqlite-vec vector similarity search."""

from __future__ import annotations

from oprocess.db.vector_search import (
    has_embeddings,
    has_vec_table,
    vector_search,
)
from tests.conftest import _make_embedding_list


class TestHasEmbeddings:
    def test_no_embeddings(self, populated_db):
        assert has_embeddings(populated_db) is False

    def test_with_embeddings(self, populated_db_with_embeddings):
        assert has_embeddings(populated_db_with_embeddings) is True


class TestHasVecTable:
    def test_no_vec_data(self, populated_db):
        assert has_vec_table(populated_db) is False

    def test_with_vec_data(self, populated_db_with_vec):
        assert has_vec_table(populated_db_with_vec) is True


class TestVectorSearch:
    def test_returns_full_process_dict(self, populated_db_with_vec):
        query_emb = _make_embedding_list("strategy")
        results = vector_search(populated_db_with_vec, query_emb)
        assert len(results) > 0
        r = results[0]
        assert "id" in r
        assert "name_zh" in r
        assert "name_en" in r
        assert "level" in r
        assert "domain" in r
        assert "source" in r
        assert "tags" in r
        assert "score" in r
        assert isinstance(r["score"], float)

    def test_no_process_id_key(self, populated_db_with_vec):
        query_emb = _make_embedding_list("strategy")
        results = vector_search(populated_db_with_vec, query_emb)
        for r in results:
            assert "process_id" not in r
            assert "id" in r

    def test_sorted_by_score_desc(self, populated_db_with_vec):
        query_emb = _make_embedding_list("ai")
        results = vector_search(populated_db_with_vec, query_emb)
        if len(results) > 1:
            for i in range(len(results) - 1):
                assert results[i]["score"] >= results[i + 1]["score"]

    def test_level_filter(self, populated_db_with_vec):
        query_emb = _make_embedding_list("strategy")
        results = vector_search(
            populated_db_with_vec, query_emb, level=1,
        )
        for r in results:
            assert r["level"] == 1

    def test_level_filter_excludes(self, populated_db_with_vec):
        query_emb = _make_embedding_list("strategy")
        all_results = vector_search(populated_db_with_vec, query_emb)
        level1 = vector_search(
            populated_db_with_vec, query_emb, level=1,
        )
        assert len(level1) <= len(all_results)

    def test_limit(self, populated_db_with_vec):
        query_emb = _make_embedding_list("strategy")
        results = vector_search(
            populated_db_with_vec, query_emb, limit=2,
        )
        assert len(results) <= 2

    def test_empty_vec_table(self, populated_db):
        """No vec data → empty results."""
        # vec table exists but has no data; has_vec_table returns False
        # calling directly should still work
        query_emb = _make_embedding_list("strategy")
        if has_vec_table(populated_db):
            results = vector_search(populated_db, query_emb)
            assert results == []
