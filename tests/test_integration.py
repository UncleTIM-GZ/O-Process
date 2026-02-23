"""Integration tests — verify full tool chain with real data."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from oprocess.db.connection import get_connection
from oprocess.db.queries import (
    count_kpis,
    count_processes,
    get_kpis_for_process,
    get_process,
    get_subtree,
    search_processes,
)
from oprocess.gateway import PassthroughGateway
from oprocess.governance.audit import get_session_log, log_invocation
from oprocess.governance.boundary import check_boundary
from oprocess.governance.provenance import ProvenanceChain

REAL_DB = Path("data/oprocess.db")


@pytest.fixture
def real_conn() -> sqlite3.Connection:
    """Connect to the real production database."""
    if not REAL_DB.exists():
        pytest.skip("Production database not found at data/oprocess.db")
    return get_connection(REAL_DB)


class TestRealData:
    """Integration tests against the real database."""

    def test_process_count(self, real_conn):
        assert count_processes(real_conn) >= 2325

    def test_kpi_count(self, real_conn):
        assert count_kpis(real_conn) >= 3910

    def test_get_root_process(self, real_conn):
        p = get_process(real_conn, "1.0")
        assert p is not None
        assert p["name_zh"] == "制定愿景与战略"
        assert p["level"] == 1

    def test_get_it_process(self, real_conn):
        p = get_process(real_conn, "8.0")
        assert p is not None
        assert "IT" in p["name_en"] or "信息技术" in p["name_zh"]

    def test_subtree_depth(self, real_conn):
        tree = get_subtree(real_conn, "1.0", max_depth=2)
        assert tree is not None
        assert len(tree["children"]) > 0
        for child in tree["children"]:
            assert child["level"] == 2

    def test_search_zh(self, real_conn):
        results = search_processes(real_conn, "供应链", lang="zh")
        assert len(results) > 0

    def test_search_en(self, real_conn):
        results = search_processes(real_conn, "supply chain", lang="en")
        assert len(results) > 0

    def test_kpis_for_process(self, real_conn):
        kpis = get_kpis_for_process(real_conn, "1.0")
        assert len(kpis) >= 1


class TestFullToolChain:
    """Test the complete tool chain: gateway → query → governance."""

    def test_search_with_governance(self, real_conn):
        gw = PassthroughGateway(session_id="int-test-1")
        provenance = ProvenanceChain()

        # Execute search
        resp = gw.execute(
            "search_process",
            search_processes,
            conn=real_conn,
            query="人力资本",
            lang="zh",
            limit=5,
        )

        assert resp.response_ms >= 0
        assert len(resp.result) > 0

        # Build provenance
        for r in resp.result:
            provenance.add(r["id"], "matched", r["name_zh"])

        assert len(provenance) > 0

        # Check boundary
        boundary = check_boundary(
            "人力资本", best_score=0.9, threshold=0.45
        )
        assert boundary.is_within_boundary is True

        # Audit log
        log_invocation(
            real_conn,
            session_id="int-test-1",
            tool_name="search_process",
            input_params={"query": "人力资本"},
            output_summary=f"{len(resp.result)} results",
            response_ms=resp.response_ms,
        )
        logs = get_session_log(real_conn, "int-test-1")
        assert len(logs) >= 1

    def test_export_chain(self, real_conn):
        """Test the full export flow: process → subtree → KPIs → doc."""
        gw = PassthroughGateway(session_id="int-test-2")

        # Get process
        resp = gw.execute(
            "get_process_tree",
            get_subtree,
            conn=real_conn,
            root_id="4.0",
            max_depth=2,
        )
        tree = resp.result
        assert tree is not None
        assert tree["id"] == "4.0"
        assert "children" in tree

        # Get KPIs
        kpis = get_kpis_for_process(real_conn, "4.0")
        assert isinstance(kpis, list)

        # Log everything
        log_invocation(
            real_conn,
            session_id="int-test-2",
            tool_name="get_process_tree",
            input_params={"process_id": "4.0"},
            response_ms=resp.response_ms,
        )


class TestServerImport:
    """Verify the server module can be imported and tools registered."""

    def test_import_server(self):
        from oprocess.server import mcp

        assert mcp.name == "O'Process"

    def test_import_gateway(self):
        from oprocess.gateway import PassthroughGateway

        gw = PassthroughGateway()
        assert gw.session_id
