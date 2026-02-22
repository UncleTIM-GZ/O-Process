---
status: pending
priority: p2
issue_id: "007"
tags: [code-review, quality]
dependencies: []
---

# Unused depth parameter in _translate_node

## Problem Statement

`_translate_node()` in translate.py accepts a `depth` parameter that is never used in the function body.

## Findings

- **Source**: kieran-python-reviewer
- **File**: `scripts/translate.py`

## Proposed Solutions

### Option A: Remove the parameter (Recommended)
- Remove `depth` from signature and all call sites
- **Effort**: Small
- **Risk**: None

## Acceptance Criteria

- [ ] `depth` parameter removed from `_translate_node` and callers
- [ ] Pipeline still passes

## Work Log

| Date | Action | Learnings |
|------|--------|-----------|
