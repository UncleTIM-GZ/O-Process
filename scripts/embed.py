"""Generate vector embeddings for process nodes using Gemini.

Usage:
    GOOGLE_API_KEY=... python scripts/embed.py

Requires google-genai: pip install google-genai
"""

from __future__ import annotations

import hashlib
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from oprocess.db.connection import get_connection, init_schema
from oprocess.db.embedder import get_embedder
from oprocess.db.vector_search import serialize_float32

BATCH_SIZE = 100


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


def main() -> None:
    embedder = get_embedder()
    if not embedder:
        print("ERROR: GOOGLE_API_KEY or GEMINI_API_KEY required")
        print("  Get a free key: https://aistudio.google.com/apikey")
        sys.exit(1)

    print(f"Using Gemini embedding ({embedder.dim}d)")

    conn = get_connection()
    init_schema(conn)

    rows = conn.execute(
        "SELECT id, name_en, name_zh, description_en, ai_context "
        "FROM processes ORDER BY id",
    ).fetchall()
    print(f"Total processes: {len(rows)}")

    # Check which need updating
    existing = {}
    for r in conn.execute(
        "SELECT process_id, text_hash FROM process_embeddings",
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
        vectors = embedder.embed(texts)

        # Write to process_embeddings (hash tracking)
        emb_rows = []
        for (pid, _, h), vec in zip(batch, vectors):
            emb_rows.append((pid, _pack_embedding(vec), h))
        conn.executemany(
            "INSERT OR REPLACE INTO process_embeddings "
            "(process_id, embedding, text_hash) VALUES (?, ?, ?)",
            emb_rows,
        )

        # Write to vec_processes (sqlite-vec search)
        vec_rows = []
        for (pid, _, _h), vec in zip(batch, vectors):
            vec_rows.append((pid, serialize_float32(vec)))
        conn.executemany(
            "INSERT OR REPLACE INTO vec_processes "
            "(process_id, embedding) VALUES (?, ?)",
            vec_rows,
        )

        conn.commit()
        embedded += len(batch)
        print(f" OK ({len(batch)} embedded)")

    print(f"\nDone: {embedded} embeddings generated")
    total = conn.execute(
        "SELECT COUNT(*) FROM process_embeddings",
    ).fetchone()[0]
    vec_total = 0
    try:
        vec_total = conn.execute(
            "SELECT COUNT(*) FROM vec_processes",
        ).fetchone()[0]
    except Exception:
        pass
    print(f"Total in process_embeddings: {total}")
    print(f"Total in vec_processes: {vec_total}")
    conn.close()


if __name__ == "__main__":
    main()
