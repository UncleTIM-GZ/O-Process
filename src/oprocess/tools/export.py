"""Export tool — generates markdown responsibility documents."""

from __future__ import annotations

from oprocess.db.queries import (
    build_path_strings_batch,
    get_ancestor_chain,
    get_kpis_for_process,
    get_process,
    get_subtree,
)
from oprocess.validators import validate_lang


def render_children(
    children: list[dict], lines: list[str], name_key: str, depth: int
) -> None:
    """Render children tree as markdown list."""
    for child in children:
        indent = "  " * depth
        lines.append(f"{indent}- {child['id']} {child[name_key]}")
        if child.get("children"):
            render_children(child["children"], lines, name_key, depth + 1)


def _build_single_doc(
    conn, process_id: str, lang: str, name_key: str, desc_key: str,
) -> tuple[list[str], int]:
    """Build markdown lines for a single process. Returns (lines, kpi_count)."""
    process = get_process(conn, process_id)
    if not process:
        return [f"Process {process_id} not found."], 0

    chain = get_ancestor_chain(conn, process_id)
    subtree = get_subtree(conn, process_id, max_depth=3)
    kpis = get_kpis_for_process(conn, process_id)

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
        render_children(subtree["children"], lines, name_key, 0)

    if kpis:
        lines.extend([
            "",
            "## KPI 指标" if lang == "zh" else "## KPIs",
            "",
        ])
        for kpi in kpis:
            lines.append(
                f"- **{kpi[name_key]}** ({kpi.get('unit', '')})",
            )

    # Provenance appendix (batch path queries to avoid N+1)
    chain_ids = [node["id"] for node in chain]
    path_map = build_path_strings_batch(conn, chain_ids)
    lines.extend([
        "",
        "## 溯源附录" if lang == "zh" else "## Provenance Appendix",
        "",
    ])
    if lang == "zh":
        lines.append("| 节点 ID | 名称 | 置信度 | 路径 | 推导规则 |")
    else:
        lines.append("| Node ID | Name | Confidence | Path | Rule |")
    lines.append("|---------|------|--------|------|---------|")
    for node in chain:
        path = path_map.get(node["id"], node["id"])
        confidence = 1.0 if node["id"] == process_id else 0.5
        lines.append(
            f"| {node['id']} | {node[name_key]} "
            f"| {confidence:.2f} | {path} | rule_based |"
        )

    return lines, len(kpis)


def build_responsibility_doc(
    conn,
    process_ids: str,
    lang: str,
    role_name: str | None = None,
) -> dict:
    """Build a full responsibility markdown document.

    Args:
        conn: Database connection.
        process_ids: Single or comma-separated process IDs (e.g. "1.0,8.0").
        lang: Language - "zh" or "en".
        role_name: Optional role name for the document title.
    """
    validate_lang(lang)
    name_key = f"name_{lang}"
    desc_key = f"description_{lang}"
    ids = [pid.strip() for pid in process_ids.split(",")]

    all_lines: list[str] = []
    total_kpis = 0

    if role_name:
        all_lines.extend([
            f"# {'岗位说明书' if lang == 'zh' else 'Role Description'}"
            f": {role_name}",
            "",
        ])

    for i, pid in enumerate(ids):
        if i > 0:
            all_lines.extend(["", "---", ""])
        lines, kpi_count = _build_single_doc(
            conn, pid, lang, name_key, desc_key,
        )
        all_lines.extend(lines)
        total_kpis += kpi_count

    return {
        "markdown": "\n".join(all_lines),
        "process_ids": ids,
        "kpi_count": total_kpis,
    }
