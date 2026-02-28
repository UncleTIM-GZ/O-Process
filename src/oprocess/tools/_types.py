"""Shared type aliases for MCP tool parameters."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BeforeValidator, Field


def _normalize_process_id(v: str | int) -> str:
    """Auto-normalize: bare digit '1' → '1.0' (L1 format)."""
    if isinstance(v, int):
        return f"{v}.0"
    if isinstance(v, str) and v.strip().isdigit():
        return f"{v.strip()}.0"
    return v


Lang = Annotated[
    Literal["zh", "en"], Field(description="Language"),
]
ProcessId = Annotated[
    str,
    Field(pattern=r"^\d+(\.\d+)*$", description="Process ID (e.g. '1.0', '8.5.3')"),
    BeforeValidator(_normalize_process_id),
]
ProcessIdList = Annotated[
    str,
    Field(
        pattern=r"^\d+(\.\d+)*(,\s*\d+(\.\d+)*)+$",
        description="Comma-separated process IDs (2+)",
    ),
]
ProcessIdListOpt = Annotated[
    str,
    Field(
        pattern=r"^\d+(\.\d+)*(,\s*\d+(\.\d+)*)*$",
        description="Comma-separated process IDs (1+)",
    ),
]
