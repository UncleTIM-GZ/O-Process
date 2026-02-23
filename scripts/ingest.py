"""Ingest framework.json and kpis.json into SQLite database.

Usage:
    python scripts/ingest.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from oprocess.db.connection import DEFAULT_DB_PATH, get_connection, init_schema
from shared.io import read_json

FRAMEWORK_PATH = Path("docs/oprocess-framework/framework.json")
KPIS_PATH = Path("docs/oprocess-framework/kpis.json")


def _flatten_tree(node: dict, rows: list[tuple]) -> None:
    """Recursively flatten tree into insertion rows."""
    rows.append((
        node["id"],
        node["level"],
        node.get("parent_id"),
        node.get("domain", "operating"),
        node["name"]["zh"],
        node["name"]["en"],
        node["description"]["zh"],
        node["description"]["en"],
        node.get("ai_context", ""),
        json.dumps(node.get("source", []), ensure_ascii=False),
        json.dumps(node.get("tags", []), ensure_ascii=False),
        json.dumps(node.get("kpi_refs", []), ensure_ascii=False),
        1 if node.get("provenance_eligible", True) else 0,
    ))
    for child in node.get("children", []):
        _flatten_tree(child, rows)


def ingest_framework(conn, framework: dict) -> int:
    """Insert all framework nodes into processes table."""
    rows: list[tuple] = []
    for cat in framework.get("categories", []):
        _flatten_tree(cat, rows)

    conn.executemany(
        """INSERT OR REPLACE INTO processes
        (id, level, parent_id, domain, name_zh, name_en,
         description_zh, description_en, ai_context,
         source, tags, kpi_refs, provenance_eligible)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        rows,
    )
    conn.commit()
    return len(rows)


def ingest_kpis(conn, kpis: list[dict]) -> int:
    """Insert all KPIs into kpis table."""
    rows = [
        (
            kpi["id"],
            kpi["process_id"],
            kpi["name"]["zh"],
            kpi["name"]["en"],
            kpi.get("unit"),
            kpi.get("formula"),
            kpi.get("category"),
            kpi.get("scor_attribute"),
            kpi.get("direction"),
        )
        for kpi in kpis
    ]
    conn.executemany(
        """INSERT OR REPLACE INTO kpis
        (id, process_id, name_zh, name_en, unit, formula,
         category, scor_attribute, direction)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        rows,
    )
    conn.commit()
    return len(rows)


def main() -> None:
    print("Loading JSON data...")
    framework = read_json(FRAMEWORK_PATH)
    kpis = read_json(KPIS_PATH)

    DEFAULT_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = get_connection()

    print("Initializing schema...")
    init_schema(conn)

    print("Ingesting framework...")
    process_count = ingest_framework(conn, framework)
    print(f"  Inserted {process_count} processes")

    print("Ingesting KPIs...")
    kpi_count = ingest_kpis(conn, kpis)
    print(f"  Inserted {kpi_count} KPIs")

    # Verify
    from oprocess.db.queries import count_kpis, count_processes

    actual_p = count_processes(conn)
    actual_k = count_kpis(conn)
    print(f"\nVerification:")
    print(f"  Processes in DB: {actual_p}")
    print(f"  KPIs in DB: {actual_k}")

    assert actual_p == process_count, f"Mismatch: {actual_p} != {process_count}"
    assert actual_k == kpi_count, f"Mismatch: {actual_k} != {kpi_count}"
    print("\nIngest complete!")
    conn.close()


if __name__ == "__main__":
    main()
