"""Tests for SessionAuditLog."""

from __future__ import annotations

import sqlite3

import pytest

from oprocess.governance.audit import (
    get_session_log,
    hash_input,
    log_invocation,
)


class TestHashInput:
    def test_deterministic(self):
        params = {"query": "供应链", "lang": "zh"}
        assert hash_input(params) == hash_input(params)

    def test_length_16(self):
        h = hash_input({"key": "value"})
        assert len(h) == 16

    def test_different_params_different_hash(self):
        h1 = hash_input({"query": "a"})
        h2 = hash_input({"query": "b"})
        assert h1 != h2

    def test_key_order_irrelevant(self):
        h1 = hash_input({"a": 1, "b": 2})
        h2 = hash_input({"b": 2, "a": 1})
        assert h1 == h2


class TestAuditLog:
    def test_log_and_retrieve(self, db_conn):
        log_invocation(
            db_conn,
            session_id="s1",
            tool_name="search_process",
            input_hash=hash_input({"query": "供应链"}),
            output_node_ids=["1.0", "4.0"],
            lang="zh",
            response_ms=42,
        )
        logs = get_session_log(db_conn, "s1")
        assert len(logs) == 1
        assert logs[0]["tool_name"] == "search_process"
        assert logs[0]["response_ms"] == 42
        assert len(logs[0]["input_hash"]) == 16
        assert logs[0]["lang"] == "zh"
        assert '"1.0"' in logs[0]["output_node_ids"]

    def test_multiple_entries(self, db_conn):
        for i in range(3):
            log_invocation(
                db_conn,
                session_id="s2",
                tool_name=f"tool_{i}",
                input_hash=hash_input({"i": i}),
            )
        logs = get_session_log(db_conn, "s2")
        assert len(logs) == 3

    def test_governance_ext_default(self, db_conn):
        log_invocation(
            db_conn,
            session_id="s5",
            tool_name="test",
            input_hash="abcdef0123456789",
        )
        logs = get_session_log(db_conn, "s5")
        assert logs[0]["governance_ext"] == "{}"

    def test_governance_ext_with_error(self, db_conn):
        log_invocation(
            db_conn,
            session_id="s8",
            tool_name="test",
            input_hash="abcdef0123456789",
            governance_ext={"error": "something failed"},
        )
        logs = get_session_log(db_conn, "s8")
        assert '"error"' in logs[0]["governance_ext"]

    def test_never_raises(self, db_conn):
        """Audit log should never raise even with bad data."""
        db_conn.close()
        log_invocation(
            db_conn,
            session_id="s4",
            tool_name="test",
            input_hash="0000000000000000",
        )


class TestAppendOnlyTriggers:
    def test_update_blocked(self, db_conn):
        log_invocation(
            db_conn,
            session_id="s6",
            tool_name="test",
            input_hash="1111111111111111",
        )
        with pytest.raises(sqlite3.IntegrityError, match="append-only"):
            db_conn.execute(
                "UPDATE session_audit_log SET tool_name = 'hacked' "
                "WHERE session_id = 's6'"
            )

    def test_delete_blocked(self, db_conn):
        log_invocation(
            db_conn,
            session_id="s7",
            tool_name="test",
            input_hash="2222222222222222",
        )
        with pytest.raises(sqlite3.IntegrityError, match="append-only"):
            db_conn.execute(
                "DELETE FROM session_audit_log WHERE session_id = 's7'"
            )
