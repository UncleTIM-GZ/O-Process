"""Vector similarity search for process nodes."""

from __future__ import annotations

import math
import sqlite3
import struct


def _unpack_embedding(blob: bytes) -> list[float]:
    """Unpack BLOB to float list."""
    n = len(blob) // 4
    return list(struct.unpack(f"{n}f", blob))


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    """Compute cosine similarity between two vectors."""
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def _embed_query_tfidf(query: str, dim: int = 384) -> list[float]:
    """Hash-based embedding for query text (matches embed.py fallback)."""
    vec = [0.0] * dim
    words = query.lower().split()
    for i, word in enumerate(words):
        h = hash(word)
        idx = abs(h) % dim
        vec[idx] += 1.0 / (1 + i * 0.1)
    norm = math.sqrt(sum(v * v for v in vec)) or 1.0
    return [v / norm for v in vec]


def vector_search(
    conn: sqlite3.Connection,
    query: str,
    limit: int = 10,
    threshold: float = 0.0,
) -> list[dict]:
    """Search processes using vector similarity.

    Returns list of {process_id, score, ...} sorted by score desc.
    """
    query_vec = _embed_query_tfidf(query)

    rows = conn.execute(
        """SELECT pe.process_id, pe.embedding,
                  p.name_zh, p.name_en, p.level, p.domain
           FROM process_embeddings pe
           JOIN processes p ON pe.process_id = p.id"""
    ).fetchall()

    results = []
    for row in rows:
        emb = _unpack_embedding(row["embedding"])
        # Handle dimension mismatch
        if len(emb) != len(query_vec):
            continue
        score = _cosine_similarity(query_vec, emb)
        if score >= threshold:
            results.append({
                "process_id": row["process_id"],
                "score": round(score, 4),
                "name_zh": row["name_zh"],
                "name_en": row["name_en"],
                "level": row["level"],
                "domain": row["domain"],
            })

    results.sort(key=lambda x: x["score"], reverse=True)
    return results[:limit]
