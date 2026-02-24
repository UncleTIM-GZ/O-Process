# O'Process MCP Server — 开发者视角：代码导读

> **版本**: 0.3.0 | **最后更新**: 2026-02-25 | **数据来源**: 源码实际实现

---

## 1. 项目结构

```
src/oprocess/                          # 主包（25 个 Python 文件，~1500 LOC）
├── __init__.py                        # 版本号唯一来源
├── __main__.py                        # python -m oprocess 入口
├── server.py                          # FastMCP 主入口 + CLI 参数
├── gateway.py                         # ToolGatewayInterface + PassthroughGateway
├── config.py                          # pyproject.toml 配置读取
├── validators.py                      # 集中式验证（正则、语言、安全过滤）
├── auth.py                            # ASGI Bearer Token + Origin 中间件
├── prompts.py                         # 3 个 MCP Prompt 模板
├── tools/
│   ├── __init__.py
│   ├── _types.py                      # Pydantic 类型别名（Lang, ProcessId 等）
│   ├── registry.py                    # 6 个非搜索 Tool 注册
│   ├── search.py                      # 2 个搜索 Tool 注册
│   ├── helpers.py                     # 辅助函数（boundary, provenance, compare）
│   ├── export.py                      # Markdown 岗位说明书生成
│   ├── serialization.py               # JSON 序列化
│   └── rate_limit.py                  # 速率限制中间件
├── db/
│   ├── __init__.py
│   ├── connection.py                  # SQLite 连接 + Schema DDL + 迁移
│   ├── queries.py                     # SQL 查询函数
│   ├── vector_search.py               # sqlite-vec 向量搜索
│   ├── embedder.py                    # Gemini Embedding Provider
│   └── row_utils.py                   # 行转换器
└── governance/
    ├── __init__.py
    ├── audit.py                       # SessionAuditLog（append-only）
    ├── boundary.py                    # BoundaryResponse（低置信度降级）
    └── provenance.py                  # ProvenanceChain（溯源链）

tests/                                 # 262 个测试用例
├── conftest.py                        # 共享 fixtures
├── test_tools/                        # Tool + Resource + Prompt 测试
│   ├── test_registry.py
│   ├── test_search.py
│   ├── test_resources.py
│   ├── test_prompts.py
│   ├── test_export.py
│   └── test_helpers.py
├── test_governance/                   # 治理能力测试
│   ├── test_audit.py
│   ├── test_boundary.py
│   └── test_provenance.py
├── test_db/                           # 数据库层测试
├── test_config.py
├── test_auth.py
├── test_rate_limit.py
├── test_performance.py                # 性能基准（pytest-benchmark）
└── fixtures/                          # 标注测试集
```

---

## 2. 快速上手

### 2.1 环境搭建

```bash
# 安装依赖（使用 uv 包管理器）
uv sync

# 运行 MCP Server（stdio 模式，最简启动）
uv run python -m oprocess

# SSE 模式（需设置 API Key）
OPROCESS_API_KEY=your-secret uv run python -m oprocess --transport sse --port 8000

# 运行测试
pytest                                  # 完整测试
pytest tests/test_tools/                # 单目录
pytest -k "test_search"                 # 按名称
pytest --benchmark-only                 # 性能基准

# Lint
ruff check .

# 提交前完整检查
ruff check . && pytest && pytest --benchmark-only
```

### 2.2 环境变量

| 变量 | 用途 | 必需 |
|------|------|------|
| `GOOGLE_API_KEY` / `GEMINI_API_KEY` | Gemini embedding API（语义搜索） | 否（回退到 LIKE） |
| `OPROCESS_API_KEY` | HTTP 模式 Bearer Token | 否（未设置=免认证） |
| `OPROCESS_ALLOWED_ORIGINS` | CORS Origin 白名单（逗号分隔） | 否 |
| `LOG_LEVEL` | 日志级别（DEBUG/INFO/WARNING） | 否（默认 WARNING） |

---

## 3. 核心调用链详解

### 3.1 Tool 调用链（以 `search_process` 为例）

```
MCP Client 发起 tools/call
  ↓
FastMCP 框架路由
  ↓
RateLimitMiddleware.on_call_tool()          # rate_limit.py:64
  → _check_rate(client_id)                  # 滑动窗口检查
  → call_next(context)                      # 通过则继续
  ↓
search_process(query, lang, limit, level)   # search.py:33
  ↓
conn = get_shared_connection()              # connection.py:44 (singleton)
  ↓
resp = get_shared_gateway().execute(        # gateway.py:133 (singleton)
    "search_process",
    search_processes,                        # queries.py:67
    conn=conn, query=query, ...
)
  ↓ (PassthroughGateway.execute 内部)
  start = time.monotonic()
  result = search_processes(...)             # 实际查询
  elapsed_ms = ...
  log_invocation(...)                        # audit.py:26 (如果 audit_conn != None)
  return ToolResponse(result, session_id, response_ms)
  ↓
resp.provenance_chain = build_search_provenance(...)  # helpers.py:52
  ↓
apply_boundary(query, results, resp)         # helpers.py:21
  → check_boundary(query, best_score)        # boundary.py:41
  → 如果低置信度，将 resp.result 包装在 boundary 响应中
  ↓
return response_to_json(resp)                # serialization.py:15
  → JSON: { result, provenance_chain, session_id, response_ms }
```

