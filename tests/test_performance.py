"""Performance benchmark tests.

Run with: pytest tests/test_performance.py --benchmark-only -p no:cov
"""

from __future__ import annotations

from oprocess.db.queries import get_subtree, search_processes
from oprocess.governance.audit import hash_input, log_invocation
from oprocess.governance.boundary import check_boundary
from oprocess.governance.provenance import ProvenanceChain
from oprocess.tools.export import build_responsibility_doc


class TestSearchPerformance:
    """Benchmark search and tree operations."""

    def test_vector_search_latency(
        self, populated_db_with_embeddings, benchmark,
    ):
        result = benchmark(
            search_processes,
            populated_db_with_embeddings,
            "strategy",
            lang="en",
        )
        assert len(result) > 0

    def test_subtree_latency(self, populated_db, benchmark):
        result = benchmark(get_subtree, populated_db, "1.0", max_depth=3)
        assert result is not None
        assert result["id"] == "1.0"

    def test_export_doc_latency(self, populated_db, benchmark):
        result = benchmark(
            build_responsibility_doc, populated_db, "1.0", "zh",
        )
        assert "markdown" in result
        assert result["kpi_count"] >= 0


class TestGovernancePerformance:
    """Benchmark governance layer operations."""

    def test_provenance_chain_assembly(self, benchmark):
        def build_chain():
            chain = ProvenanceChain()
            for i in range(10):
                chain.add(
                    f"{i}.0", f"name_{i}", 0.9,
                    f"root > {i}.0", "semantic_match",
                )
            return chain.to_list()

        result = benchmark(build_chain)
        assert len(result) == 10

    def test_audit_write_latency(self, db_conn, benchmark):
        counter = [0]

        def write_audit():
            counter[0] += 1
            log_invocation(
                db_conn,
                f"bench-{counter[0]}",
                "benchmark_tool",
                hash_input({"q": f"query-{counter[0]}"}),
            )

        benchmark(write_audit)

    def test_boundary_check_latency(self, benchmark):
        result = benchmark(check_boundary, "test query", 0.8, 0.45)
        assert result.is_within_boundary is True
