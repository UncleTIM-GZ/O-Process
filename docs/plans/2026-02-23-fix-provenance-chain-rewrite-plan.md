---
title: "fix: ProvenanceChain 重构（Phase 2）"
type: fix
status: completed
date: 2026-02-23
origin: docs/plans/2026-02-23-fix-prd-compliance-gap-plan.md Phase 2
---

# ProvenanceChain 重构 — Phase 2 实施计划

## Overview

将 ProvenanceEntry（空壳）升级为 PRD 完整规格的 ProvenanceNode，每个 Tool 填充真实溯源链，export 生成溯源附录。

## Steps

### Step 1: 重构 provenance.py — ProvenanceEntry → ProvenanceNode
- [x] ProvenanceNode: node_id, name, confidence, path, derivation_rule
- [x] ProvenanceChain.add() 适配新参数
- [x] ProvenanceChain.to_list() 返回新格式

### Step 2: ToolResponse.provenance_chain 类型 → list[dict]
- [x] gateway.py: provenance_chain 默认 list (已是)，但语义从 list[str] → list[dict]

### Step 3: queries.py 新增 build_path_string()
- [x] 复用 get_ancestor_chain()，返回 '1.0 > 1.1 > 1.1.2' 格式

### Step 4: 每个 Tool 填充真实 provenance_chain
- [x] search_process: 每个结果 → ProvenanceNode(semantic_match)
- [x] get_process_tree: [] (结构性查询)
- [x] get_kpi_suggestions: 命中节点(direct_lookup)
- [x] compare_processes: [] (结构性查询)
- [x] get_responsibilities: 所有参与节点(rule_based)
- [x] map_role_to_processes: 搜索命中(semantic_match)
- [x] export_responsibility_doc: 完整溯源图(rule_based)

### Step 5: export.py 生成溯源附录
- [x] build_responsibility_doc() 末尾增加溯源附录表格

### Step 6: 测试
- [x] 重写 test_provenance.py 适配 ProvenanceNode
- [x] 验证每个 Tool 的 provenance_chain 格式
