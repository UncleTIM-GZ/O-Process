---
status: complete
priority: p1
issue_id: "003"
tags: [code-review, data-integrity]
dependencies: []
---

# validate.py missing KPI process_id referential integrity check

## Problem Statement

KPI entries reference `process_id` but the validator does not verify these IDs exist in the framework tree. Orphan KPIs could silently exist.

## Findings

- **Source**: data-integrity-guardian
- **File**: `scripts/validate.py`
- **Evidence**: `_check_kpis` only counts entries and checks structure, not process_id validity

## Proposed Solutions

### Option A: Add process_id cross-reference check (Recommended)
- Build set of all framework node IDs, verify each KPI's `process_id` is in the set
- **Pros**: Catches orphan KPIs, simple implementation
- **Effort**: Small
- **Risk**: None

## Acceptance Criteria

- [ ] `validate.py` checks KPI process_id referential integrity
- [ ] Pipeline still passes with 0 errors

## Work Log

| Date | Action | Learnings |
|------|--------|-----------|
