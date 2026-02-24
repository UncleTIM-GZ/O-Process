---
title: "fix: P5 Commit 3 — todo cleanup + plan files"
type: fix
status: completed
date: 2026-02-24
---

# fix: P5 Commit 3 — Todo 清理 + 计划文件归档

P5-1~P5-7 全部完成后的最终收尾提交。

## 修复清单

### 1. Todo 011: translate.py 正则预编译 — 已实现

- **状态**: 早已修复（translate.py:84-93 已有 `_NOUN_PATTERNS` 和 `_VERB_PATTERNS`）
- **操作**: 标记 todo 为 complete，重命名文件

### 2. Todo 010: sources_mapping.json 身份映射 — 有意为之

- **状态**: parse_pcf.py:139-141 注释已说明 `# (identity for Phase 1)`
- **操作**: 标记 todo 为 wont_fix（有意设计，非 YAGNI 违规），重命名文件

### 3. Todos 001-009: YAML 状态更新

- **状态**: 之前已更新 YAML `status: pending` → `status: complete`，但未提交
- **操作**: 一起提交

### 4. 计划文件归档

- **操作**: 提交 P5 相关计划文件到版本控制

## Acceptance Criteria

- [x] Todo 011 标记为 complete
- [x] Todo 010 标记为 wont_fix
- [x] Todos 001-009 YAML 状态为 complete
- [x] 所有计划文件已提交
- [x] ruff check 零 error
- [x] pytest 全部通过
