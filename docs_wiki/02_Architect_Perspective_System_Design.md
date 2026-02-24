# O'Process MCP Server — 架构师视角：系统设计文档

> **版本**: 0.3.0 | **最后更新**: 2026-02-25 | **数据来源**: 源码实际实现

---

## 1. 系统架构概览

```
┌───────────────────────────────────────────────────────────────┐
│                     MCP Client (LLM)                          │
└──────────────────────────┬────────────────────────────────────┘
                           │ MCP Protocol
                           ▼
┌───────────────────────────────────────────────────────────────┐
│                   FastMCP Server Layer                         │
│  ┌──────────────┐  ┌──────────────┐  ┌────────────────────┐  │
│  │ 8 Tools      │  │ 6 Resources  │  │ 3 Prompts          │  │
│  │ (registry.py │  │ (resources.  │  │ (prompts.py)       │  │
│  │  search.py)  │  │  py)         │  │                    │  │
│  └──────┬───────┘  └──────┬───────┘  └────────────────────┘  │
│         │                 │                                   │
│  ┌──────▼─────────────────▼───────────────────────────────┐  │
│  │        RateLimitMiddleware (rate_limit.py)              │  │
│  └────────────────────────┬───────────────────────────────┘  │
│  ┌────────────────────────▼───────────────────────────────┐  │
│  │    BearerAuthMiddleware (auth.py) — HTTP only          │  │
│  └────────────────────────────────────────────────────────┘  │
└──────────────────────────┬────────────────────────────────────┘
                           │
           ┌───────────────┼───────────────┐
           ▼               ▼               ▼
┌─────────────────┐ ┌────────────┐ ┌──────────────────┐
│ ToolGateway     │ │ Governance │ │ Database Layer   │
│ Interface       │ │ Lite       │ │                  │
│ (gateway.py)    │ │            │ │ ┌──────────────┐ │
│                 │ │ ┌────────┐ │ │ │ connection.  │ │
│ ┌─────────────┐ │ │ │ Audit  │ │ │ │ py (SQLite)  │ │
│ │Passthrough  │ │ │ │ Log    │ │ │ └──────────────┘ │
│ │Gateway      │─┼─┤ └────────┘ │ │ ┌──────────────┐ │
│ │(singleton)  │ │ │ ┌────────┐ │ │ │ queries.py   │ │
│ └─────────────┘ │ │ │Boundary│ │ │ └──────────────┘ │
│                 │ │ │Response│ │ │ ┌──────────────┐ │
│ ToolResponse    │ │ └────────┘ │ │ │vector_search │ │
│ {result,        │ │ ┌────────┐ │ │ │.py           │ │
│  provenance,    │ │ │Proven- │ │ │ └──────────────┘ │
│  session_id,    │ │ │ance   │ │ │ ┌──────────────┐ │
│  response_ms}   │ │ │Chain   │ │ │ │ embedder.py  │ │
│                 │ │ └────────┘ │ │ │ (Gemini API) │ │
└─────────────────┘ └────────────┘ │ └──────────────┘ │
                                   └──────────────────┘
```

---

## 2. 模块职责与依赖关系

### 2.1 入口层

| 文件 | 行数 | 职责 |
|------|------|------|
| `__init__.py` | 3 | 版本号唯一来源 (`__version__ = "0.3.0"`) |
| `__main__.py` | 5 | `python -m oprocess` 入口 → `server.main()` |
| `server.py` | 131 | FastMCP 实例创建、注册 tools/resources/prompts、CLI 参数解析、传输模式选择 |

**server.py 初始化序列**：
```
_configure_logging()
 → mcp = FastMCP("O'Process", version=oprocess.__version__)
 → mcp.add_middleware(RateLimitMiddleware)
 → register_tools(mcp)      # registry.py + search.py
 → register_resources(mcp)  # resources.py
 → register_prompts(mcp)    # prompts.py
 → main() → argparse → mcp.run(transport=...)
```

### 2.2 工具层（tools/）

| 文件 | 行数 | 职责 |
|------|------|------|
| `registry.py` | 238 | 注册 6 个非搜索 Tool + 导入 search tools |
| `search.py` | 114 | 注册 2 个搜索 Tool（search_process, map_role_to_processes） |
| `helpers.py` | 190 | 共享辅助函数：boundary 处理、provenance 构建、compare、markdown 转换 |
| `export.py` | 141 | 岗位说明书 Markdown 导出 + 溯源附录 |
| `serialization.py` | 27 | `to_json()` / `response_to_json()` 序列化 |
| `_types.py` | 29 | Pydantic Annotated 类型别名（Lang, ProcessId, ProcessIdList） |
| `rate_limit.py` | 73 | FastMCP Middleware：滑动窗口速率限制 |