### 3.2 搜索降级链

```python
# queries.py:67-89
def search_processes(conn, query, lang, limit, level):
    validate_lang(lang)               # validators.py

    embedder = _get_embedder()        # 懒初始化 singleton
    if embedder and has_vec_table(conn):
        try:
            vecs = embedder.embed([query])
            results = vector_search(conn, vecs[0], limit, level)
            if results:
                return results        # 向量搜索成功
        except Exception:
            logger.warning(...)       # 向量搜索失败 → 降级

    return _search_like(...)          # LIKE 回退
```

### 3.3 Resource 调用链（直接返回，不经过 Gateway）

```
MCP Client 发起 resources/read
  ↓
FastMCP 框架匹配 URI 模板
  ↓
get_process_resource(process_id)     # resources.py:38
  → validate_process_id(pid, resource=True)   # ResourceError on invalid
  → conn = get_shared_connection()
  → process = get_process(conn, pid)
  → return to_json(process)
```

**注意**：Resources 不经过 Gateway，不产生审计日志，不附加 provenance。这是设计意图 — Resources 是只读查询，不需要治理增强。

---

## 4. 编码规范

### 4.1 质量门禁

| 规则 | 要求 |
|------|------|
| 单文件行数 | <= 300 行 |
| 单函数行数 | <= 50 行 |
| 嵌套层级 | <= 3 层 |
| 重复代码 | > 10 行必须抽象 |
| 类型注解 | 所有 public function 必须有 |
| Lint | ruff check 零 error |
| 测试覆盖率 | >= 80%（当前 94.75%） |

### 4.2 类型风格

```python
# 正确 ✓
str | None
list[dict]
dict[str, str]

# 不使用 ✗
Optional[str]
List[dict]
Dict[str, str]
```

### 4.3 异常使用约定

| 场景 | 异常类型 | 来源 |
|------|---------|------|
| Tool 参数验证失败 | `ToolError` | `from fastmcp.exceptions import ToolError` |
| Resource 参数验证失败 | `ResourceError` | `from fastmcp.exceptions import ResourceError` |
| Prompt 参数验证失败 | `ValueError` | 内置 |
| 速率限制 | `McpError` | `from mcp.shared.exceptions import McpError` |

**validators.py 的双模式设计**：

```python
# Tool 上下文 → raise ToolError
validate_lang(lang)                    # 默认 tool=True

# Prompt/Resource 上下文 → raise ValueError 或 ResourceError
validate_lang(lang, tool=False)        # ValueError
validate_process_id(pid, resource=True) # ResourceError
```

### 4.4 JSON 序列化

```python
# 必须使用 ensure_ascii=False 以保留中文字符
json.dumps(data, ensure_ascii=False, indent=2)

# 统一使用封装函数
from oprocess.tools.serialization import to_json, response_to_json
```

---

## 5. 数据库操作指南

### 5.1 连接获取

```python
# 生产代码 — 使用进程级 singleton
from oprocess.db.connection import get_shared_connection
conn = get_shared_connection()

# 测试代码 — 使用独立连接 + tmp_path
from oprocess.db.connection import get_connection, init_schema
conn = get_connection(tmp_path / "test.db")
init_schema(conn)
```

### 5.2 查询函数清单

| 函数 | 文件 | 返回值 |
|------|------|--------|
| `get_process(conn, id)` | queries.py:20 | `dict \| None` |
| `get_children(conn, parent_id)` | queries.py:30 | `list[dict]` |
| `get_subtree(conn, root_id, max_depth)` | queries.py:39 | `dict \| None`（嵌套 children） |
| `search_processes(conn, query, lang, limit, level)` | queries.py:67 | `list[dict]`（带 score 或无） |
| `get_kpis_for_process(conn, id)` | queries.py:124 | `list[dict]` |
| `get_processes_by_level(conn, level)` | queries.py:135 | `list[dict]` |
| `get_ancestor_chain(conn, id)` | queries.py:146 | `list[dict]`（root→leaf 顺序） |
| `build_path_string(conn, id)` | queries.py:162 | `str`（如 "1.0 > 1.1 > 1.1.2"） |
| `build_path_strings_batch(conn, ids)` | queries.py:168 | `dict[str, str]`（批量路径） |
| `count_processes(conn)` | queries.py:188 | `int` |
| `count_kpis(conn)` | queries.py:193 | `int` |

