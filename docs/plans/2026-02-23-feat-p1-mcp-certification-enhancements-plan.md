---
title: "feat: P1 MCP Certification Enhancements — 实施计划"
type: feat
status: active
date: 2026-02-23
origin: docs/plans/2026-02-23-feat-mcp-certification-upgrade-plan.md
---

# P1 MCP Certification Enhancements — 实施计划

## Overview

基于 MCP 认证升级评估的 P1 阶段（认证加分项），实施 4 项改进：
1. 多传输支持（stdio + SSE + streamable-http）
2. 简化搜索为 LIKE-only（移除失效的 TF-IDF 向量搜索）
3. 数据库连接单例管理（消除重复 `_get_conn()`）
4. 健康检查 `ping` Tool

**技术栈确认**：FastMCP 3.0.2，`mcp.run(transport=...)` 支持 `"stdio"` / `"sse"` / `"streamable-http"` / `"http"`

## 关键技术决策

### Transport 参数传递

FastMCP 3.0.2 的 `mcp.run()` 已内置 transport 参数支持：
```python
mcp.run(transport="stdio")           # 默认
mcp.run(transport="sse", host="0.0.0.0", port=8000)
mcp.run(transport="streamable-http", host="0.0.0.0", port=8000)
```

**不需要手动解析 `sys.argv`**。使用 `argparse` 传递 transport 参数到 `mcp.run()`。

### 搜索简化：移除 TF-IDF，LIKE 全面接管

当前 `_embed_query_tfidf` 使用 `query.lower().split()` 分词——中文完全无效（无空格分隔）。
LIKE 搜索已经是实际在用的路径。移除 vector_search 分支使代码更简单、行为更可预测。

**不删除 `vector_search.py` 文件**——保留用于未来 OpenAI embedding 升级。
只修改 `search_processes()` 使其始终走 LIKE 路径。

### 连接单例：模块级全局 + atexit

使用 `connection.py` 中的模块级单例。`atexit.register` 确保进程退出时关闭。
测试 fixtures 继续使用独立 `tmp_path` 连接，不受影响。

## 实施步骤

### Phase 1: 搜索简化（P1.2）— `queries.py`

**文件**: `src/oprocess/db/queries.py`

1. 移除 `from oprocess.db.vector_search import ...` 导入
2. 移除 `has_embeddings` 分支判断
3. `search_processes()` 始终执行 LIKE 搜索
4. LIKE 结果不含 `score` 字段（与当前 LIKE fallback 一致）

**改动前**（L56-91）：
```python
def search_processes(conn, query, lang="zh", limit=10, level=None):
    from oprocess.db.vector_search import has_embeddings, vector_search
    if has_embeddings(conn):
        return vector_search(conn, query, ...)
    # Fallback: SQL LIKE
    validate_lang(lang)
    ...
```

**改动后**：
```python
def search_processes(conn, query, lang="zh", limit=10, level=None):
    """Search processes by text matching (SQL LIKE)."""
    validate_lang(lang)
    col = f"name_{lang}"
    desc_col = f"description_{lang}"
    pattern = f"%{query}%"
    ...
```

**测试影响**:
- `tests/test_tools/test_vector_search.py` 保留不变（vector_search 模块仍存在）
- `tests/test_quality_gates.py` 保留不变（已使用 LIKE 路径测试）
- 更新 `test_queries.py` 中依赖 vector search 的测试（如有）
- 确认 `populated_db_with_embeddings` fixture 不影响搜索结果

### Phase 2: 连接单例（P1.3）— `connection.py` + `registry.py` + `resources.py`

**文件**: `src/oprocess/db/connection.py`

新增 `get_shared_connection()` 单例函数：

```python
import atexit

_shared_conn: sqlite3.Connection | None = None

def get_shared_connection(db_path: Path | None = None) -> sqlite3.Connection:
    """Get or create shared SQLite connection (singleton for process lifetime)."""
    global _shared_conn
    if _shared_conn is not None:
        return _shared_conn
    _shared_conn = get_connection(db_path)
    init_schema(_shared_conn)
    atexit.register(_close_shared)
    return _shared_conn

def _close_shared() -> None:
    global _shared_conn
    if _shared_conn is not None:
        _shared_conn.close()
        _shared_conn = None
```

**文件**: `src/oprocess/tools/registry.py`

1. 删除 `DB_PATH`、`_get_conn()` 定义
2. 导入 `from oprocess.db.connection import get_shared_connection`
3. 所有 `conn = _get_conn()` → `conn = get_shared_connection()`
4. 删除所有 `conn.close()` 调用

**文件**: `src/oprocess/tools/resources.py`

同上：删除 `DB_PATH`、`_get_conn()`，使用 `get_shared_connection()`，删除 `conn.close()`。

**测试影响**:
- 测试使用 `db_conn` / `populated_db` fixtures（tmp_path 独立连接），不受影响
- 新增 `test_shared_connection_singleton` 测试

### Phase 3: 多传输支持（P1.1）— `server.py` + `__main__.py`

