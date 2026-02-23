"""Shared test fixtures."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from oprocess.db.connection import get_connection, init_schema


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
