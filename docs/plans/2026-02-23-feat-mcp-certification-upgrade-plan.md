---
title: "feat: MCP Certification Upgrade — Anthropic 认证插件标准对齐"
type: feat
status: active
date: 2026-02-23
origin: MCP 技术评估（2026-02-23，Phase 6 完成后）
---

# MCP Certification Upgrade — Anthropic 认证插件标准对齐

## 评估总结

| 维度 | 当前得分 | 目标 | 主要差距 |
|------|---------|------|----------|
| 协议合规性 | 6/10 | 9/10 | 无 Pydantic schema、error dict 代替 ToolError |
| Tool 设计质量 | 7/10 | 9/10 | 输入约束缺失、lang 未白名单化 |
| 安全态势 | 4/10 | 8/10 | 无认证、SQL 动态列名、无速率限制 |
| 性能就绪度 | 5/10 | 8/10 | 向量搜索失效、无连接池、全表扫描 |
| 文档完整度 | 3/10 | 9/10 | README 空白、无 API 文档 |
| 测试质量 | 8/10 | 9/10 | 已基本达标，补充边界测试 |
| **加权总分** | **5.5/10** | **8.5/10** | |

**代码规模**: 1,664 行源码（14 模块）、125 测试、6 benchmark

---

## P0：认证阻塞项（必须修复）

预计工时：1-2 天

### 0.1 Pydantic 输入模型 — 7 个 Tool 全部适配

**问题**: 所有 Tool 依赖 FastMCP 从函数签名自动推断 schema，无显式 `inputSchema`，缺少 `description`/`enum`/`minLength`/`maximum` 等约束。LLM 可能传入无效参数。

**涉及文件**:
- `src/oprocess/tools/registry.py:58-293` — 7 个 `@mcp.tool()` 函数

**修改方案**:

新建 `src/oprocess/tools/schemas.py`（~80 行），定义 7 个 Pydantic 输入模型：

```python
"""Pydantic input schemas for MCP tools — provides explicit JSON Schema."""

from __future__ import annotations

from pydantic import BaseModel, Field


class SearchProcessInput(BaseModel):
    """搜索流程节点。"""
    query: str = Field(
        ..., min_length=1, max_length=500,
        description="搜索关键词（中文或英文）",
    )
    lang: str = Field(
        "zh", pattern=r"^(zh|en)$",
        description="搜索语言代码",
    )
    limit: int = Field(
        10, ge=1, le=50,
        description="最大返回数量",
    )
    level: int | None = Field(
        None, ge=1, le=5,
        description="按流程层级过滤（1-5）",
    )


class GetProcessTreeInput(BaseModel):
    """获取流程节点子树。"""
    process_id: str = Field(
        ..., pattern=r"^\d+(\.\d+)*$",
        description="流程节点 ID（如 '1.0', '8.5.3'）",
    )
    max_depth: int = Field(
        4, ge=1, le=5,
        description="子树最大深度",
    )


class GetKpiSuggestionsInput(BaseModel):
    """获取 KPI 建议。"""
    process_id: str = Field(
        ..., pattern=r"^\d+(\.\d+)*$",
        description="流程节点 ID",
    )


class CompareProcessesInput(BaseModel):
    """对比多个流程节点。"""
    process_ids: str = Field(
        ..., pattern=r"^\d+(\.\d+)*(,\s*\d+(\.\d+)*)+$",
        description="逗号分隔的流程 ID（如 '1.0,8.0,4.0'）",
    )


class GetResponsibilitiesInput(BaseModel):
    """生成岗位职责描述。"""
    process_id: str = Field(
        ..., pattern=r"^\d+(\.\d+)*$",
        description="流程节点 ID",
    )
    lang: str = Field("zh", pattern=r"^(zh|en)$", description="语言代码")
    output_format: str = Field(
        "json", pattern=r"^(json|markdown)$",
        description="输出格式",
    )


class MapRoleInput(BaseModel):
    """岗位到流程映射。"""
    role_description: str = Field(
        ..., min_length=1, max_length=500,
        description="岗位描述或角色名称",
    )
    lang: str = Field("zh", pattern=r"^(zh|en)$", description="语言代码")
    limit: int = Field(10, ge=1, le=50, description="最大匹配数量")
    industry: str | None = Field(
        None, max_length=100,
        description="行业标签过滤（如 'manufacturing'）",
    )


class ExportDocInput(BaseModel):
    """导出岗位说明书。"""
    process_ids: str = Field(
        ..., pattern=r"^\d+(\.\d+)*(,\s*\d+(\.\d+)*)*$",
        description="逗号分隔的流程 ID",
    )
    lang: str = Field("zh", pattern=r"^(zh|en)$", description="语言代码")
    role_name: str | None = Field(
        None, max_length=100,
        description="岗位名称（用于文档标题）",
    )
```

