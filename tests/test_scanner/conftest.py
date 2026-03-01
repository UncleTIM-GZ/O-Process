"""Scanner-specific test fixtures."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from oprocess.db.connection import get_connection, init_schema
from scripts.scanner.schema import init_scan_schema


@pytest.fixture
def scan_db(tmp_path: Path) -> sqlite3.Connection:
    """Test DB with both core and scanner schemas initialized."""
    db_path = tmp_path / "test_scan.db"
    conn = get_connection(db_path)
    init_schema(conn)
    init_scan_schema(conn)

    # Insert sample processes for scanner tests
    processes = [
        ("1.0", 1, None, "operating",
         "制定愿景与战略", "Develop Vision and Strategy",
         "为组织确立方向和愿景", "Establishing a direction and vision",
         "Strategy and vision", '["PCF:1.0"]', '["strategy"]', '[]', 1),
        ("1.1", 2, "1.0", "operating",
         "定义业务概念", "Define business concept",
         "定义业务概念和长期愿景", "Define the business concept",
         "Business concept", '["PCF:1.1"]', '["strategy"]', '[]', 1),
        ("8.0", 1, None, "management_support",
         "管理信息技术", "Manage IT",
         "管理信息技术", "Manage Information Technology",
         "IT management", '["PCF:8.0"]', '["it"]', '[]', 1),
    ]
    conn.executemany(
        """INSERT INTO processes
        (id, level, parent_id, domain, name_zh, name_en,
         description_zh, description_en, ai_context,
         source, tags, kpi_refs, provenance_eligible)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        processes,
    )
    conn.commit()
    return conn


@pytest.fixture
def sample_parsed_json() -> dict:
    """Sample parsed JSON from LLM response."""
    return {
        "node_id": "1.0",
        "scan_timestamp": "2026-03-01T00:00:00Z",
        "model_id": "gemini-2.0-flash",
        "dimension_1_ai_penetration": {
            "decision_replaceability": {"rating": "中", "basis": "测试依据"},
            "processing_acceleration": {"rating": "高", "basis": "测试依据"},
            "tacit_knowledge_dependency": {"rating": "高", "basis": "测试依据"},
            "overall_penetration": "中",
        },
        "dimension_2_change_status": {
            "status": "将变",
            "evidence_type": "类型B",
            "evidence_source": "混合来源",
            "basis_description": "测试依据描述",
        },
        "dimension_3_change_nature": {
            "applicable": True,
            "types_selected": ["A"],
            "type_descriptions": {
                "A": "增强型描述", "B": None, "C": None, "D": None,
            },
        },
        "dimension_4_boundary": {
            "current_type": "类型2",
            "boundary_description": "人机不可分割",
            "stability": "过渡中",
            "stability_note": "边界正在移动",
        },
        "dimension_5_uncertainty": {
            "overall_confidence": "中",
            "uncertainty_sources": ["benchmark_only", "fast_changing"],
            "special_note": None,
        },
        "dimension_6_signal_quality": {
            "information_period": "2022-2024",
            "source_distribution": {
                "academic": "中",
                "industry_media": "高",
                "corporate_disclosure": "低",
                "consulting_reports": "中",
                "regulatory": "低",
            },
            "potential_bias": "标杆企业偏差",
        },
        "scan_summary": {
            "one_line_judgment": "AI正在改变战略规划的信息收集方式",
            "priority_flag": "常规验证",
            "priority_reason": "证据主要来自标杆企业",
        },
    }
