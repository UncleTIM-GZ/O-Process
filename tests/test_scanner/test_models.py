"""Tests for scanner LLM models — JSON parsing and prompt building."""

from __future__ import annotations

import json

from scripts.scanner.models import (
    LLMResponse,
    build_user_prompt,
    parse_json_response,
)


class TestParseJsonResponse:
    """Test 3-step JSON parsing fallback."""

    def test_direct_json(self) -> None:
        """Step 1: direct JSON parsing."""
        raw = '{"node_id": "1.0", "status": "ok"}'
        result, err = parse_json_response(raw)
        assert result == {"node_id": "1.0", "status": "ok"}
        assert err == ""

    def test_json_in_code_block(self) -> None:
        """Step 2: extract from ```json``` block."""
        raw = 'Some text\n```json\n{"node_id": "1.0"}\n```\nMore text'
        result, err = parse_json_response(raw)
        assert result == {"node_id": "1.0"}
        assert err == ""

    def test_json_brace_extraction(self) -> None:
        """Step 3: extract first { to last }."""
        raw = 'Here is the result: {"node_id": "1.0", "val": 42} end'
        result, err = parse_json_response(raw)
        assert result == {"node_id": "1.0", "val": 42}
        assert err == ""

    def test_no_json_found(self) -> None:
        """All steps fail: no JSON in response."""
        raw = "This is just plain text without any JSON"
        result, err = parse_json_response(raw)
        assert result is None
        assert "no JSON" in err

    def test_empty_response(self) -> None:
        """Empty string should return error."""
        result, err = parse_json_response("")
        assert result is None
        assert "empty" in err

    def test_chinese_json(self) -> None:
        """Handles Chinese content in JSON."""
        data = {"node_id": "1.0", "name": "制定愿景与战略"}
        raw = json.dumps(data, ensure_ascii=False)
        result, err = parse_json_response(raw)
        assert result["name"] == "制定愿景与战略"
        assert err == ""

    def test_nested_json(self, sample_parsed_json: dict) -> None:
        """Full nested JSON structure from LLM."""
        raw = json.dumps(sample_parsed_json, ensure_ascii=False)
        result, err = parse_json_response(raw)
        assert result is not None
        assert result["node_id"] == "1.0"
        assert err == ""


class TestBuildUserPrompt:
    """Test prompt template filling."""

    def test_fills_all_fields(self) -> None:
        """All template variables should be replaced."""
        node = {
            "node_id": "1.0",
            "node_name_zh": "测试流程",
            "node_name_en": "Test Process",
            "source_framework": "APQC",
            "taxonomy_path": "1.0 测试",
            "node_level": "L1",
            "node_description": "描述文本",
            "domain_tags": "strategy | planning",
        }
        prompt = build_user_prompt(node)
        assert "1.0" in prompt
        assert "测试流程" in prompt
        assert "Test Process" in prompt
        assert "APQC" in prompt
        assert "{node_id}" not in prompt  # no unresolved placeholders

    def test_handles_empty_fields(self) -> None:
        """Empty fields should not cause errors."""
        node = {"node_id": "1.0"}
        prompt = build_user_prompt(node)
        assert "1.0" in prompt


class TestLLMResponse:
    """Test LLMResponse dataclass."""

    def test_defaults(self) -> None:
        """Default values should be sensible."""
        resp = LLMResponse()
        assert resp.model_id == ""
        assert resp.parsed_success is False
        assert resp.total_tokens == 0

    def test_with_values(self) -> None:
        """Fields should be settable."""
        resp = LLMResponse(
            model_id="gemini-2.0-flash",
            raw_response='{"test": 1}',
            parsed_success=True,
            total_tokens=100,
        )
        assert resp.model_id == "gemini-2.0-flash"
        assert resp.total_tokens == 100
