"""Tests for _types.py type aliases and validators."""
from oprocess.tools._types import _normalize_process_id


class TestNormalizeProcessId:
    def test_bare_digit(self):
        assert _normalize_process_id("1") == "1.0"
        assert _normalize_process_id("13") == "13.0"

    def test_already_dotted(self):
        assert _normalize_process_id("1.0") == "1.0"
        assert _normalize_process_id("8.5.3") == "8.5.3"

    def test_whitespace_stripped(self):
        assert _normalize_process_id(" 1 ") == "1.0"
        assert _normalize_process_id("  3  ") == "3.0"

    def test_non_digit_unchanged(self):
        assert _normalize_process_id("abc") == "abc"
        assert _normalize_process_id("1.1") == "1.1"

    def test_integer_input(self):
        assert _normalize_process_id(1) == "1.0"
        assert _normalize_process_id(13) == "13.0"
