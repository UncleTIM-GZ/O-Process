---
title: "fix: P7 — SHOULD/MAY 合规 + P2/P3 打磨"
type: fix
status: completed
date: 2026-02-24
origin: docs/plans/2026-02-24-fix-p6-mcp-spec-2025-11-25-audit-plan.md
---

# fix: P7 — SHOULD/MAY 合规 + P2/P3 打磨

基于 P6 审查报告的遗留项，完成 SHOULD 合规、MAY 增强和 P2/P3 打磨。

## Overview

P6 审查结果：MUST 100%、SHOULD 75%、MAY 0%。
本次 P7 补齐 3 项 SHOULD 缺失 + 选择性实现 MAY + 修复 4 项 P2 + 4 项 P3。

## 修复清单

### SHOULD 缺失（3 项）

| ID | 问题 | 修复方案 |
|----|------|----------|
| S10 | Tool 缺 `title` 字段 | FastMCP `@mcp.tool(title=...)` 为 8 个 tool 添加 |
| S11 | Prompt 缺 `title` 字段 | FastMCP `@mcp.prompt(title=...)` 为 3 个 prompt 添加 |
| S12 | Resource `audit/session` 无独立 auth | 在 HTTP 模式下已有 BearerAuth 覆盖，仅补充文档说明 |

### MAY 增强（选择性实现）

| ID | 能力 | 方案 | 理由 |
|----|------|------|------|
| Y1 | `outputSchema` | 为 `health_check` 添加示例 outputSchema | 最简单的入门示例 |
| Y6 | `structuredContent` | 不实现 | FastMCP 尚未原生支持 |
| Y2 | Completions | 不实现 | FastMCP 无原生 API |
| Y3 | Resource subscriptions | 不实现 | 静态数据无需 |
| Y4 | listChanged | 不实现 | 工具列表不变 |
| Y5 | Icons | 不实现 | 无图标资源 |

### P2 — 推荐改进（4 项）

| ID | 问题 | 修复 |
|----|------|------|
| P2-1 | CLAUDE.md 向量模型描述过时 | 更新为 `gemini-embedding-001（768 维）` |
| P2-2 | `get_recent_logs()` 死代码 | 删除 `audit.py:103-111` |
| P2-3 | Tool 缺 `title`（同 S10）| 合并处理 |
| P2-4 | Prompt 缺 `title`（同 S11）| 合并处理 |

### P3 — 低优先级（4 项）

| ID | 问题 | 修复 |
|----|------|------|
| P3-1 | `vector_search.py:66` 双重 `row_to_process` | 改为单次调用 |
| P3-2 | `audit_log_enabled` 配置未实际使用 | gateway 中检查此配置 |
| P3-3 | MEMORY.md 过时描述 | 更新向量模型信息 |
| P3-4 | `resources/__init__.py` 空目录存在 | 如无用则删除 |

## 实现步骤

### Step 1: Tool + Prompt title 字段（S10 + S11 + P2-3 + P2-4）

**文件**: `src/oprocess/tools/registry.py`, `src/oprocess/tools/search.py`, `src/oprocess/prompts.py`

为 8 个 tool 添加 `title` 参数：
- `search_process` → title="Process Search"
- `get_process_tree` → title="Process Tree"
- `get_kpi_suggestions` → title="KPI Suggestions"
- `compare_processes` → title="Process Comparison"
- `get_responsibilities` → title="Role Responsibilities"
- `map_role_to_processes` → title="Role-Process Mapping"
- `export_responsibility_doc` → title="Responsibility Document Export"
- `health_check` → title="Health Check"

为 3 个 prompt 添加 `title` 参数：
- `analyze_process` → title="Process Analysis Workflow"
- `generate_job_description` → title="Job Description Generator"
- `kpi_review` → title="KPI Review Workflow"

### Step 2: 死代码清理（P2-2）

**文件**: `src/oprocess/governance/audit.py`

