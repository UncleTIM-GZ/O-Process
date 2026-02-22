---
status: pending
priority: p2
issue_id: "005"
tags: [code-review, quality, yagni]
dependencies: []
---

# Remove dead code: _translate_with_api, from_dict methods

## Problem Statement

Several functions are never called in the pipeline and add unnecessary complexity:
- `_translate_with_api()` in translate.py (prints "not implemented")
- `ProcessNode.from_dict()` and `LocalizedText.from_dict()` in types.py (never called)
- `_check_evolution_log()` in validate.py (redundant with schema validation)

## Findings

- **Source**: code-simplicity-reviewer, kieran-python-reviewer
- **Files**: `scripts/translate.py`, `scripts/shared/types.py`, `scripts/validate.py`
- **Estimated reduction**: ~60 LOC

## Proposed Solutions

### Option A: Remove all dead code (Recommended)
- Delete `_translate_with_api()`, `from_dict()` methods, `_check_evolution_log()`
- **Effort**: Small
- **Risk**: None — code is never called

## Acceptance Criteria

- [ ] Dead code removed
- [ ] Pipeline still passes

## Work Log

| Date | Action | Learnings |
|------|--------|-----------|
