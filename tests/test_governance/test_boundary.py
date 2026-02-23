"""Tests for BoundaryResponse."""

from __future__ import annotations

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
