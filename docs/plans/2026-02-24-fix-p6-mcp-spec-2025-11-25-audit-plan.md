---
title: "fix: P6 — MCP Spec 2025-11-25 全面合规审查修复"
type: fix
status: completed
date: 2026-02-24
spec_version: "2025-11-25"
---

# fix: P6 — MCP Spec 2025-11-25 全面合规审查修复

基于 MCP Specification 2025-11-25 对 O'Process MCP Server 的全面审查。
审查时代码状态: commit `323d9b1` (feat/oprocess-framework-construction)。

## 审查总结

| 等级 | 合规率 | 说明 |
|------|--------|------|
| MUST | 16/16 (100%) | 全部满足 |
| SHOULD | ~85% | 4 项缺失 |
| MAY | 部分 | Prompts / Completions / icons 未实现 |

## P0 — 必须修复（正确性问题）

### P6-1: 版本号不一致

- **问题**: 三处版本号不统一
  - `pyproject.toml:4` → `version = "0.1.0"`
  - `src/oprocess/server.py:43` → `version="0.3.0"`
  - `src/oprocess/tools/resources.py:135` → `"version": "0.3.0"`
- **修复**: 统一为 `0.3.0`（反映 P4/P5 修复后的实际状态）
- **文件**: `pyproject.toml`
- **改动量**: 1 行

### P6-2: 双 Gateway 实例导致 session_id 不一致

- **问题**: `registry.py:38-47` 和 `search.py:32-41` 各自维护独立的 `_gateway` 单例
- **后果**: 同一客户端调用 `search_process`（走 search.py gateway）和 `get_process_tree`（走 registry.py gateway）会产生不同的 `session_id`，审计日志无法关联同一会话
- **修复**: 将 gateway 单例提取到共享位置（如 `gateway.py` 中增加 `get_shared_gateway()`），两处引用同一个实例
- **文件**: `src/oprocess/gateway.py`, `src/oprocess/tools/registry.py`, `src/oprocess/tools/search.py`
- **改动量**: ~15 行

### P6-3: `health_check` 不经过 Gateway

- **问题**: `registry.py:251-267` 直接查询数据库，未走 `_get_gateway().execute()`
- **后果**: health_check 调用不记入审计日志，与其他 tool 行为不一致
- **修复**: 改为走 gateway.execute("health_check", ...)
- **文件**: `src/oprocess/tools/registry.py`
- **改动量**: ~10 行

### P6-4: README 与代码不同步

- **问题**:
  - README 第 50 行写 `ping` 工具，代码已改名为 `health_check`
  - README 未记录 `OPROCESS_ALLOWED_ORIGINS` 环境变量
  - README 未记录 `rate_limit_max_calls` / `rate_limit_window_seconds` 配置
- **修复**: 更新 README 的 Tools 表、Environment Variables 表、Configuration 节
- **文件**: `README.md`
- **改动量**: ~15 行

## P1 — 推荐修复（SHOULD 级别合规）

### P6-5: Tool Annotations `destructiveHint=False` 显式声明

- **问题**: 当前 `_READ_ONLY` 和 `_READ_ONLY_OPEN` 未设 `destructiveHint`
- **规范默认值**: `destructiveHint=True`（spec 假设 tool 默认可能是破坏性的）
- **后果**: MCP 客户端会认为这些只读 tool "可能有破坏性"，影响用户体验
- **修复**: 在 ToolAnnotations 中显式设置 `destructiveHint=False`
- **文件**: `src/oprocess/tools/registry.py`, `src/oprocess/tools/search.py`
- **改动量**: 2 行

### P6-6: `resources.py` 测试覆盖率不足

- **当前**: 56.67%（项目标准 ≥ 80%）
- **缺失**: `get_process_resource`, `get_category_list`, `get_role_mapping`, `get_audit_session`, `get_schema`, `get_stats` 多数分支未覆盖
- **修复**: 新增 resource 端点测试
- **文件**: `tests/test_tools/test_resources.py`
- **改动量**: ~80 行测试

### P6-7: `auth.py` 测试覆盖率不足

- **当前**: 76.39%（项目标准 ≥ 80%）
- **缺失**: `get_allowed_origins()`, `_send_403()`, Origin 验证异步路径
- **修复**: 补充 auth middleware 测试
- **文件**: `tests/test_governance/test_auth.py`
- **改动量**: ~40 行测试

## P2 — 增强改进（竞争力提升）

### P6-8: 添加 MCP Prompts（引导式模板）

- **问题**: 服务器未实现任何 MCP Prompt，客户端无法发现核心使用场景
- **建议添加 3 个 Prompts**:
  - `analyze_process` — 输入 process_id，生成流程分析报告模板
  - `generate_job_description` — 输入 process_ids + role_name，生成岗位说明书模板
  - `kpi_review` — 输入 process_id，生成 KPI 审查建议模板
