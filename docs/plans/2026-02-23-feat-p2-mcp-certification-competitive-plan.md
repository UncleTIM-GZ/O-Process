---
title: "feat: P2 MCP Certification — Competitive Enhancements"
type: feat
status: active
date: 2026-02-23
origin: docs/plans/2026-02-23-feat-mcp-certification-upgrade-plan.md
---

# P2 MCP Certification — Competitive Enhancements

## Overview

Implement P2 items from the MCP certification upgrade plan to enhance competitiveness:
- P2.1: Structured logging (JSON format, env-configurable)
- P2.2: Audit log idempotency (request_id dedup)
- P2.3: Bearer token auth for HTTP transport
- P2.4: sqlite-vec native vector index (deferred — requires native extension)

## Implementation Order

P2.1 (logging) → P2.2 (idempotency) → P2.3 (auth) → P2.4 (deferred)

## Phase 1: P2.1 Structured Logging

**Files**: `src/oprocess/gateway.py`, `src/oprocess/server.py`

- [x] Add `logging.getLogger("oprocess")` with JSON-structured output
- [x] Log tool_name, session_id, response_ms on every gateway execute
- [x] LOG_LEVEL env var control via `logging.basicConfig`
- [x] Tests for log output

## Phase 2: P2.2 Audit Log Idempotency

**Files**: `src/oprocess/db/connection.py` (schema), `src/oprocess/governance/audit.py`

- [x] Add `request_id TEXT` column to session_audit_log
- [x] Add UNIQUE index on request_id (WHERE request_id IS NOT NULL)
- [x] Change INSERT to `INSERT OR IGNORE` when request_id provided
- [x] Backward compatible: no request_id = existing behavior
- [x] Tests for dedup + backward compat

## Phase 3: P2.3 Bearer Token Auth

**Files**: `src/oprocess/auth.py` (new), `src/oprocess/server.py`

- [x] `verify_token()` checks OPROCESS_API_KEY env var
- [x] No key configured → skip auth (stdio safe)
- [x] HTTP transport: inject auth middleware
- [x] Tests for auth logic
- [x] README updated

## Phase 4: P2.4 sqlite-vec (Deferred)

Not implemented in this PR — requires native C extension installation.
Reserved for future dedicated sprint.

## Acceptance Criteria

- [x] P2.1: JSON structured logging with LOG_LEVEL control
- [x] P2.2: Duplicate request_id writes only once
- [x] P2.3: Bearer token auth for HTTP, stdio unaffected
- [ ] P2.4: Deferred
- [x] All tests pass, coverage >= 80%, ruff clean