**文件**: `src/oprocess/server.py`

```python
if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="O'Process MCP Server")
    parser.add_argument(
        "--transport", default="stdio",
        choices=["stdio", "sse", "streamable-http"],
        help="Transport protocol (default: stdio)",
    )
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()

    kwargs = {}
    if args.transport != "stdio":
        kwargs["host"] = args.host
        kwargs["port"] = args.port
    mcp.run(transport=args.transport, **kwargs)
```

**文件**: `src/oprocess/__main__.py`

```python
"""Allow running as: python -m oprocess.server"""
import argparse
from oprocess.server import mcp

parser = argparse.ArgumentParser(description="O'Process MCP Server")
parser.add_argument(
    "--transport", default="stdio",
    choices=["stdio", "sse", "streamable-http"],
)
parser.add_argument("--host", default="0.0.0.0")
parser.add_argument("--port", type=int, default=8000)
args = parser.parse_args()

kwargs = {}
if args.transport != "stdio":
    kwargs["host"] = args.host
    kwargs["port"] = args.port
mcp.run(transport=args.transport, **kwargs)
```

**验收标准**:
- [ ] `python -m oprocess.server` → stdio 模式正常
- [ ] `python -m oprocess.server --transport=sse` → HTTP 端口启动
- [ ] `python -m oprocess.server --transport=streamable-http --port=9000` → 自定义端口

### Phase 4: ping Tool（P1.4）— `registry.py`

**文件**: `src/oprocess/tools/registry.py`

在 `register_tools()` 末尾新增：

```python
@mcp.tool()
def ping() -> str:
    """Health check — returns server status and version."""
    conn = get_shared_connection()
    try:
        process_count = count_processes(conn)
        kpi_count = count_kpis(conn)
        return json.dumps({
            "status": "ok",
            "version": "0.1.0",
            "processes": process_count,
            "kpis": kpi_count,
        }, ensure_ascii=False)
    except Exception as exc:
        return json.dumps({
            "status": "error",
            "message": str(exc),
        })
```

**测试**: 新增到 `tests/test_tools/test_queries.py` 或新建 `tests/test_tools/test_ping.py`

**文件**: `tests/test_quality_gates.py`

更新 `test_all_tools_registered` 的 `expected` 集合添加 `"ping"`。

### Phase 5: README + 验证

**文件**: `README.md`

1. Tools 表更新为 8 个（增加 `ping`）
2. Quick Start 增加 SSE 启动方式
3. Claude Desktop 配置保持不变（stdio）

**验证命令**:

```bash
ruff check .                    # lint 零 error
pytest                          # 所有测试通过
uv run python -c "
import asyncio, json
from oprocess.server import mcp
tools = asyncio.run(mcp.list_tools())
print(f'Tools: {len(tools)}')
for t in tools:
    print(f'  {t.name}')
"                               # 8 个 Tool
```

## 文件改动清单

| 文件 | 操作 | 预计行变化 |
|------|------|-----------:|
| `src/oprocess/db/queries.py` | 修改 | -8 |
| `src/oprocess/db/connection.py` | 修改 | +20 |
| `src/oprocess/tools/registry.py` | 修改 | +15 / -10 |
| `src/oprocess/tools/resources.py` | 修改 | +3 / -12 |
| `src/oprocess/server.py` | 修改 | +12 |
| `src/oprocess/__main__.py` | 修改 | +10 |
| `README.md` | 修改 | +8 |
| `tests/test_quality_gates.py` | 修改 | +1 |
| `tests/test_tools/test_connection.py` | 新建 | +25 |

## Acceptance Criteria

- [ ] `search_processes()` 始终使用 LIKE 搜索，无 vector_search 分支
- [ ] `get_shared_connection()` 单例模式，连续调用返回同一连接
- [ ] `_get_conn()` 和 `DB_PATH` 从 registry.py / resources.py 中移除
- [ ] `--transport=sse` 正常启动 HTTP 服务
- [ ] `ping` tool 返回 `{"status": "ok", ...}`
- [ ] `test_all_tools_registered` 验证 8 个 Tool
- [ ] README 更新 8 工具表和 SSE 启动方式
- [ ] `ruff check . && pytest` 全通过

## 执行顺序

```
P1.2 (LIKE 简化) → P1.3 (连接单例) → P1.1 (多传输) → P1.4 (ping) → P1.5 (README + 验证)
```

P1.2 先做是因为移除 vector_search 分支后 queries.py 更简单，后续改动更安全。
P1.3 在 P1.1 之前，因为连接管理是 registry/resources 的基础设施。

## Sources

- **Origin**: [docs/plans/2026-02-23-feat-mcp-certification-upgrade-plan.md](docs/plans/2026-02-23-feat-mcp-certification-upgrade-plan.md) §P1
- **FastMCP 3.0.2**: `mcp.run(transport=...)` 支持 stdio/sse/streamable-http/http
- **实测**: `inspect.signature(FastMCP.run)` 验证