### 5.3 向量搜索

```python
# vector_search.py
def vector_search(conn, query_embedding, limit, level) -> list[dict]:
    # 1. sqlite-vec MATCH 查询：
    #    SELECT process_id, distance FROM vec_processes
    #    WHERE embedding MATCH ? AND k = ?
    #
    # 2. 批量获取 process 详情（消除 N+1）：
    #    SELECT * FROM processes WHERE id IN (...)
    #
    # 3. 合并结果，计算 score = 1.0 - distance
    # 4. 可选 level 过滤（post-filter）
```

### 5.4 行转换

所有 process 查询结果经过 `row_to_process()` 转换，自动解析 JSON 字段：

```python
# row_utils.py
def row_to_process(row: sqlite3.Row) -> dict:
    d = dict(row)
    d["source"] = json.loads(d["source"])      # str → list
    d["tags"] = json.loads(d["tags"])           # str → list
    d["kpi_refs"] = json.loads(d["kpi_refs"])   # str → list
    d["provenance_eligible"] = bool(d["provenance_eligible"])
    return d
```

---

## 6. 添加新 Tool 指南

### 步骤 1：定义参数类型

如果需要新的参数类型，添加到 `tools/_types.py`：

```python
# tools/_types.py
MyParam = Annotated[str, Field(min_length=1, description="Description")]
```

### 步骤 2：实现 Tool 函数

在 `tools/registry.py`（或新文件，如超过 300 行则拆分）中注册：

```python
@mcp.tool(annotations=_READ_ONLY, title="My New Tool")
def my_tool(param: MyParam) -> str:
    """Tool 描述（LLM 可见）。"""
    conn = get_shared_connection()

    def _my_logic():
        # 实际查询逻辑
        return {"data": "..."}

    resp = get_shared_gateway().execute("my_tool", _my_logic)

    # 构建溯源链（如适用）
    resp.provenance_chain = [...]

    return response_to_json(resp)
```

### 步骤 3：编写测试

```python
# tests/test_tools/test_my_tool.py
class TestMyTool:
    def test_basic(self, conn):
        # 使用 fixture 提供的测试数据库连接
        ...

    def test_not_found(self, conn):
        with pytest.raises(ToolError):
            ...
```

### 步骤 4：验证

```bash
ruff check .                    # Lint 通过
pytest tests/test_tools/        # 测试通过
pytest --cov=oprocess           # 覆盖率 >= 80%
```

---

## 7. 添加新 Resource 指南

```python
# resources.py 内的 register_resources() 中

@mcp.resource("oprocess://my/{param}", mime_type="application/json")
def my_resource(param: str) -> str:
    """Resource 描述。"""
    validate_process_id(param, resource=True)  # 使用 resource=True → ResourceError
    conn = get_shared_connection()
    data = get_process(conn, param)
    if not data:
        raise ResourceError(f"Not found: {param}")
    return to_json(data)
```

**注意**：Resources 不经过 Gateway，直接返回 JSON 字符串。

---

## 8. 添加新 Prompt 指南

```python
# prompts.py 内的 register_prompts() 中

@mcp.prompt(title="My Workflow")
def my_workflow(param: str, lang: str = "zh") -> str:
    """Prompt 描述。"""
    validate_process_id(param)          # 参数验证
    validate_lang(lang, tool=False)     # tool=False → ValueError
    if lang == "zh":
        return f"## 工作流\n\n目标: `{param}`\n\n..."
    return f"## Workflow\n\nTarget: `{param}`\n\n..."
```

---

## 9. 验证函数使用指南

所有验证函数集中在 `validators.py`（Single Source of Truth）：

```python
from oprocess.validators import (
    validate_process_id,     # pid格式验证，resource=True → ResourceError
    validate_process_ids,    # 逗号分隔多ID验证
    validate_session_id,     # UUID4格式验证，resource=True → ResourceError
    validate_lang,           # zh/en验证，tool=True → ToolError
    sanitize_role_name,      # 安全过滤：去控制字符、折叠空白、100字符限制
    PROCESS_ID_RE,           # 编译后正则（可直接使用）
    SESSION_ID_RE,           # UUID4正则
    CONTROL_CHAR_RE,         # 控制字符正则
)
```

### 异常类型选择规则

| 调用场景 | 参数设置 | 抛出异常 |
|---------|---------|---------|
| Tool 内部 | `validate_lang(lang)` (默认) | `ToolError` |
| Tool 内部 | `validate_process_id(pid)` (默认) | `ValueError` |
| Resource 内部 | `validate_process_id(pid, resource=True)` | `ResourceError` |
| Prompt 内部 | `validate_lang(lang, tool=False)` | `ValueError` |