**registry.py 改造方式**:

```python
from oprocess.tools.schemas import SearchProcessInput

@mcp.tool()
def search_process(input: SearchProcessInput) -> str:
    """Search processes by keyword. Returns matching process nodes."""
    conn = _get_conn()
    resp = _gateway.execute(
        "search_process",
        search_processes,
        conn=conn,
        query=input.query,
        lang=input.lang,
        limit=input.limit,
        level=input.level,
    )
    # ... rest unchanged
```

**验收标准**:
- [ ] 7 个 Tool 全部使用 Pydantic 输入模型
- [ ] `asyncio.run(mcp.list_tools())` 每个 tool 的 `inputSchema` 包含完整字段定义
- [ ] 无效输入（lang="french"、limit=-1）返回 422 Validation Error
- [ ] 现有 125 个测试全部通过

---

### 0.2 ToolError 替换 error dict

**问题**: 错误以 `{"error": "..."}` 返回（HTTP 200），MCP 客户端无法区分「工具成功但无结果」和「工具执行失败」。

**涉及文件**:
- `src/oprocess/tools/registry.py:127` — `get_kpi_suggestions` 的 `{"error": ...}`
- `src/oprocess/tools/registry.py:185` — `get_responsibilities` 的 `{"error": ...}`
- `src/oprocess/tools/helpers.py:97` — `compare_process_nodes` 的 `{"error": ...}`
- `src/oprocess/tools/resources.py:56` — `get_process_resource` 的 `{"error": ...}`

**修改方案**:

```python
from mcp.server.fastmcp import ToolError

# registry.py — get_kpi_suggestions 内部
if not process:
    raise ToolError(f"Process {process_id} not found")

# helpers.py — compare_process_nodes
if not p:
    raise ToolError(f"Process {pid} not found")

# resources.py — resource 保持返回 JSON（Resource 没有 ToolError 概念）
# 但改用 404 语义明确的 key
if not process:
    return _to_json({"not_found": process_id, "message": "Process not found"})
```

**验收标准**:
- [ ] 所有 Tool 中的 `{"error": ...}` 改为 `raise ToolError(...)`
- [ ] Resource 中保持 JSON 返回（Resource 规范无 ToolError）
- [ ] 现有测试中的 `assert "error" in result` 更新为 `pytest.raises(ToolError)`
- [ ] Gateway 的 audit 日志正确记录 ToolError

---

### 0.3 lang 白名单校验（SQL 安全）

**问题**: `queries.py:67-68` 和 `test_quality_gates.py:50-51` 用 f-string 从 `lang` 构建列名 `name_{lang}`，若 `lang` 非 `zh`/`en` 可导致 SQL 异常或潜在注入。

**涉及文件**:
- `src/oprocess/db/queries.py:67-68` — `search_processes` 中 `f"name_{lang}"`
- `src/oprocess/tools/helpers.py:56,80` — `build_search_provenance`/`build_hierarchy_provenance` 的 `f"name_{lang}"`

**修改方案**:

在 `queries.py` 顶部加入校验工具函数：

```python
_VALID_LANGS = frozenset(("zh", "en"))

def _validate_lang(lang: str) -> str:
    """Validate and return lang, or raise ValueError."""
    if lang not in _VALID_LANGS:
        msg = f"Invalid lang '{lang}', must be 'zh' or 'en'"
        raise ValueError(msg)
    return lang
```

在所有 `f"name_{lang}"` 之前调用 `_validate_lang(lang)`。

有了 P0.1 的 Pydantic `pattern=r"^(zh|en)$"` 后，这是第二道防线（defense-in-depth）。

