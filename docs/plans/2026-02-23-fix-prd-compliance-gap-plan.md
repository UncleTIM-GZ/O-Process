---
title: "fix: O'Process PRD v2.0 合规差距修复计划"
type: fix
status: active
date: 2026-02-23
origin: PRD v2.0 + Blueprint v1.0 差距分析
---

# O'Process PRD v2.0 合规差距修复计划

## 概述

基于对 PRD v2.0 和 Blueprint v1.0 的逐项审查，当前实现完成了骨架搭建（7 Tool 注册、Gateway 模式、SQLite 入库），但存在 **17 项实质性差距**。本计划按优先级分为 6 个阶段（Phase），每阶段可独立提交和测试。

## 差距严重度总览

| 级别 | 数量 | 说明 |
|------|------|------|
| P0 架构缺陷 | 2 | 搜索引擎未使用向量；ProvenanceChain 是空壳 |
| P1 功能缺失 | 3 | 5 个 Resource 未实现；审计 Schema 不符；Boundary 未接向量 |
| P2 字段/结构缺失 | 4 | 溯源附录、input_hash、追加触发器、role_mappings |
| P3 参数缺失 | 3 | search level 过滤、compare 数组、export 多流程 |
| P4 质量门禁 | 5 | 性能基准、搜索精度、覆盖率、mcp-inspector |

---

## Phase 1: 语义搜索引擎接入（P0）

**目标**：将死代码 `vector_search.py` 真正接入搜索链路，替代 SQL LIKE。

### 1.1 改造 search_processes — 向量搜索为主、LIKE 兜底

- [x] **修改 `db/queries.py:search_processes()`**
  - 优先调用 `vector_search()` 获取带评分的结果
  - 返回值增加 `score` 字段（余弦相似度 0.0~1.0）
  - 当 `process_embeddings` 表为空时，fallback 到 SQL LIKE
  - 新增 `level` 可选参数支持层级过滤（PRD 要求）

```python
# db/queries.py — 新签名
def search_processes(
    conn: sqlite3.Connection,
    query: str,
    lang: str = "zh",
    limit: int = 10,
    level: int | None = None,  # PRD 要求新增
) -> list[dict]:
```

### 1.2 改造 vector_search — 返回完整 process dict

- [x] **修改 `db/vector_search.py:vector_search()`**
  - 返回完整 process 字段（不只是 name/level/domain），复用 `_row_to_process()`
  - 加入 `level` 过滤参数

### 1.3 BoundaryResponse 接入真实向量距离

- [x] **修改 `tools/registry.py:search_process()`**
  - 从 vector_search 结果中取 `best_score`（第一条的 score）
  - 用真实余弦相似度调用 `check_boundary()`
  - 触发时返回 `nearest_valid_nodes`（Top-3 最近节点）

- [x] **修改 `governance/boundary.py:BoundaryResponse`**
  - 增加 `boundary_reason: str` 字段
  - 增加 `query_embedding_distance: float` 字段
  - 增加 `nearest_valid_nodes: list[dict]` 字段

```python
# governance/boundary.py — PRD 完整结构
@dataclass
class BoundaryResponse:
    is_boundary: bool
    boundary_reason: str
    query_embedding_distance: float
    nearest_valid_nodes: list[dict]
    suggestion: str
```

### 1.4 map_role_to_processes 也触发 Boundary

- [x] **修改 `tools/registry.py:map_role_to_processes()`**
  - 与 search_process 相同的 boundary 逻辑

### 1.5 测试

- [x] 新增 `tests/test_tools/test_vector_search.py` — 向量搜索单元测试
- [x] 新增 boundary 触发的集成测试（真实向量距离 < 阈值场景）
- [x] 验证 LIKE fallback 在无 embedding 时工作正常

**影响文件**: `db/queries.py`, `db/vector_search.py`, `tools/registry.py`, `governance/boundary.py`
**预计新增/修改**: ~120 行代码，~60 行测试

---

## Phase 2: ProvenanceChain 重构（P0）

**目标**：从空壳升级为 PRD 完整规格的溯源链。

### 2.1 重构 ProvenanceEntry → ProvenanceNode

- [x] **修改 `governance/provenance.py`**
  - 重命名 `ProvenanceEntry` → `ProvenanceNode`
  - 字段对齐 PRD：

```python
@dataclass
class ProvenanceNode:
    node_id: str                    # 流程节点 ID
    name: str                       # 节点名称（按 lang）
    confidence: float               # 0.0-1.0
    path: str                       # '4.0 > 4.1 > 4.1.2'
    derivation_rule: str            # 'semantic_match' / 'rule_based' / 'direct_lookup'
```

