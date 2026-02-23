---
title: "feat: P0 MCP Certification — 实施计划"
type: feat
status: completed
date: 2026-02-23
origin: docs/plans/2026-02-23-feat-mcp-certification-upgrade-plan.md
---

# P0 MCP Certification — 实施计划

## Overview

基于 MCP 认证升级评估的 P0 阶段（认证阻塞项），实施 4 项关键改进：
1. Pydantic `Annotated[..., Field(...)]` 输入约束（7 个 Tool）
2. `ToolError` 替换 error dict（4 处）
3. lang 白名单校验（defense-in-depth）
4. README 完整文档

**技术栈确认**：FastMCP 3.0.2 + Pydantic 2.12.5 + `from fastmcp.exceptions import ToolError`

## 关键技术决策

### Annotated Field vs BaseModel

**选择 `Annotated[type, Field(...)]` 而非 BaseModel 单参数**。

原因（经实测验证）：
- BaseModel 参数产生嵌套 schema：`{"params": {"query": ...}}`，LLM 需多传一层
- Annotated Field 产生扁平 schema：`{"query": ...}`，对 LLM 最友好
- FastMCP 3.x 官方文档推荐 Annotated 方式
- 保持现有函数签名结构，改动最小

**不创建 `schemas.py`**。约束直接写在函数签名上，无需额外文件。

### lang 使用 Literal 而非 pattern

- `Literal["zh", "en"]` 生成 `{"enum": ["zh", "en"]}`，比 `pattern=r"^(zh|en)$"` 更清晰
- LLM 直接看到枚举值，而非需要解析正则

## 实施步骤

### Phase 1: lang 白名单（P0.3）— `queries.py` + `helpers.py`

**文件**: `src/oprocess/db/queries.py`

1. 添加 `_VALID_LANGS` 常量和 `validate_lang()` 函数
2. 在 `search_processes()` L67 前调用 `validate_lang(lang)`

**文件**: `src/oprocess/tools/helpers.py`

3. 在 `build_search_provenance()` L56 前调用
4. 在 `build_hierarchy_provenance()` L80 前调用

**文件**: `src/oprocess/tools/registry.py`

5. 在 `get_responsibilities()` L191 前调用
6. 导出 `validate_lang` 供 export.py 使用

**文件**: `src/oprocess/tools/export.py`

7. 在 `_build_section()` L109 前调用

**测试**: 新增 2 个测试到 `tests/test_tools/test_queries.py`
- `test_invalid_lang_search` → `pytest.raises(ValueError)`
- `test_invalid_lang_provenance` → `pytest.raises(ValueError)`

### Phase 2: Pydantic Annotated Field（P0.1）— `registry.py`

**文件**: `src/oprocess/tools/registry.py`

为 7 个 tool 函数添加 `Annotated[..., Field(...)]` 约束：

| Tool | 参数改动 |
|------|---------|
| `search_process` | `query: Annotated[str, Field(min_length=1, max_length=500)]`, `lang: Annotated[Literal["zh","en"], Field()]`, `limit: Annotated[int, Field(ge=1, le=50)]`, `level: Annotated[int \| None, Field(ge=1, le=5)]` |
| `get_process_tree` | `process_id: Annotated[str, Field(pattern=r"^\d+(\.\d+)*$")]`, `max_depth: Annotated[int, Field(ge=1, le=5)]` |
| `get_kpi_suggestions` | `process_id: Annotated[str, Field(pattern=...)]` |
| `compare_processes` | `process_ids: Annotated[str, Field(pattern=r"^\d+(\.\d+)*(,\s*\d+(\.\d+)*)+$")]` |
| `get_responsibilities` | `process_id`, `lang: Literal`, `output_format: Annotated[Literal["json","markdown"], Field()]` |
| `map_role_to_processes` | `role_description: Annotated[str, Field(min_length=1, max_length=500)]`, `lang`, `limit`, `industry: Annotated[str \| None, Field(max_length=100)]` |
| `export_responsibility_doc` | `process_ids`, `lang`, `role_name: Annotated[str \| None, Field(max_length=100)]` |

**新增 imports**:
```python
from __future__ import annotations
from typing import Annotated, Literal
from pydantic import Field
```

**测试**: 新增 `tests/test_tools/test_schema_validation.py`
- `test_all_tools_have_input_schema` — 验证每个 tool 的 parameters 包含完整约束
- `test_invalid_lang_rejected` — Pydantic 验证拒绝 `lang="french"`
- `test_invalid_limit_rejected` — Pydantic 验证拒绝 `limit=-1`

