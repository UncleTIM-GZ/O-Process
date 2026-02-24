---
title: src/oprocess/ 代码质量审查
date: 2026-02-25
scope: src/oprocess/ (25 files, ~1500 LOC)
status: resolved
ruff: pass
tests: 252 passed, 10 errors (sqlite-vec env)
coverage: 90.97%
---

# 代码审查报告

**项目**: O'Process MCP Server (`src/oprocess/`)
**文件数**: 25 个 Python 文件，总计 ~1500 行有效代码
**Ruff Lint**: 零错误
**测试**: 252 通过，10 errors（sqlite-vec 环境问题）
**覆盖率**: 90.97%（> 80% 门禁）

---

## 🔴 严重问题（必须修复）

### 问题 1: 版本号不一致
- **文件**: `src/oprocess/__init__.py:3` vs `src/oprocess/server.py:75` vs `src/oprocess/tools/resources.py:135`
- **风险**: `__init__.py` 声明 `"0.1.0"`，但 `server.py` 和 `resources.py` 都硬编码 `"0.3.0"`。客户端通过不同接口获取的版本号不一致。
- **建议**: 统一使用 `oprocess.__version__` 作为唯一来源。

---

## 🟡 警告（应该修复）

### 问题 2: `Lang` 类型别名重复定义
- **文件**: `src/oprocess/tools/registry.py:45-47` 和 `src/oprocess/tools/search.py:29-31`
- **风险**: 完全相同的 `Annotated[Literal["zh", "en"], ...]`，违反 DRY 原则。
- **建议**: 定义在一个共享位置（如 `registry.py`），`search.py` 导入使用。

### 问题 3: 正则和验证函数大量重复
- **文件**:
  - `_PROCESS_ID_RE`: `src/oprocess/prompts.py:13` + `src/oprocess/tools/resources.py:33`（完全相同）
  - `_SESSION_ID_RE` / UUID4 校验: `src/oprocess/tools/resources.py:34-37` + `src/oprocess/governance/audit.py:17-20`（完全相同）
  - `_validate_lang`: `src/oprocess/prompts.py:30-33` vs `src/oprocess/db/queries.py:23-27`（功能相同，异常类不同）
- **风险**: 修改一处遗漏另一处；> 10 行重复代码违反项目规约。
- **建议**: 抽取到 `src/oprocess/validators.py` 共用。

### 问题 4: 版本号三处硬编码
- **文件**: `src/oprocess/__init__.py:3`、`src/oprocess/server.py:75`、`src/oprocess/tools/resources.py:135`
- **风险**: 每次发版需改三处，易遗漏。
- **建议**: `server.py` 和 `resources.py` 统一引用 `oprocess.__version__`。

### 问题 5: `get_kpi_suggestions` 重复查询
- **文件**: `src/oprocess/tools/registry.py:110-133`
- **风险**: `get_process(conn, process_id)` 在 `_get_kpis()` 内部调用一次（L111），gateway 执行后又调用一次（L127），造成双倍 DB 查询。
- **建议**: 从 `resp.result["process"]` 中提取已有数据构建 provenance。

### 问题 6: `export.py` 溯源附录 N+1 查询
- **文件**: `src/oprocess/tools/export.py:85-91`
- **风险**: 对每个祖先节点逐个调用 `build_path_string(conn, node["id"])`，每次调用又遍历祖先链。已有 `build_path_strings_batch` 批量函数未使用。
- **建议**: 改用 `build_path_strings_batch` 批量构建路径。

### 问题 7: 配置解析静默吞异常
- **文件**: `src/oprocess/config.py:45-46`
- **风险**: `except Exception: pass` 完全无日志。pyproject.toml 格式错误时无任何提示。
- **建议**: 添加 `logger.warning("Failed to parse pyproject.toml", exc_info=True)`。

---

## 🟢 建议（可选改进）

### 问题 8: ASGI 中间件缺少类型注解
- **文件**: `src/oprocess/auth.py:71, 74`
- **风险**: `__init__(self, app)` 和 `__call__(self, scope, receive, send)` 缺乏类型注解，不符合"所有 public function 必须有类型注解"的质量门禁。
- **建议**: 添加 ASGI 标准类型注解。

### 问题 9: `compare_process_nodes` 祖先链 N+1
- **文件**: `src/oprocess/tools/helpers.py:134-137`
- **风险**: 对比 N 个流程时，每个流程调用 `get_ancestor_chain()`（最多 5 次 DB 查询），对比 5 个流程最多 25 次查询。
- **建议**: 可以收集所有 pid 后批量查询，但当前使用场景（通常 2-3 个流程对比）影响有限。

---

## ✅ 优点

- **安全性优秀**: SQL 全部参数化查询；`_escape_like()` 处理 LIKE 通配符；Bearer auth 使用 `hmac.compare_digest` 防时序攻击；审计日志 append-only 触发器保护
- **架构清晰**: Gateway 模式统一所有 Tool 调用路径；Governance-Lite 三能力（Audit/Boundary/Provenance）解耦良好
- **代码规范**: 所有文件 < 300 行（最大 259 行）；ruff lint 零错误；覆盖率 90.97%
- **性能考虑**: `build_path_strings_batch` 批量缓存路径；vector_search 使用 JOIN 消除 N+1
- **输入验证**: Pydantic Field 做参数验证；prompt 注入防护（`_sanitize_role_name`）；BoundaryResponse 结构化降级
- **错误隔离**: 审计日志写入失败不阻塞主流程（try/except + warning）

---

## 修复优先级

| 优先级 | 问题 | 估计工作量 |
|--------|------|-----------|
| P0 | #1 版本号不一致 | Small |
| P1 | #4 版本号 DRY | Small |
| P1 | #2 Lang 类型别名重复 | Small |
| P1 | #3 正则/验证函数重复 | Medium |
| P1 | #5 get_kpi_suggestions 双查询 | Small |
| P1 | #6 export.py N+1 | Small |
| P1 | #7 配置解析静默吞异常 | Small |
| P2 | #8 ASGI 类型注解 | Small |
| P2 | #9 compare N+1 | Medium |