### 2.2 ProvenanceChain 序列化为 ToolResponse.provenance_chain

- [x] **修改 `gateway.py:ToolResponse`**
  - `provenance_chain` 类型从 `list[str]` → `list[dict]`（序列化后的 ProvenanceNode）

### 2.3 每个 Tool 填充真实溯源链

- [x] **`search_process`**: 每个匹配结果创建 ProvenanceNode（confidence=score, derivation_rule="semantic_match"）
- [x] **`get_process_tree`**: provenance_chain = []（PRD：结构性查询无推导）
- [x] **`get_kpi_suggestions`**: 命中节点本身（derivation_rule="direct_lookup"）
- [x] **`compare_processes`**: provenance_chain = []（PRD：结构性查询无推导）
- [x] **`get_responsibilities`**: 所有参与推导的流程节点（confidence=贡献权重）
- [x] **`map_role_to_processes`**: 搜索命中路径（confidence=向量相似度）
- [x] **`export_responsibility_doc`**: 完整溯源图

### 2.4 export_responsibility_doc 生成溯源附录

- [x] **修改 `tools/export.py:build_responsibility_doc()`**
  - 在 Markdown 文档末尾增加「溯源附录」章节
  - 列出所有 ProvenanceNode（ID、名称、置信度、推导规则）

```markdown
## 溯源附录

| 节点 ID | 名称 | 置信度 | 路径 | 推导规则 |
|---------|------|--------|------|---------|
| 4.4.3 | 管理运输与配送 | 0.92 | 4.0 > 4.4 > 4.4.3 | semantic_match |
```

### 2.5 辅助函数 — 构建 path 字符串

- [x] **新增 `db/queries.py:build_path_string()`**
  - 输入 process_id，返回 `'4.0 > 4.4 > 4.4.3'` 格式的路径字符串
  - 复用 `get_ancestor_chain()`

### 2.6 测试

- [x] 更新 `tests/test_governance/test_provenance.py` — 适配新 ProvenanceNode
- [x] 新增集成测试验证每个 Tool 的 provenance_chain 格式和非空率

**影响文件**: `governance/provenance.py`, `gateway.py`, `tools/registry.py`, `tools/export.py`, `db/queries.py`
**预计新增/修改**: ~150 行代码，~80 行测试

---

## Phase 3: SessionAuditLog Schema 对齐 PRD（P1）

**目标**：审计日志 Schema 完全对齐 PRD 第 5.3 节。

### 3.1 重建 audit_log 表

- [x] **修改 `db/connection.py:SCHEMA_SQL`**
  - 表名 `audit_log` → `session_audit_log`
  - `input_params` → `input_hash`（SHA256 前 16 位）
  - 新增 `output_node_ids TEXT`
  - 新增 `lang TEXT`
  - 新增 `governance_ext TEXT DEFAULT '{}'`
  - 删除 `error TEXT`（不在 PRD 中）
  - 新增追加写入触发器：

```sql
CREATE TRIGGER IF NOT EXISTS no_update_audit
BEFORE UPDATE ON session_audit_log
BEGIN SELECT RAISE(ABORT, 'audit log is append-only'); END;

CREATE TRIGGER IF NOT EXISTS no_delete_audit
BEFORE DELETE ON session_audit_log
BEGIN SELECT RAISE(ABORT, 'audit log is append-only'); END;
```

### 3.2 修改 audit.py — input_hash + 新字段

- [x] **修改 `governance/audit.py:log_invocation()`**
  - 输入参数 JSON 序列化后取 SHA256 前 16 位作为 `input_hash`
  - 新增 `output_node_ids` 参数（provenance chain 的 node_id 列表）
  - 新增 `lang` 参数
  - 新增 `governance_ext` 参数（默认 `{}`）
  - 删除 `error` 参数

```python
import hashlib

def _hash_input(params: dict) -> str:
    raw = json.dumps(params, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(raw.encode()).hexdigest()[:16]
```

### 3.3 修改 gateway.py — 传递新审计字段

- [x] **修改 `gateway.py:PassthroughGateway.execute()`**
  - 审计日志调用传入 output_node_ids（从 ToolResponse.provenance_chain 提取）
  - 注意：需要在 execute 返回前设置 provenance_chain，然后提取 node_ids

### 3.4 数据迁移脚本

- [x] ~~**新增 `scripts/migrate_audit.py`**~~ — 不需要（init_schema 幂等，旧表无实质数据）

### 3.5 测试

