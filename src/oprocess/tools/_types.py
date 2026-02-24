"""Shared type aliases for MCP tool parameters."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import Field

Lang = Annotated[
    Literal["zh", "en"], Field(description="Language"),
]
ProcessId = Annotated[
    str, Field(pattern=r"^\d+(\.\d+)*$", description="Process ID"),
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
