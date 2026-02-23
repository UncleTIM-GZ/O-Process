"""Database query functions for O'Process."""

from __future__ import annotations

import json
import sqlite3


def get_process(conn: sqlite3.Connection, process_id: str) -> dict | None:
    """Get a single process by ID."""
    row = conn.execute(
        "SELECT * FROM processes WHERE id = ?", (process_id,)
    ).fetchone()
    if not row:
        return None
    return _row_to_process(row)


def get_children(conn: sqlite3.Connection, parent_id: str) -> list[dict]:
    """Get direct children of a process."""
    rows = conn.execute(
        "SELECT * FROM processes WHERE parent_id = ? ORDER BY id",
        (parent_id,),
    ).fetchall()
    return [_row_to_process(r) for r in rows]


def get_subtree(
    conn: sqlite3.Connection, root_id: str, max_depth: int = 4
) -> dict | None:
    """Get process with nested children up to max_depth levels."""
    root = get_process(conn, root_id)
    if not root:
        return None

    def _build(node: dict, depth: int) -> dict:
        if depth >= max_depth:
            node["children"] = []
            return node
        children = get_children(conn, node["id"])
        node["children"] = [_build(c, depth + 1) for c in children]
        return node

    return _build(root, 0)


def search_processes(
    conn: sqlite3.Connection,
    query: str,
    lang: str = "zh",
    limit: int = 10,
    level: int | None = None,
) -> list[dict]:
    """Search processes — vector search primary, SQL LIKE fallback.

    Returns list of process dicts. When vector search is used,
    each dict includes a `score` field (cosine similarity 0.0-1.0).
    """
    from oprocess.db.vector_search import has_embeddings, vector_search

    if has_embeddings(conn):
        return vector_search(
            conn, query, limit=limit, threshold=0.0, level=level,
        )

    # Fallback: SQL LIKE (no score available)
    col = f"name_{lang}"
    desc_col = f"description_{lang}"
    pattern = f"%{query}%"
    conditions = [f"({col} LIKE ? OR {desc_col} LIKE ?)"]
    params: list = [pattern, pattern]
    if level is not None:
        conditions.append("level = ?")
        params.append(level)
    params.append(limit)
    where = " AND ".join(conditions)
    rows = conn.execute(
        f"SELECT * FROM processes WHERE {where} ORDER BY level, id LIMIT ?",
        params,
    ).fetchall()
    return [_row_to_process(r) for r in rows]


def get_kpis_for_process(
    conn: sqlite3.Connection, process_id: str
) -> list[dict]:
    """Get all KPIs for a process."""
    rows = conn.execute(
        "SELECT * FROM kpis WHERE process_id = ? ORDER BY id",
        (process_id,),
    ).fetchall()
    return [_row_to_kpi(r) for r in rows]


def get_processes_by_level(
    conn: sqlite3.Connection, level: int
) -> list[dict]:
    """Get all processes at a specific level."""
    rows = conn.execute(
        "SELECT * FROM processes WHERE level = ? ORDER BY id",
        (level,),
    ).fetchall()
    return [_row_to_process(r) for r in rows]


def get_ancestor_chain(
    conn: sqlite3.Connection, process_id: str
) -> list[dict]:
    """Get the ancestor chain from root to the given process."""
    chain = []
    current = get_process(conn, process_id)
    while current:
        chain.append(current)
        if current["parent_id"]:
            current = get_process(conn, current["parent_id"])
        else:
            break
    chain.reverse()
    return chain


def count_processes(conn: sqlite3.Connection) -> int:
    """Count total processes."""
    row = conn.execute("SELECT COUNT(*) FROM processes").fetchone()
    return row[0]


def count_kpis(conn: sqlite3.Connection) -> int:
    """Count total KPIs."""
    row = conn.execute("SELECT COUNT(*) FROM kpis").fetchone()
    return row[0]


def _row_to_process(row: sqlite3.Row) -> dict:
    """Convert a database row to a process dict."""
    d = dict(row)
    d["source"] = json.loads(d["source"])
    d["tags"] = json.loads(d["tags"])
    d["kpi_refs"] = json.loads(d["kpi_refs"])
    d["provenance_eligible"] = bool(d["provenance_eligible"])
    return d


def _row_to_kpi(row: sqlite3.Row) -> dict:
    """Convert a database row to a KPI dict."""
    return dict(row)