### Phase 3: ToolError（P0.2）— `registry.py` + `helpers.py` + `resources.py`

**文件**: `src/oprocess/tools/registry.py`

1. 添加 `from fastmcp.exceptions import ToolError`
2. `get_kpi_suggestions` L127: `return {"error":...}` → `raise ToolError(...)`
3. `get_responsibilities` L185: `return {"error":...}` → `raise ToolError(...)`

**文件**: `src/oprocess/tools/helpers.py`

4. 添加 `from fastmcp.exceptions import ToolError`
5. `compare_process_nodes` L97: `return {"error":...}` → `raise ToolError(...)`

**文件**: `src/oprocess/tools/resources.py`

6. `get_process_resource` L56: `{"error":...}` → `{"not_found": process_id, "message": "..."}`
   （Resource 无 ToolError 概念，改语义更明确的 key）

**测试修改**:
- `tests/test_tools/test_kpi_role.py:108-110`: `TestCompareProcesses.test_missing_process`
  → `pytest.raises(ToolError)` 替代 `assert "error" in result`
- `tests/test_tools/test_resources.py`: 验证 resource 返回 `not_found` key

**Gateway 兼容性**：已确认 `PassthroughGateway.execute()` L78-80 正确捕获 Exception → 记录 audit → 重新抛出。ToolError 作为 Exception 子类自动兼容。

### Phase 4: README（P0.4）

**文件**: `README.md`（重写，约 200 行）

内容结构：
1. 标题 + 简介
2. Quick Start
3. Claude Desktop 配置 JSON
4. Tools 签名表（7 个，含参数/类型/默认值/约束）
5. Resources URI 表（6 个）
6. Governance-Lite 简介
7. Development 命令
8. License

### Phase 5: 修复 pyproject.toml build-backend

- `hatchling.backends` → `hatchling.build`（已在研究阶段修复）

### Phase 6: 验证

```bash
ruff check .                    # lint 零 error
pytest                          # 所有测试通过（含新增）
uv run python -c "
import asyncio, json
from oprocess.server import mcp
tools = asyncio.run(mcp.list_tools())
for t in tools:
    print(f'{t.name}: {json.dumps(t.parameters, indent=2)}')
"                               # 验证每个 tool 的 inputSchema 完整
```

## 文件改动清单

| 文件 | 操作 | 预计行变化 |
|------|------|-----------|
| `src/oprocess/db/queries.py` | 修改 | +12 |
| `src/oprocess/tools/registry.py` | 修改 | +15 / -5 |
| `src/oprocess/tools/helpers.py` | 修改 | +8 / -3 |
| `src/oprocess/tools/resources.py` | 修改 | +2 / -2 |
| `src/oprocess/tools/export.py` | 修改 | +3 |
| `README.md` | 重写 | +200 |
| `pyproject.toml` | 修改 | 已修复 |
| `tests/test_tools/test_queries.py` | 修改 | +15 |
| `tests/test_tools/test_kpi_role.py` | 修改 | +5 / -3 |
| `tests/test_tools/test_schema_validation.py` | 新建 | +60 |
| `tests/test_tools/test_resources.py` | 修改 | +5 |

## Acceptance Criteria

- [x] 7 个 Tool 全部使用 `Annotated[..., Field(...)]` 约束
- [x] `mcp.list_tools()` 每个 tool 的 `parameters` 包含 description/enum/minLength/pattern 等
- [x] 所有 `{"error": ...}` 替换为 `raise ToolError(...)` 或 `{"not_found": ...}`
- [x] `search_processes(conn, "test", lang="fr")` 抛出 `ValueError`
- [x] `compare_process_nodes(conn, "1.0,99.99")` 抛出 `ToolError`
- [x] README 包含 Claude Desktop JSON + Tool 表 + Resource 表
- [x] `ruff check . && pytest` 全通过
- [x] build-backend 为 `hatchling.build`

## 执行顺序

```
P0.3 (lang 白名单) → P0.1 (Annotated Field) → P0.2 (ToolError) → P0.4 (README) → P0.5 (验证)
```

## Sources

- **Origin**: [docs/plans/2026-02-23-feat-mcp-certification-upgrade-plan.md](docs/plans/2026-02-23-feat-mcp-certification-upgrade-plan.md)
- **FastMCP docs**: gofastmcp.com/servers/tools — Annotated Field 和 ToolError 用法
- **实测**: FastMCP 3.0.2 + Pydantic 2.12.5 行为验证
