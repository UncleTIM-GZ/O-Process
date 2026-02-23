"""Tests for BoundaryResponse."""

from __future__ import annotations

import pytest

from oprocess.governance.boundary import check_boundary


class TestBoundary:
    def test_within_boundary(self):
        resp = check_boundary("供应链", best_score=0.8, threshold=0.45)
        assert resp.is_within_boundary is True
        assert resp.suggestion == ""

    def test_below_threshold(self):
        resp = check_boundary("xyzabc", best_score=0.1, threshold=0.45)
        assert resp.is_within_boundary is False
        assert "低于置信阈值" in resp.suggestion

    def test_exact_threshold(self):
        resp = check_boundary("test", best_score=0.45, threshold=0.45)
        assert resp.is_within_boundary is True

    def test_to_dict(self):
        resp = check_boundary("q", best_score=0.3, threshold=0.45)
        d = resp.to_dict()
        assert d["boundary_triggered"] is True
        assert d["best_score"] == 0.3
        assert d["threshold"] == 0.45
        assert "boundary_reason" in d
        assert "query_embedding_distance" in d
        assert "nearest_valid_nodes" in d

    def test_new_fields_below_threshold(self):
        nodes = [{"id": "1.0", "name_zh": "x", "name_en": "y", "score": 0.3}]
        resp = check_boundary(
            "q", best_score=0.3, threshold=0.45,
            nearest_valid_nodes=nodes,
        )
        assert resp.boundary_reason != ""
        assert resp.query_embedding_distance == pytest.approx(0.7)
        assert len(resp.nearest_valid_nodes) == 1
        assert resp.nearest_valid_nodes[0]["id"] == "1.0"

    def test_new_fields_within_boundary(self):
        resp = check_boundary("ok", best_score=0.9, threshold=0.45)
        assert resp.boundary_reason == ""
        assert resp.query_embedding_distance == pytest.approx(0.1)
        assert resp.nearest_valid_nodes == []
