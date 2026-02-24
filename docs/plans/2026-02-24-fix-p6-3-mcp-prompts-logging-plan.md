---
title: "fix: P6.3 — MCP Prompts + Logging"
type: fix
status: completed
date: 2026-02-24
origin: docs/plans/2026-02-24-fix-p6-mcp-spec-2025-11-25-audit-plan.md
---

# fix: P6.3 — MCP Prompts + Logging

P6 合规修复最后一个 Commit：P6-8 (MCP Prompts) + P6-9 (MCP logging)。

## Overview

基于 MCP Spec 2025-11-25，为 O'Process MCP Server 添加：
1. **3 个 MCP Prompts** — 引导式模板，帮助客户端发现和使用核心功能
2. **MCP logging capability 声明** — 让客户端知道服务器支持日志

## 关键决策

| 决策 | 选择 | 理由 |
|------|------|------|
| Prompt 是否查数据库 | **否，纯文本引导模板** | MCP Prompt 设计意图是给 LLM 提供结构化指引，具体数据由 Tool 提供 |
| Prompt 返回类型 | **`str`** | FastMCP 自动包装为 PromptMessage，最简单 |
| P6-9 async 改造 | **不改造** | 现有同步架构稳定；FastMCP 自动声明 logging capability；改造风险 >> 收益 |
| 多语言支持 | **有 `lang` 参数** | 与项目双语定位一致 |
| 文件位置 | **`src/oprocess/prompts.py`** | 与 tools/ 目录同级，遵循项目结构中 CLAUDE.md 的规划 |

## P6-8: MCP Prompts 实现

### 3 个 Prompt 定义

#### 1. `analyze_process`

- **参数**: `process_id: str` (required), `lang: str = "zh"` (optional)
- **功能**: 返回流程分析引导模板，指导 LLM 使用 `get_process_tree` + `get_kpi_suggestions` 工具
- **返回**: 中文/英文结构化分析指引字符串

#### 2. `generate_job_description`

- **参数**: `process_ids: str` (required), `role_name: str` (required), `lang: str = "zh"` (optional)
- **功能**: 返回岗位说明书引导模板，指导 LLM 使用 `get_responsibilities` + `export_responsibility_doc` 工具
- **返回**: 中文/英文岗位说明书指引字符串

#### 3. `kpi_review`

- **参数**: `process_id: str` (required), `lang: str = "zh"` (optional)
- **功能**: 返回 KPI 审查引导模板，指导 LLM 使用 `get_kpi_suggestions` 工具
- **返回**: 中文/英文 KPI 审查指引字符串

### 参数验证

在 Prompt 函数内部手动验证：
- `process_id`: 正则 `r"^\d+(\.\d+)*$"` 匹配
- `process_ids`: 正则 `r"^\d+(\.\d+)*(,\s*\d+(\.\d+)*)*$"` 匹配
- `role_name`: 非空且 ≤ 100 字符
- `lang`: 必须为 "zh" 或 "en"
- 验证失败抛 `ValueError`（FastMCP 映射为 -32602）

## P6-9: MCP Logging 简化方案

**不做 Tool 的 async 改造**。采用简化方案：

1. FastMCP 3.0.2 注册 Prompt 后自动声明 `prompts` capability
2. 现有 Python logging（`oprocess` logger）已提供服务端日志
3. Gateway 的 audit log 已记录所有 Tool 调用

P6-9 的实质收益是**让客户端知道服务器有日志能力**，这通过 FastMCP 自动 capability 声明即可。不需要在同步 Tool 中强行注入 async Context.log()。

## 文件改动

### 新增文件

| 文件 | 行数 | 说明 |
|------|------|------|
| `src/oprocess/prompts.py` | ~80 行 | 3 个 Prompt + `register_prompts()` |
| `tests/test_tools/test_prompts.py` | ~100 行 | Prompt 测试 |

### 修改文件

| 文件 | 改动 | 行数 |
|------|------|------|
| `src/oprocess/server.py` | 添加 `register_prompts(mcp)` 调用 | +2 行 |
| `.dev/CURRENT.md` | 更新 P6-8, P6-9 状态 | ~5 行 |

## 实现步骤

### Step 1: 创建 `src/oprocess/prompts.py`

```python
# ~80 行
# - _validate_process_id(pid) / _validate_lang(lang) helpers
# - register_prompts(mcp) 函数
# - 3 个 @mcp.prompt 装饰器函数
# - 每个 Prompt 返回 str（结构化引导模板）
```

### Step 2: 修改 `src/oprocess/server.py`

```python
from oprocess.prompts import register_prompts
# ... 在 register_resources(mcp) 之后
register_prompts(mcp)
```

### Step 3: 创建 `tests/test_tools/test_prompts.py`

测试覆盖：
- 3 个 Prompt 正常返回（zh + en）
- 缺失必需参数抛异常
- 无效 process_id 格式抛异常
- 无效 lang 抛异常
- role_name 过长抛异常
- 返回内容包含预期关键词

### Step 4: 验证 & 清理

- `ruff check src/ tests/` 零 error
- `pytest` 全通过
- 覆盖率 ≥ 85%
- 更新 `.dev/CURRENT.md`

## Acceptance Criteria

- [x] 3 个 MCP Prompts 可被客户端发现（`prompts/list` 返回 3 项）
- [x] Prompt 参数验证正确（无效输入返回 -32602 错误码）
- [x] Prompt 返回格式符合 MCP Spec（包含 messages[]）
- [x] 双语支持（zh/en）
- [x] 测试覆盖所有 Prompt + 错误路径
- [x] ruff check 零 error
- [x] 总覆盖率 ≥ 85%

## Commit Message

```
fix(compliance): P6.3 — MCP Prompts + logging capability

- P6-8: 3 MCP Prompts (analyze_process, generate_job_description, kpi_review)
- P6-9: logging capability via FastMCP auto-declaration
- Bilingual prompt templates (zh/en)
- Full test coverage for prompts
```

## Sources

- **Origin plan:** [docs/plans/2026-02-24-fix-p6-mcp-spec-2025-11-25-audit-plan.md](docs/plans/2026-02-24-fix-p6-mcp-spec-2025-11-25-audit-plan.md) — P6-8 & P6-9
- [MCP Spec 2025-11-25 Prompts](https://modelcontextprotocol.io/specification/2025-11-25/server/prompts)
- [MCP Spec 2025-11-25 Logging](https://modelcontextprotocol.io/specification/2025-11-25/server/utilities/logging)
- FastMCP 3.0.2 `@mcp.prompt` decorator API
