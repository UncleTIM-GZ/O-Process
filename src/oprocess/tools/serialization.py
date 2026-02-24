"""Shared JSON serialization for MCP tools and resources."""

from __future__ import annotations

import json

from oprocess.gateway import ToolResponse


def to_json(data: object) -> str:
    """Serialize any data to JSON string for MCP responses."""
    return json.dumps(data, ensure_ascii=False, indent=2)


def response_to_json(resp: ToolResponse) -> str:
    """Serialize ToolResponse to JSON string for MCP."""
    return json.dumps(
        {
            "result": resp.result,
            "provenance_chain": resp.provenance_chain,
            "session_id": resp.session_id,
            "response_ms": resp.response_ms,
        },
        ensure_ascii=False,
        indent=2,
    )
