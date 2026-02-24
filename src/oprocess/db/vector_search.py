"""Vector similarity search using sqlite-vec."""

from __future__ import annotations

import sqlite3
import struct

from oprocess.db.row_utils import row_to_process


def serialize_float32(vec: list[float]) -> bytes:
    """Pack float list to bytes for sqlite-vec MATCH."""
    return struct.pack(f"{len(vec)}f", *vec)


def has_embeddings(conn: sqlite3.Connection) -> bool:
    """Check if process_embeddings table has data."""
    row = conn.execute("SELECT COUNT(*) FROM process_embeddings").fetchone()
    return row[0] > 0


def has_vec_table(conn: sqlite3.Connection) -> bool:
    """Check if vec_processes virtual table exists and has data."""
    try:
        row = conn.execute(
            "SELECT COUNT(*) FROM vec_processes",
        ).fetchone()
        return row[0] > 0
    except Exception:
        return False


def vector_search(
    conn: sqlite3.Connection,
    query_embedding: list[float],
    limit: int = 10,
    level: int | None = None,
) -> list[dict]:
    """Search processes using sqlite-vec nearest-neighbor.

    Returns list of process dicts with `score` field (1.0 - distance),
    sorted by score descending.

    Uses JOIN to eliminate N+1 query pattern.
    """
    # Fetch more than needed when filtering by level (post-filter)
    fetch_limit = limit * 5 if level is not None else limit

    vec_rows = conn.execute(
        "SELECT process_id, distance FROM vec_processes "
        "WHERE embedding MATCH ? AND k = ? ORDER BY distance",
        (serialize_float32(query_embedding), fetch_limit),
    ).fetchall()

    if not vec_rows:
        return []

    # Batch-fetch all process rows in one query (eliminates N+1)
    pids = [vr[0] for vr in vec_rows]
    placeholders = ",".join("?" * len(pids))
    proc_rows = conn.execute(
        f"SELECT * FROM processes WHERE id IN ({placeholders})",
        pids,
    ).fetchall()

    proc_map = {row_to_process(r)["id"]: row_to_process(r) for r in proc_rows}

    results = []
    for vr in vec_rows:
        pid = vr[0]
        distance = vr[1]
        proc = proc_map.get(pid)
        if not proc:
            continue
        if level is not None and proc["level"] != level:
            continue
        proc["score"] = round(1.0 - distance, 4)
        results.append(proc)
        if len(results) >= limit:
            break

    return results
