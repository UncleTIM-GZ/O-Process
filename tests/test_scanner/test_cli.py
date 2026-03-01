"""Tests for scanner CLI — dry-run and status."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from oprocess.db.connection import get_connection, init_schema
from scripts.scanner.cli import (
    _parse_models,
    run_dry_run,
    show_status,
)
from scripts.scanner.schema import init_scan_schema


@pytest.fixture
def cli_db(tmp_path: Path) -> sqlite3.Connection:
    """DB with schema + sample data for CLI tests."""
    conn = get_connection(tmp_path / "cli_test.db")
    init_schema(conn)
    init_scan_schema(conn)

    processes = [
        ("1.0", 1, None, "operating",
         "测试流程A", "Test A", "", "", "",
         '["PCF:1.0"]', '["strategy"]', '[]', 1),
        ("2.0", 1, None, "operating",
         "测试流程B", "Test B", "", "", "",
         '["ITIL:2.0"]', '["it"]', '[]', 1),
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


class TestDryRun:
    """Test dry-run output."""

    def test_dry_run_output(self, cli_db: sqlite3.Connection,
                            capsys: pytest.CaptureFixture) -> None:
        """Dry run should show node counts."""
        run_dry_run(cli_db)
        out = capsys.readouterr().out
        assert "Total nodes" in out
        assert "2" in out  # 2 sample nodes
        assert "Pending" in out


class TestStatus:
    """Test status output."""

    def test_status_no_results(self, cli_db: sqlite3.Connection,
                               capsys: pytest.CaptureFixture) -> None:
        """Status with no scan results."""
        show_status(cli_db)
        out = capsys.readouterr().out
        assert "Status" in out


class TestParseModels:
    """Test model name parsing."""

    def test_all(self) -> None:
        assert _parse_models("all") == ["gemini", "deepseek"]

    def test_single(self) -> None:
        assert _parse_models("gemini") == ["gemini"]

    def test_comma_separated(self) -> None:
        assert _parse_models("gemini,deepseek") == ["gemini", "deepseek"]

    def test_whitespace(self) -> None:
        assert _parse_models(" gemini , deepseek ") == ["gemini", "deepseek"]
