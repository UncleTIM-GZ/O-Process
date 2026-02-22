"""Text normalization utilities for O'Process framework construction."""

from __future__ import annotations


def normalize_text(text: str) -> str:
    """Normalize text: NBSP → regular space, strip whitespace."""
    return text.replace("\u00a0", " ").strip()