**验收标准**:
- [ ] `search_processes(conn, "test", lang="fr")` 抛出 `ValueError`
- [ ] `build_search_provenance(conn, [], "xx")` 抛出 `ValueError`
- [ ] 新增 2 个测试验证非法 lang 被拒绝

---

### 0.4 README + Claude Desktop 配置

**问题**: README 为空，无安装/使用文档。MCP 认证要求至少包含：安装指南、Tool 签名表、Resource 列表、Claude Desktop 配置片段。

**新建/修改文件**:
- `README.md` — 完整文档（~200 行）

**内容大纲**:

```markdown
# O'Process — AI-Native Process Classification MCP Server

## Overview
2325 process nodes from APQC PCF 7.4 + ITIL 4 + SCOR 12.0 + AI-era,
with 3910 KPI metrics. Bilingual (zh + en).

## Quick Start
uv sync && uv run python -m oprocess.server

## Claude Desktop Configuration
{
  "mcpServers": {
    "oprocess": {
      "command": "uv",
      "args": ["run", "python", "-m", "oprocess.server"],
      "cwd": "/path/to/oprocess"
    }
  }
}

## Tools (7)
| Tool | Description | Key Parameters |
|------|-------------|----------------|
| search_process | 语义搜索流程节点 | query, lang, limit |
| ... | ... | ... |

## Resources (6)
| URI | Description |
|-----|-------------|
| oprocess://process/{id} | 完整流程节点信息 |
| ... | ... |

## Governance-Lite
- SessionAuditLog: 追加写入审计日志
- BoundaryResponse: 低置信度结构化降级
- ProvenanceChain: 每次调用的推导溯源链

## Development
uv sync --all-extras
ruff check .
pytest
pytest --benchmark-only

## License
```

**验收标准**:
- [ ] README 包含 Claude Desktop JSON 配置片段
- [ ] 7 个 Tool 的签名表（参数、类型、默认值）
- [ ] 6 个 Resource 的 URI 表
- [ ] Quick Start 可复制执行

---

## P1：强烈推荐（认证加分项）

预计工时：3-5 天

### 1.1 多传输支持（stdio + SSE）

**问题**: 仅支持 `mcp.run()` 默认的 stdio 模式，无法适应远程部署场景。

**涉及文件**:
- `src/oprocess/server.py:25-26`

**修改方案**:

```python
if __name__ == "__main__":
    import sys
    transport = "stdio"
    for arg in sys.argv[1:]:
        if arg.startswith("--transport="):
            transport = arg.split("=", 1)[1]
    mcp.run(transport=transport)
```

使用方式：
```bash
uv run python -m oprocess.server                    # stdio (默认)
uv run python -m oprocess.server --transport=sse     # SSE
```

**验收标准**:
- [x] `--transport=stdio` 正常启动
- [x] `--transport=sse` 正常启动（本地 HTTP 端口）
- [x] README 更新两种启动方式

---

### 1.2 修复向量搜索

**问题**: `_embed_query_tfidf` 使用 `query.lower().split()` 分词——中文完全无效（无空格分隔），Recall@3 = 0%。当前靠 LIKE 兜底。

**涉及文件**:
- `src/oprocess/db/vector_search.py:28-37` — `_embed_query_tfidf`

**方案 A（短期，2 小时）**: 移除伪向量，LIKE 全面接管

将 `search_processes()` 改为始终使用 LIKE 搜索，移除 `has_embeddings` 分支判断。`score` 字段设为 `1.0`（精确匹配）。这样 BoundaryResponse 的阈值判定也变得可靠。

```python
# queries.py — search_processes 简化
def search_processes(conn, query, lang="zh", limit=10, level=None):
    """Search processes — SQL LIKE text matching."""
    lang = _validate_lang(lang)
    col, desc_col = f"name_{lang}", f"description_{lang}"
    pattern = f"%{query}%"
    # ... LIKE 查询 ...
    # 每个结果 score = 1.0
```

**方案 B（中期，1-2 天）**: 接入 text-embedding-3-small

