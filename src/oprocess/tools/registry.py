"""Tool implementations — registered via register_tools(mcp).

All non-search MCP tool functions live here, keeping server.py lean.
Search tools are in search.py.
"""

from __future__ import annotations

import json
from typing import Annotated, Literal

from fastmcp.exceptions import ToolError
from mcp.types import ToolAnnotations
from pydantic import Field

from oprocess.db.connection import check_vec_available, get_shared_connection
from oprocess.db.queries import (
    count_kpis,
    count_processes,
    get_ancestor_chain,
    get_children,
    get_kpis_for_process,
    get_process,
    get_subtree,
)
from oprocess.gateway import get_shared_gateway
from oprocess.tools._types import Lang, ProcessId, ProcessIdList, ProcessIdListOpt
from oprocess.tools.export import build_responsibility_doc
from oprocess.tools.helpers import (
    build_hierarchy_provenance,
    build_lookup_provenance,
    compare_process_nodes,
    responsibilities_to_md,
)
from oprocess.tools.search import register_search_tools
from oprocess.tools.serialization import response_to_json
from oprocess.validators import validate_lang

# -- Tool annotations --
_READ_ONLY = ToolAnnotations(
    readOnlyHint=True, idempotentHint=True, openWorldHint=False,
    destructiveHint=False,
)


def register_tools(mcp) -> None:
    """Register all tool functions on the FastMCP instance."""
    # Register search tools from search.py
    register_search_tools(mcp)

    @mcp.tool(annotations=_READ_ONLY, title="Process Tree")
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
        resp = get_shared_gateway().execute(
            "get_process_tree",
            get_subtree,
            conn=conn,
            root_id=process_id,
            max_depth=max_depth,
        )

        if resp.result is None:
            msg = f"Process {process_id} not found"
            raise ToolError(msg)

        return response_to_json(resp)

    @mcp.tool(annotations=_READ_ONLY, title="KPI Suggestions")
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

        resp = get_shared_gateway().execute("get_kpi_suggestions", _get_kpis)
        if resp.result and "process" in resp.result:
            resp.provenance_chain = build_lookup_provenance(
                conn, process_id, resp.result["process"]["name_zh"],
            )

        return response_to_json(resp)

    @mcp.tool(annotations=_READ_ONLY, title="Process Comparison")
    def compare_processes(
        process_ids: ProcessIdList,
    ) -> str:
        """Compare two or more process nodes side-by-side across all attributes.

        Accepts comma-separated process IDs. Returns differences in name, description,
        domain, level, KPI count, and hierarchy path for each node."""
        conn = get_shared_connection()
        resp = get_shared_gateway().execute(
            "compare_processes",
            compare_process_nodes,
            conn=conn,
            process_ids=process_ids,
        )

        return response_to_json(resp)

    @mcp.tool(annotations=_READ_ONLY, title="Role Responsibilities")
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
            direct_children = get_children(conn, process_id)
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
                    for c in direct_children
                ],
                "domain": process["domain"],
            }
            if output_format == "markdown":
                return responsibilities_to_md(data, lang)
            return data

        resp = get_shared_gateway().execute(
            "get_responsibilities", _responsibilities,
        )
        resp.provenance_chain = build_hierarchy_provenance(
            conn, process_id, lang,
        )

        return response_to_json(resp)

    @mcp.tool(annotations=_READ_ONLY, title="Responsibility Document Export")
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
        resp = get_shared_gateway().execute(
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

        return response_to_json(resp)

    @mcp.tool(annotations=_READ_ONLY, title="Health Check")
    def health_check() -> str:
        """Health check for the O'Process MCP server.

        Returns JSON with status, server name, process/KPI counts,
        and sqlite-vec extension availability."""
        conn = get_shared_connection()

        def _health():
            return {
                "status": "ok",
                "server": "O'Process",
                "total_processes": count_processes(conn),
                "total_kpis": count_kpis(conn),
                "vec_available": check_vec_available(conn),
            }

        resp = get_shared_gateway().execute("health_check", _health)
        return json.dumps(resp.result, ensure_ascii=False)
