"""Tests for scanner database schema."""

from __future__ import annotations

from pathlib import Path

from oprocess.db.connection import get_connection, init_schema
from scripts.scanner.schema import init_scan_schema


def test_init_scan_schema_creates_tables(tmp_path: Path) -> None:
    """All 4 scanner tables should be created."""
    conn = get_connection(tmp_path / "test.db")
    init_schema(conn)
    init_scan_schema(conn)

    tables = {
        row["name"]
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
    }

    assert "ai_impact_scan_results" in tables
    assert "ai_scan_raw_responses" in tables
    assert "ai_scan_audit_log" in tables
    assert "ai_scan_batch_summary" in tables
    conn.close()


def test_scan_results_columns(tmp_path: Path) -> None:
    """Verify key columns exist in ai_impact_scan_results."""
    conn = get_connection(tmp_path / "test.db")
    init_schema(conn)
    init_scan_schema(conn)

    cols = {
        row[1]
        for row in conn.execute(
            "PRAGMA table_info(ai_impact_scan_results)"
        ).fetchall()
    }

    expected = {
        "node_id", "batch_id", "scan_timestamp",
        "penetration_overall", "change_status",
        "boundary_current_type", "uncertainty_confidence",
        "model_agreement_status", "processing_status",
        "divergence_detail", "summary_one_line",
    }
    assert expected.issubset(cols)
    conn.close()


def test_idempotent_schema_init(tmp_path: Path) -> None:
    """Calling init_scan_schema twice should not raise."""
    conn = get_connection(tmp_path / "test.db")
    init_schema(conn)
    init_scan_schema(conn)
    init_scan_schema(conn)  # should not raise

    count = conn.execute(
        "SELECT COUNT(*) FROM sqlite_master "
        "WHERE type='table' AND name='ai_impact_scan_results'"
    ).fetchone()[0]
    assert count == 1
    conn.close()


def test_raw_responses_columns(tmp_path: Path) -> None:
    """Verify key columns in ai_scan_raw_responses."""
    conn = get_connection(tmp_path / "test.db")
    init_schema(conn)
    init_scan_schema(conn)

    cols = {
        row[1]
        for row in conn.execute(
            "PRAGMA table_info(ai_scan_raw_responses)"
        ).fetchall()
    }

    expected = {
        "batch_id", "node_id", "model_id", "raw_response",
        "parsed_success", "response_time_ms",
    }
    assert expected.issubset(cols)
    conn.close()


def test_raw_responses_prompt_columns(tmp_path: Path) -> None:
    """Migration should add system_prompt, user_prompt, model_config."""
    conn = get_connection(tmp_path / "test.db")
    init_schema(conn)
    init_scan_schema(conn)

    cols = {
        row[1]
        for row in conn.execute(
            "PRAGMA table_info(ai_scan_raw_responses)"
        ).fetchall()
    }

    assert "system_prompt" in cols
    assert "user_prompt" in cols
    assert "model_config" in cols
    conn.close()


def test_migration_idempotent(tmp_path: Path) -> None:
    """Running migration twice should not raise or duplicate columns."""
    conn = get_connection(tmp_path / "test.db")
    init_schema(conn)
    init_scan_schema(conn)
    init_scan_schema(conn)  # second call — idempotent

    col_names = [
        row[1]
        for row in conn.execute(
            "PRAGMA table_info(ai_scan_raw_responses)"
        ).fetchall()
    ]
    # No duplicates
    assert len(col_names) == len(set(col_names))
    assert "system_prompt" in col_names
    conn.close()


def test_migration_backfills_system_prompt(tmp_path: Path) -> None:
    """Existing records should get system_prompt backfilled."""
    from scripts.scanner.models import SYSTEM_PROMPT

    conn = get_connection(tmp_path / "test.db")
    init_schema(conn)
    # Create tables WITHOUT migration columns first
    conn.executescript(
        "CREATE TABLE IF NOT EXISTS ai_scan_raw_responses ("
        "id INTEGER PRIMARY KEY, batch_id TEXT, node_id TEXT, "
        "model_id TEXT, scan_timestamp TEXT, prompt_tokens INTEGER, "
        "completion_tokens INTEGER, total_tokens INTEGER, "
        "raw_response TEXT, parsed_success INTEGER, "
        "parse_error TEXT, response_time_ms INTEGER);"
    )
    # Insert a pre-migration record
    conn.execute(
        "INSERT INTO ai_scan_raw_responses "
        "(batch_id, node_id, model_id, scan_timestamp, raw_response) "
        "VALUES ('b1', 'n1', 'gemini', '2026-01-01', '{}')",
    )
    conn.commit()

    # Now run migration
    from scripts.scanner.schema import _migrate_raw_responses_prompts
    _migrate_raw_responses_prompts(conn)

    row = conn.execute(
        "SELECT system_prompt FROM ai_scan_raw_responses WHERE node_id = 'n1'",
    ).fetchone()
    assert row[0] == SYSTEM_PROMPT
    conn.close()
