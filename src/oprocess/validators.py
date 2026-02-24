"""Shared validation utilities — single source of truth.

Consolidates regex patterns and validation functions used across
prompts, resources, governance, and queries modules.
"""

from __future__ import annotations

import re

from fastmcp.exceptions import ResourceError, ToolError

# -- Compiled regex patterns (module-level for performance) --

PROCESS_ID_RE = re.compile(r"^\d+(\.\d+)*$")
PROCESS_IDS_RE = re.compile(r"^\d+(\.\d+)*(,\s*\d+(\.\d+)*)*$")
SESSION_ID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$",
    re.IGNORECASE,
)
CONTROL_CHAR_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]")

_VALID_LANGS = frozenset({"zh", "en"})


def validate_process_id(pid: str, *, resource: bool = False) -> None:
    """Validate process_id format (e.g. '1.0', '7.3.2').

    Args:
        pid: The process ID to validate.
        resource: If True, raise ResourceError; otherwise ValueError.
    """
    if not PROCESS_ID_RE.match(pid):
        msg = f"Invalid process ID format: {pid!r}"
        raise ResourceError(msg) if resource else ValueError(msg)


def validate_process_ids(pids: str) -> None:
    """Validate comma-separated process IDs."""
    if not PROCESS_IDS_RE.match(pids):
        msg = f"Invalid process_ids format: {pids!r}"
        raise ValueError(msg)


def validate_session_id(session_id: str, *, resource: bool = False) -> bool:
    """Validate session_id is a valid UUID4 format.

    Args:
        session_id: The session ID to validate.
        resource: If True, raise ResourceError on failure; otherwise return bool.

    Returns:
        True if valid. When resource=True, raises instead of returning False.
    """
    valid = bool(SESSION_ID_RE.match(session_id))
    if not valid and resource:
        msg = f"Invalid session ID format: {session_id}"
        raise ResourceError(msg)
    return valid


def validate_lang(lang: str, *, tool: bool = True) -> None:
    """Validate language parameter.

    Args:
        lang: Language code to validate.
        tool: If True, raise ToolError; otherwise ValueError.
    """
    if lang not in _VALID_LANGS:
        msg = f"Invalid language '{lang}'. Must be one of: {sorted(_VALID_LANGS)}"
        raise ToolError(msg) if tool else ValueError(msg)


def sanitize_role_name(name: str) -> str:
    """Validate and sanitize role_name to prevent prompt injection.

    Strips control chars, collapses whitespace, enforces length limit.
    """
    cleaned = CONTROL_CHAR_RE.sub("", name)
    cleaned = " ".join(cleaned.split())
    if not cleaned:
        msg = "role_name cannot be empty"
        raise ValueError(msg)
    if len(cleaned) > 100:
        msg = f"role_name exceeds 100 chars ({len(cleaned)})"
        raise ValueError(msg)
    return cleaned