删除 `get_recent_logs()` 函数（L103-111），无任何调用方。

### Step 3: 文档同步（P2-1 + P3-3）

**文件**: `CLAUDE.md`, MEMORY.md

将 `text-embedding-3-small（1536 维，离线预计算）` 更新为 `gemini-embedding-001（768 维，离线预计算）`。

### Step 4: vector_search 双重调用修复（P3-1）

**文件**: `src/oprocess/db/vector_search.py`

```python
# Before (L66):
proc_map = {row_to_process(r)["id"]: row_to_process(r) for r in proc_rows}

# After:
proc_map = {}
for r in proc_rows:
    p = row_to_process(r)
    proc_map[p["id"]] = p
```

### Step 5: audit_log_enabled 配置生效（P3-2）

**文件**: `src/oprocess/gateway.py`

在 `get_shared_gateway()` 中检查 `get_config()["audit_log_enabled"]`，若为 False 则不传 `audit_conn`。

### Step 6: 空目录清理（P3-4）

检查 `src/oprocess/resources/__init__.py` 是否被使用，若无用则删除整个 `resources/` 目录。

### Step 7: 测试更新

- 更新 `test_server.py` 验证 tool/prompt title 字段存在
- 更新 `test_audit.py` 删除 `get_recent_logs` 相关测试（如有）
- 添加 `audit_log_enabled=False` 的测试
- 验证 vector_search 修复

### Step 8: 验证 & 清理

- `ruff check src/ tests/` 零 error
- `pytest` 全通过
- 覆盖率 ≥ 85%
- 更新 `.dev/CURRENT.md`

## Acceptance Criteria

- [x] 所有 8 个 Tool 含 `title` 字段
- [x] 所有 3 个 Prompt 含 `title` 字段
- [x] `get_recent_logs()` 已删除
- [x] CLAUDE.md 向量模型描述正确
- [x] MEMORY.md 无需更新（未包含向量模型描述）
- [x] `vector_search.py` 无双重 `row_to_process` 调用
- [x] `audit_log_enabled` 配置实际生效
- [x] 空目录已清理
- [x] ruff check 零 error
- [x] pytest 全通过（261 passed）
- [x] 覆盖率 94.72% ≥ 85%

## Commit 策略

### Commit 1: P7.1 — SHOULD + MAY 合规
```
src/oprocess/tools/registry.py      — tool title 字段
src/oprocess/tools/search.py        — tool title 字段
src/oprocess/prompts.py             — prompt title 字段
tests/test_tools/test_server.py     — title 验证测试
```

### Commit 2: P7.2 — P2/P3 打磨
```
src/oprocess/governance/audit.py    — 删除死代码
src/oprocess/db/vector_search.py    — 修复双重调用
src/oprocess/gateway.py             — audit_log_enabled 生效
CLAUDE.md                           — 文档同步
.dev/CURRENT.md                     — 状态更新
```

## 涉及文件

### 源码修改
- `src/oprocess/tools/registry.py` — S10, tool title
- `src/oprocess/tools/search.py` — S10, tool title
- `src/oprocess/prompts.py` — S11, prompt title
- `src/oprocess/governance/audit.py` — P2-2, 删除死代码
- `src/oprocess/db/vector_search.py` — P3-1, 修复双重调用
- `src/oprocess/gateway.py` — P3-2, audit_log_enabled
- `CLAUDE.md` — P2-1, 文档同步

### 测试修改
- `tests/test_tools/test_server.py` — title 验证
- `tests/test_governance/test_audit.py` — 删除死代码测试

## Sources

- **Origin**: [P6 审查报告](docs/plans/2026-02-24-fix-p6-mcp-spec-2025-11-25-audit-plan.md)
- [MCP Spec 2025-11-25 Tools](https://modelcontextprotocol.io/specification/2025-11-25/server/tools)
- [MCP Spec 2025-11-25 Prompts](https://modelcontextprotocol.io/specification/2025-11-25/server/prompts)
