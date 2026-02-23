"""Tests for SessionAuditLog."""

from __future__ import annotations

from oprocess.governance.audit import get_session_log, log_invocation


class TestAuditLog:
    def test_log_and_retrieve(self, db_conn):
        log_invocation(
            db_conn,
            session_id="s1",
            tool_name="search_process",
            input_params={"query": "供应链"},
            output_summary="3 results",
            response_ms=42,
        )
        logs = get_session_log(db_conn, "s1")
        assert len(logs) == 1
        assert logs[0]["tool_name"] == "search_process"
        assert logs[0]["response_ms"] == 42

    def test_multiple_entries(self, db_conn):
        for i in range(3):
            log_invocation(
                db_conn,
                session_id="s2",
                tool_name=f"tool_{i}",
                input_params={},
            )
        logs = get_session_log(db_conn, "s2")
        assert len(logs) == 3

    def test_error_logging(self, db_conn):
        log_invocation(
            db_conn,
            session_id="s3",
            tool_name="bad_tool",
            input_params={},
            error="Something went wrong",
        )
        logs = get_session_log(db_conn, "s3")
        assert logs[0]["error"] == "Something went wrong"

    def test_never_raises(self, db_conn):
        """Audit log should never raise even with bad data."""
        # Close connection to force error
        db_conn.close()
        # This should not raise
        log_invocation(
            db_conn,
            session_id="s4",
            tool_name="test",
            input_params={},
        )
