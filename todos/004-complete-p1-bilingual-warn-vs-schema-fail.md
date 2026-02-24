---
status: complete
priority: p1
issue_id: "004"
tags: [code-review, data-integrity]
dependencies: []
---

# Schema minLength:1 vs validate.py WARN inconsistency

## Problem Statement

The JSON Schema requires `minLength: 1` for `name.zh`, `name.en`, `description.zh`, `description.en`, which means empty strings FAIL schema validation. But `_check_bilingual` in validate.py only emits WARN for missing/empty descriptions. This inconsistency could mask real data quality issues.

## Findings

- **Source**: data-integrity-guardian, kieran-python-reviewer
- **File**: `scripts/validate.py`
- **Evidence**: `_check_bilingual` uses `warnings += 1` but schema validation would FAIL for the same condition

## Proposed Solutions

### Option A: Align validate.py with schema (Recommended)
- Change bilingual check from WARN to FAIL for empty strings that violate schema
- Keep WARN only for quality issues (e.g., description same as name)
- **Effort**: Small
- **Risk**: Low — may surface existing data issues that need fixing

## Acceptance Criteria

- [ ] Bilingual check severity aligns with schema constraints
- [ ] Pipeline still passes with 0 errors (fix any data issues exposed)

## Work Log

| Date | Action | Learnings |
|------|--------|-----------|