**文件拆分策略**：registry.py + search.py 拆分是为了满足 300 行质量门禁。`_types.py` 独立是为了避免 registry.py ↔ search.py 的循环导入。

### 2.3 数据库层（db/）

| 文件 | 行数 | 职责 |
|------|------|------|
| `connection.py` | 199 | 连接管理、Schema DDL、sqlite-vec 加载、迁移 |
| `queries.py` | 203 | 所有 SQL 查询函数（CRUD + 搜索 + 路径构建） |
| `vector_search.py` | 86 | sqlite-vec 最近邻搜索 + N+1 消除 |
| `embedder.py` | 66 | EmbedProvider Protocol + GeminiEmbedder 实现 |
| `row_utils.py` | 17 | `row_to_process()` 行转换器（JSON 字段解析） |

### 2.4 治理层（governance/）

| 文件 | 行数 | 职责 |
|------|------|------|
| `audit.py` | 92 | SessionAuditLog：追加写入 + 会话查询 |
| `boundary.py` | 74 | BoundaryResponse：低置信度结构化降级 |
| `provenance.py` | 68 | ProvenanceChain + ProvenanceNode dataclass |

### 2.5 横切关注点

| 文件 | 行数 | 职责 |
|------|------|------|
| `config.py` | 51 | pyproject.toml `[tool.oprocess]` 配置解析（singleton） |
| `validators.py` | 88 | 集中式验证：正则、语言、session_id、role_name 安全过滤 |
| `auth.py` | 140 | ASGI 中间件：Bearer Token + Origin 校验 |

---

## 3. 核心设计模式

### 3.1 Gateway 模式

所有 Tool 调用必须经过 `ToolGatewayInterface`，实现关注点分离：

```python
# gateway.py
class PassthroughGateway(ToolGatewayInterface):
    def execute(self, tool_name, func, **kwargs) -> ToolResponse:
        start = time.monotonic()
        result = func(**kwargs)       # 实际执行
        elapsed_ms = ...              # 计时
        log_invocation(...)           # 审计（可选）
        return ToolResponse(result, session_id, response_ms)
```

**单例模式**：`get_shared_gateway()` 返回进程级 singleton，确保同一 session 内所有 Tool 共享 session_id。

**审计开关**：根据 `config.audit_log_enabled` 决定是否传入 `audit_conn`。当 `audit_conn=None` 时跳过审计。

### 3.2 ToolResponse 信封

```python
@dataclass
class ToolResponse:
    result: Any                        # 实际返回数据
    provenance_chain: list[dict] = []  # 溯源链（Tool 层填充）
    session_id: str = ""               # UUID4 会话标识
    response_ms: int = 0               # 执行耗时（ms）
```

Gateway 负责 `result` + `session_id` + `response_ms`，Tool 实现层负责 `provenance_chain`。

### 3.3 搜索降级链

```
用户查询
  → 检查 Embedder 是否可用（GOOGLE_API_KEY / GEMINI_API_KEY）
    → 检查 vec_processes 虚拟表是否有数据
      → 向量搜索（sqlite-vec nearest-neighbor）
        → 成功且有结果 → 返回带 score 的结果
        → 失败 → 降级到 LIKE
    → 无向量数据 → 降级到 LIKE
  → 无 Embedder → 降级到 LIKE

LIKE 回退:
  SELECT * FROM processes
  WHERE name_{lang} LIKE ? OR description_{lang} LIKE ?
  ORDER BY level, id LIMIT ?
```

### 3.4 N+1 查询消除

| 位置 | 方案 |
|------|------|
| `vector_search.py` | 向量搜索结果通过 `SELECT * WHERE id IN (...)` 批量获取 process 详情 |
| `helpers.py:build_search_provenance()` | 使用 `build_path_strings_batch()` 批量构建祖先路径 |
| `helpers.py:compare_process_nodes()` | 使用 `build_path_strings_batch()` 一次获取所有路径 |
| `export.py:_build_single_doc()` | 使用 `build_path_strings_batch()` 构建溯源附录路径 |

