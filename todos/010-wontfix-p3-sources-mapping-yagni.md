---
status: wont_fix
priority: p3
issue_id: "010"
tags: [code-review, yagni]
dependencies: []
---

# sources_mapping.json is identity mapping (YAGNI)

## Problem Statement

`sources_mapping.json` maps PCF IDs to O'Process IDs but they are identical (identity mapping). The file adds no value and the generation code is dead weight.

## Findings

- **Source**: code-simplicity-reviewer
- **File**: `scripts/parse_pcf.py`, `docs/oprocess-framework/sources_mapping.json`

## Proposed Solutions

### Option A: Keep but document as intentional (Recommended for v1)
- The plan explicitly requires this file for PCF traceability
- Add a comment in parse_pcf.py explaining the mapping is currently identity but will diverge in v2
- **Effort**: Minimal
- **Risk**: None

### Option B: Remove entirely
- Delete sources_mapping.json and generation code
- **Risk**: Violates plan quality gate requirement

## Acceptance Criteria

- [ ] Decision documented (keep or remove)

## Work Log

| Date | Action | Learnings |
|------|--------|-----------|
| 2026-02-24 | wont_fix: identity mapping is intentional (Phase 1) | parse_pcf.py:139 documents this as `# (identity for Phase 1)` |
