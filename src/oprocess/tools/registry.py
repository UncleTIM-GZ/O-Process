"""Tool implementations — registered via register_tools(mcp).

All MCP tool functions live here, keeping server.py lean.
"""

from __future__ import annotations

import json
from typing import Annotated, Literal

from fastmcp.exceptions import ToolError
from mcp.types import ToolAnnotations
from pydantic import Field

from oprocess.db.connection import get_shared_connection
from oprocess.db.queries import (
    count_kpis,
    count_processes,
    get_ancestor_chain,
    get_kpis_for_process,
    get_process,
    get_processes_by_level,
    get_subtree,
    search_processes,
    validate_lang,
)
from oprocess.gateway import PassthroughGateway, ToolResponse
from oprocess.tools.export import build_responsibility_doc
from oprocess.tools.helpers import (
    apply_boundary,
    build_hierarchy_provenance,
    build_lookup_provenance,
    build_search_provenance,
    compare_process_nodes,
    responsibilities_to_md,
)

_gateway: PassthroughGateway | None = None


def _get_gateway() -> PassthroughGateway:
    """Lazy-init gateway with audit_conn from shared connection."""
    global _gateway
    if _gateway is None:
        conn = get_shared_connection()
        _gateway = PassthroughGateway(audit_conn=conn)
    return _gateway

# -- Tool annotations --
_READ_ONLY = ToolAnnotations(
    readOnlyHint=True, idempotentHint=True, openWorldHint=False,
)
_READ_ONLY_OPEN = ToolAnnotations(
    readOnlyHint=True, idempotentHint=True, openWorldHint=True,
)

# -- Reusable Annotated type aliases for tool parameters --
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


def _to_json(resp: ToolResponse) -> str:
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


def register_tools(mcp) -> None:
    """Register all tool functions on the FastMCP instance."""

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
        return _to_json(resp)

    @mcp.tool(annotations=_READ_ONLY)
    def get_process_tree(
        process_id: ProcessId,
        max_depth: Annotated[
            int, Field(ge=1, le=5, description="Max depth"),
        ] = 4,
    ) -> str:
        """Retrieve a process node and its full subtree.

        Returns hierarchical JSON with id, name, description,
        and nested children up to max_depth levels.
        Use to explore the 5-level process taxonomy."""
        conn = get_shared_connection()
        resp = _get_gateway().execute(
            "get_process_tree",
            get_subtree,
            conn=conn,
            root_id=process_id,
            max_depth=max_depth,
        )

        return _to_json(resp)

    @mcp.tool(annotations=_READ_ONLY)
    def get_kpi_suggestions(
        process_id: ProcessId,
    ) -> str:
        """Retrieve KPI metrics for a process node.

        Queries the 3910-entry KPI database.
        Returns process info, KPI list with name/unit/category,
        count, and provenance chain."""
        conn = get_shared_connection()

        def _get_kpis():
            process = get_process(conn, process_id)
            if not process:
                msg = f"Process {process_id} not found"
                raise ToolError(msg)
            kpis = get_kpis_for_process(conn, process_id)
            return {
                "process": {
                    "id": process["id"],
                    "name_zh": process["name_zh"],
                    "name_en": process["name_en"],
                },
                "kpis": kpis,
                "count": len(kpis),
            }

        resp = _get_gateway().execute("get_kpi_suggestions", _get_kpis)
        process = get_process(conn, process_id)
        if process:
            resp.provenance_chain = build_lookup_provenance(
                conn, process_id, process["name_zh"],
            )

        return _to_json(resp)

    @mcp.tool(annotations=_READ_ONLY)
    def compare_processes(
        process_ids: ProcessIdList,
    ) -> str:
        """Compare two or more process nodes side-by-side across all attributes.

        Accepts comma-separated process IDs. Returns differences in name, description,
        domain, level, KPI count, and hierarchy path for each node."""
        conn = get_shared_connection()
        resp = _get_gateway().execute(
            "compare_processes",
            compare_process_nodes,
            conn=conn,
            process_ids=process_ids,
        )

        return _to_json(resp)

    @mcp.tool(annotations=_READ_ONLY)
    def get_responsibilities(
        process_id: ProcessId,
        lang: Lang = "zh",
        output_format: Annotated[
            Literal["json", "markdown"],
            Field(description="Output format"),
        ] = "json",
    ) -> str:
        """Generate role responsibilities for a process node.

        Includes full hierarchy context: ancestor chain,
        sub-processes, and domain.
        Supports JSON or Markdown output. Has provenance."""
        validate_lang(lang)
        conn = get_shared_connection()

        def _responsibilities():
            process = get_process(conn, process_id)
            if not process:
                msg = f"Process {process_id} not found"
                raise ToolError(msg)

            chain = get_ancestor_chain(conn, process_id)
            all_next = get_processes_by_level(
                conn, process["level"] + 1,
            )
            nk, dk = f"name_{lang}", f"description_{lang}"
            data = {
                "process": {
                    "id": process["id"],
                    "name": process[nk],
                    "description": process[dk],
                },
                "hierarchy": [
                    {"id": n["id"], "name": n[nk]} for n in chain
                ],
                "sub_processes": [
                    {"id": c["id"], "name": c[nk]}
                    for c in all_next
                    if c.get("parent_id") == process_id
                ],
                "domain": process["domain"],
            }
            if output_format == "markdown":
                return responsibilities_to_md(data, lang)
            return data

        resp = _get_gateway().execute(
            "get_responsibilities", _responsibilities,
        )
        resp.provenance_chain = build_hierarchy_provenance(
            conn, process_id, lang,
        )

        return _to_json(resp)

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
        return _to_json(resp)

    @mcp.tool(annotations=_READ_ONLY)
    def export_responsibility_doc(
        process_ids: ProcessIdListOpt,
        lang: Lang = "zh",
        role_name: Annotated[
            str | None,
            Field(max_length=100, description="Role name"),
        ] = None,
    ) -> str:
        """Export a complete role responsibility document.

        Generates Markdown with provenance appendix.
        Accepts one or more process IDs. Sections: role
        overview, responsibilities, KPIs, provenance."""
        conn = get_shared_connection()
        resp = _get_gateway().execute(
            "export_responsibility_doc",
            build_responsibility_doc,
            conn=conn,
            process_ids=process_ids,
            lang=lang,
            role_name=role_name,
        )
        # Build combined provenance for all processes
        ids = [pid.strip() for pid in process_ids.split(",")]
        all_prov: list[dict] = []
        for pid in ids:
            all_prov.extend(
                build_hierarchy_provenance(conn, pid, lang),
            )
        resp.provenance_chain = all_prov

        return _to_json(resp)

    @mcp.tool(annotations=_READ_ONLY)
    def ping() -> str:
        """Health check. Returns server status and data counts.

        Reports server name, total processes, and total KPIs."""
        conn = get_shared_connection()
        return json.dumps(
            {
                "status": "ok",
                "server": "O'Process",
                "total_processes": count_processes(conn),
                "total_kpis": count_kpis(conn),
            },
            ensure_ascii=False,
        )