- [x] 更新 `tests/test_governance/test_audit.py` — 适配新 Schema
- [x] 新增追加写入触发器测试（UPDATE/DELETE 应抛异常）
- [x] 验证 input_hash 而非原始 input_params 被存储

**影响文件**: `db/connection.py`, `governance/audit.py`, `gateway.py`
**预计新增/修改**: ~80 行代码，~40 行测试

---

## Phase 4: MCP Resources 实现（P1）

**目标**：实现 PRD 第 4.2 节要求的 5 个 Resource。

### 4.1 实现 5 个 Resource

- [ ] **`oprocess://process/{id}`** — 单个流程节点完整信息
  - 调用 `get_process()` 返回 JSON

- [ ] **`oprocess://category/list`** — 全部顶层分类列表
  - 查询 `level=1` 的所有流程，返回 `[{id, name_zh, name_en, domain}]`

- [ ] **`oprocess://role/{role_name}`** — 角色对应流程映射缓存
  - 调用 `search_processes(role_name)` 返回映射结果
  - 后续可接入 `role_mappings` 表做缓存

- [ ] **`oprocess://audit/session/{session_id}`** — Session 审计日志摘要
  - 调用 `get_session_log()` 返回该 session 的全部记录

- [ ] **`oprocess://schema/sqlite`** — 当前数据库 Schema 定义
  - 返回 `SCHEMA_SQL` 常量内容

### 4.2 代码位置

- [ ] **新建 `tools/resources.py`** — 所有 Resource 注册函数
- [ ] **修改 `tools/registry.py`** — 调用 `register_resources(mcp)` 或在同文件注册

### 4.3 保留 oprocess://stats

- [ ] 当前已有的 `oprocess://stats` 保留（虽不在 PRD 中但有用）

### 4.4 role_mappings 表

- [ ] **修改 `db/connection.py`** — 新增 `role_mappings` 表：

```sql
CREATE TABLE IF NOT EXISTS role_mappings (
    role_name TEXT NOT NULL,
    process_id TEXT NOT NULL,
    confidence REAL,
    created_at TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (process_id) REFERENCES processes(id)
);
```

### 4.5 测试

- [ ] 新增 `tests/test_tools/test_resources.py` — 每个 Resource 的读取测试

**影响文件**: 新建 `tools/resources.py`, `db/connection.py`, `tools/registry.py`
**预计新增/修改**: ~120 行代码，~60 行测试

---

## Phase 5: Tool 签名对齐 PRD（P3）

**目标**：补齐 PRD 要求但当前缺失的参数。

### 5.1 search_process — level 过滤

- [ ] 已在 Phase 1 处理（新增 `level` 参数）

### 5.2 compare_processes — 支持 N 个流程

- [ ] **修改 `tools/registry.py:compare_processes()`**
  - 参数从 `process_id_a, process_id_b` → `process_ids: str`（逗号分隔 ID 列表）
  - 内部循环对比所有组合

```python
@mcp.tool()
def compare_processes(
    process_ids: str,  # 逗号分隔，如 "1.0,8.0,4.0"
) -> str:
    """Compare multiple process nodes."""
```

### 5.3 export_responsibility_doc — 多流程 + 角色名

- [ ] **修改 `tools/registry.py:export_responsibility_doc()`**
  - 新增 `role_name: str` 可选参数
  - `process_id` → `process_ids: str`（逗号分隔，支持多流程）
  - 生成包含多流程的综合岗位说明书

### 5.4 get_responsibilities — format 参数

- [ ] **修改 `tools/registry.py:get_responsibilities()`**
  - 新增 `format: str = "json"` 参数（"json" / "markdown"）

### 5.5 map_role_to_processes — industry 过滤

- [ ] **修改 `tools/registry.py:map_role_to_processes()`**
  - 新增 `industry: str | None` 可选参数
  - 通过 tags 字段做行业过滤

### 5.6 测试

- [ ] 更新现有测试适配新签名
- [ ] 新增多流程对比测试
- [ ] 新增多流程导出测试

**影响文件**: `tools/registry.py`, `tools/export.py`
**预计新增/修改**: ~100 行代码，~50 行测试

---

## Phase 6: 质量门禁与性能基准（P4）

**目标**：建立 PRD 第 10 节要求的完整质量验证体系。

### 6.1 pytest-benchmark 性能基准

- [ ] **新增 `tests/test_performance.py`**
  - search_process P50 < 100ms / P95 < 300ms
  - ProvenanceChain 组装 < 20ms
  - Audit 写入 < 5ms
  - 使用 `@pytest.mark.benchmark` 装饰器

### 6.2 搜索精度评估