`build_path_strings_batch` 实现原理：遍历每个 ID 的祖先链时，将沿途所有中间节点缓存，后续共享相同祖先的 ID 无需重复查询。

### 3.5 Embedding Provider Protocol

```python
@runtime_checkable
class EmbedProvider(Protocol):
    @property
    def dim(self) -> int: ...
    def embed(self, texts: list[str]) -> list[list[float]]: ...
```

当前唯一实现：`GeminiEmbedder`（gemini-embedding-001, 768 维）。Protocol 设计使未来可扩展其他 embedding 模型。懒加载：仅在首次搜索时初始化，且使用模块级 singleton 缓存。

---

## 4. 数据库设计

### 4.1 Schema（5 个物理表 + 1 个虚拟表）

```sql
-- 核心数据表
processes         -- 2325 行：流程节点（5 级树形、双语、标签）
kpis              -- 3910 行：KPI 指标（关联 process_id）
process_embeddings -- 预计算 Gemini 768 维向量
role_mappings      -- 预留缓存表（当前未使用）

-- 虚拟表
vec_processes     -- sqlite-vec ANN 索引

-- 治理表
session_audit_log  -- Append-only 审计日志

-- 约束
FOREIGN KEY (parent_id) → processes(id)
FOREIGN KEY (process_id) → processes(id) / kpis(id) / process_embeddings(id)
TRIGGER no_update_audit: 禁止 UPDATE
TRIGGER no_delete_audit: 禁止 DELETE
UNIQUE INDEX idx_audit_request_id: 幂等写入
```

### 4.2 索引策略

| 索引 | 表 | 用途 |
|------|----|------|
| `idx_processes_parent` | processes | 子节点查询 |
| `idx_processes_level` | processes | 按层级筛选 |
| `idx_processes_domain` | processes | 按领域筛选 |
| `idx_kpis_process` | kpis | KPI 关联查询 |
| `idx_audit_session` | session_audit_log | 会话日志检索 |
| `idx_audit_timestamp` | session_audit_log | 时间范围查询 |
| `idx_audit_request_id` | session_audit_log | 幂等去重（唯一、部分索引） |

### 4.3 SQLite 配置

```python
conn.execute("PRAGMA journal_mode=WAL")    # 写前日志，支持并发读
conn.execute("PRAGMA foreign_keys=ON")     # 启用外键约束
conn.row_factory = sqlite3.Row             # 结果行可按列名访问
```

### 4.4 迁移管理

采用代码内迁移（in-code migration），在 `init_schema()` 中按顺序执行：

1. `SCHEMA_SQL` — CREATE TABLE IF NOT EXISTS（幂等）
2. `_create_vec_table()` — 创建 sqlite-vec 虚拟表（异常安全）
3. `_migrate_audit_request_id()` — v0.2.0 迁移：添加 request_id 列 + 唯一索引

---

## 5. 安全设计

### 5.1 认证与授权

| 层面 | 实现 | 文件 |
|------|------|------|
| Bearer Token | `OPROCESS_API_KEY` 环境变量 | auth.py |
| 时序攻击防护 | `hmac.compare_digest()` | auth.py:46 |
| Origin 验证 | `OPROCESS_ALLOWED_ORIGINS` 环境变量 | auth.py:28-33 |
| stdio 免认证 | HTTP 模式才加载 BearerAuthMiddleware | server.py:121-125 |

### 5.2 输入验证

| 验证项 | 实现 | 位置 |
|--------|------|------|
| process_id 格式 | 正则 `^\d+(\.\d+)*$` | validators.py:15 |
| session_id 格式 | UUID4 正则 | validators.py:17-20 |
| lang 枚举 | frozenset{"zh", "en"} | validators.py:23 |
| role_name 安全 | 去除控制字符 + 折叠空白 + 100 字符限制 | validators.py:74-87 |
| SQL 注入防护 | 全部参数化查询 | queries.py 全文件 |
| LIKE 通配符转义 | `_escape_like()` 转义 `%`, `_`, `\` | queries.py:92-94 |
| Pydantic Field | min_length / max_length / pattern / ge / le | _types.py, registry.py, search.py |

### 5.3 速率限制

```python
class RateLimitMiddleware(Middleware):
    # 滑动窗口：per-client 追踪
    # 默认: 60 calls / 60 seconds
    # 超限时抛出 McpError (code=-32000)
    # client_id 从 FastMCP context 获取