- 修改 `scripts/embed.py`，使用 OpenAI API 生成 1536 维 embedding
- 修改 `_embed_query_tfidf` → `_embed_query_openai`，在线查询向量
- 需要 `OPENAI_API_KEY` 环境变量

**方案 C（长期，3-5 天）**: sqlite-vec 原生扩展

- 引入 `sqlite-vec` 扩展，原生 HNSW 索引
- 无需全表扫描，查询复杂度 O(log n)

**建议**: 先执行方案 A（立即可用），P2 阶段执行方案 B/C。

**验收标准**:
- [x] 搜索中文关键词返回正确结果
- [x] BoundaryResponse 阈值判定可靠
- [x] Top-3 Recall ≥ 85%（50 标注查询集）

---

### 1.3 数据库连接管理

**问题**: 每次 Tool/Resource 调用都 `get_connection()` + `init_schema()` 创建新连接。对于 stdio 模式的进程内 SQLite，这是不必要的开销。

**涉及文件**:
- `src/oprocess/tools/registry.py:35-38` — `_get_conn()`
- `src/oprocess/tools/resources.py:35-38` — `_get_conn()`
- `src/oprocess/db/connection.py:11-18` — `get_connection()`

**修改方案**:

在 `connection.py` 中实现模块级单例：

```python
_conn: sqlite3.Connection | None = None

def get_shared_connection(db_path: Path | None = None) -> sqlite3.Connection:
    """Get or create the shared SQLite connection (singleton)."""
    global _conn
    if _conn is not None:
        return _conn
    _conn = get_connection(db_path)
    init_schema(_conn)
    return _conn
```

`registry.py` 和 `resources.py` 改用 `get_shared_connection()`，去掉 `conn.close()` 调用。

**验收标准**:
- [x] 连续调用 10 次 Tool，只创建 1 次连接
- [x] 进程退出时连接正确关闭（atexit hook）
- [x] 现有测试使用 fixture 隔离，不受影响

---

### 1.4 健康检查 ping Tool

**问题**: MCP 认证推荐提供健康检查端点。

**涉及文件**:
- `src/oprocess/tools/registry.py` — 新增 `ping` tool

**修改方案**:

```python
@mcp.tool()
def ping() -> str:
    """Health check — returns server status and version."""
    conn = _get_conn()
    try:
        count = count_processes(conn)
        return json.dumps({
            "status": "ok",
            "version": "0.1.0",
            "processes": count,
        })
    except Exception as exc:
        return json.dumps({"status": "error", "message": str(exc)})
    finally:
        conn.close()
```

**验收标准**:
- [x] `ping` 返回 `{"status": "ok", ...}`
- [x] DB 不可用时返回 `{"status": "error", ...}`
- [x] `test_all_tools_registered` 更新为 8 个 Tool

---

## P2：增强竞争力（差异化优势）

预计工时：1-2 周

### 2.1 结构化日志

**问题**: 无 logging 输出，排障困难。

**修改方案**: 在 `gateway.py` 和 `registry.py` 中加入结构化日志：

```python
import logging
logger = logging.getLogger("oprocess")

# gateway.py execute()
logger.info(
    "tool.execute",
    extra={"tool": tool_name, "session_id": self.session_id, "ms": elapsed_ms},
)
```

**验收标准**:
- [ ] `logging.getLogger("oprocess")` 输出 JSON 格式日志
- [ ] 每次 Tool 调用记录 tool_name、session_id、response_ms
- [ ] 日志级别可通过环境变量 `LOG_LEVEL` 控制

---

### 2.2 审计日志幂等性

**问题**: `log_invocation()` 每次写入新行，MCP 客户端重试时产生重复记录。

**修改方案**: 在 `session_audit_log` 表加入 `request_id` 字段 + UNIQUE 约束：

```sql
ALTER TABLE session_audit_log ADD COLUMN request_id TEXT;
CREATE UNIQUE INDEX IF NOT EXISTS idx_audit_request ON session_audit_log(request_id);
```

`log_invocation()` 新增 `request_id` 参数，使用 `INSERT OR IGNORE`。

**验收标准**:
- [ ] 相同 `request_id` 只写入一次
- [ ] 无 `request_id` 时行为不变（向后兼容）

---

### 2.3 OAuth 2.1 认证（HTTP 传输）

