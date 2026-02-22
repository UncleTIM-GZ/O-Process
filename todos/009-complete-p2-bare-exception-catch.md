---
status: pending
priority: p2
issue_id: "009"
tags: [code-review, quality]
dependencies: []
---

# Bare Exception catch in validate.py schema validation

## Problem Statement

`validate.py` catches bare `Exception` in the schema validation section, which could mask unexpected errors.

## Findings

- **Source**: kieran-python-reviewer
- **File**: `scripts/validate.py`

## Proposed Solutions

### Option A: Catch specific exceptions (Recommended)
- Use `jsonschema.ValidationError` and `jsonschema.SchemaError`
- **Effort**: Small
- **Risk**: None

## Acceptance Criteria

- [ ] Specific exceptions caught instead of bare `Exception`
- [ ] Pipeline still passes

## Work Log

| Date | Action | Learnings |
|------|--------|-----------|
