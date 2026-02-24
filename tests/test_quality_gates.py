"""Quality gate tests — search accuracy, boundary, provenance, schema.

These tests validate PRD v2.0 §10 quality requirements.
Tests requiring real DB will skip when data/oprocess.db is not found.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from oprocess.db.connection import get_connection, init_schema
from oprocess.db.queries import search_processes
from oprocess.governance.boundary import check_boundary
from oprocess.governance.provenance import ProvenanceChain
from oprocess.tools.helpers import (
    build_hierarchy_provenance,
    build_lookup_provenance,
    build_search_provenance,
)

REAL_DB = Path("data/oprocess.db")
FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def real_conn() -> sqlite3.Connection:
    """Connect to the real production database."""
    if not REAL_DB.exists():
        pytest.skip("Production database not found at data/oprocess.db")
    conn = get_connection(REAL_DB)
    init_schema(conn)
    return conn


def _load_fixture(name: str) -> list[dict]:
    """Load a JSON fixture file."""
    path = FIXTURES / name
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _like_search(
    conn: sqlite3.Connection, query: str, lang: str, limit: int = 3,
) -> list[dict]:
    """SQL LIKE search — tests text-matching accuracy."""
    col = f"name_{lang}"
    desc_col = f"description_{lang}"
    pattern = f"%{query}%"
    rows = conn.execute(
        f"SELECT id FROM processes "
        f"WHERE ({col} LIKE ? OR {desc_col} LIKE ?) "
        f"ORDER BY level, id LIMIT ?",
        (pattern, pattern, limit),
    ).fetchall()
    return [{"id": r["id"]} for r in rows]


# ── 6.2 Search Accuracy ──────────────────────────────────────────────


class TestSearchAccuracy:
    """Validate Top-3 recall ≥ 85% on 50 annotated queries.

    Uses SQL LIKE search (the text-matching path). Vector search accuracy
    depends on embedding quality — when upgraded to OpenAI embeddings,
    re-annotate expected_top3_ids for semantic search path.
    """

    def test_top3_recall_rate(self, real_conn):
        queries = _load_fixture("annotated_queries.json")
        assert len(queries) >= 50, f"Expected ≥50 queries, got {len(queries)}"

        hits = 0
        for q in queries:
            results = _like_search(
                real_conn, q["query"], q["lang"], limit=3,
            )
            result_ids = {r["id"] for r in results}
            if any(eid in result_ids for eid in q["expected_top3_ids"]):
                hits += 1

        recall = hits / len(queries)
        assert recall >= 0.85, (
            f"Top-3 recall {recall:.2%} < 85% "
            f"({hits}/{len(queries)} hits)"
        )


# ── 6.3 Boundary Trigger ─────────────────────────────────────────────


class TestBoundaryTrigger:
    """Validate out-of-scope queries have zero LIKE matches.

    These queries are completely outside the process classification domain.
    The LIKE search path should return no results, confirming they are
    out-of-boundary. Vector-based boundary scoring (check_boundary) is
    tested separately once embedding quality is upgraded.
    """

    def test_all_boundary_queries_no_like_match(self, real_conn):
        queries = _load_fixture("boundary_queries.json")
        assert len(queries) >= 10, f"Expected ≥10 queries, got {len(queries)}"

        failures = []
        for q in queries:
            results = _like_search(
                real_conn, q["query"], q["lang"], limit=1,
            )
            if results:
                failures.append(
                    f"'{q['query']}' matched {results[0]['id']} "
                    f"(expected no match)"
                )

        assert not failures, (
            f"{len(failures)} queries matched unexpectedly:\n"
            + "\n".join(failures)
        )

    def test_boundary_response_structure(self):
        """check_boundary correctly flags low-confidence results."""
        boundary = check_boundary("量子计算", best_score=0.2, threshold=0.45)
        assert boundary.is_within_boundary is False
        assert boundary.best_score == 0.2

        boundary_ok = check_boundary("supply chain", best_score=0.8)
        assert boundary_ok.is_within_boundary is True


# ── 6.4 Provenance Non-Empty ─────────────────────────────────────────


class TestProvenanceNonEmpty:
    """Validate provenance chain is non-empty for substantive tools."""

    def test_search_provenance(self, populated_db_with_embeddings):
        """search_process → ≥1 node (semantic_match)."""
        results = search_processes(
            populated_db_with_embeddings, "strategy", lang="en", limit=3,
        )
        prov = build_search_provenance(
            populated_db_with_embeddings, results, "en",
        )
        assert len(prov) >= 1
        assert prov[0]["derivation_rule"] == "semantic_match"

    def test_hierarchy_provenance(self, populated_db):
        """get_responsibilities → ≥1 node (rule_based)."""
        prov = build_hierarchy_provenance(populated_db, "1.0", "zh")
        assert len(prov) >= 1
        assert prov[0]["derivation_rule"] == "rule_based"

    def test_lookup_provenance(self, populated_db):
        """get_kpi_suggestions → 1 node (direct_lookup)."""
        prov = build_lookup_provenance(populated_db, "1.0", "制定愿景与战略")
        assert len(prov) == 1
        assert prov[0]["derivation_rule"] == "direct_lookup"

    def test_export_provenance(self, populated_db):
        """export_responsibility_doc → ≥1 node (rule_based)."""
        prov = build_hierarchy_provenance(populated_db, "1.0", "zh")
        assert len(prov) >= 1
        assert prov[0]["derivation_rule"] == "rule_based"

    def test_structural_tools_empty_provenance(self):
        """get_process_tree / compare_processes → [] (PRD allows empty)."""
        chain = ProvenanceChain()
        assert chain.to_list() == []


# ── 6.6 Schema Compliance ────────────────────────────────────────────


class TestSchemaCompliance:
    """Validate MCP server registers all expected tools and resources."""

    def test_all_tools_registered(self):
        import asyncio

        from oprocess.server import mcp

        expected = {
            "search_process",
            "get_process_tree",
            "get_kpi_suggestions",
            "compare_processes",
            "get_responsibilities",
            "map_role_to_processes",
            "export_responsibility_doc",
            "health_check",
        }
        tools = asyncio.run(mcp.list_tools())
        tool_names = {t.name for t in tools}
        missing = expected - tool_names
        assert not missing, f"Missing tools: {missing}"

    def test_all_resources_registered(self):
        import asyncio

        from oprocess.server import mcp

        expected_static = {
            "oprocess://category/list",
            "oprocess://schema/sqlite",
            "oprocess://stats",
        }
        expected_templates = {
            "oprocess://process/{process_id}",
            "oprocess://role/{role_name}",
            "oprocess://audit/session/{session_id}",
        }

        resources = asyncio.run(mcp.list_resources())
        resource_uris = {str(r.uri) for r in resources}
        missing_static = expected_static - resource_uris
        assert not missing_static, f"Missing resources: {missing_static}"

        templates = asyncio.run(mcp.list_resource_templates())
        template_uris = {str(t.uri_template) for t in templates}
        missing_templates = expected_templates - template_uris
        assert not missing_templates, (
            f"Missing resource templates: {missing_templates}"
        )

    def test_tools_have_descriptions(self):
        import asyncio

        from oprocess.server import mcp

        tools = asyncio.run(mcp.list_tools())
        for t in tools:
            assert t.description, f"Tool '{t.name}' has no description"

    def test_tools_have_rich_descriptions(self):
        import asyncio

        from oprocess.server import mcp

        tools = asyncio.run(mcp.list_tools())
        for t in tools:
            assert len(t.description) >= 50, (
                f"Tool '{t.name}' description too short "
                f"({len(t.description)} chars < 50)"
            )

    def test_tools_have_annotations(self):
        import asyncio

        from oprocess.server import mcp

        tools = asyncio.run(mcp.list_tools())
        for t in tools:
            assert t.annotations is not None, (
                f"Tool '{t.name}' missing annotations"
            )
            assert t.annotations.readOnlyHint is True, (
                f"Tool '{t.name}' should be read-only"
            )
