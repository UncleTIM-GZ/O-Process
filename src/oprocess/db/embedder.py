"""Pluggable embedding provider abstraction.

Supports Google Gemini (gemini-embedding-001) out of the box.
Falls back gracefully when no API key or library is available.
"""

from __future__ import annotations

import logging
import os
from typing import Protocol, runtime_checkable

logger = logging.getLogger(__name__)

GEMINI_DIM = 768


@runtime_checkable
class EmbedProvider(Protocol):
    """Interface for embedding providers."""

    @property
    def dim(self) -> int: ...

    def embed(self, texts: list[str]) -> list[list[float]]: ...


class GeminiEmbedder:
    """Google Gemini embedding provider (gemini-embedding-001)."""

    def __init__(self, api_key: str) -> None:
        from google import genai  # lazy import

        self._client = genai.Client(api_key=api_key)
        self._dim = GEMINI_DIM

    @property
    def dim(self) -> int:
        return self._dim

    def embed(self, texts: list[str]) -> list[list[float]]:
        from google.genai import types

        result = self._client.models.embed_content(
            model="gemini-embedding-001",
            contents=texts,
            config=types.EmbedContentConfig(
                output_dimensionality=self._dim,
            ),
        )
        return [e.values for e in result.embeddings]


def get_embedder() -> EmbedProvider | None:
    """Create an embedder from environment, or None if unavailable."""
    api_key = os.environ.get("GOOGLE_API_KEY") or os.environ.get(
        "GEMINI_API_KEY",
    )
    if not api_key:
        return None
    try:
        return GeminiEmbedder(api_key)
    except Exception:
        logger.warning("Failed to initialize GeminiEmbedder", exc_info=True)
        return None
