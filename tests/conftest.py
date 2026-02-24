"""Shared test fixtures."""

from __future__ import annotations

import math
import sqlite3
import struct
from pathlib import Path

import pytest

from oprocess.db.connection import get_connection, init_schema
from oprocess.db.embedder import GEMINI_DIM


@pytest.fixture
def db_conn(tmp_path: Path) -> sqlite3.Connection:
    """Get a test database connection with schema initialized."""
    db_path = tmp_path / "test.db"
    conn = get_connection(db_path)
    init_schema(conn)
    return conn


@pytest.fixture
def populated_db(db_conn: sqlite3.Connection) -> sqlite3.Connection:
    """Database with sample test data."""
    # Insert sample processes
    processes = [
        ("1.0", 1, None, "operating", "制定愿景与战略", "Develop Vision and Strategy",
         "为组织确立方向和愿景", "Establishing a direction and vision",
         "Strategy and vision", '["PCF:1.0"]', '["strategy"]', '[]', 1),
        ("1.1", 2, "1.0", "operating", "定义业务概念", "Define business concept",
         "定义业务概念和长期愿景", "Define the business concept and long-term vision",
         "Business concept", '["PCF:1.1"]', '["strategy"]', '[]', 1),
        ("8.0", 1, None, "management_support", "管理信息技术", "Manage IT",
         "管理信息技术", "Manage Information Technology",
         "IT management", '["PCF:8.0"]', '["it"]', '[]', 1),
        ("8.5", 2, "8.0", "management_support", "管理 AI 智能运维", "Manage AI Ops",
         "管理 AI 和智能运维", "Manage AI and Intelligent Operations",
         "AI operations", '["ITIL:ai"]', '["ai", "it"]', '[]', 1),
    ]
    db_conn.executemany(
        """INSERT INTO processes
        (id, level, parent_id, domain, name_zh, name_en,
         description_zh, description_en, ai_context,
         source, tags, kpi_refs, provenance_eligible)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        processes,
    )

    # Insert sample KPIs
    kpis = [
        ("kpi.1.0.01", "1.0", "战略执行率", "Strategy execution rate",
         "%", None, "Process Efficiency", None, "higher_is_better"),
        ("kpi.8.0.01", "8.0", "IT 服务可用性", "IT service availability",
         "%", None, "Reliability", None, "higher_is_better"),
    ]
    db_conn.executemany(
        """INSERT INTO kpis
        (id, process_id, name_zh, name_en, unit, formula,
         category, scor_attribute, direction)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        kpis,
    )
    db_conn.commit()
    return db_conn


def _make_embedding(keyword: str, dim: int = GEMINI_DIM) -> bytes:
    """Create a deterministic test embedding from a keyword.

    Uses PYTHONHASHSEED-safe approach: fixed positions per character.
    """
    vec = [0.0] * dim
    for i, ch in enumerate(keyword):
        idx = (ord(ch) * 31 + i * 7) % dim
        vec[idx] += 1.0 / (1 + i * 0.1)
    norm = math.sqrt(sum(v * v for v in vec)) or 1.0
    vec = [v / norm for v in vec]
    return struct.pack(f"{dim}f", *vec)


def _make_embedding_list(keyword: str, dim: int = GEMINI_DIM) -> list[float]:
    """Create a deterministic test embedding as float list."""
    blob = _make_embedding(keyword, dim)
    return list(struct.unpack(f"{dim}f", blob))


@pytest.fixture
def populated_db_with_embeddings(
    populated_db: sqlite3.Connection,
) -> sqlite3.Connection:
    """Database with sample processes AND vector embeddings."""
    embeddings = [
        ("1.0", _make_embedding("strategy vision"), "hash1"),
        ("1.1", _make_embedding("business concept"), "hash2"),
        ("8.0", _make_embedding("information technology"), "hash3"),
        ("8.5", _make_embedding("ai operations mlops"), "hash4"),
    ]
    populated_db.executemany(
        "INSERT INTO process_embeddings (process_id, embedding, text_hash) "
        "VALUES (?, ?, ?)",
        embeddings,
    )
    populated_db.commit()
    return populated_db


@pytest.fixture
def populated_db_with_vec(
    populated_db_with_embeddings: sqlite3.Connection,
) -> sqlite3.Connection:
    """Database with embeddings in BOTH process_embeddings and vec_processes."""
    conn = populated_db_with_embeddings
    # Copy embeddings into vec_processes for sqlite-vec search
    rows = conn.execute(
        "SELECT process_id, embedding FROM process_embeddings",
    ).fetchall()
    for row in rows:
        conn.execute(
            "INSERT OR REPLACE INTO vec_processes "
            "(process_id, embedding) VALUES (?, ?)",
            (row["process_id"], bytes(row["embedding"])),
        )
    conn.commit()
    return conn