**问题**: HTTP/SSE 传输模式下无任何认证，任何客户端都可调用。

**修改方案**: 实现 Bearer Token 认证中间件：

```python
# src/oprocess/auth.py
import os

def verify_token(token: str) -> bool:
    expected = os.environ.get("OPROCESS_API_KEY")
    if not expected:
        return True  # 未配置则跳过（stdio 模式）
    return token == expected
```

在 SSE 传输时注入认证检查。stdio 模式不受影响。

**验收标准**:
- [ ] `OPROCESS_API_KEY` 设置时，无 token 请求返回 401
- [ ] stdio 模式不受影响
- [ ] README 文档化认证配置

---

### 2.4 sqlite-vec 原生向量索引

**问题**: 当前全表扫描 2325 行 + 纯 Python 余弦计算，P50 ~80ms。

**修改方案**:
- 引入 `sqlite-vec` 扩展
- 创建 HNSW 虚拟表
- 查询复杂度 O(log n)

```sql
CREATE VIRTUAL TABLE vec_processes USING vec0(
    process_id TEXT PRIMARY KEY,
    embedding FLOAT[1536]
);
```

**验收标准**:
- [ ] 向量搜索 P50 < 10ms
- [ ] 精度无回退（Recall@3 ≥ 85%）
- [ ] 回退逻辑：无 sqlite-vec 时降级到 LIKE 搜索

---

## 执行顺序

```
P0.3 (lang 白名单) → P0.1 (Pydantic schema) → P0.2 (ToolError) → P0.4 (README)
    ↓ 认证最低门槛达成
P1.2A (LIKE 全面接管) → P1.3 (连接池) → P1.1 (多传输) → P1.4 (ping)
    ↓ 生产就绪
P2.1 (日志) → P2.2 (幂等性) → P2.3 (OAuth) → P2.4 (sqlite-vec)
```

**关键依赖**:
- P0.1 (Pydantic) 自然包含 lang 校验，但 P0.3 是 defense-in-depth
- P0.2 (ToolError) 需要同步更新测试中的 `assert "error" in result`
- P1.2 (向量搜索) 独立于其他项，可随时执行
- P1.3 (连接池) 在所有 Tool/Resource 改造后统一执行更安全

---

## 修改文件清单

| 优先级 | 文件 | 操作 | 预计行数变化 |
|--------|------|------|-------------|
| P0 | `src/oprocess/tools/schemas.py` | 新建 | +80 |
| P0 | `src/oprocess/tools/registry.py` | 修改 | ±40 |
| P0 | `src/oprocess/tools/helpers.py` | 修改 | ±10 |
| P0 | `src/oprocess/tools/resources.py` | 修改 | ±5 |
| P0 | `src/oprocess/db/queries.py` | 修改 | +15 |
| P0 | `README.md` | 重写 | +200 |
| P0 | `pyproject.toml` | 修改 | +1 (pydantic dep) |
| P0 | `tests/test_tools/test_server.py` | 修改 | ±15 |
| P0 | `tests/test_quality_gates.py` | 修改 | ±10 |
| P1 | `src/oprocess/server.py` | 修改 | +8 |
| P1 | `src/oprocess/db/connection.py` | 修改 | +20 |
| P1 | `src/oprocess/db/vector_search.py` | 修改或删除 | ±30 |
| P2 | `src/oprocess/gateway.py` | 修改 | +10 |
| P2 | `src/oprocess/governance/audit.py` | 修改 | +15 |
| P2 | `src/oprocess/auth.py` | 新建 | +30 |

---

## Acceptance Criteria (总)

- [ ] **P0 完成**: Pydantic schema + ToolError + lang 白名单 + README
- [ ] **P1 完成**: 多传输 + 向量搜索修复 + 连接池 + ping
- [ ] **P2 完成**: 日志 + 幂等性 + OAuth + sqlite-vec
- [ ] 全流程: `ruff check . && pytest && pytest --benchmark-only` 全通过
- [ ] 认证自查: 7+1 Tool 全部有完整 inputSchema，无 error dict
- [ ] 文档自查: README 包含 Quick Start + Tool 表 + Resource 表 + Claude Desktop 配置
