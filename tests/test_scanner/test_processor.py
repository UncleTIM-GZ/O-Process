"""Tests for scanner processor — agreement, merge, and DB writes."""

from __future__ import annotations

import json
import sqlite3

from scripts.scanner.models import LLMResponse
from scripts.scanner.processor import (
    build_node_context,
    check_agreement,
    load_pending_nodes,
    merge_results,
    write_node_results,
)


class TestCheckAgreement:
    """Test multi-model consistency checks."""

    def _make_response(
        self, model_id: str, change_status: str, penetration: str,
    ) -> LLMResponse:
        return LLMResponse(
            model_id=model_id,
            parsed_success=True,
            parsed_json={
                "dimension_1_ai_penetration": {
                    "overall_penetration": penetration,
                },
                "dimension_2_change_status": {
                    "status": change_status,
                },
            },
        )

    def test_full_agreement(self) -> None:
        """Both models agree on both fields."""
        responses = [
            self._make_response("gemini", "已变", "高"),
            self._make_response("deepseek", "已变", "高"),
        ]
        result = check_agreement(responses)
        assert result["status"] == "agreement"
        assert result["divergent_fields"] == []

    def test_divergent_change_status(self) -> None:
        """Models disagree on change_status."""
        responses = [
            self._make_response("gemini", "已变", "高"),
            self._make_response("deepseek", "将变", "高"),
        ]
        result = check_agreement(responses)
        assert result["status"] == "divergent"
        assert "change_status" in result["divergent_fields"]
        assert "interpretation_hint" in result

    def test_divergent_penetration(self) -> None:
        """Models disagree on overall_penetration."""
        responses = [
            self._make_response("gemini", "稳定", "高"),
            self._make_response("deepseek", "稳定", "低"),
        ]
        result = check_agreement(responses)
        assert result["status"] == "divergent"
        assert "overall_penetration" in result["divergent_fields"]

    def test_single_model(self) -> None:
        """Only one successful model → single_model."""
        responses = [
            self._make_response("gemini", "已变", "高"),
            LLMResponse(model_id="deepseek", parsed_success=False),
        ]
        result = check_agreement(responses)
        assert result["status"] == "single_model"


class TestMergeResults:
    """Test result merging logic."""

    def test_merge_agreement(self, sample_parsed_json: dict) -> None:
        """Agreement: values come from primary model."""
        resp = LLMResponse(
            model_id="gemini",
            parsed_success=True,
            parsed_json=sample_parsed_json,
        )
        agreement = {"status": "agreement", "divergent_fields": []}
        merged = merge_results([resp], agreement)

        assert merged["change_status"] == "将变"
        assert merged["penetration_overall"] == "中"
        assert merged["processing_status"] == "completed"
        assert merged["model_agreement_status"] == "agreement"
        assert merged["divergence_detail"] is None

    def test_merge_divergent(self, sample_parsed_json: dict) -> None:
        """Divergent: divergence_detail should be populated."""
        resp = LLMResponse(
            model_id="gemini",
            parsed_success=True,
            parsed_json=sample_parsed_json,
        )
        agreement = {
            "status": "divergent",
            "divergent_fields": ["change_status"],
            "judgments": {
                "gemini": {"change_status": "已变", "overall_penetration": "高"},
                "deepseek": {"change_status": "将变", "overall_penetration": "高"},
            },
        }
        merged = merge_results([resp], agreement)
        assert merged["model_agreement_status"] == "divergent"
        detail = json.loads(merged["divergence_detail"])
        assert "divergent_fields" in detail

    def test_merge_no_successful(self) -> None:
        """No successful responses → empty dict."""
        resp = LLMResponse(model_id="gemini", parsed_success=False)
        agreement = {"status": "single_model", "divergent_fields": []}
        merged = merge_results([resp], agreement)
        assert merged == {}


class TestWriteNodeResults:
    """Test transactional DB writes."""

    def test_write_success(self, scan_db: sqlite3.Connection,
                           sample_parsed_json: dict) -> None:
        """Successful write creates records in all tables."""
        resp = LLMResponse(
            model_id="gemini-2.0-flash",
            raw_response='{"test": 1}',
            parsed_success=True,
            parsed_json=sample_parsed_json,
            total_tokens=100,
            response_time_ms=500,
        )
        agreement = {"status": "single_model", "divergent_fields": []}
        merged = merge_results([resp], agreement)

        ok = write_node_results(
            scan_db, "1.0", "batch-001", [resp], merged,
            "2026-03-01T00:00:00Z",
        )
        assert ok is True

        # Verify scan result written
        count = scan_db.execute(
            "SELECT COUNT(*) FROM ai_impact_scan_results "
            "WHERE node_id = '1.0'",
        ).fetchone()[0]
        assert count == 1

        # Verify raw response written
        count = scan_db.execute(
            "SELECT COUNT(*) FROM ai_scan_raw_responses "
            "WHERE node_id = '1.0'",
        ).fetchone()[0]
        assert count == 1

        # Verify audit log entries
        count = scan_db.execute(
            "SELECT COUNT(*) FROM ai_scan_audit_log "
            "WHERE batch_id = 'batch-001'",
        ).fetchone()[0]
        assert count >= 1


