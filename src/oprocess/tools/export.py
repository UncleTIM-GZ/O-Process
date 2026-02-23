"""Export tool — generates markdown responsibility documents."""

from __future__ import annotations

from oprocess.db.queries import (
    get_ancestor_chain,
    get_kpis_for_process,
    get_process,
    get_subtree,
)


def render_children(
    children: list[dict], lines: list[str], name_key: str, depth: int
) -> None:
    """Render children tree as markdown list."""
    for child in children:
        indent = "  " * depth
        lines.append(f"{indent}- {child['id']} {child[name_key]}")
        if child.get("children"):
            render_children(child["children"], lines, name_key, depth + 1)


def build_responsibility_doc(conn, process_id: str, lang: str) -> dict:
    """Build a full responsibility markdown document for a process."""
    process = get_process(conn, process_id)
    if not process:
        return {"error": f"Process {process_id} not found"}

    chain = get_ancestor_chain(conn, process_id)
    subtree = get_subtree(conn, process_id, max_depth=3)
    kpis = get_kpis_for_process(conn, process_id)

    name_key = f"name_{lang}"
    desc_key = f"description_{lang}"

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

    lines.extend([
        "",
        "## 描述" if lang == "zh" else "## Description",
        "",
    ])
    lines.append(process[desc_key])

    if subtree and subtree.get("children"):
        lines.extend([
            "",
            "## 子流程" if lang == "zh" else "## Sub-processes",
            "",
        ])
        render_children(subtree["children"], lines, name_key, 0)

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
