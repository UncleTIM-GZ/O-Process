"""Database query functions for O'Process."""

from __future__ import annotations

import logging
import re
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


_DEFAULT_MAX_NODES = 200


def get_subtree(
    conn: sqlite3.Connection,
    root_id: str,
    max_depth: int = 4,
    max_nodes: int = _DEFAULT_MAX_NODES,
) -> dict | None:
    """Get process with nested children up to max_depth levels.

    Limits total nodes to max_nodes. When exceeded, remaining
    children are omitted and a truncation warning is added.
    """
    root = get_process(conn, root_id)
    if not root:
        return None

    node_count = 0
    truncated = False

    def _build(node: dict, depth: int) -> dict:
        nonlocal node_count, truncated
        node_count += 1
        if depth >= max_depth:
            # Leaf at max depth — only mark truncated if it has children
            children = get_children(conn, node["id"])
            if children:
                truncated = True
            node["children"] = []
            return node
        if node_count >= max_nodes:
            truncated = True
            node["children"] = []
            return node
        children = get_children(conn, node["id"])
        built: list[dict] = []
        for c in children:
            if node_count >= max_nodes:
                truncated = True
                break
            built.append(_build(c, depth + 1))
        node["children"] = built
        return node

    tree = _build(root, 0)
    if truncated:
        tree["_truncated"] = True
        tree["_truncation_warning"] = (
            f"Response truncated at {node_count} nodes "
            f"(limit: {max_nodes}). Use a deeper process_id "
            f"or reduce max_depth to see full details."
        )
    return tree


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


# Minimal English stopwords for LIKE fallback tokenization
_EN_STOPWORDS = frozenset({
    "a", "an", "the", "is", "are", "was", "were", "be", "been",
    "in", "on", "at", "to", "for", "of", "and", "or", "not",
    "it", "this", "that", "with", "from", "by", "as", "do",
    "how", "what", "which", "who", "where", "when", "can",
})

_CJK_RE = re.compile(r"[\u4e00-\u9fff]")


def _tokenize_query(query: str) -> list[str]:
    """Tokenize search query into individual search tokens.

    English: split on whitespace, filter stopwords, min 2 chars.
    Chinese: extract 2-char bigrams (overlapping sliding window).
    Mixed text: combine both strategies.
    """
    tokens: list[str] = []
    seen: set[str] = set()
    # English/ASCII tokens
    for word in query.split():
        cleaned = word.strip().lower()
        is_cjk = _CJK_RE.search(cleaned)
        if len(cleaned) >= 2 and cleaned not in _EN_STOPWORDS and not is_cjk:
            if cleaned not in seen:
                seen.add(cleaned)
                tokens.append(cleaned)
    # Chinese bigrams from CJK characters
    cjk_chars = _CJK_RE.findall(query)
    for i in range(len(cjk_chars) - 1):
        bigram = cjk_chars[i] + cjk_chars[i + 1]
        if bigram not in seen:
            seen.add(bigram)
            tokens.append(bigram)
    # Fallback: use original query if nothing extracted
    if not tokens:
        tokens = [query.strip()]
    return tokens


def _search_like(
    conn: sqlite3.Connection,
    query: str,
    lang: str,
    limit: int,
    level: int | None,
) -> list[dict]:
    """Token-based LIKE search with OR matching.

    Tokenizes query, matches any token against name/description,
    ranks results by number of matched tokens (descending).
    """
    tokens = _tokenize_query(query)
    # Whitelist column names to prevent SQL injection via lang param
    col = "name_zh" if lang == "zh" else "name_en"
    desc_col = "description_zh" if lang == "zh" else "description_en"

    or_parts: list[str] = []
    score_parts: list[str] = []
    params: list = []
    for token in tokens:
        pat = f"%{_escape_like(token)}%"
        clause = (
            f"({col} LIKE ? ESCAPE '\\' "
            f"OR {desc_col} LIKE ? ESCAPE '\\')"
        )
        or_parts.append(clause)
        score_parts.append(f"(CASE WHEN {clause} THEN 1 ELSE 0 END)")
        params.extend([pat, pat])

    score_expr = " + ".join(score_parts)
    # Each token generates 2 LIKE placeholders (name + desc).
    # The same placeholders appear twice in the SQL:
    #   1) in SELECT's CASE score expressions
    #   2) in WHERE's OR conditions
    # So params must be duplicated: [score params...] + [where params...]
    all_params = list(params) + list(params)

    where = f"({' OR '.join(or_parts)})"
    if level is not None:
        where += " AND level = ?"
        all_params.append(level)
    all_params.append(limit)

    sql = (
        f"SELECT *, ({score_expr}) AS match_score "
        f"FROM processes WHERE {where} "
        f"ORDER BY match_score DESC, level, id LIMIT ?"
    )
    rows = conn.execute(sql, all_params).fetchall()
    results = [row_to_process(r) for r in rows]
    # Strip internal match_score from output
    for r in results:
        r.pop("match_score", None)
    return results


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
