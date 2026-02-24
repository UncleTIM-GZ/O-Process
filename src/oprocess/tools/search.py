"""Search-related MCP tools — search_process and map_role_to_processes.

Split from registry.py to keep files under 300 lines.
"""

from __future__ import annotations

from typing import Annotated, Literal

from mcp.types import ToolAnnotations
from pydantic import Field

from oprocess.db.connection import get_shared_connection
from oprocess.db.queries import search_processes
from oprocess.gateway import PassthroughGateway
from oprocess.tools.helpers import (
    apply_boundary,
    build_search_provenance,
)
from oprocess.tools.serialization import response_to_json

# -- Tool annotations --
_READ_ONLY_OPEN = ToolAnnotations(
    readOnlyHint=True, idempotentHint=True, openWorldHint=True,
)

# -- Reusable Annotated type aliases --
Lang = Annotated[
    Literal["zh", "en"], Field(description="Language"),
]

_gateway: PassthroughGateway | None = None


def _get_gateway() -> PassthroughGateway:
    """Lazy-init gateway with audit_conn from shared connection."""
    global _gateway
    if _gateway is None:
        conn = get_shared_connection()
        _gateway = PassthroughGateway(audit_conn=conn)
    return _gateway


def register_search_tools(mcp) -> None:
    """Register search-related tool functions on the FastMCP instance."""

    @mcp.tool(annotations=_READ_ONLY_OPEN)
    def search_process(
        query: Annotated[
            str, Field(min_length=1, max_length=500),
        ],
        lang: Lang = "zh",
        limit: Annotated[
            int, Field(ge=1, le=50, description="Max results"),
        ] = 10,
        level: Annotated[
            int | None, Field(ge=1, le=5, description="Level 1-5"),
        ] = None,
    ) -> str:
        """Search the O'Process framework (2325 nodes).

        Covers APQC PCF 7.4 + ITIL 4 + SCOR 12.0.
        Supports semantic vector search with cosine similarity.
        Returns matching nodes with id, name, description, score.
        Low-confidence queries trigger BoundaryResponse."""
        conn = get_shared_connection()
        resp = _get_gateway().execute(
            "search_process",
            search_processes,
            conn=conn,
            query=query,
            lang=lang,
            limit=limit,
            level=level,
        )
        results = resp.result if isinstance(resp.result, list) else []
        resp.provenance_chain = build_search_provenance(
            conn, results, lang,
        )

        apply_boundary(query, results, resp)
        return response_to_json(resp)

    @mcp.tool(annotations=_READ_ONLY_OPEN)
    def map_role_to_processes(
        role_description: Annotated[
            str,
            Field(min_length=1, max_length=500),
        ],
        lang: Lang = "zh",
        limit: Annotated[
            int, Field(ge=1, le=50, description="Max matches"),
        ] = 10,
        industry: Annotated[
            str | None,
            Field(max_length=100, description="Industry tag"),
        ] = None,
    ) -> str:
        """Map a job role to relevant process nodes.

        Uses semantic search to find matching processes.
        Returns ranked list with confidence scores.
        Optionally filter by industry tag.
        Low-confidence triggers BoundaryResponse."""
        conn = get_shared_connection()
        resp = _get_gateway().execute(
            "map_role_to_processes",
            search_processes,
            conn=conn,
            query=role_description,
            lang=lang,
            limit=limit,
        )
        results = resp.result if isinstance(resp.result, list) else []
        if industry:
            results = [
                r for r in results
                if industry.lower() in [
                    t.lower() for t in r.get("tags", [])
                ]
            ]
            resp.result = results
        resp.provenance_chain = build_search_provenance(
            conn, results, lang,
        )

        apply_boundary(role_description, results, resp)
        return response_to_json(resp)