class TestWritePromptColumns:
    """Test that prompt/config columns are written to raw_responses."""

    def test_prompt_columns_written(
        self, scan_db: sqlite3.Connection, sample_parsed_json: dict,
    ) -> None:
        """system_prompt, user_prompt, model_config should be stored."""
        resp = LLMResponse(
            model_id="gemini-2.5-flash",
            raw_response='{"test": 1}',
            parsed_success=True,
            parsed_json=sample_parsed_json,
            total_tokens=100,
            response_time_ms=500,
            system_prompt="You are a test assistant.",
            user_prompt="Scan node 1.0",
            model_config='{"model": "gemini-2.5-flash", "temperature": 0.3}',
        )
        agreement = {"status": "single_model", "divergent_fields": []}
        merged = merge_results([resp], agreement)

        ok = write_node_results(
            scan_db, "1.0", "batch-prompt", [resp], merged,
            "2026-03-01T00:00:00Z",
        )
        assert ok is True

        row = scan_db.execute(
            "SELECT system_prompt, user_prompt, model_config "
            "FROM ai_scan_raw_responses WHERE batch_id = 'batch-prompt'",
        ).fetchone()

        assert row["system_prompt"] == "You are a test assistant."
        assert row["user_prompt"] == "Scan node 1.0"
        assert '"gemini-2.5-flash"' in row["model_config"]

    def test_empty_prompt_stored_as_null(
        self, scan_db: sqlite3.Connection, sample_parsed_json: dict,
    ) -> None:
        """Empty prompt fields should be stored as NULL."""
        resp = LLMResponse(
            model_id="gemini-2.5-flash",
            raw_response='{"test": 1}',
            parsed_success=True,
            parsed_json=sample_parsed_json,
            total_tokens=50,
            response_time_ms=200,
        )
        agreement = {"status": "single_model", "divergent_fields": []}
        merged = merge_results([resp], agreement)

        ok = write_node_results(
            scan_db, "8.0", "batch-null", [resp], merged,
            "2026-03-01T00:00:00Z",
        )
        assert ok is True

        row = scan_db.execute(
            "SELECT system_prompt, user_prompt, model_config "
            "FROM ai_scan_raw_responses WHERE batch_id = 'batch-null'",
        ).fetchone()

        assert row["system_prompt"] is None
        assert row["user_prompt"] is None
        assert row["model_config"] is None


class TestLoadPendingNodes:
    """Test incremental node loading."""

    def test_load_all_nodes(self, scan_db: sqlite3.Connection) -> None:
        """All 3 sample nodes should load."""
        nodes = load_pending_nodes(scan_db, "batch-001")
        assert len(nodes) == 3

    def test_skip_completed(self, scan_db: sqlite3.Connection) -> None:
        """Completed nodes should be skipped."""
        # Mark 1.0 as completed
        scan_db.execute(
            "INSERT INTO ai_impact_scan_results "
            "(node_id, batch_id, scan_timestamp, processing_status) "
            "VALUES ('1.0', 'old-batch', '2026-01-01T00:00:00Z', 'completed')",
        )
        scan_db.commit()

        nodes = load_pending_nodes(scan_db, "batch-002")
        node_ids = [n["node_id"] for n in nodes]
        assert "1.0" not in node_ids
        assert len(nodes) == 2

    def test_limit(self, scan_db: sqlite3.Connection) -> None:
        """Limit parameter should cap results."""
        nodes = load_pending_nodes(scan_db, "batch-001", limit=1)
        assert len(nodes) == 1

    def test_specific_node(self, scan_db: sqlite3.Connection) -> None:
        """--node-id should load only that node."""
        nodes = load_pending_nodes(scan_db, "batch-001", node_id="8.0")
        assert len(nodes) == 1
        assert nodes[0]["node_id"] == "8.0"


class TestBuildNodeContext:
    """Test node context building."""

    def test_context_fields(self, scan_db: sqlite3.Connection) -> None:
        """Context should have all required fields."""
        row = scan_db.execute(
            "SELECT * FROM processes WHERE id = '1.0'",
        ).fetchone()
        ctx = build_node_context(scan_db, row)

        assert ctx["node_id"] == "1.0"
        assert ctx["node_name_zh"] == "制定愿景与战略"
        assert ctx["node_name_en"] == "Develop Vision and Strategy"
        assert ctx["node_level"] == "L1"
        assert "APQC" in ctx["source_framework"] or "PCF" in ctx["source_framework"]
        assert ctx["taxonomy_path"]  # not empty
