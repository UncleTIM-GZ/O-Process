"""Tests for database query functions."""

from __future__ import annotations

from oprocess.db.queries import (
    count_kpis,
    count_processes,
    get_ancestor_chain,
    get_children,
    get_kpis_for_process,
    get_process,
    get_processes_by_level,
    get_subtree,
    search_processes,
)


class TestGetProcess:
    def test_existing(self, populated_db):
        p = get_process(populated_db, "1.0")
        assert p is not None
        assert p["id"] == "1.0"
        assert p["name_zh"] == "制定愿景与战略"
        assert p["level"] == 1

    def test_not_found(self, populated_db):
        assert get_process(populated_db, "99.99") is None

    def test_source_is_list(self, populated_db):
        p = get_process(populated_db, "1.0")
        assert isinstance(p["source"], list)
        assert "PCF:1.0" in p["source"]


class TestGetChildren:
    def test_children(self, populated_db):
        children = get_children(populated_db, "1.0")
        assert len(children) == 1
        assert children[0]["id"] == "1.1"

    def test_no_children(self, populated_db):
        children = get_children(populated_db, "1.1")
        assert len(children) == 0


class TestGetSubtree:
    def test_with_children(self, populated_db):
        tree = get_subtree(populated_db, "1.0")
        assert tree is not None
        assert tree["id"] == "1.0"
        assert len(tree["children"]) == 1
        assert tree["children"][0]["id"] == "1.1"

    def test_not_found(self, populated_db):
        assert get_subtree(populated_db, "99.99") is None


class TestSearch:
    def test_search_zh_like_fallback(self, populated_db):
        """Without embeddings, uses SQL LIKE fallback."""
        results = search_processes(populated_db, "愿景", lang="zh")
        assert len(results) >= 1
        assert any(r["id"] == "1.0" for r in results)
        # LIKE fallback has no score field
        assert "score" not in results[0]

    def test_search_en_like_fallback(self, populated_db):
        results = search_processes(populated_db, "Strategy", lang="en")
        assert len(results) >= 1

    def test_search_no_results(self, populated_db):
        results = search_processes(populated_db, "xyznonexistent")
        assert len(results) == 0

    def test_search_vector_mode(self, populated_db_with_embeddings):
        """With embeddings, uses vector search and includes score."""
        results = search_processes(
            populated_db_with_embeddings, "strategy",
        )
        assert len(results) > 0
        assert "score" in results[0]
        assert isinstance(results[0]["score"], float)

    def test_search_level_filter_like(self, populated_db):
        results = search_processes(populated_db, "管理", level=1)
        for r in results:
            assert r["level"] == 1

    def test_search_level_filter_vector(self, populated_db_with_embeddings):
        results = search_processes(
            populated_db_with_embeddings, "strategy", level=1,
        )
        for r in results:
            assert r["level"] == 1


class TestKPIs:
    def test_get_kpis(self, populated_db):
        kpis = get_kpis_for_process(populated_db, "1.0")
        assert len(kpis) == 1
        assert kpis[0]["id"] == "kpi.1.0.01"

    def test_no_kpis(self, populated_db):
        kpis = get_kpis_for_process(populated_db, "1.1")
        assert len(kpis) == 0


class TestAncestorChain:
    def test_chain(self, populated_db):
        chain = get_ancestor_chain(populated_db, "1.1")
        assert len(chain) == 2
        assert chain[0]["id"] == "1.0"
        assert chain[1]["id"] == "1.1"

    def test_root(self, populated_db):
        chain = get_ancestor_chain(populated_db, "1.0")
        assert len(chain) == 1


class TestCounts:
    def test_process_count(self, populated_db):
        assert count_processes(populated_db) == 4

    def test_kpi_count(self, populated_db):
        assert count_kpis(populated_db) == 2


class TestLevelQuery:
    def test_level_1(self, populated_db):
        procs = get_processes_by_level(populated_db, 1)
        assert len(procs) == 2
        ids = {p["id"] for p in procs}
        assert "1.0" in ids
        assert "8.0" in ids
