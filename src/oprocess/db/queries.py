"""Database query functions for O'Process."""

from __future__ import annotations

import logging
import sqlite3

from oprocess.db.embedder import EmbedProvider, get_embedder
from oprocess.db.row_utils import row_to_process
from oprocess.db.vector_search import has_vec_table, vector_search
from oprocess.validators import validate_lang

logger = logging.getLogger(__name__)

# Module-level singleton for embedder (lazy init)
_embedder: EmbedProvider | None = None
_embedder_checked = False


def get_process(conn: sqlite3.Connection, process_id: str) -> dict | None:
    """Get a single process by ID."""
    row = conn.execute(
        "SELECT * FROM processes WHERE id = ?", (process_id,)
    ).fetchone()
    if not row:
        return None
    return row_to_process(row)


def get_children(conn: sqlite3.Connection, parent_id: str) -> list[dict]:
    """Get direct children of a process."""
    rows = conn.execute(
        "SELECT * FROM processes WHERE parent_id = ? ORDER BY id",
        (parent_id,),
    ).fetchall()
    return [row_to_process(r) for r in rows]


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


def _get_embedder() -> EmbedProvider | None:
    """Get module-level embedder singleton (lazy init)."""
    global _embedder, _embedder_checked
    if not _embedder_checked:
        _embedder = get_embedder()
        _embedder_checked = True
    return _embedder


def search_processes(
    conn: sqlite3.Connection,
    query: str,
    lang: str = "zh",
    limit: int = 10,
    level: int | None = None,
) -> list[dict]:
    """Search processes — vector search with LIKE fallback.

    Uses Gemini embedding + sqlite-vec when available,
    falls back to SQL LIKE when no embedder or vec table.
    """
    validate_lang(lang)
    embedder = _get_embedder()
    if embedder and has_vec_table(conn):
        try:
            vecs = embedder.embed([query])
            results = vector_search(conn, vecs[0], limit, level)
            if results:
                return results
        except Exception:
            logger.warning("Vector search failed, falling back to LIKE")
    return _search_like(conn, query, lang, limit, level)


def _escape_like(s: str) -> str:
    """Escape LIKE wildcards so they match literally."""
    return s.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _search_like(
    conn: sqlite3.Connection,
    query: str,
    lang: str,
    limit: int,
    level: int | None,
) -> list[dict]:
    """Text-based LIKE search (fallback)."""
    col = f"name_{lang}"
    desc_col = f"description_{lang}"
    pattern = f"%{_escape_like(query)}%"
    conditions = [
        f"({col} LIKE ? ESCAPE '\\' OR {desc_col} LIKE ? ESCAPE '\\')",
    ]
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
    return [row_to_process(r) for r in rows]


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
    return [row_to_process(r) for r in rows]


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


def build_path_string(conn: sqlite3.Connection, process_id: str) -> str:
    """Build ancestor path string like '1.0 > 1.1 > 1.1.2'."""
    chain = get_ancestor_chain(conn, process_id)
    return " > ".join(n["id"] for n in chain)


def build_path_strings_batch(
    conn: sqlite3.Connection, process_ids: list[str],
) -> dict[str, str]:
    """Build ancestor path strings for multiple IDs in batch.

    Caches intermediate results to reduce repeated lookups.
    """
    cache: dict[str, str] = {}
    for pid in process_ids:
        if pid not in cache:
            chain = get_ancestor_chain(conn, pid)
            # Cache all ancestors encountered along the way
            for i, node in enumerate(chain):
                if node["id"] not in cache:
                    cache[node["id"]] = " > ".join(
                        n["id"] for n in chain[:i + 1]
                    )
    return {pid: cache.get(pid, pid) for pid in process_ids}


def count_processes(conn: sqlite3.Connection) -> int:
    """Count total processes."""
    row = conn.execute("SELECT COUNT(*) FROM processes").fetchone()
    return row[0]


def count_kpis(conn: sqlite3.Connection) -> int:
    """Count total KPIs."""
    row = conn.execute("SELECT COUNT(*) FROM kpis").fetchone()
    return row[0]


def _row_to_kpi(row: sqlite3.Row) -> dict:
    """Convert a database row to a KPI dict."""
    return dict(row)
