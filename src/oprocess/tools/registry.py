"""Tool implementations — registered via register_tools(mcp).

All MCP tool functions live here, keeping server.py lean.
"""

from __future__ import annotations

import json
from pathlib import Path

from oprocess.db.connection import get_connection, init_schema
from oprocess.db.queries import (
    get_ancestor_chain,
    get_kpis_for_process,
    get_process,
    get_processes_by_level,
    get_subtree,
    search_processes,
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

DB_PATH = Path("data/oprocess.db")
_gateway = PassthroughGateway()


def _get_conn():
    conn = get_connection(DB_PATH)
    init_schema(conn)
    return conn


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

    @mcp.tool()
    def search_process(
        query: str,
        lang: str = "zh",
        limit: int = 10,
        level: int | None = None,
    ) -> str:
        """Search processes by keyword. Returns matching process nodes.

        Args:
            query: Search keyword (Chinese or English)
            lang: Language for search - "zh" or "en"
            limit: Maximum results to return
            level: Filter by process level (1-5)
        """
        conn = _get_conn()
        resp = _gateway.execute(
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
        conn.close()
        apply_boundary(query, results, resp)
        return _to_json(resp)

    @mcp.tool()
    def get_process_tree(
        process_id: str,
        max_depth: int = 4,
    ) -> str:
        """Get a process node with its children tree.

        Args:
            process_id: Process ID (e.g., "1.0", "8.5.3")
            max_depth: Maximum depth of children to include
        """
        conn = _get_conn()
        resp = _gateway.execute(
            "get_process_tree",
            get_subtree,
            conn=conn,
            root_id=process_id,
            max_depth=max_depth,
        )
        conn.close()
        return _to_json(resp)

    @mcp.tool()
    def get_kpi_suggestions(
        process_id: str,
    ) -> str:
        """Get KPI suggestions for a process node.

        Args:
            process_id: Process ID to get KPIs for
        """
        conn = _get_conn()

        def _get_kpis():
            process = get_process(conn, process_id)
            if not process:
                return {"error": f"Process {process_id} not found"}
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

        resp = _gateway.execute("get_kpi_suggestions", _get_kpis)
        process = get_process(conn, process_id)
        if process:
            resp.provenance_chain = build_lookup_provenance(
                conn, process_id, process["name_zh"],
            )
        conn.close()
        return _to_json(resp)

    @mcp.tool()
    def compare_processes(
        process_ids: str,
    ) -> str:
        """Compare multiple process nodes.

        Args:
            process_ids: Comma-separated process IDs (e.g. "1.0,8.0,4.0")
        """
        conn = _get_conn()
        resp = _gateway.execute(
            "compare_processes",
            compare_process_nodes,
            conn=conn,
            process_ids=process_ids,
        )
        conn.close()
        return _to_json(resp)

    @mcp.tool()
    def get_responsibilities(
        process_id: str,
        lang: str = "zh",
        output_format: str = "json",
    ) -> str:
        """Generate role responsibilities for a process node.

        Args:
            process_id: Process ID to generate responsibilities for
            lang: Language - "zh" or "en"
            output_format: Output format - "json" or "markdown"
        """
        conn = _get_conn()

        def _responsibilities():
            process = get_process(conn, process_id)
            if not process:
                return {"error": f"Process {process_id} not found"}

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

        resp = _gateway.execute(
            "get_responsibilities", _responsibilities,
        )
        resp.provenance_chain = build_hierarchy_provenance(
            conn, process_id, lang,
        )
        conn.close()
        return _to_json(resp)

    @mcp.tool()
    def map_role_to_processes(
        role_description: str,
        lang: str = "zh",
        limit: int = 10,
        industry: str | None = None,
    ) -> str:
        """Map a job role to relevant processes.

        Args:
            role_description: Description of the job role
            lang: Language for results - "zh" or "en"
            limit: Maximum number of process matches
            industry: Filter by industry tag (e.g. "manufacturing")
        """
        conn = _get_conn()
        resp = _gateway.execute(
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
        conn.close()
        apply_boundary(role_description, results, resp)
        return _to_json(resp)

    @mcp.tool()
    def export_responsibility_doc(
        process_ids: str,
        lang: str = "zh",
        role_name: str | None = None,
    ) -> str:
        """Export a complete responsibility document.

        Args:
            process_ids: Comma-separated process IDs (e.g. "1.0,8.0")
            lang: Language - "zh" or "en"
            role_name: Optional role name for the document title
        """
        conn = _get_conn()
        resp = _gateway.execute(
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
        conn.close()
        return _to_json(resp)

