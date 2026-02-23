"""Tests for KPI and role-related tool functions."""

from __future__ import annotations

from oprocess.db.queries import (
    get_ancestor_chain,
    get_kpis_for_process,
    get_process,
    get_processes_by_level,
    search_processes,
)
from oprocess.gateway import PassthroughGateway


class TestKPISuggestions:
    def test_get_kpis_for_process(self, populated_db):
        kpis = get_kpis_for_process(populated_db, "1.0")
        assert len(kpis) == 1
        assert kpis[0]["name_zh"] == "战略执行率"
        assert kpis[0]["unit"] == "%"

    def test_kpi_fields(self, populated_db):
        kpis = get_kpis_for_process(populated_db, "8.0")
        assert len(kpis) == 1
        kpi = kpis[0]
        assert kpi["category"] == "Reliability"
        assert kpi["direction"] == "higher_is_better"

    def test_no_kpis(self, populated_db):
        kpis = get_kpis_for_process(populated_db, "8.5")
        assert len(kpis) == 0


class TestResponsibilities:
    def test_hierarchy_chain(self, populated_db):
        chain = get_ancestor_chain(populated_db, "8.5")
        assert len(chain) == 2
        assert chain[0]["id"] == "8.0"
        assert chain[1]["id"] == "8.5"

    def test_sub_processes(self, populated_db):
        """Children at level 2 of root 1.0."""
        procs = get_processes_by_level(populated_db, 2)
        children_of_1 = [p for p in procs if p.get("parent_id") == "1.0"]
        assert len(children_of_1) == 1
        assert children_of_1[0]["id"] == "1.1"

    def test_process_details(self, populated_db):
        p = get_process(populated_db, "8.5")
        assert p["domain"] == "management_support"
        assert "AI" in p["name_zh"]


class TestMapRole:
    def test_search_by_role(self, populated_db):
        results = search_processes(populated_db, "IT", lang="en")
        assert len(results) >= 1
        ids = {r["id"] for r in results}
        assert "8.0" in ids

    def test_search_zh_role(self, populated_db):
        results = search_processes(populated_db, "战略", lang="zh")
        assert len(results) >= 1


class TestExportDoc:
    def test_gateway_wraps(self, populated_db):
        gw = PassthroughGateway(session_id="test")

        def _export():
            p = get_process(populated_db, "1.0")
            get_ancestor_chain(populated_db, "1.0")  # verify no error
            kpis = get_kpis_for_process(populated_db, "1.0")
            return {
                "markdown": f"# {p['name_zh']}",
                "process_id": "1.0",
                "kpi_count": len(kpis),
            }

        resp = gw.execute("export_responsibility_doc", _export)
        assert resp.result["process_id"] == "1.0"
        assert resp.result["kpi_count"] == 1
        assert "制定愿景与战略" in resp.result["markdown"]
        assert resp.session_id == "test"
