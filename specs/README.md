# O'Process 功能规范索引

## 概述

O'Process 是 AI 原生的流程分类框架（OPF），基于 APQC PCF 7.4 融合 ITIL 4、SCOR 12.0 和 AI 时代流程。本项目将框架数据通过 MCP Server 暴露给 AI Agent 使用。

## 开发路线

```
M-0.5 翻译质量 → M0 数据入库 → M1 Server 骨架 → M2 Tools + Gov → M3 集成发布
```

## Spec 列表

| 序号 | 文件 | 里程碑 | 复杂度 | 说明 |
|------|------|--------|--------|------|
| 01 | `specs/01-translation-quality.md` | M-0.5 | 中 | Anthropic Batch API 高质量翻译 + ai_context 质量提升 |
| 02 | `specs/02-data-ingestion.md` | M0 | 中 | framework.json → SQLite + 向量嵌入 |
| 03 | `specs/03-mcp-server-skeleton.md` | M1 | 中 | FastMCP 主入口 + ToolGatewayInterface |
| 04 | `specs/04-core-query-tools.md` | M2a | 高 | search_process + get_process_tree + compare_processes |
| 05 | `specs/05-kpi-role-tools.md` | M2b | 高 | get_kpi_suggestions + get_responsibilities + map_role + export |
| 06 | `specs/06-governance-lite.md` | M2c | 高 | SessionAuditLog + BoundaryResponse + ProvenanceChain |
| 07 | `specs/07-integration-release.md` | M3 | 中 | 集成测试 + pyproject.toml 打包 + 文档 |

## 依赖关系

- Spec 02 依赖 Spec 01（翻译完成后再入库）
- Spec 03 依赖 Spec 02（需要 SQLite 数据）
- Spec 04/05/06 依赖 Spec 03（需要 Server 骨架）
- Spec 07 依赖 Spec 04+05+06（所有 Tools 就绪后集成）
