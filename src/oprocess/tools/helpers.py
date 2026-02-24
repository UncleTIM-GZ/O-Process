"""Shared helpers for MCP tool implementations."""

from __future__ import annotations

import sqlite3

from fastmcp.exceptions import ToolError

from oprocess.db.queries import (
    build_path_string,
    build_path_strings_batch,
    get_ancestor_chain,
    get_process,
    validate_lang,
)
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
    """Build provenance chain from search results (batch-optimized)."""
    validate_lang(lang)
    if not results:
        return []

    chain = ProvenanceChain()
    name_key = f"name_{lang}"

    # Batch-build paths to reduce N+1 queries
    ids = [r["id"] for r in results]
    path_map = build_path_strings_batch(conn, ids)

    for r in results:
        chain.add(
            node_id=r["id"],
            name=r.get(name_key, r.get("name_zh", "")),
            confidence=r.get("score", 1.0),
            path=path_map.get(r["id"], r["id"]),
            derivation_rule=derivation_rule,
        )
    return chain.to_list()


def build_hierarchy_provenance(
    conn: sqlite3.Connection,
    process_id: str,
    lang: str,
) -> list[dict]:
    """Build provenance chain from ancestor hierarchy."""
    validate_lang(lang)
    chain = ProvenanceChain()
    ancestors = get_ancestor_chain(conn, process_id)

    # Batch-build paths for all ancestors
    ids = [node["id"] for node in ancestors]
    path_map = build_path_strings_batch(conn, ids)

    for node in ancestors:
        weight = 1.0 if node["id"] == process_id else 0.5
        chain.add(
            node_id=node["id"],
            name=node[f"name_{lang}"],
            confidence=weight,
            path=path_map.get(node["id"], node["id"]),
            derivation_rule="rule_based",
        )
    return chain.to_list()


def compare_process_nodes(
    conn: sqlite3.Connection, process_ids: str,
) -> dict:
    """Compare multiple process nodes by their IDs (comma-separated)."""
    ids = [pid.strip() for pid in process_ids.split(",")]
    processes = {}
    for pid in ids:
        p = get_process(conn, pid)
        if not p:
            msg = f"Process {pid} not found"
            raise ToolError(msg)
        processes[pid] = p

    comparisons = []
    for i, id_a in enumerate(ids):
        for id_b in ids[i + 1:]:
            a, b = processes[id_a], processes[id_b]
            comparisons.append({
                "pair": [id_a, id_b],
                "same_parent": a.get("parent_id") == b.get("parent_id"),
                "same_domain": a.get("domain") == b.get("domain"),
                "same_level": a.get("level") == b.get("level"),
            })

    return {
        "processes": {
            pid: {
                **p,
                "path": [n["id"] for n in get_ancestor_chain(conn, pid)],
            }
            for pid, p in processes.items()
        },
        "comparisons": comparisons,
    }


def responsibilities_to_md(data: dict, lang: str) -> str:
    """Convert responsibilities data dict to markdown string."""
    p = data["process"]
    lines = [
        f"# {p['name']}",
        "",
        f"**ID**: {p['id']}",
        f"**Domain**: {data['domain']}",
        "",
        "## 描述" if lang == "zh" else "## Description",
        "",
        p["description"],
        "",
        "## 层级" if lang == "zh" else "## Hierarchy",
        "",
    ]
    for node in data["hierarchy"]:
        lines.append(f"- {node['id']} {node['name']}")
    if data["sub_processes"]:
        lines.extend([
            "",
            "## 子流程" if lang == "zh" else "## Sub-processes",
            "",
        ])
        for sp in data["sub_processes"]:
            lines.append(f"- {sp['id']} {sp['name']}")
    return "\n".join(lines)


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
