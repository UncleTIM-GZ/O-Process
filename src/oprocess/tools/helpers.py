"""Shared helpers for MCP tool implementations."""

from __future__ import annotations

import sqlite3

from oprocess.db.queries import build_path_string, get_ancestor_chain
from oprocess.gateway import ToolResponse
from oprocess.governance.boundary import check_boundary
from oprocess.governance.provenance import ProvenanceChain


def apply_boundary(
    query: str, results: list[dict], resp: ToolResponse,
) -> None:
    """Apply boundary check to search results (mutates resp in-place).

    When results have `score` (vector mode), use real cosine similarity.
    When results lack `score` (LIKE fallback), skip boundary check.
    """
    if not results or "score" not in results[0]:
        return  # LIKE fallback — no scores, skip boundary

    best_score = results[0]["score"]
    nearest = [
        {
            "id": r["id"],
            "name_zh": r["name_zh"],
            "name_en": r["name_en"],
            "score": r["score"],
        }
        for r in results[:3]
    ]
    boundary = check_boundary(
        query, best_score, nearest_valid_nodes=nearest,
    )
    if not boundary.is_within_boundary:
        resp.result = {
            "results": resp.result,
            "boundary": boundary.to_dict(),
        }


def build_search_provenance(
    conn: sqlite3.Connection,
    results: list[dict],
    lang: str,
    derivation_rule: str = "semantic_match",
) -> list[dict]:
    """Build provenance chain from search results."""
    chain = ProvenanceChain()
    name_key = f"name_{lang}"
    for r in results:
        chain.add(
            node_id=r["id"],
            name=r.get(name_key, r.get("name_zh", "")),
            confidence=r.get("score", 1.0),
            path=build_path_string(conn, r["id"]),
            derivation_rule=derivation_rule,
        )
    return chain.to_list()


def build_hierarchy_provenance(
    conn: sqlite3.Connection,
    process_id: str,
    lang: str,
) -> list[dict]:
    """Build provenance chain from ancestor hierarchy."""
    chain = ProvenanceChain()
    ancestors = get_ancestor_chain(conn, process_id)
    for node in ancestors:
        weight = 1.0 if node["id"] == process_id else 0.5
        chain.add(
            node_id=node["id"],
            name=node[f"name_{lang}"],
            confidence=weight,
            path=build_path_string(conn, node["id"]),
            derivation_rule="rule_based",
        )
    return chain.to_list()


def build_lookup_provenance(
    conn: sqlite3.Connection,
    process_id: str,
    name: str,
) -> list[dict]:
    """Build provenance for a direct lookup."""
    chain = ProvenanceChain()
    chain.add(
        node_id=process_id,
        name=name,
        confidence=1.0,
        path=build_path_string(conn, process_id),
        derivation_rule="direct_lookup",
    )
    return chain.to_list()
