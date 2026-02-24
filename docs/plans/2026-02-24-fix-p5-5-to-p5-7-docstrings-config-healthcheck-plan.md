---
title: "fix: P5-5~P5-7 Tool docstrings + config + health check"
type: fix
status: completed
date: 2026-02-24
---

# fix: P5-5~P5-7 Tool docstrings + 配置化 + 连接健康检查

P5-1~P5-4 完成后的第二批修复。

## Enhancement Summary

**Deepened on:** 2026-02-24
**Research agents used:** FastMCP docstring patterns, security review, simplicity review

### Key Improvements
1. P5-5 精简为仅 Resource docstrings（Tool docstrings 已足够好，不改）
2. P5-6 配置值需类型校验（安全审查建议）
3. P5-7 简化为仅添加 `vec_available` bool 字段（不做 "degraded" 状态）

### New Considerations Discovered
- FastMCP 使用 `inspect.getdoc()` 完整提取多行 docstring，不截断
- 配置化需防止负数/零值注入（rate limit = 0 等于无限制）
- `check_vec_available()` 不暴露 SQL 错误消息，仅返回 bool

## 修复清单

### P5-5: Tool/Resource docstrings 增强

- **文件**: `src/oprocess/tools/registry.py`, `src/oprocess/tools/search.py`, `src/oprocess/tools/resources.py`
- **问题**: MCP Tool/Resource 的 `description` 字段由 Python docstring 自动生成。当前部分 docstring 过短（`health_check` 仅 2 行，Resource 函数仅 1 行），不利于 LLM 理解工具用途。
- **修复**:
  - `health_check`: 补充返回字段说明
  - Resource 函数: 每个补充到 2-3 行（用途 + 返回格式 + 错误场景）
  - 不改 Tool 参数的 `Field(description=...)` — 当前已满足需求
- **改动量**: ~20 行（纯注释）

### P5-6: Rate Limit 配置化

- **文件**: `src/oprocess/tools/rate_limit.py`, `src/oprocess/config.py`, `src/oprocess/server.py`
- **问题**: `RateLimitMiddleware(max_calls=60, window_seconds=60)` 硬编码在构造器默认参数中。用户无法通过 pyproject.toml 调整限流参数。
- **修复**:
  - 在 `config.py` 的 `_DEFAULTS` 添加 `rate_limit_max_calls: 60`, `rate_limit_window_seconds: 60`
  - 在 `server.py` 创建 `RateLimitMiddleware` 时从 `get_config()` 读取
  - `rate_limit.py` 本身不改（构造器已接受参数）
- **不做**: DB Path 配置化（已通过 `get_shared_connection(db_path=)` 支持传入）、Server name/version 配置化（从 pyproject.toml 读过于间接）
- **改动量**: ~5 行

### P5-7: health_check 扩展 — 连接 + vec 状态

- **文件**: `src/oprocess/tools/registry.py`, `src/oprocess/db/connection.py`
- **问题**: 当前 `health_check()` 只返回 `count_processes` / `count_kpis`，不报告 sqlite-vec 扩展是否加载、连接是否正常。
- **修复**:
  - 在 `connection.py` 添加 `check_vec_available(conn)` 函数 — 执行 `SELECT vec_version()` 捕获异常
  - 在 `health_check()` 增加 `vec_available` 和 `connection_ok` 字段
  - 用 try/except 包裹整个检查，失败则返回 `status: "degraded"`
- **不做**: 新增 `oprocess://health` Resource（与 health_check Tool 重复）、启动自检（复杂度高，收益低）
- **测试**: 新增 `test_health_check_fields` 验证返回字段
- **改动量**: ~20 行

## Acceptance Criteria

- [x] P5-5: 所有 Resource docstring ≥ 2 行；health_check docstring 含返回字段说明
- [x] P5-6: `pyproject.toml` 中可配置 `rate_limit_max_calls` / `rate_limit_window_seconds`
- [x] P5-7: `health_check()` 返回 `vec_available` 字段
- [x] `ruff check .` 零 error
- [x] `pytest` 全部通过 (204 passed)
- [x] 覆盖率 ≥ 80% (89.80%)
- [x] 所有修改文件 ≤ 300 行

## 涉及文件

### 源码修改
- `src/oprocess/tools/registry.py` — P5-5 + P5-7
- `src/oprocess/tools/search.py` — P5-5
- `src/oprocess/tools/resources.py` — P5-5
- `src/oprocess/config.py` — P5-6
- `src/oprocess/server.py` — P5-6
- `src/oprocess/db/connection.py` — P5-7

### 测试修改
- `tests/test_tools/test_registry_tools.py` — P5-7 新增测试
