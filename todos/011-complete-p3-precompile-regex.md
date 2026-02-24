---
status: complete
priority: p3
issue_id: "011"
tags: [code-review, performance]
dependencies: []
---

# Pre-compile regex patterns in translate.py

## Problem Statement

`_glossary_translate()` compiles regex patterns on every call. Pre-compiling could save 50-100ms across the pipeline.

## Findings

- **Source**: performance-oracle
- **File**: `scripts/translate.py`

## Proposed Solutions

### Option A: Pre-compile at module level (Recommended)
- Build compiled regex dict once at module load
- Sort by length (longest first) once
- **Effort**: Small
- **Risk**: None

## Acceptance Criteria

- [ ] Regex patterns pre-compiled
- [ ] Pipeline still passes

## Work Log

| Date | Action | Learnings |
|------|--------|-----------|
| 2026-02-24 | complete: already implemented at translate.py:84-93 | _NOUN_PATTERNS and _VERB_PATTERNS pre-compiled at module level |
