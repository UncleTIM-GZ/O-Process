"""Tests for vector similarity search."""

from __future__ import annotations

import struct

from oprocess.db.vector_search import (
    _cosine_similarity,
    _embed_query_tfidf,
    has_embeddings,
    vector_search,
)


class TestHasEmbeddings:
    def test_no_embeddings(self, populated_db):
        assert has_embeddings(populated_db) is False

    def test_with_embeddings(self, populated_db_with_embeddings):
        assert has_embeddings(populated_db_with_embeddings) is True


class TestVectorSearch:
    def test_returns_full_process_dict(self, populated_db_with_embeddings):
        results = vector_search(populated_db_with_embeddings, "strategy")
        assert len(results) > 0
        r = results[0]
        # Must have full process fields + score
        assert "id" in r
        assert "name_zh" in r
        assert "name_en" in r
        assert "level" in r
        assert "domain" in r
        assert "source" in r
        assert "tags" in r
        assert "score" in r
        assert isinstance(r["score"], float)

    def test_no_process_id_key(self, populated_db_with_embeddings):
        """vector_search should use 'id' not 'process_id'."""
        results = vector_search(populated_db_with_embeddings, "strategy")
        for r in results:
            assert "process_id" not in r
            assert "id" in r

    def test_sorted_by_score_desc(self, populated_db_with_embeddings):
        results = vector_search(populated_db_with_embeddings, "ai")
        if len(results) > 1:
            for i in range(len(results) - 1):
                assert results[i]["score"] >= results[i + 1]["score"]

    def test_level_filter(self, populated_db_with_embeddings):
        results = vector_search(
            populated_db_with_embeddings, "strategy", level=1,
        )
        for r in results:
            assert r["level"] == 1

    def test_level_filter_excludes(self, populated_db_with_embeddings):
        all_results = vector_search(
            populated_db_with_embeddings, "strategy",
        )
        level1 = vector_search(
            populated_db_with_embeddings, "strategy", level=1,
        )
        assert len(level1) <= len(all_results)

    def test_threshold_filter(self, populated_db_with_embeddings):
        results = vector_search(
            populated_db_with_embeddings, "strategy", threshold=0.99,
        )
        for r in results:
            assert r["score"] >= 0.99

    def test_limit(self, populated_db_with_embeddings):
        results = vector_search(
            populated_db_with_embeddings, "strategy", limit=2,
        )
        assert len(results) <= 2

    def test_dimension_mismatch_skipped(self, populated_db_with_embeddings):
        """Embeddings with wrong dimension are silently skipped."""
        conn = populated_db_with_embeddings
        # Insert a 10-dim embedding (mismatch with 384)
        bad_emb = struct.pack("10f", *([0.1] * 10))
        conn.execute(
            "INSERT OR REPLACE INTO process_embeddings "
            "(process_id, embedding, text_hash) VALUES (?, ?, ?)",
            ("1.1", bad_emb, "bad"),
        )
        conn.commit()
        # Should not crash, just skip the mismatched one
        results = vector_search(conn, "business")
        assert isinstance(results, list)

    def test_empty_table(self, populated_db):
        """No embeddings → empty results."""
        results = vector_search(populated_db, "strategy")
        assert results == []


class TestCosineSimilarity:
    def test_identical(self):
        v = [1.0, 2.0, 3.0]
        assert abs(_cosine_similarity(v, v) - 1.0) < 1e-6

    def test_orthogonal(self):
        a = [1.0, 0.0]
        b = [0.0, 1.0]
        assert abs(_cosine_similarity(a, b)) < 1e-6

    def test_zero_vector(self):
        assert _cosine_similarity([0, 0], [1, 2]) == 0.0


class TestEmbedQuery:
    def test_returns_correct_dim(self):
        vec = _embed_query_tfidf("hello world", dim=384)
        assert len(vec) == 384

    def test_normalized(self):
        vec = _embed_query_tfidf("test query")
        import math
        norm = math.sqrt(sum(v * v for v in vec))
        assert abs(norm - 1.0) < 1e-6
