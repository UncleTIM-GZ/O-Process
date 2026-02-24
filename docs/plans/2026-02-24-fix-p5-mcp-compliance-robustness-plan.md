---
title: "fix: P5-1~P5-4 MCP compliance + robustness"
type: fix
status: completed
date: 2026-02-24
---

# fix: P5-1~P5-4 MCP 合规 + 健壮性修复

P4 完成后审计发现的 4 项 SHOULD 级别合规与健壮性问题。

## Enhancement Summary

**Deepened on:** 2026-02-24
**Research agents used:** FastMCP error handling, security review, simplicity review

### Key Improvements
1. P5-2 简化为仅空值检查（FastMCP URI 参数已保证非空，仅防御性编程）
2. P5-3 简化为仅空 ID 过滤（重复 ID 和单 ID 是合法输入，非错误）
3. P5-4 保留兜底 `except Exception` 分支（避免未预见异常导致启动崩溃）

### New Considerations Discovered
- `validate_lang()` 被 Tool 和 Resource 共同调用，改为 ToolError 需确认 resource 路径无影响
- `_load_sqlite_vec` 细化异常后必须保留兜底分支，否则 RuntimeError 等会导致服务启动失败
- 日志中避免 `exc_info=True` 以防泄露内部路径信息

## 修复清单

### P5-1: validate_lang() 抛出 ValueError 而非 ToolError

- **文件**: `src/oprocess/db/queries.py:21-25`
- **问题**: `validate_lang()` 被 MCP Tool 直接调用（registry.py, search.py），但抛出 `ValueError`。MCP 规范要求 Tool 层错误统一为 `ToolError`。
- **修复**: 将 `raise ValueError(msg)` 改为 `raise ToolError(msg)`
- **测试**: 更新 `tests/test_tools/test_queries.py` 中已有的 `test_invalid_lang_raises` 断言
- **改动量**: 2 行（1 import + 1 raise）

### P5-2: get_role_mapping resource 缺少输入验证

- **文件**: `src/oprocess/tools/resources.py:83-101`
- **问题**: `role_name` 参数无空/空白字符串检查
- **修复**: 添加 guard clause — `strip()` 后空值检查，使用 `ResourceError`
- **不做**: 长度限制（无技术依据，中文岗位名可能超长）、字符白名单（限制合法输入）
- **测试**: 在 `tests/test_tools/test_resources.py` 新增 `TestRoleMappingValidation`
- **改动量**: 3 行

### P5-3: compare_process_nodes 空 ID 过滤

- **文件**: `src/oprocess/tools/helpers.py:107-140`
- **问题**: `"1.0,,8.0"` 空 ID 会导致 `get_process(conn, "")` 查询
- **修复**: 过滤空 ID（`ids = [pid for pid in ... if pid]`）
- **不做**: 重复 ID 检查（合法输入，返回空比较列表）、单 ID 检查（返回空比较列表是合理降级）
- **测试**: 在 `tests/test_tools/test_kpi_role.py` 新增 1 个测试
- **改动量**: 1 行

### P5-4: connection.py 异常捕获具体化

- **文件**: `src/oprocess/db/connection.py:30-39, 74-83`
- **问题**: `except (ImportError, Exception):` 冗余且掩盖真实错误
- **修复**:
  - `_load_sqlite_vec`: `except ImportError` + `except Exception`（添加 `logger.debug`）
  - `_create_vec_table`: `except Exception`（保持，添加 `logger.debug` 带 `type(e).__name__`）
- **不做**: 拆分到 `sqlite3.OperationalError`（可能遗漏未预见异常导致启动失败）
- **改动量**: ~6 行

## Acceptance Criteria

- [x] P5-1: `validate_lang("fr")` 抛出 `ToolError` 而非 `ValueError`
- [x] P5-2: `get_role_mapping("")` 抛出 `ResourceError`
- [x] P5-3: `compare_process_nodes(conn, "1.0,,8.0")` 不传空 ID 给数据库
- [x] P5-4: `_load_sqlite_vec` 区分 `ImportError` 和其他异常，均有日志记录
- [x] `ruff check .` 零 error
- [x] `pytest` 全部通过 (202 passed)
- [x] 覆盖率 ≥ 80% (89.92%)
- [x] 所有修改文件 ≤ 300 行

## Context

- 前序: P4 (commits `b71497b`, `07d12be`) 完成了 13 项 MCP 合规修复
- 每项修复改动量极小，总计 ~12 行代码变更 + ~15 行测试
- 遵循已有的 guard clause / ToolError / ResourceError 模式

## 涉及文件

### 源码修改
- `src/oprocess/db/queries.py` — P5-1
- `src/oprocess/tools/resources.py` — P5-2
- `src/oprocess/tools/helpers.py` — P5-3
- `src/oprocess/db/connection.py` — P5-4

### 测试修改
- `tests/test_tools/test_queries.py` — P5-1 断言更新
- `tests/test_tools/test_resources.py` — P5-2 新增测试
- `tests/test_tools/test_kpi_role.py` — P5-3 新增测试