---

## 10. Gateway 使用模式

### 标准模式（推荐）

```python
conn = get_shared_connection()
resp = get_shared_gateway().execute(
    "tool_name",          # 工具名称（用于审计日志）
    actual_function,       # 实际执行的函数
    conn=conn,            # 参数透传
    param1=value1,
)
# resp.result       → 函数返回值
# resp.session_id   → UUID4
# resp.response_ms  → 执行时间
# resp.provenance_chain → [] (需要 Tool 层填充)
```

### 闭包模式（适合多步骤逻辑）

```python
def _complex_logic():
    process = get_process(conn, pid)
    if not process:
        raise ToolError(f"Not found: {pid}")
    kpis = get_kpis_for_process(conn, pid)
    return {"process": process, "kpis": kpis}

resp = get_shared_gateway().execute("tool_name", _complex_logic)
```

---

## 11. 测试编写指南

### 11.1 Fixtures

```python
# conftest.py 提供的常用 fixtures
@pytest.fixture
def conn(tmp_path):
    """提供带完整 schema 的临时 SQLite 连接。"""
    ...

@pytest.fixture
def conn_with_data(conn):
    """带测试数据的连接。"""
    ...
```

### 11.2 测试结构

```
tests/
├── test_tools/        # 对应 src/oprocess/tools/
├── test_governance/   # 对应 src/oprocess/governance/
├── test_db/           # 对应 src/oprocess/db/
├── test_config.py     # 对应 config.py
├── test_auth.py       # 对应 auth.py
└── test_rate_limit.py # 对应 rate_limit.py
```

### 11.3 测试命名约定

```python
class TestMyFunction:
    def test_valid_input(self):      # 正常路径
        ...
    def test_invalid_input(self):    # 异常路径
        ...
    def test_edge_case(self):        # 边界条件
        ...
    def test_not_found(self):        # 资源不存在
        ...
```

---

## 12. Git 约定

```bash
# 分支命名
feature/<name>    # 新功能
fix/<name>        # Bug 修复
docs/<name>       # 文档

# 提交消息格式 (Conventional Commits)
feat(tools): add search_process
fix(gateway): correct session_id generation
docs(wiki): add architecture document
refactor(validators): consolidate regex patterns
test(audit): add boundary response tests

# 每次改动控制在 < 100 行，可测试增量
```

---

## 13. 文件行数速查

> 所有文件均符合 300 行质量门禁。

| 文件 | 行数 | 职责 |
|------|------|------|
| server.py | 131 | FastMCP 入口 |
| gateway.py | 149 | Gateway + ToolResponse |
| config.py | 51 | 配置 |
| validators.py | 88 | 验证 |
| auth.py | 140 | 认证 |
| prompts.py | 105 | Prompt 模板 |
| registry.py | 238 | 6 个 Tool |
| search.py | 114 | 2 个 Tool |
| helpers.py | 190 | 辅助函数 |
| export.py | 141 | Markdown 导出 |
| serialization.py | 27 | JSON 序列化 |
| _types.py | 29 | 类型别名 |
| rate_limit.py | 73 | 速率限制 |
| connection.py | 199 | 数据库连接 |
| queries.py | 203 | SQL 查询 |
| vector_search.py | 86 | 向量搜索 |
| embedder.py | 66 | Embedding |
| row_utils.py | 17 | 行转换 |
| audit.py | 92 | 审计日志 |
| boundary.py | 74 | 边界响应 |
| provenance.py | 68 | 溯源链 |

---

## 14. 常见调试场景

### 向量搜索不工作

```bash
# 检查 1: sqlite-vec 是否安装
python -c "import sqlite_vec; print(sqlite_vec)"

# 检查 2: 环境变量
echo $GOOGLE_API_KEY

# 检查 3: 启用 DEBUG 日志
LOG_LEVEL=DEBUG uv run python -m oprocess

# 预期日志:
# "Vector search failed, falling back to LIKE"  → embedder 有问题
# "Failed to load sqlite-vec"                    → 扩展加载失败
# "sqlite-vec unavailable"                       → 虚拟表创建失败
```

### 审计日志未写入

```bash
# 检查 pyproject.toml
[tool.oprocess]
audit_log_enabled = true   # 必须为 true

# 检查日志
LOG_LEVEL=WARNING uv run python -m oprocess
# 预期: "Audit log write failed" 如果有问题
```

### 认证失败（HTTP 模式）

```bash
# 设置 API Key
export OPROCESS_API_KEY=your-secret

# 测试请求
curl -H "Authorization: Bearer your-secret" http://localhost:8000/...
```
