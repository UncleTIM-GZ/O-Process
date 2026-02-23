"""O'Process MCP Server — FastMCP entry point.

Run:
    python -m oprocess.server
    # or
    fastmcp run src/oprocess/server.py
"""

from __future__ import annotations

import json
from pathlib import Path

from fastmcp import FastMCP

from oprocess.db.connection import get_connection, init_schema
from oprocess.db.queries import (
    count_kpis,
    count_processes,
    get_ancestor_chain,
    get_kpis_for_process,
    get_process,
    get_processes_by_level,
    get_subtree,
    search_processes,
)
from oprocess.gateway import PassthroughGateway, ToolResponse

mcp = FastMCP(
    "O'Process",
    instructions="AI-native process classification framework (OPF). "
    "Query 2325 processes + 3910 KPIs from APQC PCF 7.4 + ITIL 4 + SCOR 12.0.",
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


@mcp.tool()
def search_process(
    query: str,
    lang: str = "zh",
    limit: int = 10,
) -> str:
    """Search processes by keyword. Returns matching process nodes.

    Args:
        query: Search keyword (Chinese or English)
        lang: Language for search - "zh" or "en"
        limit: Maximum results to return
    """
    conn = _get_conn()
    resp = _gateway.execute(
        "search_process",
        search_processes,
        conn=conn,
        query=query,
        lang=lang,
        limit=limit,
    )
    conn.close()
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
    conn.close()
    return _to_json(resp)


@mcp.tool()
def compare_processes(
    process_id_a: str,
    process_id_b: str,
) -> str:
    """Compare two process nodes side by side.

    Args:
        process_id_a: First process ID
        process_id_b: Second process ID
    """
    conn = _get_conn()

    def _compare():
        a = get_process(conn, process_id_a)
        b = get_process(conn, process_id_b)
        if not a:
            return {"error": f"Process {process_id_a} not found"}
        if not b:
            return {"error": f"Process {process_id_b} not found"}

        chain_a = get_ancestor_chain(conn, process_id_a)
        chain_b = get_ancestor_chain(conn, process_id_b)

        return {
            "process_a": a,
            "process_b": b,
            "path_a": [n["id"] for n in chain_a],
            "path_b": [n["id"] for n in chain_b],
            "same_parent": a.get("parent_id") == b.get("parent_id"),
            "same_domain": a.get("domain") == b.get("domain"),
            "same_level": a.get("level") == b.get("level"),
        }

    resp = _gateway.execute("compare_processes", _compare)
    conn.close()
    return _to_json(resp)


@mcp.tool()
def get_responsibilities(
    process_id: str,
    lang: str = "zh",
) -> str:
    """Generate role responsibilities for a process node.

    Args:
        process_id: Process ID to generate responsibilities for
        lang: Language - "zh" or "en"
    """
    conn = _get_conn()

    def _responsibilities():
        process = get_process(conn, process_id)
        if not process:
            return {"error": f"Process {process_id} not found"}

        chain = get_ancestor_chain(conn, process_id)
        children = get_processes_by_level(conn, process["level"] + 1)
        child_procs = [c for c in children if c.get("parent_id") == process_id]

        name_key = f"name_{lang}"
        desc_key = f"description_{lang}"

        return {
            "process": {
                "id": process["id"],
                "name": process[name_key],
                "description": process[desc_key],
            },
            "hierarchy": [
                {"id": n["id"], "name": n[name_key]} for n in chain
            ],
            "sub_processes": [
                {"id": c["id"], "name": c[name_key]} for c in child_procs
            ],
            "domain": process["domain"],
        }

    resp = _gateway.execute("get_responsibilities", _responsibilities)
    resp.provenance_chain = [process_id]
    conn.close()
    return _to_json(resp)


@mcp.tool()
def map_role_to_processes(
    role_description: str,
    lang: str = "zh",
    limit: int = 10,
) -> str:
    """Map a job role to relevant processes.

    Args:
        role_description: Description of the job role
        lang: Language for results - "zh" or "en"
        limit: Maximum number of process matches
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
    conn.close()
    return _to_json(resp)


@mcp.tool()
def export_responsibility_doc(
    process_id: str,
    lang: str = "zh",
) -> str:
    """Export a complete responsibility document for a process.

    Args:
        process_id: Process ID to export
        lang: Language - "zh" or "en"
    """
    conn = _get_conn()

    def _export():
        process = get_process(conn, process_id)
        if not process:
            return {"error": f"Process {process_id} not found"}

        chain = get_ancestor_chain(conn, process_id)
        subtree = get_subtree(conn, process_id, max_depth=3)
        kpis = get_kpis_for_process(conn, process_id)

        name_key = f"name_{lang}"
        desc_key = f"description_{lang}"

        # Build markdown document
        lines = [
            f"# {process[name_key]}",
            "",
            f"**ID**: {process['id']}",
            f"**Domain**: {process['domain']}",
            f"**Level**: {process['level']}",
            "",
            "## 层级路径" if lang == "zh" else "## Hierarchy Path",
            "",
        ]
        for node in chain:
            indent = "  " * (node["level"] - 1)
            lines.append(f"{indent}- {node['id']} {node[name_key]}")

        lines.extend(["", "## 描述" if lang == "zh" else "## Description", ""])
        lines.append(process[desc_key])

        if subtree and subtree.get("children"):
            lines.extend([
                "",
                "## 子流程" if lang == "zh" else "## Sub-processes",
                "",
            ])
            _render_children(subtree["children"], lines, name_key, 0)

        if kpis:
            lines.extend([
                "",
                "## KPI 指标" if lang == "zh" else "## KPIs",
                "",
            ])
            for kpi in kpis:
                lines.append(f"- **{kpi[name_key]}** ({kpi.get('unit', '')})")

        return {
            "markdown": "\n".join(lines),
            "process_id": process_id,
            "kpi_count": len(kpis),
        }

    resp = _gateway.execute("export_responsibility_doc", _export)
    resp.provenance_chain = [process_id]
    conn.close()
    return _to_json(resp)


def _render_children(
    children: list[dict], lines: list[str], name_key: str, depth: int
) -> None:
    """Render children tree as markdown list."""
    for child in children:
        indent = "  " * depth
        lines.append(f"{indent}- {child['id']} {child[name_key]}")
        if child.get("children"):
            _render_children(child["children"], lines, name_key, depth + 1)


@mcp.resource("oprocess://stats")
def get_stats() -> str:
    """Get O'Process framework statistics."""
    conn = _get_conn()
    stats = {
        "total_processes": count_processes(conn),
        "total_kpis": count_kpis(conn),
        "version": "0.1.0",
        "sources": ["APQC PCF 7.4", "ITIL 4", "SCOR 12.0", "AI-era"],
    }
    conn.close()
    return json.dumps(stats, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    mcp.run()