- [ ] **新增 `tests/fixtures/annotated_queries.json`** — 50 个标注查询集
  - 格式：`{query, expected_top3_ids, lang}`
  - 覆盖中英文、跨分类、边界场景

- [ ] **新增 `tests/test_search_accuracy.py`**
  - Top-3 召回准确率 ≥ 85% 断言

### 6.3 BoundaryResponse 标注测试集

- [ ] **新增 `tests/fixtures/boundary_queries.json`** — 10 个越界查询
  - 确保触发 BoundaryResponse 的查询集

### 6.4 ProvenanceChain 非空率验证

- [ ] **新增测试** — 遍历所有实质内容 Tool，验证 provenance_chain 非空

### 6.5 测试覆盖率

- [ ] **修改 `pyproject.toml`** — 添加 pytest-cov 配置
  - 目标覆盖率 ≥ 80%

```toml
[tool.pytest.ini_options]
addopts = "--cov=oprocess --cov-report=term-missing --cov-fail-under=80"
```

### 6.6 mcp-inspector 检查

- [ ] 使用 `mcp-inspector` 或 `fastmcp` 内置校验检查 Tool schema 合规性
- [ ] 如有不合规项，修复并记录

**影响文件**: 新建 `tests/test_performance.py`, `tests/test_search_accuracy.py`, `tests/fixtures/`
**预计新增**: ~200 行测试 + 60 条标注数据

---

## DB Schema 变更汇总（跨 Phase）

```sql
-- Phase 3: 审计日志重建
DROP TABLE IF EXISTS audit_log;
CREATE TABLE session_audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    tool_name TEXT NOT NULL,
    input_hash TEXT NOT NULL,
    output_node_ids TEXT,
    lang TEXT,
    response_ms INTEGER,
    timestamp TEXT NOT NULL,
    governance_ext TEXT DEFAULT '{}'
);
CREATE TRIGGER no_update_audit BEFORE UPDATE ON session_audit_log
BEGIN SELECT RAISE(ABORT, 'audit log is append-only'); END;
CREATE TRIGGER no_delete_audit BEFORE DELETE ON session_audit_log
BEGIN SELECT RAISE(ABORT, 'audit log is append-only'); END;

-- Phase 4: 角色映射缓存
CREATE TABLE role_mappings (
    role_name TEXT NOT NULL,
    process_id TEXT NOT NULL,
    confidence REAL,
    created_at TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (process_id) REFERENCES processes(id)
);

-- Phase 5（可选）: processes 表扩展列
-- name_ext TEXT DEFAULT '{}',  -- JSON: {"ja": ..., "ko": ...}
-- category TEXT,
-- author_note TEXT
```

---

## 执行顺序与依赖关系

```
Phase 1 (语义搜索) ──┐
                      ├──> Phase 2 (Provenance) ──> Phase 3 (Audit)
Phase 4 (Resources) ──┘                                   │
                                                           v
                                     Phase 5 (Tool 签名) ──> Phase 6 (质量门禁)
```

- Phase 1 和 Phase 4 可并行
- Phase 2 依赖 Phase 1（需要 score 字段做 confidence）
- Phase 3 依赖 Phase 2（需要 provenance node_ids 写入审计）
- Phase 5 可在 Phase 1-3 之后独立进行
- Phase 6 在所有功能完成后执行

---

## 验收标准

| 维度 | Phase 1-5 完成后 | Phase 6 完成后 |
|------|------------------|---------------|
| MCP Tools | 7 个全量实现，签名对齐 PRD | + 性能基准通过 |
| MCP Resources | 5 + 1 个全部在线 | - |
| 语义搜索 | 向量余弦相似度为主 | Top-3 ≥ 85% |
| ProvenanceChain | 所有实质 Tool 返回完整 Node | 非空率 100% |
| SessionAuditLog | SHA256 hash、追加触发器、governance_ext | 写入 < 5ms |
| BoundaryResponse | 真实向量距离触发、含 nearest_nodes | 10 个越界查询通过 |
| 测试 | 全部通过 | 覆盖率 ≥ 80% |
| Ruff | 零 error | - |

---

## 工作量估算

| Phase | 代码变更(行) | 测试变更(行) | 复杂度 |
|-------|-------------|-------------|--------|
| 1. 语义搜索 | ~120 | ~60 | 中 |
| 2. Provenance | ~150 | ~80 | 高 |
| 3. Audit Schema | ~80 | ~40 | 中 |
| 4. Resources | ~120 | ~60 | 低 |
| 5. Tool 签名 | ~100 | ~50 | 低 |
| 6. 质量门禁 | ~30 | ~200 | 中 |
| **总计** | **~600** | **~490** | - |
