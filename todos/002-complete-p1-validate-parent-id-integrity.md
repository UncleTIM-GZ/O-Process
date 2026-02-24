---
status: complete
priority: p1
issue_id: "002"
tags: [code-review, data-integrity]
dependencies: []
---

# validate.py missing parent_id referential integrity check

## Problem Statement

The validation script checks for unique IDs and schema conformance but does NOT verify that every node's `parent_id` references an existing node. Orphaned nodes could silently corrupt the tree.

## Findings

- **Source**: data-integrity-guardian
- **File**: `scripts/validate.py`
- **Evidence**: No function checks `parent_id` against known IDs

## Proposed Solutions

### Option A: Add parent_id check in _check_tree (Recommended)
- Collect all node IDs, then verify every `parent_id` (except L1 roots with `parent_id: null`) exists in the set
- **Pros**: Simple, fast, catches orphans
- **Effort**: Small
- **Risk**: None

## Acceptance Criteria

- [ ] `validate.py` checks parent_id referential integrity
- [ ] Pipeline still passes with 0 errors

## Work Log

| Date | Action | Learnings |
|------|--------|-----------|
