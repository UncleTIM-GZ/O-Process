---
title: "fix: 语义搜索引擎接入（Phase 1）"
type: fix
status: completed
date: 2026-02-23
origin: docs/plans/2026-02-23-fix-prd-compliance-gap-plan.md Phase 1
---

# 语义搜索引擎接入 — Phase 1 实施计划

## Overview

将死代码 `vector_search.py` 接入搜索链路，替代 SQL LIKE 作为主搜索引擎。向量搜索为主、LIKE 为兜底；BoundaryResponse 使用真实余弦相似度而非硬编码值。

## Problem Statement

1. `vector_search()` 存在于代码中但从未被调用 — 所有搜索走 SQL LIKE
2. `search_process` 工具用 `1.0 if results else 0.0` 硬编码 boundary score
3. `vector_search()` 返回 6 个字段 vs `_row_to_process()` 返回 12+ 个字段 — 字段不一致
4. `vector_search()` 用 `process_id` key vs 其余代码用 `id` key — 命名不一致
5. `map_role_to_processes` 没有 boundary 检查
6. 搜索不支持 `level` 参数过滤（PRD 要求）

## 设计决策

| 决策 | 选择 | 原因 |
|------|------|------|
| 嵌入模式 | 仅 TF-IDF (384d) | 现有 DB 中嵌入为 384d，OpenAI 为未来工作 |
| Fallback 触发 | 检查 `process_embeddings` 行数 | 避免空结果和维度不匹配的歧义 |
| `nearest_valid_nodes` 格式 | `{id, name_zh, name_en, score}` Top-3 | 简洁且信息足够 |
| `lang` 在向量模式 | 不影响搜索，仅影响排序展示 | TF-IDF 对 lang 不敏感 |
| Fallback 模式 boundary | 跳过（无 score 可用） | LIKE 不产生相似度分数 |

## Implementation Phases

### Step 1: 修改 `vector_search()` — 返回完整 process dict + level 过滤

**文件**: `src/oprocess/db/vector_search.py`

- [x] 改造 `vector_search()` 签名增加 `level: int | None = None`
- [x] JOIN 查询改为 `SELECT p.*, pe.embedding`，获取全部 process 字段
- [x] 用 `_row_to_process()` 构建完整 dict，再追加 `score` 字段
- [x] 返回 key 统一为 `id`（不再用 `process_id`）
- [x] level 过滤加入 SQL WHERE 条件
- [x] 导入 `_row_to_process` from `queries.py`

```python
def vector_search(
    conn: sqlite3.Connection,
    query: str,
    limit: int = 10,
    threshold: float = 0.0,
    level: int | None = None,
) -> list[dict]:
```

### Step 2: 修改 `search_processes()` — 向量优先、LIKE 兜底

**文件**: `src/oprocess/db/queries.py`

- [x] 增加 `level: int | None = None` 参数
- [x] 检查 `process_embeddings` 是否有数据（`SELECT COUNT(*) FROM process_embeddings`）
- [x] 有数据 → 调用 `vector_search()`，结果带 `score` 字段
- [x] 无数据 → 走 SQL LIKE fallback，结果 `score = None`
- [x] LIKE 模式增加 level 过滤
- [x] 返回标记 `_search_mode: "vector" | "fallback"` 供上层判断

```python
def search_processes(
    conn: sqlite3.Connection,
    query: str,
    lang: str = "zh",
    limit: int = 10,
    level: int | None = None,
) -> list[dict]:
```

### Step 3: 增强 `BoundaryResponse` — PRD 完整字段

**文件**: `src/oprocess/governance/boundary.py`

- [x] `BoundaryResponse` 增加字段：
  - `boundary_reason: str`
  - `query_embedding_distance: float`
  - `nearest_valid_nodes: list[dict]`
- [x] `check_boundary()` 增加 `nearest_valid_nodes` 参数
- [x] `to_dict()` 序列化新字段
- [x] 更新 `is_within_boundary` → `is_boundary`（取反语义，PRD 用 `is_boundary`）

### Step 4: 修改 `search_process` 工具 — 真实 score + boundary

**文件**: `src/oprocess/tools/registry.py`

- [x] 传递 `level` 参数给 `search_processes()`
- [x] 从结果中取真实 `best_score`（第一条的 `score`，若有）
- [x] 若 `_search_mode == "fallback"`，跳过 boundary 检查
- [x] Boundary 触发时，`nearest_valid_nodes` 从 vector_search(threshold=0.0) Top-3 获取
- [x] `search_process` 工具签名增加 `level: int | None = None`

### Step 5: 修改 `map_role_to_processes` 工具 — 添加 boundary

**文件**: `src/oprocess/tools/registry.py`

- [x] 复用与 `search_process` 相同的 boundary 逻辑
- [x] 提取公共 boundary 逻辑为 `_apply_boundary()` helper

### Step 6: 测试

**文件**: `tests/conftest.py`, `tests/test_vector_search.py`, `tests/test_queries.py`

- [x] `conftest.py`: `populated_db` fixture 增加 `process_embeddings` 数据（4 条 384d 向量）
- [x] 新增 `tests/test_vector_search.py`:
  - 向量搜索返回完整 process dict + score
  - level 过滤
  - threshold 过滤
  - 维度不匹配 → 跳过（不崩溃）
- [x] 更新 `tests/test_queries.py`:
  - `search_processes` 有 embedding 时走向量
  - `search_processes` 无 embedding 时走 LIKE
  - level 过滤
- [x] 更新 boundary 测试:
  - 真实向量 score 传入 `check_boundary()`
  - `nearest_valid_nodes` 非空验证

## 影响文件

| 文件 | 操作 |
|------|------|
| `src/oprocess/db/vector_search.py` | 修改 — 完整 dict 返回 + level |
| `src/oprocess/db/queries.py` | 修改 — 向量优先 + level + fallback |
| `src/oprocess/governance/boundary.py` | 修改 — PRD 完整字段 |
| `src/oprocess/tools/registry.py` | 修改 — 真实 score + boundary + level |
| `tests/conftest.py` | 修改 — embedding fixture |
| `tests/test_vector_search.py` | 新增 |
| `tests/test_queries.py` | 修改 |

## Acceptance Criteria

- [x] `search_process` 工具在有 embeddings 时使用向量搜索
- [x] `search_process` 工具在无 embeddings 时 fallback 到 SQL LIKE
- [x] `BoundaryResponse` 使用真实余弦相似度分数
- [x] `BoundaryResponse` 包含 `nearest_valid_nodes` (Top-3)
- [x] `map_role_to_processes` 有 boundary 检查
- [x] 所有搜索结果包含完整 process dict（不只是 6 个字段）
- [x] `level` 参数过滤正常工作
- [x] 所有现有测试通过
- [x] 新增测试全部通过
- [x] ruff lint 通过

## Sources

- **Origin plan:** [docs/plans/2026-02-23-fix-prd-compliance-gap-plan.md](../plans/2026-02-23-fix-prd-compliance-gap-plan.md) Phase 1
- PRD v2.0 Section 4.1 (search_process), Section 5.2 (BoundaryResponse)