```

### 5.4 审计安全

- Append-Only 触发器保护：数据库层禁止 UPDATE / DELETE
- SHA256 输入哈希（截断 16 位）：记录调用参数指纹，不存储明文
- sqlite3.Connection 对象从审计序列化中排除

---

## 6. 错误处理策略

| 层面 | 错误类型 | 处理策略 |
|------|---------|---------|
| Tool 验证失败 | `ToolError` (fastmcp) | MCP 协议错误响应 |
| Resource 验证失败 | `ResourceError` (fastmcp) | MCP 协议错误响应 |
| Prompt 验证失败 | `ValueError` | FastMCP 框架捕获 |
| 速率限制 | `McpError` (code=-32000) | MCP 协议错误响应 |
| 审计写入失败 | `Exception` → `logger.warning` | 静默降级，不影响主流程 |
| sqlite-vec 不可用 | `Exception` → `logger.debug` | 降级到 LIKE 搜索 |
| Embedder 初始化失败 | `Exception` → `logger.warning` | 返回 None，降级到 LIKE |
| 配置解析失败 | `Exception` → `logger.warning` | 使用默认配置 |

**设计原则**：主流程使用明确异常类型；辅助功能（审计、向量）采用静默降级。

---

## 7. 连接与生命周期管理

### 7.1 Singleton 模式

| 组件 | Singleton 工厂 | 作用域 |
|------|----------------|--------|
| SQLite Connection | `get_shared_connection()` | 进程级 |
| Gateway | `get_shared_gateway()` | 进程级 |
| Config | `get_config()` → `_config` | 模块级 |
| Embedder | `_get_embedder()` | 模块级 |

### 7.2 进程关闭

```python
# connection.py
atexit.register(_close_shared)  # 进程退出时安全关闭 SQLite 连接
```

---

## 8. 依赖图

```
pyproject.toml 依赖:
├── fastmcp >= 2.0        # MCP 框架
├── sqlite-vec >= 0.1.6   # 向量搜索扩展
└── [optional] google-genai >= 1.0  # Gemini embedding

运行时内部依赖图:
server.py
├── config.py
├── tools/registry.py
│   ├── tools/search.py
│   │   ├── tools/_types.py
│   │   └── tools/helpers.py
│   ├── tools/_types.py
│   ├── tools/helpers.py
│   └── tools/export.py
├── tools/resources.py
│   └── validators.py
├── prompts.py
│   └── validators.py
├── tools/rate_limit.py
├── gateway.py
│   └── governance/audit.py
│       └── validators.py
├── db/connection.py
│   └── db/embedder.py
├── db/queries.py
│   ├── db/embedder.py
│   ├── db/row_utils.py
│   └── db/vector_search.py
├── governance/boundary.py
│   └── config.py
└── governance/provenance.py
```

---

## 9. 性能设计

### 9.1 查询优化

| 策略 | 位置 | 效果 |
|------|------|------|
| sqlite-vec JOIN 消除 N+1 | vector_search.py:58-64 | 向量搜索后一次性获取所有 process 详情 |
| build_path_strings_batch 缓存 | queries.py:168-185 | 批量构建祖先路径，共享中间结果 |
| WAL 模式 | connection.py:24 | 允许并发读 |
| 预计算 embedding | process_embeddings 表 | 避免运行时调用 Gemini API |
| 模块级 Embedder singleton | queries.py:16-17 | 避免重复初始化 |

### 9.2 质量门禁

| 指标 | 要求 |
|------|------|
| P50 响应时间 | < 100ms（本地 stdio） |
| P95 响应时间 | < 300ms（本地 stdio） |
| 语义搜索 Top-3 准确率 | >= 85%（50 个标注查询集） |

---

## 10. 可扩展性设计

| 扩展点 | 当前实现 | 扩展路径 |
|--------|---------|---------|
| Embedding 模型 | Gemini-001 (768-dim) | 实现 `EmbedProvider` Protocol |
| 传输协议 | stdio / SSE / streamable-http | FastMCP 支持的所有协议 |
| 角色缓存 | role_mappings 表（预留） | 从实时搜索切换到缓存查询 |
| 配置来源 | pyproject.toml | 扩展为环境变量或外部配置 |
| 多语言 | zh / en | 扩展 `_VALID_LANGS` + 数据列 |
