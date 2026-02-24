"""Tests for KPI and role-related tool functions."""

from __future__ import annotations

import pytest
from fastmcp.exceptions import ToolError

from oprocess.db.queries import (
    get_ancestor_chain,
    get_kpis_for_process,
    get_process,
    get_processes_by_level,
    search_processes,
)
from oprocess.gateway import PassthroughGateway, ToolResponse
from oprocess.tools.export import build_responsibility_doc
from oprocess.tools.helpers import (
    apply_boundary,
    compare_process_nodes,
    responsibilities_to_md,
)


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
        gw = PassthroughGateway(session_id="abababab-abab-4aba-8aba-abababababab")

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
        assert resp.session_id == "abababab-abab-4aba-8aba-abababababab"


class TestCompareProcesses:
    def test_two_processes(self, populated_db):
        result = compare_process_nodes(populated_db, "1.0,8.0")
        assert "processes" in result
        assert "1.0" in result["processes"]
        assert "8.0" in result["processes"]
        assert len(result["comparisons"]) == 1
        cmp = result["comparisons"][0]
        assert cmp["pair"] == ["1.0", "8.0"]
        assert cmp["same_level"] is True  # both level 1

    def test_three_processes(self, populated_db):
        result = compare_process_nodes(populated_db, "1.0,8.0,1.1")
        assert len(result["comparisons"]) == 3  # C(3,2) = 3

    def test_missing_process(self, populated_db):
        with pytest.raises(ToolError, match="Process 99.99 not found"):
            compare_process_nodes(populated_db, "1.0,99.99")

    def test_includes_path(self, populated_db):
        result = compare_process_nodes(populated_db, "1.1,8.5")
        assert "path" in result["processes"]["1.1"]
        assert result["processes"]["1.1"]["path"] == ["1.0", "1.1"]

    def test_empty_ids_filtered(self, populated_db):
        """P5-3: Empty IDs in comma-separated list are filtered out."""
        result = compare_process_nodes(populated_db, "1.0,,8.0")
        assert "1.0" in result["processes"]
        assert "8.0" in result["processes"]
        assert len(result["comparisons"]) == 1


class TestResponsibilitiesMarkdown:
    def test_format_markdown(self, populated_db):
        data = {
            "process": {
                "id": "1.0",
                "name": "制定愿景与战略",
                "description": "为组织确立方向和愿景",
            },
            "hierarchy": [{"id": "1.0", "name": "制定愿景与战略"}],
            "sub_processes": [{"id": "1.1", "name": "定义业务概念"}],
            "domain": "operating",
        }
        md = responsibilities_to_md(data, "zh")
        assert "# 制定愿景与战略" in md
        assert "## 描述" in md
        assert "## 子流程" in md
        assert "1.1 定义业务概念" in md

    def test_format_en(self, populated_db):
        data = {
            "process": {
                "id": "1.0",
                "name": "Develop Vision",
                "description": "Establish direction",
            },
            "hierarchy": [{"id": "1.0", "name": "Develop Vision"}],
            "sub_processes": [],
            "domain": "operating",
        }
        md = responsibilities_to_md(data, "en")
        assert "## Description" in md
        assert "## Sub-processes" not in md  # empty


class TestExportMultiProcess:
    def test_single_process(self, populated_db):
        result = build_responsibility_doc(populated_db, "1.0", "zh")
        assert "制定愿景与战略" in result["markdown"]
        assert result["process_ids"] == ["1.0"]
        assert result["kpi_count"] >= 1

    def test_multi_process(self, populated_db):
        result = build_responsibility_doc(
            populated_db, "1.0,8.0", "zh",
        )
        assert "制定愿景与战略" in result["markdown"]
        assert "管理信息技术" in result["markdown"]
        assert result["process_ids"] == ["1.0", "8.0"]
        assert "---" in result["markdown"]  # separator

    def test_with_role_name(self, populated_db):
        result = build_responsibility_doc(
            populated_db, "1.0", "zh", role_name="CTO",
        )
        assert "CTO" in result["markdown"]
        assert "岗位说明书" in result["markdown"]

    def test_missing_process(self, populated_db):
        result = build_responsibility_doc(populated_db, "99.99", "zh")
        assert "not found" in result["markdown"]


class TestIndustryFilter:
    def test_filter_by_tag(self, populated_db):
        results = search_processes(populated_db, "管理", lang="zh")
        # Filter for "it" tag
        filtered = [
            r for r in results
            if "it" in [t.lower() for t in r.get("tags", [])]
        ]
        for r in filtered:
            assert "it" in [t.lower() for t in r["tags"]]


class TestApplyBoundary:
    def test_no_results(self):
        resp = ToolResponse(result=[])
        apply_boundary("test", [], resp)
        assert resp.result == []  # unchanged

    def test_no_score_field(self):
        results = [{"id": "1.0", "name_zh": "a"}]
        resp = ToolResponse(result=results)
        apply_boundary("test", results, resp)
        assert resp.result == results  # unchanged (LIKE fallback)

    def test_within_boundary(self):
        results = [
            {"id": "1.0", "name_zh": "a", "name_en": "A", "score": 0.9},
            {"id": "1.1", "name_zh": "b", "name_en": "B", "score": 0.8},
        ]
        resp = ToolResponse(result=results)
        apply_boundary("test", results, resp)
        assert resp.result == results  # unchanged

    def test_outside_boundary(self):
        results = [
            {"id": "1.0", "name_zh": "a", "name_en": "A", "score": 0.2},
        ]
        resp = ToolResponse(result=results)
        apply_boundary("test", results, resp)
        assert "boundary" in resp.result
        assert resp.result["boundary"]["boundary_triggered"] is True