- **文件**: `src/oprocess/tools/prompts.py`（新建），`src/oprocess/server.py`
- **改动量**: ~60 行

### P6-9: MCP logging capability（Context.log）

- **问题**: 仅用 Python logging，未通过 MCP Context.log() 发送结构化日志给客户端
- **建议**: 在关键 tool 内添加 `ctx.log("info", data=...)` 调用
- **前置**: FastMCP 3.x 支持 Context 参数注入
- **文件**: `src/oprocess/tools/registry.py`, `src/oprocess/tools/search.py`
- **改动量**: ~20 行

### P6-10: atexit 线程安全修复

- **问题**: `connection.py:65` `_close_shared()` 在 pytest 多线程环境下抛出 `ProgrammingError`
- **修复**: 在 `_close_shared()` 中捕获 `ProgrammingError` 异常
- **文件**: `src/oprocess/db/connection.py`
- **改动量**: 3 行

### P6-11: Completions / outputSchema / icons（远期）

- **Completions**: 为 `process_id` 参数提供自动补全
- **outputSchema**: 为 tool 返回值定义结构化 schema
- **icons**: 为 server / tools 添加图标
- **优先级**: 低，视需求决定

## Commit 策略

### Commit 1: P6.1 — P0 正确性修复
```
pyproject.toml                      — 版本统一 0.3.0
src/oprocess/gateway.py             — get_shared_gateway() 共享单例
src/oprocess/tools/registry.py      — 引用共享 gateway + health_check 走 gateway
src/oprocess/tools/search.py        — 引用共享 gateway
README.md                           — 同步更新
```

### Commit 2: P6.2 — SHOULD 合规 + 测试补充
```
src/oprocess/tools/registry.py      — destructiveHint=False
src/oprocess/tools/search.py        — destructiveHint=False
src/oprocess/db/connection.py       — atexit 线程安全
tests/test_tools/test_resources.py  — resource 端点测试
tests/test_governance/test_auth.py  — auth 覆盖率补充
```

### Commit 3: P6.3 — MCP Prompts + logging（可选）
```
src/oprocess/tools/prompts.py       — (new) 3 个 Prompt 模板
src/oprocess/server.py              — 注册 prompts
tests/test_tools/test_prompts.py    — Prompt 测试
```

## Acceptance Criteria

### P0 (Commit 1)
- [x] `pyproject.toml` version = "0.3.0"
- [x] Gateway 单例全局唯一，search 和 registry 共享同一 session_id
- [x] health_check 调用记入审计日志
- [x] README Tools 表中 `ping` → `health_check`
- [x] README 包含 `OPROCESS_ALLOWED_ORIGINS` 文档
- [x] ruff check src/ tests/ 零 error
- [x] pytest 全部通过

### P1 (Commit 2)
- [x] 所有 ToolAnnotations 含 `destructiveHint=False`
- [x] `resources.py` 覆盖率 ≥ 80%
- [x] `auth.py` 覆盖率 ≥ 80%
- [x] atexit 无 ProgrammingError 输出
- [x] 总覆盖率 ≥ 85%

### P2 (Commit 3)
- [x] 3 个 MCP Prompts 可被客户端发现
- [x] Prompt 参数验证正确
- [x] Prompt 返回格式符合 MCP Spec

## 涉及文件

### 源码修改
- `pyproject.toml` — P6-1
- `src/oprocess/gateway.py` — P6-2
- `src/oprocess/tools/registry.py` — P6-2, P6-3, P6-5
- `src/oprocess/tools/search.py` — P6-2, P6-5
- `src/oprocess/db/connection.py` — P6-10
- `src/oprocess/tools/prompts.py` — P6-8 (新建)
- `src/oprocess/server.py` — P6-8
- `README.md` — P6-4

### 测试修改
- `tests/test_tools/test_resources.py` — P6-6
- `tests/test_governance/test_auth.py` — P6-7
- `tests/test_tools/test_prompts.py` — P6-8 (新建)

## 参考规范

- [MCP Spec 2025-11-25](https://modelcontextprotocol.io/specification/2025-11-25)
- [MCP Tools Spec](https://modelcontextprotocol.io/specification/2025-11-25/server/tools)
- [MCP Resources Spec](https://modelcontextprotocol.io/specification/2025-11-25/server/resources)
- [MCP Prompts Spec](https://modelcontextprotocol.io/specification/2025-11-25/server/prompts)
- [MCP Security Best Practices](https://modelcontextprotocol.io/specification/2025-11-25/basic/security_best_practices)
