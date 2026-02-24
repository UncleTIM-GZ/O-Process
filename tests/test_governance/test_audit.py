"""Tests for SessionAuditLog."""

from __future__ import annotations

import sqlite3

import pytest

from oprocess.governance.audit import (
    _validate_session_id,
    get_session_log,
    hash_input,
    log_invocation,
)

# Valid UUID4 session IDs for testing
_SID1 = "11111111-1111-4111-8111-111111111111"
_SID2 = "22222222-2222-4222-8222-222222222222"
_SID3 = "33333333-3333-4333-8333-333333333333"
_SID4 = "44444444-4444-4444-8444-444444444444"
_SID5 = "55555555-5555-4555-8555-555555555555"
_SID6 = "66666666-6666-4666-8666-666666666666"
_SID7 = "77777777-7777-4777-8777-777777777777"
_SID8 = "88888888-8888-4888-8888-888888888888"
_SID_IDEM = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
_SID_NORID = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"
_SID_DIFF = "cccccccc-cccc-4ccc-8ccc-cccccccccccc"


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


class TestSessionIdValidation:
    """P2-7: session_id format validation."""

    def test_valid_uuid4(self):
        assert _validate_session_id(_SID1) is True

    def test_invalid_short(self):
        assert _validate_session_id("s1") is False

    def test_invalid_format(self):
        assert _validate_session_id("not-a-uuid") is False

    def test_invalid_empty(self):
        assert _validate_session_id("") is False

    def test_invalid_session_skips_log(self, db_conn):
        """Invalid session_id should silently skip logging."""
        log_invocation(
            db_conn,
            session_id="bad-id",
            tool_name="test",
            input_hash="0000000000000000",
        )
        logs = get_session_log(db_conn, "bad-id")
        assert logs == []


class TestAuditLog:
    def test_log_and_retrieve(self, db_conn):
        log_invocation(
            db_conn,
            session_id=_SID1,
            tool_name="search_process",
            input_hash=hash_input({"query": "供应链"}),
            output_node_ids=["1.0", "4.0"],
            lang="zh",
            response_ms=42,
        )
        logs = get_session_log(db_conn, _SID1)
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
                session_id=_SID2,
                tool_name=f"tool_{i}",
                input_hash=hash_input({"i": i}),
            )
        logs = get_session_log(db_conn, _SID2)
        assert len(logs) == 3

    def test_governance_ext_default(self, db_conn):
        log_invocation(
            db_conn,
            session_id=_SID5,
            tool_name="test",
            input_hash="abcdef0123456789",
        )
        logs = get_session_log(db_conn, _SID5)
        assert logs[0]["governance_ext"] == "{}"

    def test_governance_ext_with_error(self, db_conn):
        log_invocation(
            db_conn,
            session_id=_SID8,
            tool_name="test",
            input_hash="abcdef0123456789",
            governance_ext={"error": "something failed"},
        )
        logs = get_session_log(db_conn, _SID8)
        assert '"error"' in logs[0]["governance_ext"]

    def test_never_raises(self, db_conn):
        """Audit log should never raise even with bad data."""
        db_conn.close()
        log_invocation(
            db_conn,
            session_id=_SID4,
            tool_name="test",
            input_hash="0000000000000000",
        )


class TestIdempotency:
    def test_duplicate_request_id_ignored(self, db_conn):
        """Same request_id should only write once."""
        for _ in range(3):
            log_invocation(
                db_conn,
                session_id=_SID_IDEM,
                tool_name="search",
                input_hash="aabbccdd00112233",
                request_id="req-001",
            )
        logs = get_session_log(db_conn, _SID_IDEM)
        assert len(logs) == 1

    def test_no_request_id_allows_duplicates(self, db_conn):
        """Without request_id, multiple writes are allowed."""
        for _ in range(3):
            log_invocation(
                db_conn,
                session_id=_SID_NORID,
                tool_name="search",
                input_hash="aabbccdd00112233",
            )
        logs = get_session_log(db_conn, _SID_NORID)
        assert len(logs) == 3

    def test_different_request_ids_both_written(self, db_conn):
        """Different request_ids write separate entries."""
        log_invocation(
            db_conn,
            session_id=_SID_DIFF,
            tool_name="search",
            input_hash="aabbccdd00112233",
            request_id="req-A",
        )
        log_invocation(
            db_conn,
            session_id=_SID_DIFF,
            tool_name="search",
            input_hash="aabbccdd00112233",
            request_id="req-B",
        )
        logs = get_session_log(db_conn, _SID_DIFF)
        assert len(logs) == 2


class TestAppendOnlyTriggers:
    def test_update_blocked(self, db_conn):
        log_invocation(
            db_conn,
            session_id=_SID6,
            tool_name="test",
            input_hash="1111111111111111",
        )
        with pytest.raises(sqlite3.IntegrityError, match="append-only"):
            db_conn.execute(
                "UPDATE session_audit_log SET tool_name = 'hacked' "
                f"WHERE session_id = '{_SID6}'"
            )

    def test_delete_blocked(self, db_conn):
        log_invocation(
            db_conn,
            session_id=_SID7,
            tool_name="test",
            input_hash="2222222222222222",
        )
        with pytest.raises(sqlite3.IntegrityError, match="append-only"):
            db_conn.execute(
                "DELETE FROM session_audit_log "
                f"WHERE session_id = '{_SID7}'"
            )
