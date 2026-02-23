"""Text normalization utilities for O'Process framework construction."""

from __future__ import annotations


def normalize_text(text: str) -> str:
    """Normalize text: NBSP → regular space, strip whitespace."""
    return text.replace("\u00a0", " ").strip()


def truncate_at_sentence(text: str, max_len: int = 300) -> str:
    """Truncate text at the nearest sentence boundary within max_len."""
    if not text or len(text) <= max_len:
        return text
    truncated = text[:max_len]
    # Find last sentence-ending punctuation
    last_period = max(truncated.rfind(". "), truncated.rfind("。"))
    if last_period > max_len // 2:
        return truncated[: last_period + 1].rstrip()
    # Fallback: find last period (even at end of string)
    last_dot = truncated.rfind(".")
    if last_dot > max_len // 2:
        return truncated[: last_dot + 1].rstrip()
    return truncated.rstrip()
