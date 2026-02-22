---
status: pending
priority: p2
issue_id: "008"
tags: [code-review, quality]
dependencies: []
---

# Missing type annotations and Optional[str] inconsistency

## Problem Statement

1. `types.py` uses `Optional[str]` in some places but `str | None` in `io.py` — inconsistent style
2. Large constants (ITIL_PRACTICES, SCOR_PROCESSES, AI_PROCESS_GROUPS, AI_SCATTERED) lack type annotations
3. `load_framework()` returns bare `dict` instead of typed return

## Findings

- **Source**: kieran-python-reviewer, architecture-strategist
- **Files**: `scripts/shared/types.py`, `scripts/shared/io.py`, `scripts/merge_itil.py`, `scripts/merge_scor.py`, `scripts/add_ai_processes.py`

## Proposed Solutions

### Option A: Normalize to str | None, add type hints (Recommended)
- Use `str | None` consistently (modern Python 3.10+ style)
- Add type annotations to large constants
- **Effort**: Small
- **Risk**: None

## Acceptance Criteria

- [ ] Consistent `str | None` style across all files
- [ ] Major constants have type annotations
- [ ] Pipeline still passes

## Work Log

| Date | Action | Learnings |
|------|--------|-----------|
