"""Generate vector embeddings for process nodes.

Usage:
    OPENAI_API_KEY=... python scripts/embed.py

Falls back to TF-IDF vectors if no API key is set.
"""

from __future__ import annotations

import hashlib
import json
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from oprocess.db.connection import get_connection

BATCH_SIZE = 100
EMBEDDING_DIM = 1536  # text-embedding-3-small


def _text_for_embedding(row: dict) -> str:
    """Build the text to embed for a process node."""
    parts = [row["name_en"], row["name_zh"]]
    if row["description_en"]:
        parts.append(row["description_en"])
    if row["ai_context"]:
        parts.append(row["ai_context"])
    return " | ".join(parts)


def _text_hash(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()[:16]


def _pack_embedding(vec: list[float]) -> bytes:
    """Pack float list to bytes for BLOB storage."""
    return struct.pack(f"{len(vec)}f", *vec)


def _embed_openai(texts: list[str], api_key: str) -> list[list[float]]:
    """Embed texts using OpenAI API."""
    import openai

    client = openai.OpenAI(api_key=api_key)
    response = client.embeddings.create(
        model="text-embedding-3-small",
        input=texts,
    )
    return [item.embedding for item in response.data]


def _embed_tfidf(texts: list[str], dim: int = 384) -> list[list[float]]:
    """Simple hash-based embedding fallback (no API needed)."""
    import math

    vectors = []
    for text in texts:
        vec = [0.0] * dim
        words = text.lower().split()
        for i, word in enumerate(words):
            h = hash(word)
            idx = abs(h) % dim
            vec[idx] += 1.0 / (1 + i * 0.1)
        norm = math.sqrt(sum(v * v for v in vec)) or 1.0
        vectors.append([v / norm for v in vec])
    return vectors


def main() -> None:
    import os

    api_key = os.environ.get("OPENAI_API_KEY")
    use_openai = bool(api_key)

    if use_openai:
        print(f"Using OpenAI text-embedding-3-small ({EMBEDDING_DIM}d)")
    else:
        print("No OPENAI_API_KEY — using TF-IDF fallback (384d)")
        print("  Set OPENAI_API_KEY for production-quality embeddings")

    conn = get_connection()
    rows = conn.execute(
        "SELECT id, name_en, name_zh, description_en, ai_context "
        "FROM processes ORDER BY id"
    ).fetchall()

    print(f"Total processes: {len(rows)}")

    # Check which need updating
    existing = {}
    for r in conn.execute(
        "SELECT process_id, text_hash FROM process_embeddings"
    ).fetchall():
        existing[r["process_id"]] = r["text_hash"]

    to_embed = []
    for row in rows:
        row_dict = dict(row)
        text = _text_for_embedding(row_dict)
        h = _text_hash(text)
        if existing.get(row_dict["id"]) != h:
            to_embed.append((row_dict["id"], text, h))

    print(f"  Already embedded: {len(rows) - len(to_embed)}")
    print(f"  To embed: {len(to_embed)}")

    if not to_embed:
        print("All embeddings up to date!")
        conn.close()
        return

    total_batches = (len(to_embed) + BATCH_SIZE - 1) // BATCH_SIZE
    embedded = 0

    for i in range(0, len(to_embed), BATCH_SIZE):
        batch = to_embed[i : i + BATCH_SIZE]
        batch_num = i // BATCH_SIZE + 1
        texts = [t for _, t, _ in batch]

        print(f"  Batch {batch_num}/{total_batches}...", end="", flush=True)

        if use_openai:
            vectors = _embed_openai(texts, api_key)
        else:
            vectors = _embed_tfidf(texts)

        insert_rows = []
        for (pid, _, h), vec in zip(batch, vectors):
            insert_rows.append((pid, _pack_embedding(vec), h))

        conn.executemany(
            """INSERT OR REPLACE INTO process_embeddings
            (process_id, embedding, text_hash)
            VALUES (?, ?, ?)""",
            insert_rows,
        )
        conn.commit()
        embedded += len(batch)
        print(f" OK ({len(batch)} embedded)")

    print(f"\nDone: {embedded} embeddings generated")
    total = conn.execute(
        "SELECT COUNT(*) FROM process_embeddings"
    ).fetchone()[0]
    print(f"Total embeddings in DB: {total}")
    conn.close()


if __name__ == "__main__":
    main()
