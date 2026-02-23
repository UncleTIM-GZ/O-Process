---
title: "fix: SessionAuditLog Schema 对齐 PRD（Phase 3）"
type: fix
status: completed
date: 2026-02-23
origin: docs/plans/2026-02-23-fix-prd-compliance-gap-plan.md Phase 3
---

# SessionAuditLog Schema 对齐 PRD — Phase 3 实施计划

## Overview

将 `audit_log` 表升级为 PRD v2.0 第 5.3 节要求的 `session_audit_log`，包括 input_hash、output_node_ids、追加写入触发器等。

## Steps

### Step 1: 重建 DB Schema — audit_log → session_audit_log

- [x] 修改 `db/connection.py:SCHEMA_SQL`
  - 表名 `audit_log` → `session_audit_log`
  - `input_params TEXT` → `input_hash TEXT NOT NULL`（SHA256 前 16 位）
  - 新增 `output_node_ids TEXT`（JSON 数组）
  - 新增 `lang TEXT`
  - 删除 `error TEXT`（不在 PRD 中）
  - 删除 `output_summary TEXT`（被 output_node_ids 替代）
  - 新增 `governance_ext TEXT DEFAULT '{}'`
  - 新增 append-only 触发器（no_update_audit, no_delete_audit）
  - 更新索引名称

### Step 2: 重写 audit.py — input_hash + 新字段

- [x] `log_invocation()` 签名变更：
  - 删除 `input_params` → 新增 `input_hash` 参数
  - 删除 `output_summary` → 新增 `output_node_ids` 参数
  - 删除 `error` 参数
  - 新增 `lang` 参数
  - 新增 `governance_ext` 参数（默认 `'{}'`）
- [x] 新增 `_hash_input(params: dict) -> str` 辅助函数
- [x] `get_session_log()` / `get_recent_logs()` 更新表名
- [x] INSERT 语句更新为新列名

### Step 3: 修改 gateway.py — 传递新审计字段

- [x] `PassthroughGateway.execute()` 中审计调用传入：
  - `input_hash`：调用 `_hash_input()` 对 kwargs 哈希
  - `lang`：从 kwargs 中提取（若存在）
  - `output_node_ids` 设为 None（gateway 层无法获取，PRD 可选字段）
  - 删除 `error` 和 `output_summary` 参数
- [x] 清理死代码 `error_msg` 变量

### Step 4: 更新集成测试中的审计调用

- [x] `test_integration.py` 中 `log_invocation()` 调用适配新签名
- [x] `real_conn` fixture 加入 `init_schema()` 确保新表存在
- [x] 更新 `test_audit.py` — 适配新 Schema
  - 更新所有 `log_invocation()` 调用签名
  - 新增 `TestHashInput` 测试类（4 个测试）
  - 新增 `TestAppendOnlyTriggers` 测试类（2 个测试）
  - 新增 `governance_ext` 默认值测试
  - 删除旧 error 相关测试

### Step 5: 验证

- [x] 85 测试全量通过
- [x] Ruff lint 清洁
