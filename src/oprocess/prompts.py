"""MCP Prompt templates — registered via register_prompts(mcp).

Three guided prompts that help clients discover and use core tools:
- analyze_process: process analysis workflow
- generate_job_description: role responsibility document
- kpi_review: KPI review for a process
"""

from __future__ import annotations

from oprocess.validators import (
    sanitize_role_name,
    validate_lang,
    validate_process_id,
    validate_process_ids,
)


def register_prompts(mcp) -> None:
    """Register all prompt templates on the FastMCP instance."""

    @mcp.prompt(title="Process Analysis Workflow")
    def analyze_process(process_id: str, lang: str = "zh") -> str:
        """Guided workflow for analyzing a process node."""
        validate_process_id(process_id)
        validate_lang(lang, tool=False)
        if lang == "zh":
            return (
                f"## 流程分析工作流\n\n"
                f"目标流程 ID: `{process_id}`\n\n"
                f"请按以下步骤操作：\n"
                f"1. 调用 `get_process_tree` 获取流程 `{process_id}` 的层级结构\n"
                f"2. 调用 `get_kpi_suggestions` 获取该流程的 KPI 指标\n"
                f"3. 分析流程的层级位置、子流程覆盖范围\n"
                f"4. 评估 KPI 指标的完整性和合理性\n"
                f"5. 输出结构化分析报告"
            )
        return (
            f"## Process Analysis Workflow\n\n"
            f"Target process ID: `{process_id}`\n\n"
            f"Follow these steps:\n"
            f"1. Call `get_process_tree` to retrieve the hierarchy of `{process_id}`\n"
            f"2. Call `get_kpi_suggestions` to get KPI metrics for this process\n"
            f"3. Analyze the process position and sub-process coverage\n"
            f"4. Evaluate KPI completeness and relevance\n"
            f"5. Output a structured analysis report"
        )

    @mcp.prompt(title="Job Description Generator")
    def generate_job_description(
        process_ids: str, role_name: str, lang: str = "zh",
    ) -> str:
        """Guided workflow for generating a role responsibility document."""
        validate_process_ids(process_ids)
        safe_name = sanitize_role_name(role_name)
        validate_lang(lang, tool=False)
        if lang == "zh":
            return (
                f"## 岗位说明书生成工作流\n\n"
                f"岗位名称: **{safe_name}**\n"
                f"关联流程: `{process_ids}`\n\n"
                f"请按以下步骤操作：\n"
                f"1. 对每个流程 ID 调用 `get_responsibilities` 获取职责描述\n"
                f"2. 调用 `export_responsibility_doc` 生成完整岗位说明书\n"
                f"3. 审查生成的文档，确保职责覆盖完整\n"
                f"4. 检查溯源附录，验证数据来源"
            )
        return (
            f"## Job Description Generation Workflow\n\n"
            f"Role: **{safe_name}**\n"
            f"Related processes: `{process_ids}`\n\n"
            f"Follow these steps:\n"
            f"1. Call `get_responsibilities` for each process ID\n"
            f"2. Call `export_responsibility_doc` to generate the full document\n"
            f"3. Review the generated document for completeness\n"
            f"4. Verify the provenance appendix for data sources"
        )

    @mcp.prompt(title="KPI Review Workflow")
    def kpi_review(process_id: str, lang: str = "zh") -> str:
        """Guided workflow for reviewing KPIs of a process."""
        validate_process_id(process_id)
        validate_lang(lang, tool=False)
        if lang == "zh":
            return (
                f"## KPI 审查工作流\n\n"
                f"目标流程 ID: `{process_id}`\n\n"
                f"请按以下步骤操作：\n"
                f"1. 调用 `get_kpi_suggestions` 获取流程 `{process_id}` 的 KPI 列表\n"
                f"2. 审查每个 KPI 的名称、单位、方向是否合理\n"
                f"3. 检查 KPI 覆盖是否完整（效率、质量、成本、时效）\n"
                f"4. 识别缺失的关键指标并提出建议\n"
                f"5. 输出 KPI 审查报告"
            )
        return (
            f"## KPI Review Workflow\n\n"
            f"Target process ID: `{process_id}`\n\n"
            f"Follow these steps:\n"
            f"1. Call `get_kpi_suggestions` for process `{process_id}`\n"
            f"2. Review each KPI's name, unit, and direction\n"
            f"3. Check KPI coverage (efficiency, quality, cost, timeliness)\n"
            f"4. Identify missing key metrics and make suggestions\n"
            f"5. Output a KPI review report"
        )
