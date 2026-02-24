---
status: complete
priority: p2
issue_id: "006"
tags: [code-review, quality]
dependencies: []
---

# Regex \b word boundary issue with mixed Chinese-English text

## Problem Statement

`translate.py` uses `\b` word boundary markers in regex patterns for glossary translation. `\b` doesn't work correctly with mixed Chinese-English text because Chinese characters don't have word boundaries in regex.

## Findings

- **Source**: kieran-python-reviewer
- **File**: `scripts/translate.py`
- **Evidence**: `re.sub(rf'\b{re.escape(en)}\b', zh, text, flags=re.IGNORECASE)` — will fail to match English words adjacent to Chinese characters

## Proposed Solutions

### Option A: Use lookahead/lookbehind for non-CJK boundaries (Recommended)
- Replace `\b` with `(?<![a-zA-Z])` and `(?![a-zA-Z])` for English term matching
- Pre-sort glossary by length (longest first) to prevent partial matches
- **Effort**: Small
- **Risk**: Low

## Acceptance Criteria

- [ ] Glossary translation works correctly with mixed Chinese-English text
- [ ] Pipeline still passes

## Work Log

| Date | Action | Learnings |
|------|--------|-----------|
